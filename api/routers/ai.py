"""
AI Provider endpoints - status, chat, model selection.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.ai_providers import ai, AIMessage, PROVIDER_PRIORITY, DEFAULT_MODELS, OPENROUTER_FREE_MODELS

router = APIRouter()


class ChatRequest(BaseModel):
    prompt: str
    system: str = ""
    provider: Optional[str] = None
    model: Optional[str] = None
    max_tokens: int = 2048


class MessageItem(BaseModel):
    role: str
    content: str


class ChatMessagesRequest(BaseModel):
    messages: list[MessageItem]
    system: str = ""
    provider: Optional[str] = None
    model: Optional[str] = None
    max_tokens: int = 2048


@router.get("/ai/status")
async def ai_status():
    """Show all configured AI providers and their default models."""
    return {
        **ai.status(),
        "openrouter_free_models": OPENROUTER_FREE_MODELS,
    }


@router.post("/ai/chat")
async def ai_chat(body: ChatRequest):
    """Send a prompt to the best available AI provider."""
    try:
        response = await ai.chat(
            prompt=body.prompt,
            system=body.system,
            provider=body.provider,
            model=body.model,
            max_tokens=body.max_tokens,
        )
        return {
            "text": response.text,
            "provider": response.provider,
            "model": response.model,
            "tokens_in": response.input_tokens,
            "tokens_out": response.output_tokens,
        }
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ai/chat/messages")
async def ai_chat_messages(body: ChatMessagesRequest):
    """Send a conversation (multi-turn) to AI."""
    try:
        messages = [AIMessage(role=m.role, content=m.content) for m in body.messages]
        response = await ai.chat_messages(
            messages=messages,
            system=body.system,
            provider=body.provider,
            model=body.model,
            max_tokens=body.max_tokens,
        )
        return {
            "text": response.text,
            "provider": response.provider,
            "model": response.model,
            "tokens_in": response.input_tokens,
            "tokens_out": response.output_tokens,
        }
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
