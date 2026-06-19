from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import asyncio
from app.agent.graph import agent
from app.services.session import session_manager

router = APIRouter(prefix="/chat", tags=["chat"])

MAX_QUERY_LENGTH = 4096
MIN_QUERY_LENGTH = 1


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=MIN_QUERY_LENGTH, max_length=MAX_QUERY_LENGTH)
    session_id: str = "default"


class ChatResponse(BaseModel):
    response: str
    query_type: str
    session_id: str
    scheme_list: list = []


@router.post("/text", response_model=ChatResponse)
async def text_chat(request: ChatRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    session = await session_manager.get_or_create(request.session_id)
    session.add_message("user", request.query)

    history = session.messages[-10:]

    try:
        result = await agent.ainvoke(
            {
                "query": request.query,
                "query_type": "direct",
                "filters": {},
                "tool_data": {},
                "scheme_data": {},
                "context": history,
                "response": "",
                "session_id": request.session_id,
            }
        )

        response = result.get("response", "No response generated")
        session.add_message("assistant", response)

        try:
            asyncio.create_task(session_manager.save_session(session))
        except Exception:
            pass

        schemes_data = result.get("scheme_data", {}).get("schemes", [])

        return ChatResponse(
            response=response,
            query_type=result.get("query_type", "unknown"),
            session_id=request.session_id,
            scheme_list=schemes_data,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")
