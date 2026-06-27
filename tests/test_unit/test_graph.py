def test_route_query_fallback():
    from app.agent.graph import route_query

    assert route_query({"query_type": None}) == "direct"
    assert route_query({"query_type": "unknown"}) == "direct"
    assert route_query({"query_type": "handoff"}) == "handoff"
    assert route_query({"query_type": "direct"}) == "direct"
    assert route_query({"query_type": "tool"}) == "tool"
    assert route_query({"query_type": "scheme"}) == "scheme"
    assert route_query({}) == "direct"


def test_graph_has_handoff_edge():
    from app.agent.graph import agent

    graph = agent.get_graph()
    edges = graph.edges
    handoff_found = any(
        "handoff" in str(e) for e in edges
    )
    assert handoff_found, "handoff edge not found in graph"
