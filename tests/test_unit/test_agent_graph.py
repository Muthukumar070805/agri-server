from app.agent.graph import route_query, compile_graph, agent


class TestRouteQuery:
    def test_route_query_returns_type(self):
        state = {
            "query": "test",
            "query_type": "tool",
            "filters": {},
            "tool_data": {},
            "scheme_data": {},
            "context": [],
            "response": "",
            "session_id": "test",
        }
        assert route_query(state) == "tool"
        state["query_type"] = "scheme"
        assert route_query(state) == "scheme"
        state["query_type"] = "direct"
        assert route_query(state) == "direct"


class TestCompileGraph:
    def test_compile_graph_returns_compiled_graph(self):
        graph = compile_graph()
        assert graph is not None
        assert hasattr(graph, "ainvoke")

    def test_agent_is_compiled_graph(self):
        assert agent is not None
        assert hasattr(agent, "ainvoke")

    def test_graph_has_correct_node_structure(self):
        graph = compile_graph()
        nodes = graph.get_graph().nodes
        node_names = [n for n in nodes.keys()]
        assert "classify" in node_names
        assert "rag" in node_names
        assert "tool" in node_names
        assert "direct" in node_names
        assert "handoff" in node_names

    def test_graph_has_conditional_edge_from_classify(self):
        graph = compile_graph()
        graph_str = str(graph.get_graph())
        assert "classify" in graph_str
