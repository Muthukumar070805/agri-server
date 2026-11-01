from langgraph.graph import END, StateGraph

from app.agent.nodes import classify, direct_node, handoff_node, rag_node, tool_node
from app.agent.state import AgentState


def route_query(state: AgentState) -> str:
    qtype = state.get("query_type")
    if qtype in ("tool", "scheme", "direct", "handoff"):
        return qtype
    return "direct"


def compile_graph():
    graph = StateGraph(AgentState)

    graph.add_node("classify", classify)
    graph.add_node("rag", rag_node)
    graph.add_node("tool", tool_node)
    graph.add_node("direct", direct_node)
    graph.add_node("handoff", handoff_node)

    graph.set_entry_point("classify")

    graph.add_conditional_edges(
        "classify",
        route_query,
        {
            "tool": "tool",
            "scheme": "rag",
            "direct": "direct",
            "handoff": "handoff",
        },
    )

    graph.add_edge("tool", "direct")
    graph.add_edge("rag", "direct")
    graph.add_edge("direct", END)

    return graph.compile()


agent = compile_graph()
