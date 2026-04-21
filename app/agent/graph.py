from langgraph.graph import StateGraph, END
from app.agent.state import AgentState
from app.agent.nodes import classify, rag_node, tool_node, direct_node, handoff_node


def route_query(state: AgentState) -> str:
    return state["query_type"]


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
            "direct": "direct",
        },
    )

    graph.add_edge("tool", "direct")
    graph.add_edge("direct", END)

    return graph.compile()


agent = compile_graph()
