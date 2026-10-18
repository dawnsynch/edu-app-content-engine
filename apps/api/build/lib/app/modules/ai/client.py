import json
from decimal import Decimal, InvalidOperation
from time import monotonic
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.settings import Settings
from app.modules.ai.errors import PermanentAIError, TransientAIError
from app.modules.ai.prompts import SYSTEM_PROMPT, content_prompt
from app.modules.ai.schemas import (
    AnalysisResult,
    EmbeddingResult,
    EnrichmentDecision,
    ModelUsage,
)


class LiteLLMClient:
    """OpenAI-compatible client whose only upstream is the LiteLLM gateway."""

    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    @property
    def headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.settings.litellm_master_key:
            headers["Authorization"] = f"Bearer {self.settings.litellm_master_key}"
        return headers

    async def analyze(self, payload: dict[str, object]) -> AnalysisResult:
        body = {
            "model": self.settings.litellm_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content_prompt(payload)},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "edu_content_enrichment",
                    "strict": True,
                    "schema": EnrichmentDecision.model_json_schema(),
                },
            },
        }
        response, latency_ms = await self._post("/v1/chat/completions", body)
        data = self._json_object(response)
        try:
            choices = data["choices"]
            content = choices[0]["message"]["content"]
            if not isinstance(content, str):
                raise TypeError("message content is not text")
            decision = EnrichmentDecision.model_validate(json.loads(content))
        except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as exc:
            raise PermanentAIError("LiteLLM returned invalid structured enrichment output") from exc
        return AnalysisResult(
            decision=decision,
            usage=self._usage(response, data, self.settings.litellm_model, latency_ms),
        )

    async def embed(self, text: str) -> EmbeddingResult:
        body = {"model": self.settings.litellm_embedding_model, "input": text}
        response, latency_ms = await self._post("/v1/embeddings", body)
        data = self._json_object(response)
        try:
            vector = data["data"][0]["embedding"]
            if not isinstance(vector, list) or not vector:
                raise TypeError("embedding is empty")
            typed_vector = [float(value) for value in vector]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise PermanentAIError("LiteLLM returned an invalid embedding") from exc
        return EmbeddingResult(
            vector=typed_vector,
            usage=self._usage(
                response,
                data,
                self.settings.litellm_embedding_model,
                latency_ms,
            ),
        )

    async def _post(self, path: str, body: dict[str, Any]) -> tuple[httpx.Response, int]:
        started = monotonic()
        try:
            response = await self.client.post(
                f"{self.settings.litellm_base_url.rstrip('/')}{path}",
                headers=self.headers,
                json=body,
                timeout=self.settings.ai_http_timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise TransientAIError("LiteLLM request failed") from exc
        latency_ms = int((monotonic() - started) * 1000)
        if response.status_code == 429 or response.status_code >= 500:
            raise TransientAIError(f"LiteLLM returned HTTP {response.status_code}")
        if response.status_code >= 400:
            raise PermanentAIError(f"LiteLLM returned HTTP {response.status_code}")
        return response, latency_ms

    @staticmethod
    def _json_object(response: httpx.Response) -> dict[str, Any]:
        try:
            data: Any = response.json()
        except ValueError as exc:
            raise PermanentAIError("LiteLLM returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise PermanentAIError("LiteLLM response must be a JSON object")
        return data

    @staticmethod
    def _usage(
        response: httpx.Response,
        data: dict[str, Any],
        model_alias: str,
        latency_ms: int,
    ) -> ModelUsage:
        raw_usage = data.get("usage")
        usage: dict[str, Any] = raw_usage if isinstance(raw_usage, dict) else {}
        input_tokens = int(usage.get("prompt_tokens", 0))
        output_tokens = int(usage.get("completion_tokens", 0))
        total_tokens = int(usage.get("total_tokens", input_tokens + output_tokens))
        cost_value: object = response.headers.get("x-litellm-response-cost")
        hidden = data.get("_hidden_params")
        if cost_value is None and isinstance(hidden, dict):
            cost_value = hidden.get("response_cost")
        cost = None
        if cost_value not in (None, ""):
            try:
                cost = Decimal(str(cost_value))
            except InvalidOperation:
                cost = None
        request_id = data.get("id")
        return ModelUsage(
            model_alias=model_alias,
            provider_request_id=request_id if isinstance(request_id, str) else None,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
        )
