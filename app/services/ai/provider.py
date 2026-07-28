"""
Provider-agnostic AI interface. All agents call through AIProvider so the
underlying model (OpenAI / Gemini / Claude) can be swapped via config
without touching agent logic.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any


@dataclass
class AIResponse:
    text: str
    raw: dict[str, Any]
    provider: str
    model: str


class AIProvider(abc.ABC):
    name: str

    @abc.abstractmethod
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        json_mode: bool = False,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> AIResponse:
        """Send a single-turn completion request and return normalized response."""
        raise NotImplementedError


class ClaudeProvider(AIProvider):
    name = "claude"

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        import anthropic

        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        json_mode: bool = False,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> AIResponse:
        if json_mode:
            system_prompt += "\n\nRespond with ONLY valid JSON. No markdown, no preamble."
        resp = await self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = "".join(block.text for block in resp.content if block.type == "text")
        return AIResponse(text=text, raw=resp.model_dump(), provider=self.name, model=self._model)


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4.1"):
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        json_mode: bool = False,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> AIResponse:
        resp = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format={"type": "json_object"} if json_mode else None,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        text = resp.choices[0].message.content or ""
        return AIResponse(text=text, raw=resp.model_dump(), provider=self.name, model=self._model)


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        self._client = genai.GenerativeModel(model)
        self._model = model

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        json_mode: bool = False,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> AIResponse:
        generation_config = {
            "max_output_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            generation_config["response_mime_type"] = "application/json"
        resp = await self._client.generate_content_async(
            [system_prompt, user_prompt],
            generation_config=generation_config,
        )
        return AIResponse(text=resp.text, raw={}, provider=self.name, model=self._model)


def get_ai_provider(provider_name: str | None = None) -> AIProvider:
    from app.core.config import settings

    provider_name = provider_name or settings.AI_DEFAULT_PROVIDER
    if provider_name == "claude":
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY not configured")
        return ClaudeProvider(api_key=settings.ANTHROPIC_API_KEY)
    if provider_name == "openai":
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY not configured")
        return OpenAIProvider(api_key=settings.OPENAI_API_KEY)
    if provider_name == "gemini":
        if not settings.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY not configured")
        return GeminiProvider(api_key=settings.GEMINI_API_KEY)
    raise ValueError(f"Unknown AI provider: {provider_name}")
