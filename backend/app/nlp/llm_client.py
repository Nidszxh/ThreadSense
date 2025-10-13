"""OpenAI-compatible chat client, env-configured (works with OpenAI, Groq, Ollama)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from openai import OpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


@dataclass
class CompletionResult:
    text: str
    tokens_in: int
    tokens_out: int


_client: "LLMClient | None" = None


class LLMClient:
    def __init__(
        self,
        api_key: str | None,
        base_url: str,
        model: str,
        timeout: float,
        json_mode: bool,
    ) -> None:
        self.api_key = api_key or ""
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.json_mode = json_mode
        self._client: OpenAI | None = None

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                max_retries=2,
            )
        return self._client

    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 600,
        temperature: float = 0.3,
        json_mode: bool | None = None,
    ) -> CompletionResult:
        if not self.available:
            raise LLMError("LLM not configured: set LLM_API_KEY")
        use_json = self.json_mode if json_mode is None else json_mode
        request: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if use_json:
            request["response_format"] = {"type": "json_object"}
        try:
            response = self._get_client().chat.completions.create(**request)
        except Exception as exc:  # noqa: BLE001  (surface any provider failure)
            raise LLMError(f"LLM request failed: {exc}") from exc

        text = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        tokens_in = getattr(usage, "prompt_tokens", 0) or 0
        tokens_out = getattr(usage, "completion_tokens", 0) or 0
        logger.debug("LLM completion: %s tokens in, %s tokens out", tokens_in, tokens_out)
        return CompletionResult(text=text, tokens_in=tokens_in, tokens_out=tokens_out)


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = LLMClient(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            timeout=settings.llm_timeout_seconds,
            json_mode=settings.llm_json_mode,
        )
    return _client
