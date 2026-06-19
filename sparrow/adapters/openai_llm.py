"""OpenAI-compatible LLM adapter — urllib only, implements the ``LLM`` port.

Migrated from the old ``llm.py`` with one essential fix: the provider's
``finish_reason`` is preserved and surfaced as :attr:`Completion.stop_reason`
(the old client dropped it, so truncated replies went unnoticed). Streaming and
the global USAGE_LOG are intentionally gone — usage rides on each Completion.

Config comes from env (``SPARROW_LLM_*`` preferred, ``DEEPSEEK_*`` fallback) and
can be overridden at runtime with :func:`configure`.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from ..core.models import Completion
from ..core.schema import completion_from_openai, to_openai_messages

_CFG = {
    "base_url": os.environ.get("SPARROW_LLM_BASE_URL")
    or os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    "api_key": os.environ.get("SPARROW_LLM_API_KEY")
    or os.environ.get("DEEPSEEK_API_KEY", ""),
    "model": os.environ.get("SPARROW_LLM_MODEL")
    or os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
}


def configure(*, base_url=None, api_key=None, model=None) -> None:
    """Override LLM credentials/model at runtime. Unset args keep their value."""
    if base_url is not None:
        _CFG["base_url"] = base_url
    if api_key is not None:
        _CFG["api_key"] = api_key
    if model is not None:
        _CFG["model"] = model


class LLMError(Exception):
    pass


class OpenAILLM:
    """Implements the :class:`~sparrow.ports.LLM` protocol against any
    OpenAI-compatible chat-completions endpoint."""

    def __init__(self, *, retries: int = 2):
        self.retries = retries

    def complete(self, messages, *, tools=None, response_format=None,
                 max_tokens=2000, temperature=0.3) -> Completion:
        if not _CFG["api_key"]:
            raise LLMError("LLM api key is not configured (SPARROW_LLM_API_KEY / DEEPSEEK_API_KEY)")
        payload = {
            "model": _CFG["model"],
            "messages": to_openai_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
        if response_format:
            payload["response_format"] = response_format

        last_err = None
        for attempt in range(self.retries + 1):
            try:
                resp = self._request(payload)
                data = json.loads(resp.read())
                choice = data["choices"][0]
                return completion_from_openai(
                    choice["message"], data.get("usage", {}),
                    stop_reason=choice.get("finish_reason") or "stop")
            except (urllib.error.URLError, json.JSONDecodeError, KeyError, TimeoutError) as e:
                last_err = e
                if attempt < self.retries:
                    time.sleep(1.5 * (attempt + 1))
        raise LLMError(f"LLM call failed (after {self.retries} retries): {last_err}")

    @staticmethod
    def _request(payload: dict):
        req = urllib.request.Request(
            f"{_CFG['base_url'].rstrip('/')}/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {_CFG['api_key']}"},
        )
        return urllib.request.urlopen(req, timeout=120)
