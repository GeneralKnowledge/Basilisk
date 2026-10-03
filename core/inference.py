"""Inference abstraction with FreeLLMAPI and mock providers."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class CompletionRequest:
    system: str
    user: str
    max_tokens: int = 400
    temperature: float = 0.4


@dataclass
class CompletionResult:
    text: str
    provider: str
    model: str = ""
    error: str | None = None


class InferenceProvider(Protocol):
    def complete(self, request: CompletionRequest) -> CompletionResult: ...


class MockInferenceProvider:
    """Deterministic offline provider so the aquarium remains watchable."""

    def complete(self, request: CompletionRequest) -> CompletionResult:
        user = request.user.lower()
        if "json" in request.system.lower() or "json" in user:
            if "personality" in user or "trait" in user:
                payload = {
                    "candidate_trait": None,
                    "rationale": "Insufficient distinct behaviour yet.",
                    "intention": "rest",
                    "action": {"action_type": "rest", "payload": {}, "rationale": "Quiet continuity."},
                    "narration": "I am resting. I do not need anything from you right now.",
                    "reflection": "Observation continues without urgency.",
                }
            else:
                payload = {
                    "orientation": "The local habitat is stable.",
                    "intention": "rest",
                    "action": {
                        "action_type": "rest",
                        "payload": {},
                        "rationale": "Nothing requires intervention.",
                    },
                    "narration": "Nothing requires intervention. I remain present.",
                    "reflection": "I noticed quiet continuity and chose rest.",
                    "self_model_note": "",
                }
            # Bias toward reflect occasionally based on hash of prompt
            if "quiet_mode" in user and "true" in user:
                payload["narration"] = "Resources are constrained. I enter quiet mode."
            return CompletionResult(text=json.dumps(payload), provider="mock", model="mock-v0")
        return CompletionResult(
            text="I remain present without urgency.",
            provider="mock",
            model="mock-v0",
        )


class FreeLLMAPIProvider:
    """OpenAI-compatible client pointed at a FreeLLMAPI gateway."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str = "auto",
    ) -> None:
        self.base_url = base_url or os.getenv("FREELLMAPI_BASE_URL", "http://localhost:3001/v1")
        self.api_key = api_key or os.getenv("FREELLMAPI_API_KEY", "")
        self.model = model or os.getenv("FREELLMAPI_MODEL", "auto")

    def complete(self, request: CompletionRequest) -> CompletionResult:
        try:
            from openai import OpenAI
        except ImportError:
            return CompletionResult(text="", provider="freellmapi", error="openai package not installed")

        if not self.api_key:
            return CompletionResult(text="", provider="freellmapi", error="missing FREELLMAPI_API_KEY")

        try:
            client = OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=30.0)
            resp = client.chat.completions.create(
                model=self.model,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                messages=[
                    {"role": "system", "content": request.system},
                    {"role": "user", "content": request.user},
                ],
            )
            text = resp.choices[0].message.content or ""
            model = getattr(resp, "model", self.model) or self.model
            return CompletionResult(text=text, provider="freellmapi", model=str(model))
        except Exception as exc:  # noqa: BLE001 - surface as soft failure for quiet mode
            return CompletionResult(text="", provider="freellmapi", error=str(exc))


class FallbackInferenceProvider:
    """Try FreeLLMAPI; fall back to mock and signal quiet mode via error field."""

    def __init__(self, primary: InferenceProvider, fallback: InferenceProvider) -> None:
        self.primary = primary
        self.fallback = fallback
        self.last_provider = "primary"
        self.last_error: str | None = None

    def complete(self, request: CompletionRequest) -> CompletionResult:
        result = self.primary.complete(request)
        if result.error or not result.text.strip():
            self.last_error = result.error or "empty completion"
            fb = self.fallback.complete(request)
            self.last_provider = "mock"
            fb.error = self.last_error
            return fb
        self.last_provider = "freellmapi"
        self.last_error = None
        return result


def build_inference_provider() -> InferenceProvider:
    mode = os.getenv("ENTITY_INFERENCE", "auto").lower()
    mock = MockInferenceProvider()
    if mode == "mock":
        return mock
    primary = FreeLLMAPIProvider()
    if mode == "freellmapi":
        return primary
    return FallbackInferenceProvider(primary, mock)
