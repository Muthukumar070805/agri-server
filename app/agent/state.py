from typing import TypedDict, Literal, Callable, Optional


class AgentState(TypedDict):
    query: str
    query_type: Literal["tool", "scheme", "direct"]
    filters: dict
    tool_data: dict
    scheme_data: dict
    context: list
    response: str
    session_id: str
    stream_callback: Optional[Callable]