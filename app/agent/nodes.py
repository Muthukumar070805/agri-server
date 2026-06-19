from typing import Optional
from app.agent.state import AgentState
from app.models.classify import classify_query
from langgraph.prebuilt import ToolNode
import json

_tool_node: Optional[ToolNode] = None


async def classify(state: AgentState) -> AgentState:
    query = state["query"]
    query_type, filters = await classify_query(query)
    state["query_type"] = query_type
    state["filters"] = filters
    return state


async def rag_node(state: AgentState) -> AgentState:
    from app.services.rag import aquery_schemes

    result = await aquery_schemes(
        query=state["query"], scheme_type=state.get("filters", {}).get("type")
    )
    state["scheme_data"] = result
    return state


async def tool_node(state: AgentState) -> AgentState:
    from app.agent.tools import get_farm_data

    if state["query_type"] == "tool":
        result = await get_farm_data(farm_id="default")
        try:
            state["tool_data"] = json.loads(result)
        except json.JSONDecodeError:
            state["tool_data"] = {}
    else:
        state["tool_data"] = {}
    return state


async def direct_node(state: AgentState) -> AgentState:
    from app.models.reasoning import ReasoningLLM

    query = state["query"]
    tool_data = state.get("tool_data", {})
    scheme_data = state.get("scheme_data", {})
    context = state.get("context", [])

    tool_info = ""
    if tool_data:
        tool_info = f"\n\nFarm Data:\n{json.dumps(tool_data, indent=2)}"

    scheme_info = ""
    if scheme_data:
        scheme_info = f"\n\nScheme Information:\n{json.dumps(scheme_data, indent=2)}"

    context_str = ""
    if context:
        context_str = f"\n\nConversation History:\n{json.dumps(context, indent=2)}"

    full_prompt = f"User Query: {query}{tool_info}{scheme_info}{context_str}"
    system_msg = "You are a helpful AI assistant for a farmer helpline. Use the provided farm data and scheme information to answer user questions accurately. Be concise for voice output."

    llm = ReasoningLLM()
    full_response = ""
    callback = state.get("stream_callback")

    if callback:
        async for token in llm.astream(full_prompt, system=system_msg):
            full_response += token
            await callback(token)
    else:
        full_response = llm.generate(full_prompt, system=system_msg)

    state["response"] = full_response
    return state


def handoff_node(state: AgentState) -> AgentState:
    state["response"] = "I'll connect you with a human agent. Please hold."
    return state
