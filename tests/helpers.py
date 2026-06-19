def validate_chat_response(json_data: dict):
    assert "response" in json_data
    assert isinstance(json_data["response"], str)
    assert json_data["query_type"] in ("tool", "scheme", "direct")
    assert isinstance(json_data["session_id"], str)
    assert isinstance(json_data.get("scheme_list", []), list)


def assert_health_response(json_data: dict):
    assert json_data["status"] == "healthy"


def assert_circuit_entry(circuit: dict):
    assert circuit["state"] in ("closed", "open", "half_open")
    assert isinstance(circuit["failures"], int)
    assert "last_failure_time" in circuit
