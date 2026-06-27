def test_agent_state_has_farm_id():
    from app.agent.state import AgentState

    state: AgentState = {
        "query": "test",
        "query_type": "direct",
        "filters": {},
        "tool_data": {},
        "scheme_data": {},
        "context": [],
        "response": "",
        "session_id": "test",
        "stream_callback": None,
    }
    assert state.get("farm_id", "default") == "default"
