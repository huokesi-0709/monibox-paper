"""Chat endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas.chat import ChatMessage, ChatRequest, ChatResponse
from api.services.chat_service import ChatServiceError, send_message

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/reply", response_model=ChatResponse)
def reply(payload: ChatRequest) -> ChatResponse:
    try:
        result = send_message(payload.session_id, payload.message)
    except ChatServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"聊天服务异常：{exc}") from exc

    return ChatResponse(
        reply=result.reply,
        session_id=result.session_id,
        messages=[
            ChatMessage(role=item["role"], content=item["content"])
            for item in result.messages
        ],
        debug=result.debug,
    )
