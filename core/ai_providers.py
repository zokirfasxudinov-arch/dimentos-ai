"""
Dimentos AI Studio OS - Unified AI Provider
Wraps Anthropic, Gemini, OpenRouter, Groq, OpenAI into one interface.
Agents call ai.chat(...) and the best available provider is used automatically.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

from loguru import logger

from core.config import settings


@dataclass
class AIMessage:
    role: str  # "user" | "assistant" | "system"
    content: str


@dataclass
class AIResponse:
    text: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


# Priority order: fast/cheap first, powerful last as fallback
PROVIDER_PRIORITY = ["groq", "gemini", "openrouter", "anthropic", "openai"]

# Default models per provider
DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5",
    "openai":    "gpt-4o-mini",
    "gemini":    "gemini-2.5-flash-lite",
    "groq":      "llama-3.3-70b-versatile",
    "openrouter": "google/gemini-2.0-flash-lite:free",
}

# Free models on OpenRouter (good defaults)
OPENROUTER_FREE_MODELS = [
    "google/gemini-2.0-flash-lite:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "qwen/qwen-2.5-72b-instruct:free",
]


async def _call_anthropic(messages: list[AIMessage], model: str, system: str, max_tokens: int) -> AIResponse:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    msgs = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]
    sys_prompt = system or next((m.content for m in messages if m.role == "system"), None)

    response = await client.messages.create(
        model=model or DEFAULT_MODELS["anthropic"],
        max_tokens=max_tokens,
        system=sys_prompt or "You are a helpful AI assistant.",
        messages=msgs,
    )
    return AIResponse(
        text=response.content[0].text,
        provider="anthropic",
        model=response.model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )


async def _call_gemini(messages: list[AIMessage], model: str, system: str, max_tokens: int) -> AIResponse:
    import google.generativeai as genai
    genai.configure(api_key=settings.gemini_api_key)
    m = model or DEFAULT_MODELS["gemini"]
    gen_model = genai.GenerativeModel(
        model_name=m,
        system_instruction=system or "You are a helpful AI assistant.",
    )
    history = []
    last_user = None
    for msg in messages:
        if msg.role == "system":
            continue
        if msg.role == "user":
            last_user = msg.content
            if history:
                history.append({"role": "user", "parts": [msg.content]})
        elif msg.role == "assistant":
            history.append({"role": "model", "parts": [msg.content]})

    if not last_user:
        raise ValueError("No user message found")

    chat = gen_model.start_chat(history=history[:-1] if history else [])
    response = await asyncio.to_thread(
        chat.send_message,
        last_user,
        generation_config={"max_output_tokens": max_tokens},
    )
    return AIResponse(
        text=response.text,
        provider="gemini",
        model=m,
    )


async def _call_openai_compat(
    messages: list[AIMessage],
    model: str,
    system: str,
    max_tokens: int,
    api_key: str,
    base_url: str,
    provider_name: str,
) -> AIResponse:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    for m in messages:
        if m.role == "system" and not system:
            msgs.append({"role": "system", "content": m.content})
        elif m.role != "system":
            msgs.append({"role": m.role, "content": m.content})

    response = await client.chat.completions.create(
        model=model,
        messages=msgs,
        max_tokens=max_tokens,
    )
    usage = response.usage
    return AIResponse(
        text=response.choices[0].message.content,
        provider=provider_name,
        model=response.model,
        input_tokens=usage.prompt_tokens if usage else 0,
        output_tokens=usage.completion_tokens if usage else 0,
    )


async def _call_groq(messages: list[AIMessage], model: str, system: str, max_tokens: int) -> AIResponse:
    return await _call_openai_compat(
        messages=messages,
        model=model or DEFAULT_MODELS["groq"],
        system=system,
        max_tokens=max_tokens,
        api_key=settings.groq_api_key,
        base_url="https://api.groq.com/openai/v1",
        provider_name="groq",
    )


async def _call_openrouter(messages: list[AIMessage], model: str, system: str, max_tokens: int) -> AIResponse:
    return await _call_openai_compat(
        messages=messages,
        model=model or DEFAULT_MODELS["openrouter"],
        system=system,
        max_tokens=max_tokens,
        api_key=settings.active_openrouter_key,
        base_url="https://openrouter.ai/api/v1",
        provider_name="openrouter",
    )


async def _call_openai(messages: list[AIMessage], model: str, system: str, max_tokens: int) -> AIResponse:
    return await _call_openai_compat(
        messages=messages,
        model=model or DEFAULT_MODELS["openai"],
        system=system,
        max_tokens=max_tokens,
        api_key=settings.openai_api_key,
        base_url="https://api.openai.com/v1",
        provider_name="openai",
    )


_PROVIDER_FUNCS = {
    "anthropic": _call_anthropic,
    "gemini":    _call_gemini,
    "groq":      _call_groq,
    "openrouter": _call_openrouter,
    "openai":    _call_openai,
}


class AIProviderService:
    """
    Unified AI interface for all Dimentos agents.

    Usage:
        ai = AIProviderService()

        # Simple text prompt
        result = await ai.chat("Summarize this text: ...")

        # With messages history
        result = await ai.chat_messages([
            AIMessage("system", "You are a finance analyst"),
            AIMessage("user", "What is ROI?"),
        ])

        # Force specific provider
        result = await ai.chat("Hello", provider="anthropic", model="claude-haiku-4-5")
    """

    def available(self) -> list[str]:
        return settings.available_providers

    def _pick_provider(self, preferred: Optional[str] = None) -> Optional[str]:
        available = self.available()
        if not available:
            return None
        if preferred and preferred in available:
            return preferred
        for p in PROVIDER_PRIORITY:
            if p in available:
                return p
        return available[0]

    async def chat(
        self,
        prompt: str,
        system: str = "",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = 2048,
    ) -> AIResponse:
        """Send a simple text prompt. Returns AIResponse."""
        return await self.chat_messages(
            messages=[AIMessage(role="user", content=prompt)],
            system=system,
            provider=provider,
            model=model,
            max_tokens=max_tokens,
        )

    async def chat_messages(
        self,
        messages: list[AIMessage],
        system: str = "",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = 2048,
        fallback: bool = True,
    ) -> AIResponse:
        """Send a conversation. Falls back to next provider on error."""
        available = self.available()
        if not available:
            raise RuntimeError("No AI providers configured. Add at least one API key to .env")

        chosen = self._pick_provider(provider)
        if not chosen:
            raise RuntimeError("No AI providers available")

        providers_to_try = [chosen]
        if fallback:
            for p in PROVIDER_PRIORITY:
                if p in available and p != chosen:
                    providers_to_try.append(p)

        last_err = None
        for prov in providers_to_try:
            try:
                fn = _PROVIDER_FUNCS.get(prov)
                if not fn:
                    continue
                m = model if provider == prov else (DEFAULT_MODELS.get(prov, "") if not model else model)
                result = await fn(messages, m, system, max_tokens)
                logger.debug(f"AI call via {prov}/{result.model}: {result.output_tokens} out tokens")
                # Fire-and-forget cost logging (don't block on DB errors)
                asyncio.create_task(self._log_usage(result))
                return result
            except Exception as e:
                logger.warning(f"AI provider {prov} failed: {e}")
                last_err = e
                continue

        raise RuntimeError(f"All AI providers failed. Last error: {last_err}")

    async def _log_usage(self, result: "AIResponse") -> None:
        """Log AI usage to DB for cost tracking. Silently ignores errors."""
        try:
            import httpx
            await httpx.AsyncClient().post(
                f"http://localhost:{settings.api_port}/api/finance/log",
                json={
                    "provider": result.provider,
                    "model": result.model,
                    "tokens_in": result.input_tokens,
                    "tokens_out": result.output_tokens,
                },
                timeout=3,
            )
        except Exception:
            pass

    async def quick(self, prompt: str, max_tokens: int = 512) -> str:
        """Shortcut: returns just the text string. Uses fastest available provider."""
        resp = await self.chat(prompt, max_tokens=max_tokens)
        return resp.text

    def status(self) -> dict:
        available = self.available()
        return {
            "providers": available,
            "total": len(available),
            "priority_order": [p for p in PROVIDER_PRIORITY if p in available],
            "default_models": {p: DEFAULT_MODELS.get(p, "custom") for p in available},
        }


# Singleton
ai = AIProviderService()
