from app.agent.state import AgentState
from app.models.classify import classify_query
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from app.models.ollama import get_chat_llm
from app.agent.tools import (
    get_weather,
    get_scheme_info,
    get_soil_data,
    get_satellite_data,
    get_farm_data,
)
import json


tools = [get_weather, get_scheme_info, get_soil_data, get_satellite_data]


def classify(state: AgentState) -> AgentState:
    query = state["query"]
    query_type = classify_query(query)
    state["query_type"] = query_type
    return state


def rag_node(state: AgentState) -> AgentState:
    query = state["query"]
    result = get_scheme_info.invoke({"query": query})
    state["response"] = f"Based on scheme information: {result}"
    return state


def tool_node(state: AgentState) -> AgentState:
    if state["query_type"] == "tool":
        result = get_farm_data.invoke({"farm_id": "default"})
        try:
            state["tool_data"] = json.loads(result.content)
        except json.JSONDecodeError:
            state["tool_data"] = {}
    else:
        state["tool_data"] = {}
    return state


def direct_node(state: AgentState) -> AgentState:
    from app.models.reasoning import ReasoningLLM

    query = state["query"]
    tool_data = state.get("tool_data", {})
    context = state.get("context", [])

    tool_info = ""
    if tool_data:
        tool_info = f"\n\nFarm Data:\n{json.dumps(tool_data, indent=2)}"

    context_str = ""
    if context:
        context_str = f"\n\nConversation History:\n{json.dumps(context, indent=2)}"

    full_prompt = f"User Query: {query}{tool_info}{context_str}"

    system_msg = "You are a helpful AI assistant for a farmer helpline. Use the provided farm data to answer user questions accurately."
    llm = ReasoningLLM()
    response = llm.generate(full_prompt, system=system_msg)

    state["response"] = response
    return state


def handoff_node(state: AgentState) -> AgentState:
    state["response"] = "I'll connect you with a human agent. Please hold."
    return state
