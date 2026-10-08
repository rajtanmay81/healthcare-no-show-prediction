"""Provider-agnostic LLM abstraction.

The rest of the application depends only on :class:`LLMClient`. Providers are selected with
``LLM_PROVIDER`` (``anthropic`` | ``openai`` | ``none``) and configured via environment variables;
no API key is ever hardcoded.

* ``anthropic`` - official Anthropic Python SDK (Messages API). Default model ``claude-opus-5-5``.
* ``openai``    - any OpenAI-compatible Chat Completions endpoint (OpenAI, Azure, Groq, vLLM, Ollama...)
                  via ``LLM_BASE_URL``.
* ``none``      - no external calls; the assistant falls back to deterministic, grounded templates.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from functools import lru_cache

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

DEFAULT_MODELS = {"anthropic": "claude-opus-5-5", "openai": "gpt-4o-mini"}


class LLMError(Exception):
    """Raised when the provider call fails; callers fall back to templates."""


class LLMClient(ABC):
    provider: str
    model: str

    @abstractmethod
    def generate(self, system: str, prompt: str) -> str:
        """Return the model's text response for a single-turn, grounded request."""


class AnthropicClient(LLMClient):
    provider = "anthropic"

    def __init__(self, settings: Settings) -> None:
        import anthropic

        self._anthropic = anthropic
        self.model = settings.LLM_MODEL or DEFAULT_MODELS["anthropic"]
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.effort = settings.LLM_EFFORT
        kwargs: dict[str, object] = {"timeout": settings.LLM_TIMEOUT_SECONDS, "max_retries": 2}
        if settings.LLM_API_KEY:
            kwargs["api_key"] = settings.LLM_API_KEY  # otherwise the SDK resolves ANTHROPIC_API_KEY etc.
        if settings.LLM_BASE_URL:
            kwargs["base_url"] = settings.LLM_BASE_URL
        self.client = anthropic.Anthropic(**kwargs)  # type: ignore[arg-type]

    def generate(self, system: str, prompt: str) -> str:
        anthropic = self._anthropic
        try:
            # Server-side fallback reroutes a safety-classifier decline to another model within the same call.
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_config={"effort": self.effort},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.RateLimitError as exc:
            raise LLMError("LLM provider rate limit reached") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"LLM provider returned HTTP {exc.status_code}") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("Could not reach the LLM provider") from exc

        if response.stop_reason == "refusal":
            raise LLMError("The LLM declined this request")
        text = "".join(block.text for block in response.content if block.type == "text").strip()
        if not text:
            raise LLMError("LLM returned an empty response")
        return text


class OpenAICompatibleClient(LLMClient):
    provider = "openai"

    def __init__(self, settings: Settings) -> None:
        if not settings.LLM_API_KEY:
            raise LLMError("LLM_API_KEY is required for the openai provider")
        self.model = settings.LLM_MODEL or DEFAULT_MODELS["openai"]
        self.url = (settings.LLM_BASE_URL or "https://api.openai.com/v1").rstrip("/") + "/chat/completions"
        self.headers = {"Authorization": f"Bearer {settings.LLM_API_KEY}"}
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.temperature = settings.LLM_TEMPERATURE
        self.timeout = settings.LLM_TIMEOUT_SECONDS

    def generate(self, system: str, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        try:
            resp = httpx.post(self.url, json=payload, headers=self.headers, timeout=self.timeout)
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"] or ""
        except httpx.HTTPStatusError as exc:
            raise LLMError(f"LLM provider returned HTTP {exc.response.status_code}") from exc
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise LLMError("LLM provider call failed") from exc
        if not text.strip():
            raise LLMError("LLM returned an empty response")
        return text.strip()


@lru_cache
def get_llm_client() -> LLMClient | None:
    """Configured client, or ``None`` when no provider is configured (template fallback mode)."""
    settings = get_settings()
    try:
        if settings.LLM_PROVIDER == "anthropic":
            return AnthropicClient(settings)
        if settings.LLM_PROVIDER == "openai":
            return OpenAICompatibleClient(settings)
    except Exception:  # noqa: BLE001 - misconfiguration must not take the API down
        logger.exception("Failed to initialise LLM provider %s; using template fallback", settings.LLM_PROVIDER)
    return None
