"""Deterministic test doubles for external services (plan item P0-04)."""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.llm_client import BaseLLMProvider, LLMResponse

FAKE_DEFAULT_RESPONSE = "FAKE_LLM_RESPONSE: no scripted reply"


@dataclass
class RecordedCall:
    system: str
    messages: list[dict]
    max_tokens: int
    temperature: float


class FakeLLMProvider(BaseLLMProvider):
    """Returns scripted replies in order, then a default reply, and records every call.

    The default reply is neither JSON nor Structured Text, so agents take their
    deterministic fallback paths unless a test scripts a reply with `script()`.
    """

    def __init__(self) -> None:
        self.calls: list[RecordedCall] = []
        self._scripted: list[str] = []

    def script(self, *replies: str) -> None:
        self._scripted.extend(replies)

    async def complete(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> LLMResponse:
        self.calls.append(RecordedCall(system=system, messages=list(messages), max_tokens=max_tokens, temperature=temperature))
        content = self._scripted.pop(0) if self._scripted else FAKE_DEFAULT_RESPONSE
        return LLMResponse(
            content=content,
            input_tokens=0,
            output_tokens=0,
            model="fake-llm",
            provider="fake",
            cost_usd=0.0,
        )


class FakeRAGService:
    """Stands in for RAGService so tests never load embeddings or touch /app/rag_db."""

    def __init__(self) -> None:
        self.queries: list[dict] = []

    def seed(self) -> int:
        return 0

    def retrieve(self, query: str, domain: str = "", n_results: int = 3) -> list[dict]:
        self.queries.append({"query": query, "domain": domain, "n_results": n_results})
        return []
