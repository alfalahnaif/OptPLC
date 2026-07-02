from __future__ import annotations

import asyncio
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger(__name__)
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # seconds


@dataclass
class LLMResponse:
    content: str
    input_tokens: int
    output_tokens: int
    model: str
    provider: str
    cost_usd: float


class BaseLLMProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> LLMResponse:
        raise NotImplementedError


def _estimate_cost(model_name: str, input_tokens: int, output_tokens: int, pricing: dict[str, dict[str, float]]) -> float:
    for key, price in pricing.items():
        if key in model_name:
            return (input_tokens * price["input"] + output_tokens * price["output"]) / 1000
    return 0.0


class AnthropicProvider(BaseLLMProvider):
    PRICING: dict[str, dict[str, float]] = {
        "claude-opus-4": {"input": 0.015, "output": 0.075},
        "claude-sonnet-4": {"input": 0.003, "output": 0.015},
        "claude-haiku-4": {"input": 0.00025, "output": 0.00125},
    }

    def __init__(self) -> None:
        self.model_name = settings.anthropic_model
        try:
            import anthropic

            self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        except ImportError as exc:
            raise RuntimeError("Anthropic package not installed. Run: pip install anthropic") from exc

    async def complete(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> LLMResponse:
        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await self._client.messages.create(
                    model=self.model_name,
                    system=system,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                break
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "rate_limit" in error_str.lower() or "Rate limit" in error_str:
                    retry_match = re.search(r"try again in (\d+\.?\d*)s", error_str)
                    wait_time = float(retry_match.group(1)) + 0.5 if retry_match else (RETRY_BASE_DELAY * (2 ** attempt))

                    if attempt < MAX_RETRIES:
                        logger.warning(
                            f"[{self.__class__.__name__}] Rate limited (attempt {attempt+1}/{MAX_RETRIES}). "
                            f"Waiting {wait_time:.1f}s before retry..."
                        )
                        await asyncio.sleep(wait_time)
                        last_error = e
                        continue
                raise
        else:
            raise last_error

        content = "".join(block.text for block in response.content if hasattr(block, "text"))
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost_usd = _estimate_cost(self.model_name, input_tokens, output_tokens, self.PRICING)

        logger.info(
            "llm_complete provider=%s model=%s input_tokens=%s output_tokens=%s cost_usd=%.6f",
            "anthropic",
            self.model_name,
            input_tokens,
            output_tokens,
            cost_usd,
        )

        return LLMResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self.model_name,
            provider="anthropic",
            cost_usd=cost_usd,
        )


class OpenAIProvider(BaseLLMProvider):
    PRICING: dict[str, dict[str, float]] = {
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    }

    def __init__(self) -> None:
        self.model_name = settings.openai_model
        try:
            import openai

            self._openai = openai
            self._client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        except ImportError as exc:
            raise RuntimeError("OpenAI package not installed. Run: pip install openai") from exc

    async def complete(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> LLMResponse:
        openai_messages = [{"role": "system", "content": system}, *messages] if system else list(messages)

        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await self._client.chat.completions.create(
                    model=self.model_name,
                    messages=openai_messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                break
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "rate_limit" in error_str.lower() or "Rate limit" in error_str:
                    retry_match = re.search(r"try again in (\d+\.?\d*)s", error_str)
                    wait_time = float(retry_match.group(1)) + 0.5 if retry_match else (RETRY_BASE_DELAY * (2 ** attempt))

                    if attempt < MAX_RETRIES:
                        logger.warning(
                            f"[{self.__class__.__name__}] Rate limited (attempt {attempt+1}/{MAX_RETRIES}). "
                            f"Waiting {wait_time:.1f}s before retry..."
                        )
                        await asyncio.sleep(wait_time)
                        last_error = e
                        continue
                raise
        else:
            raise last_error

        content = response.choices[0].message.content or ""
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0
        cost_usd = _estimate_cost(self.model_name, input_tokens, output_tokens, self.PRICING)

        logger.info(
            "llm_complete provider=%s model=%s input_tokens=%s output_tokens=%s cost_usd=%.6f",
            "openai",
            self.model_name,
            input_tokens,
            output_tokens,
            cost_usd,
        )

        return LLMResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self.model_name,
            provider="openai",
            cost_usd=cost_usd,
        )


class GeminiProvider(BaseLLMProvider):
    def __init__(self):
        try:
            import openai

            if not settings.gemini_api_key:
                raise RuntimeError("GEMINI_API_KEY is not set in .env")
            self._client = openai.AsyncOpenAI(
                api_key=settings.gemini_api_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            )
            self._model = getattr(settings, "gemini_model", "gemini-2.0-flash")
        except ImportError as exc:
            raise RuntimeError("OpenAI package not installed. Run: pip install openai") from exc

    async def complete(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> LLMResponse:
        import logging

        logger = logging.getLogger(__name__)

        all_messages: list[dict] = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=all_messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                break
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "rate_limit" in error_str.lower() or "Rate limit" in error_str:
                    retry_match = re.search(r"try again in (\d+\.?\d*)s", error_str)
                    wait_time = float(retry_match.group(1)) + 0.5 if retry_match else (RETRY_BASE_DELAY * (2 ** attempt))

                    if attempt < MAX_RETRIES:
                        logger.warning(
                            f"[{self.__class__.__name__}] Rate limited (attempt {attempt+1}/{MAX_RETRIES}). "
                            f"Waiting {wait_time:.1f}s before retry..."
                        )
                        await asyncio.sleep(wait_time)
                        last_error = e
                        continue
                raise
        else:
            raise last_error

        content = response.choices[0].message.content or ""
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0

        # Gemini Flash pricing: $0.075 per 1M input, $0.30 per 1M output
        cost = (input_tokens * 0.000000075) + (output_tokens * 0.0000003)

        logger.info(
            f"[GeminiProvider] model={self._model} "
            f"tokens={input_tokens + output_tokens} cost=${cost:.6f}"
        )

        return LLMResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self._model,
            provider="gemini",
            cost_usd=cost,
        )


class GroqProvider(BaseLLMProvider):
    """
    Groq inference via OpenAI-compatible API.
    Endpoint: https://api.groq.com/openai/v1
    Free tier: 14,400 requests/day — generous for development.
    """

    def __init__(self):
        try:
            import openai
            from app.config import settings

            if not settings.groq_api_key:
                raise RuntimeError(
                    "GROQ_API_KEY is not set in .env"
                )
            self._client = openai.AsyncOpenAI(
                api_key=settings.groq_api_key,
                base_url="https://api.groq.com/openai/v1",
            )
            self._model = getattr(settings, "groq_model", "llama-3.3-70b-versatile")
        except ImportError as exc:
            raise RuntimeError(
                "OpenAI package not installed. Run: pip install openai"
            ) from exc

    async def complete(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> LLMResponse:
        import logging

        logger = logging.getLogger(__name__)

        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=all_messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                break
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "rate_limit" in error_str.lower() or "Rate limit" in error_str:
                    retry_match = re.search(r"try again in (\d+\.?\d*)s", error_str)
                    wait_time = float(retry_match.group(1)) + 0.5 if retry_match else (RETRY_BASE_DELAY * (2 ** attempt))

                    if attempt < MAX_RETRIES:
                        logger.warning(
                            f"[{self.__class__.__name__}] Rate limited (attempt {attempt+1}/{MAX_RETRIES}). "
                            f"Waiting {wait_time:.1f}s before retry..."
                        )
                        await asyncio.sleep(wait_time)
                        last_error = e
                        continue
                raise
        else:
            raise last_error

        content = response.choices[0].message.content or ""
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0

        # Groq free tier — no charge
        cost = 0.0

        logger.info(
            f"[GroqProvider] model={self._model} "
            f"tokens={input_tokens + output_tokens} cost=${cost:.6f}"
        )

        return LLMResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self._model,
            provider="groq",
            cost_usd=cost,
        )


class OllamaProvider(BaseLLMProvider):
    def __init__(self) -> None:
        self.model_name = settings.ollama_model
        self.base_url = settings.ollama_base_url.rstrip("/")
        try:
            import httpx

            self._httpx = httpx
            self._http = httpx.AsyncClient(timeout=120.0)
        except ImportError as exc:
            raise RuntimeError("httpx not installed. Run: pip install httpx") from exc

    async def complete(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> LLMResponse:
        payload_messages = [{"role": "system", "content": system}, *messages] if system else list(messages)
        payload = {
            "model": self.model_name,
            "messages": payload_messages,
            "stream": False,
            "options": {"temperature": temperature},
        }

        try:
            response = await self._http.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
        except self._httpx.ConnectError as exc:
            raise RuntimeError(
                f"Failed to connect to Ollama at {self.base_url}. Ensure Ollama is running and accessible."
            ) from exc
        except self._httpx.HTTPError as exc:
            raise RuntimeError(f"Ollama chat request failed: {exc}") from exc

        body = response.json()
        content = body.get("message", {}).get("content", "")
        input_tokens = int(body.get("prompt_eval_count", 0) or 0)
        output_tokens = int(body.get("eval_count", 0) or 0)

        logger.info(
            "llm_complete provider=%s model=%s input_tokens=%s output_tokens=%s cost_usd=%.6f",
            "ollama",
            self.model_name,
            input_tokens,
            output_tokens,
            0.0,
        )

        return LLMResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self.model_name,
            provider="ollama",
            cost_usd=0.0,
        )


_CLIENT_SINGLETON: BaseLLMProvider | None = None


def get_llm_client() -> BaseLLMProvider:
    global _CLIENT_SINGLETON
    if _CLIENT_SINGLETON is not None:
        return _CLIENT_SINGLETON

    provider = settings.llm_provider.strip().lower()
    if provider == "anthropic":
        _CLIENT_SINGLETON = AnthropicProvider()
    elif provider == "openai":
        _CLIENT_SINGLETON = OpenAIProvider()
    elif provider == "gemini":
        _CLIENT_SINGLETON = GeminiProvider()
    elif provider == "groq":
        return GroqProvider()
    elif provider == "ollama":
        _CLIENT_SINGLETON = OllamaProvider()
    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER: '{provider}'. "
            f"Supported: anthropic, openai, gemini, groq, ollama"
        )

    return _CLIENT_SINGLETON


async def llm_complete(
    system: str,
    messages: list[dict],
    max_tokens: int = settings.llm_max_tokens,
    temperature: float = settings.llm_temperature,
) -> LLMResponse:
    client = get_llm_client()
    return await client.complete(
        system=system,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )


# How any agent will use this — identical regardless of provider:
#
# from app.agents.llm_client import llm_complete
#
# async def _generate_with_llm(self, plan: PlanObject) -> PlanObject:
#     response = await llm_complete(
#         system=PLANNING_SYSTEM_PROMPT,
#         messages=[{"role": "user", "content": requirement_text}],
#         temperature=0.1,
#     )
#     return parse_json_safely(response.content)
#
# To switch from Anthropic to OpenAI: change LLM_PROVIDER=openai in .env
# To switch to local Ollama: change LLM_PROVIDER=ollama in .env
# Zero changes to any agent code.
