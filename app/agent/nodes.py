import asyncio
import json
import re

from app.agent.state import AgentState
from app.core.logger import get_logger
from app.models.classify import classify_query

_PRONOUN_TRIGGERS = (
    "this",
    "that",
    "it",
    "these",
    "those",
    "they",
    "the scheme",
    "same scheme",
    "above scheme",
    "this scheme",
)
_PRONOUN_PATTERN = re.compile(
    rf"\b({'|'.join(re.escape(w) for w in _PRONOUN_TRIGGERS)})\b", re.IGNORECASE
)


async def _rewrite_query_if_followup(query: str, context: list) -> str:
    prior_turns = [
        m
        for m in context
        if not (m.get("role") == "user" and m.get("content") == query)
    ]
    if not prior_turns or not _PRONOUN_PATTERN.search(query):
        return query

    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        from app.models.provider import ProviderSelector

        selector = ProviderSelector()
        model_name = selector.resolve_model("classify")
        llm = selector.get_chat_llm(model=model_name, temperature=0.0)

        recent_history = [
            f"{m.get('role', 'user')}: {m.get('content', '')}" for m in prior_turns[-4:]
        ]
        history_text = "\n".join(recent_history)

        system_prompt = (
            "You are a query contextualizer for a farmer helpline. "
            "Given recent conversation history and a follow-up user query containing "
            "pronouns or anaphoric references (e.g. 'this', 'the scheme'), rewrite "
            "the query as a standalone search query that mentions the exact scheme "
            "or subject. Output ONLY the rewritten query text with no explanation "
            "or quotes. If the query is already standalone, return it verbatim."
        )
        human_prompt = (
            f"Conversation History:\n{history_text}\n\nFollow-up Query: {query}"
        )

        response = await asyncio.wait_for(
            llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=human_prompt),
                ]
            ),
            timeout=8.0,
        )
        rewritten = response.content.strip().strip("\"'")
        return rewritten if rewritten else query
    except Exception as e:  # noqa: BLE001 - fallback to original query if rewriter fails
        logger = get_logger(__name__)
        logger.warning(f"Coreference rewrite skipped due to error: {e}")
        return query


def _extract_target_type(filters: dict | None) -> str | list[str] | None:
    if not filters:
        return None
    types = filters.get("types")
    if isinstance(types, list) and types:
        return types[0] if len(types) == 1 else types
    return filters.get("type")


async def classify(state: AgentState) -> AgentState:
    import asyncio

    from app.agent.tools import get_farm_data
    from app.models.classify import _fast_classify
    from app.services.rag import aquery_schemes

    query = state["query"]
    context = state.get("context", [])
    if context:
        query = await _rewrite_query_if_followup(query, context)
        state["query"] = query

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
                target_type = _extract_target_type(filters)
                state["scheme_data"] = await aquery_schemes(
                    query=query, scheme_type=target_type
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
    scheme_type = _extract_target_type(state.get("filters"))

    if settings.llm_cache_enabled:
        type_str = (
            ",".join(sorted(scheme_type))
            if isinstance(scheme_type, list)
            else (scheme_type or "all")
        )
        q_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
        cache_key = f"node_rag:{farm_id}:{q_hash}:{type_str}"
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
        (
            "Clarification rule: If the user query is very short, broad, or names "
            "an entity (such as 'tractor', 'polyhouse', 'seeds') without a specific "
            "question or goal, do not guess or refuse. Politely ask the user to "
            "clarify what specific information they need (for example: available "
            "government subsidies/schemes, eligibility criteria, application "
            "procedures, or operational guidelines)."
        ),
        (
            "Jurisdiction rule: If the user query is specific to a particular state "
            "(such as Tamil Nadu), do NOT apply guidelines, schemes, or compensation "
            "rules from a different state (such as Odisha). Explicitly advise that "
            "norms are state-specific."
        ),
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
    callback = state.get("stream_callback")

    if qtype == "scheme" and scheme_data.get("error"):
        outage_msg = (
            "Our government schemes database is temporarily undergoing maintenance. "
            "Please check back shortly or consult your local agriculture extension "
            "office."
        )
        state["response"] = outage_msg
        if callback:
            await callback(outage_msg)
        context.append({"role": "user", "content": query})
        context.append({"role": "assistant", "content": outage_msg})
        state["context"] = context[-10:]
        return state

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
        from app.core.config import get_settings

        timeout = get_settings().llm_timeout_seconds
        loop = asyncio.get_running_loop()
        full_response = await asyncio.wait_for(
            loop.run_in_executor(None, llm.generate, full_prompt, system_msg),
            timeout=float(timeout),
        )

    state["response"] = full_response

    context.append({"role": "user", "content": query})
    context.append({"role": "assistant", "content": full_response})
    state["context"] = context[-10:]

    return state


def handoff_node(state: AgentState) -> AgentState:
    state["response"] = "I'll connect you with a human agent. Please hold."
    return state
