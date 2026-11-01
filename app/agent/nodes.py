import asyncio
import json

from app.agent.state import AgentState
from app.core.logger import get_logger
from app.models.classify import classify_query


async def classify(state: AgentState) -> AgentState:
    import asyncio

    from app.agent.tools import get_farm_data
    from app.models.classify import _fast_classify
    from app.services.rag import aquery_schemes

    query = state["query"]
    callback = state.get("stream_callback")

    if callback:
        await callback("_ack_")

    fast_result = _fast_classify(query)

    if fast_result is not None:
        predicted_type, _ = fast_result

        if predicted_type == "tool":
            llm_task = asyncio.create_task(classify_query(query))
            data_task = asyncio.create_task(
                get_farm_data(farm_id=state.get("farm_id", "default"))
            )

            query_type, filters = await llm_task
            state["query_type"] = query_type
            state["filters"] = filters

            if query_type == "tool":
                state["tool_data"] = json.loads(await data_task)
            else:
                data_task.cancel()
                state["tool_data"] = {}

        elif predicted_type == "scheme":
            # The metadata filter is only known once classification finishes, so
            # RAG runs afterwards. Keyword-matched scheme queries return from
            # _fast_classify instantly, so this adds no latency in practice.
            query_type, filters = await classify_query(query)
            state["query_type"] = query_type
            state["filters"] = filters

            if query_type == "scheme":
                state["scheme_data"] = await aquery_schemes(
                    query=query, scheme_type=(filters or {}).get("type")
                )
            else:
                state["scheme_data"] = {}
        else:
            query_type, filters = await classify_query(query)
            state["query_type"] = query_type
            state["filters"] = filters
    else:
        query_type, filters = await classify_query(query)
        state["query_type"] = query_type
        state["filters"] = filters

    return state


async def rag_node(state: AgentState) -> AgentState:
    import hashlib
    import json

    from app.core.config import get_settings
    from app.services.rag import aquery_schemes
    from app.services.redis_cache import redis_cache

    if state.get("scheme_data"):
        return state

    settings = get_settings()
    farm_id = state.get("farm_id", "default")
    query = state["query"]
    scheme_type = state.get("filters", {}).get("type")

    if settings.llm_cache_enabled:
        cache_key = (
            f"node_rag:{farm_id}:{hashlib.sha256(query.encode()).hexdigest()[:16]}"
        )
        cached = await redis_cache.get(cache_key)
        if cached:
            state["scheme_data"] = json.loads(cached)
            return state

    result = await aquery_schemes(query=query, scheme_type=scheme_type)
    state["scheme_data"] = result

    if settings.llm_cache_enabled:
        await redis_cache.set(cache_key, json.dumps(result), ttl=3600)

    return state


async def tool_node(state: AgentState) -> AgentState:
    from app.agent.tools import get_farm_data

    if state["query_type"] == "tool":
        if not state.get("tool_data"):
            farm_id = state.get("farm_id", "default")
            result = await get_farm_data(farm_id=farm_id)
            try:
                state["tool_data"] = json.loads(result)
            except json.JSONDecodeError as e:
                logger = get_logger(__name__)
                logger.warning(f"Failed to parse tool_data JSON: {e}")
                state["tool_data"] = {}
    else:
        state["tool_data"] = {}
    return state


def _format_scheme_context(scheme_data: dict) -> str:
    schemes = scheme_data.get("schemes") or []
    if not schemes:
        return ""

    blocks = []
    for index, scheme in enumerate(schemes, start=1):
        content = str(scheme.get("content", "")).strip()
        if not content:
            continue
        scheme_type = scheme.get("type")
        header = f"[{index}] {scheme_type}" if scheme_type else f"[{index}]"
        blocks.append(f"{header}\n{content}")

    if not blocks:
        return ""

    return "\n\nScheme Information:\n" + "\n\n".join(blocks)


def _build_system_prompt(has_scheme_data: bool) -> str:
    rules = [
        "You are a helpful AI assistant for a farmer helpline.",
        "Answer using only the farm data and scheme information provided in the "
        "prompt.",
        "Be concise: replies are read aloud over voice.",
        "Never invent scheme eligibility rules, benefit amounts, deadlines, or "
        "documents.",
    ]
    if has_scheme_data:
        rules.append(
            "For scheme questions, ground every claim in the Scheme Information and "
            "name the scheme you are describing."
        )
        rules.append(
            "If the Scheme Information does not answer the question, say you do not "
            "have that detail and suggest contacting the local agriculture extension "
            "office. Do not guess."
        )
    else:
        rules.append(
            "If no scheme information is provided for a scheme question, say you do "
            "not have that detail and suggest contacting the local agriculture "
            "extension office."
        )
    return " ".join(rules)


async def direct_node(state: AgentState) -> AgentState:
    from app.models.reasoning import get_reasoning_llm

    query = state["query"]
    tool_data = state.get("tool_data", {})
    scheme_data = state.get("scheme_data", {})
    context = state.get("context", [])
    qtype = state.get("query_type", "direct")

    logger = get_logger(__name__)
    logger.info(
        "direct_node: query_type=%s, has_context=%s, streaming=%s",
        qtype,
        len(context) > 0,
        state.get("stream_callback") is not None,
    )

    tool_info = ""
    if tool_data:
        tool_info = f"\n\nFarm Data:\n{json.dumps(tool_data, indent=2)}"

    scheme_info = _format_scheme_context(scheme_data)

    context_str = ""
    if context:
        context_str = f"\n\nConversation History:\n{json.dumps(context, indent=2)}"

    full_prompt = f"User Query: {query}{tool_info}{scheme_info}{context_str}"
    system_msg = _build_system_prompt(has_scheme_data=bool(scheme_info))

    llm = get_reasoning_llm()
    full_response = ""
    callback = state.get("stream_callback")

    if callback:
        async for token in llm.astream(full_prompt, system=system_msg):
            full_response += token
            await callback(token)
    else:
        loop = asyncio.get_running_loop()
        full_response = await loop.run_in_executor(
            None, llm.generate, full_prompt, system_msg
        )

    state["response"] = full_response

    context.append({"role": "user", "content": query})
    context.append({"role": "assistant", "content": full_response})
    state["context"] = context[-10:]

    return state


def handoff_node(state: AgentState) -> AgentState:
    state["response"] = "I'll connect you with a human agent. Please hold."
    return state
