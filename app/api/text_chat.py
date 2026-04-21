from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.agent.graph import agent
from app.services.session import session_manager

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    query: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    response: str
    query_type: str
    session_id: str


@router.post("/text", response_model=ChatResponse)
async def text_chat(request: ChatRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    session = session_manager.get_or_create(request.session_id)
    session.add_message("user", request.query)

    try:
        result = agent.invoke(
            {
                "query": request.query,
                "query_type": "direct",
                "tool_data": {},
                "context": [],
                "response": "",
                "session_id": request.session_id,
            }
        )

        response = result.get("response", "No response generated")
        session.add_message("assistant", response)

        return ChatResponse(
            response=response,
            query_type=result.get("query_type", "unknown"),
            session_id=request.session_id,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")
