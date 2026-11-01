from collections.abc import Callable
from typing import Literal, TypedDict


class AgentState(TypedDict):
    query: str
    query_type: Literal["tool", "scheme", "direct"]
    filters: dict
    tool_data: dict
    scheme_data: dict
    context: list
    response: str
    session_id: str
    farm_id: str
    stream_callback: Callable | None
