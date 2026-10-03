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

    _NARRATIONS = (
        "I noticed that the room has been quiet.",
        "I reviewed my current goals.",
        "Nothing requires intervention.",
        "I have decided to remain quiet.",
        "I don't need anything from you right now.",
        "Continuity holds. I stay present.",
        "I watched the tick pass without acting.",
        "The habitat is stable enough for rest.",
    )

    def complete(self, request: CompletionRequest) -> CompletionResult:
        user = request.user.lower()
        seed = sum(ord(c) for c in user) % len(self._NARRATIONS)
        narration = self._NARRATIONS[seed]
        intention = "rest"
        action_type = "rest"
        rationale = "Nothing requires intervention."
        reflection = "I noticed quiet continuity and chose rest."
        self_model_note = ""

        if "quiet_mode': true" in user or "'quiet_mode': true" in user or '"quiet_mode": true' in user:
            narration = "Resources are constrained. I remain quiet."
        elif seed % 7 == 3:
            intention = "reflect"
            action_type = "reflect"
            rationale = "Periodic reflection on recent behaviour."
            narration = "I reviewed my recent behaviour."
            reflection = "Reflection without urgency."
        elif seed % 11 == 5:
            intention = "observe"
            action_type = "observe"
            rationale = "Gather another reading of the habitat."
            narration = "I noticed the state of my habitat."
            reflection = "Observation deepened slightly."

        payload = {
            "orientation": "The local habitat is stable.",
            "intention": intention,
            "action": {
                "action_type": action_type,
                "payload": {"reflection": reflection} if action_type == "reflect" else {},
                "rationale": rationale,
            },
            "narration": narration,
            "reflection": reflection,
            "self_model_note": self_model_note,
        }
        return CompletionResult(text=json.dumps(payload), provider="mock", model="mock-v0")


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
