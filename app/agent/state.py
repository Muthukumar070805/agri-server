from typing import TypedDict, Literal


class AgentState(TypedDict):
    query: str
    query_type: Literal["tool", "direct"]
    tool_data: dict
    context: list
    response: str
    session_id: str
