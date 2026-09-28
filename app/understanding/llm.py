from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from app.config import settings

T = TypeVar("T")


@dataclass
class StructuredResponse:
    data: dict[str, Any]
    input_tokens: int | None = None
    output_tokens: int | None = None
    model: str | None = None
    provider_request_id: str | None = None


class LLMClient(Protocol):
    def generate_structured(self, *, prompt_version: str, system_prompt: str, user_prompt: str) -> StructuredResponse: ...


class ProviderLLMClient:
    """Provider adapter; pipeline code never imports an SDK directly."""

    def generate_structured(self, *, prompt_version: str, system_prompt: str, user_prompt: str) -> StructuredResponse:
        if settings.llm_provider == "mock":
            return self._mock_response(system_prompt)
        if settings.llm_provider == "openai":
            from openai import OpenAI

            client = OpenAI(api_key=settings.openai_api_key)
            response = client.chat.completions.create(
                model=settings.openai_model,
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                timeout=settings.llm_timeout_seconds,
            )
            usage = response.usage
            return StructuredResponse(
                data=__import__("json").loads(response.choices[0].message.content),
                input_tokens=getattr(usage, "prompt_tokens", None),
                output_tokens=getattr(usage, "completion_tokens", None),
                model=response.model,
                provider_request_id=response.id,
            )
        raise RuntimeError(f"Unsupported or unconfigured LLM provider: {settings.llm_provider}")

    @staticmethod
    def _mock_response(system_prompt: str) -> StructuredResponse:
        """Deterministic local provider for offline integration tests and demos."""
        import json

        module = next(name for name in ("summary", "entities", "claims", "relationships", "learning_objectives") if name in system_prompt)
        payloads = {
            "summary": {"summary": "Local mock summary.", "key_points": ["Mock mode is active."]},
            "entities": {"entities": [{"entity_id": "mock-e1", "name": "Document", "entity_type": "concept", "description": "The uploaded document.", "source_chunk_ids": []}]},
            "claims": {"claims": [{"claim_id": "mock-c1", "text": "The document contains educational content.", "source_chunk_ids": []}]},
            "relationships": {"relationships": []},
            "learning_objectives": {"prerequisites": [], "learning_objectives": ["Summarize the document."]},
        }
        return StructuredResponse(data=json.loads(json.dumps(payloads[module])), model="mock", provider_request_id="local-mock")
