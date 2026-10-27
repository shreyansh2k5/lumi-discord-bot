"""AI provider abstraction and the prompt-preserving chat interface."""

import asyncio
import os
from abc import ABC, abstractmethod
from typing import Any

import aiohttp

from config import (
    AI_MAX_TOKENS,
    FALLBACK_PROVIDER,
    PRIMARY_PROVIDER,
)
from core.personality import get_system_prompt, get_temperature

GROQ_MODEL_ID = "openai/gpt-oss-120b"
OPENROUTER_MODEL_ID = "dots-studio/dots-3-note-preview:free"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
AI_UNAVAILABLE_MESSAGE = "⚠️ My brain is a bit fuzzy right now..."


class AIUnavailableError(Exception):
    """Raised when all configured AI response attempts have failed."""


class ProviderError(Exception):
    """An error returned by or encountered while calling an AI provider."""

    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class ProviderConfigurationError(ProviderError):
    """A provider cannot be used because its local configuration is invalid."""


class AIProvider(ABC):
    name: str
    api_key_environment_variable: str
    api_url: str
    model_id: str

    @abstractmethod
    async def generate(self, messages: list[dict[str, str]]) -> str:
        raise NotImplementedError


class HTTPAIProvider(AIProvider):
    """Shared OpenAI-compatible HTTP implementation for providers."""

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self._session

    async def generate(self, messages: list[dict[str, str]]) -> str:
        api_key = os.getenv(self.api_key_environment_variable)
        if not api_key:
            raise ProviderConfigurationError(
                f"{self.api_key_environment_variable} not set."
            )

        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
        if self.name == "openrouter":
            headers.update({
                "HTTP-Referer": "https://lumi-bot.app",
                "X-Title": "Lumi Discord Bot",
            })

        body = {
            "model": self.model_id,
            "messages": messages,
            "temperature": get_temperature(),
            "max_tokens": AI_MAX_TOKENS,
        }
        if self.name == "openrouter":
            body["reasoning"] = {"enabled": False}

        try:
            session = await self._get_session()
            async with session.post(self.api_url, json=body, headers=headers) as response:
                data: Any = await response.json(content_type=None)
                if response.status != 200:
                    if response.status == 429:
                        message = "Rate limited (429)"
                    elif response.status >= 500:
                        message = f"Server error ({response.status})"
                    elif response.status in (401, 403):
                        message = "Authentication failed"
                    else:
                        message = f"HTTP {response.status}: {data}"
                    retryable = response.status == 429 or response.status >= 500
                    raise ProviderError(
                        message,
                        retryable=retryable,
                    )

                try:
                    text = (
                        data["choices"][0]["message"].get("content") or ""
                    ).strip()
                except (AttributeError, IndexError, KeyError, TypeError) as error:
                    raise ProviderError("returned an invalid response") from error
                if not text:
                    raise ProviderError("returned no message text")
                return text
        except ProviderError:
            raise
        except (asyncio.TimeoutError, aiohttp.ServerTimeoutError) as error:
            raise ProviderError("Timeout", retryable=True) from error
        except aiohttp.ClientConnectionError as error:
            raise ProviderError(f"Connection error: {error}", retryable=True) from error
        except aiohttp.ClientError as error:
            raise ProviderError(str(error)) from error
        except ValueError as error:
            raise ProviderError(f"Invalid response: {error}") from error


class GroqProvider(HTTPAIProvider):
    name = "groq"
    api_key_environment_variable = "GROQ_API_KEY"
    api_url = GROQ_API_URL
    model_id = GROQ_MODEL_ID


class OpenRouterProvider(HTTPAIProvider):
    name = "openrouter"
    api_key_environment_variable = "OPENROUTER_API_KEY"
    api_url = OPENROUTER_API_URL
    model_id = OPENROUTER_MODEL_ID


class ProviderManager:
    """Selects providers and falls back only for transient primary failures."""

    def __init__(
        self,
        providers: dict[str, AIProvider] | None = None,
        primary_provider: str = PRIMARY_PROVIDER,
        fallback_provider: str = FALLBACK_PROVIDER,
    ) -> None:
        self.providers = providers or {
            "groq": GroqProvider(),
            "openrouter": OpenRouterProvider(),
        }
        self.primary_provider = primary_provider
        self.fallback_provider = fallback_provider
        self.active_provider = self.providers.get(primary_provider)

    async def generate_response(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        primary = self.providers.get(self.primary_provider)
        fallback = self.providers.get(self.fallback_provider)
        if primary is None:
            print(f"[AI] Unknown primary provider: {self.primary_provider}")
            raise AIUnavailableError("No primary AI provider is configured.")

        last_error: ProviderError | None = None
        for attempt in range(3):
            try:
                response = await primary.generate(messages)
                self.active_provider = primary
                return response
            except ProviderError as error:
                last_error = error
                if not error.retryable:
                    break
                if attempt < 2:
                    await asyncio.sleep(2**attempt)

        if fallback is None:
            print(f"[AI] Unknown fallback provider: {self.fallback_provider}")
            raise AIUnavailableError from last_error

        if last_error is not None:
            print(f"[AI] Primary provider unavailable; using fallback: {last_error}")

        try:
            response = await fallback.generate(messages)
            self.active_provider = fallback
            return response
        except ProviderError as error:
            print(f"[AI] All providers failed: {error}")
            raise AIUnavailableError from error

ai_manager = ProviderManager()


async def query_model(
    messages: list[dict],
    server_emojis: str = "",
    server_name: str = "",
    channel_name: str = "",
    time_of_day: str = "",
) -> str:
    """Build the existing Lumi prompt and send it through the provider manager."""
    system_prompt = get_system_prompt(
        server_emojis=server_emojis,
        server_name=server_name,
        channel_name=channel_name,
        time_of_day=time_of_day,
    )

    ai_messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for msg in messages:
        content = msg.get("content", "").strip()
        if content:
            role = "assistant" if msg["role"] == "assistant" else "user"
            ai_messages.append({"role": role, "content": content})

    if ai_messages[-1]["role"] != "user":
        ai_messages.append({"role": "user", "content": "Continue."})

    return await ai_manager.generate_response(ai_messages)
