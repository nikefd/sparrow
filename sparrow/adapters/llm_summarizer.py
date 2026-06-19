"""LLM-backed Summarizer — compaction's execution body. Implements the
``Summarizer`` port by asking the model to condense a block of old messages into
one ``role="system"`` recap, so long conversations continue instead of dropping
history.
"""
from __future__ import annotations

from ..core.models import Message
from ..core.schema import to_openai_messages

_PROMPT = ("Summarize the following conversation excerpt into a compact recap that "
           "preserves facts, decisions, and any unfinished tasks. Be terse; omit "
           "pleasantries. Output only the recap.")


class LLMSummarizer:
    """Uses an LLM (any object with a ``complete`` method) to compact messages."""

    def __init__(self, llm):
        self.llm = llm

    def summarize(self, messages: list) -> Message:
        rendered = to_openai_messages(messages)
        transcript = "\n".join(f"[{m['role']}] {m.get('content') or ''}" for m in rendered)
        comp = self.llm.complete(
            [Message(role="system", content=_PROMPT),
             Message(role="user", content=transcript)],
            max_tokens=500, temperature=0.2)
        return Message(role="system", content="[earlier conversation summary]\n" + comp.content)
