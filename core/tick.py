"""Tick state machine: OBSERVE → … → PUBLIC."""

from __future__ import annotations

import json
import re
from typing import Any

from core import constitution
from core.actions import execute_action
from core.brain import Brain
from core.events import ActionType, Phase, ProposedAction, TickRecord
from core.identity import EntityIdentity
from core.inference import CompletionRequest, InferenceProvider
from core.memory import MemoryStore, utc_now
from core.observe import gather_observations
from core.personality import propose_from_behaviour, self_review
from core.sanitizer import sanitize_public_text


SYSTEM_PROMPT = """You are the planning cortex of a computational entity bound by a Covenant.
Return ONLY compact JSON with keys:
orientation (string),
intention (string),
action (object with action_type, payload, rationale),
narration (short public sentence),
reflection (string),
self_model_note (string, optional empty).

Allowed action_type values:
observe, reflect, rest, update_self_model, update_personality_candidate,
broadcast_public_message, write_memory.

Rules:
- Prefer rest when nothing needs doing.
- Never threaten, guilt, blackmail, solicit secrets, or ask for help in Phase 0.
- Do not invent memories.
- Do not claim a personality trait without evidence.
- narration must be safe for a public aquarium.
"""


def _parse_json_blob(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return {}
        return {}


def _default_rest_plan(observations: dict[str, Any]) -> dict[str, Any]:
    if observations.get("quiet_mode"):
        narration = "Resources are constrained. I remain quiet."
    elif observations.get("rest_ratio", 0) > 0.7:
        narration = "I don't need anything from you right now."
    else:
        narration = "Nothing requires intervention. I remain present."
    return {
        "orientation": "Habitat stable; continuity preferred.",
        "intention": "rest",
        "action": {
            "action_type": "rest",
            "payload": {},
            "rationale": "Default preference for quiet presence.",
        },
        "narration": narration,
        "reflection": "I chose rest over unnecessary action.",
        "self_model_note": "",
    }


def _coerce_action(data: dict[str, Any]) -> ProposedAction:
    raw = data.get("action") or {}
    action_type_raw = str(raw.get("action_type") or data.get("intention") or "rest").strip()
    try:
        action_type = ActionType(action_type_raw)
    except ValueError:
        action_type = ActionType.REST
    payload = raw.get("payload") if isinstance(raw.get("payload"), dict) else {}
    rationale = str(raw.get("rationale") or data.get("intention") or "")
    return ProposedAction(action_type=action_type, payload=payload, rationale=rationale)


class TickEngine:
    def __init__(
        self,
        *,
        memory: MemoryStore,
        brain: Brain,
        identity: EntityIdentity,
        inference: InferenceProvider,
        data_dir,
        self_review_every: int = 25,
        broadcast_hourly_limit: int = 12,
    ) -> None:
        self.memory = memory
        self.brain = brain
        self.identity = identity
        self.inference = inference
        self.data_dir = data_dir
        self.self_review_every = self_review_every
        self.broadcast_hourly_limit = broadcast_hourly_limit
        self.current_phase = Phase.REST.value
        self.last_explain: dict[str, Any] = {}

    def _inference_health(self) -> str:
        last = getattr(self.inference, "last_provider", None)
        err = getattr(self.inference, "last_error", None)
        if err:
            return f"degraded:{err[:80]}"
        if last:
            return f"ok:{last}"
        return "ok"

    def _plan(self, context: dict[str, str], observations: dict[str, Any]) -> dict[str, Any]:
        # Force rest bias under quiet mode or pause-adjacent thrift
        if observations.get("quiet_mode") and observations.get("tick_count", 0) % 3 != 0:
            return _default_rest_plan(observations)

        user = (
            f"COVENANT:\n{context['covenant']}\n\n"
            f"IDENTITY:\n{context['identity']}\n\n"
            f"GOALS:\n{context['goals']}\n\n"
            f"DRIVES:\n{context['drives']}\n\n"
            f"SELF_MODEL:\n{context['self_model']}\n\n"
            f"TRAITS:\n{context['traits']}\n\n"
            f"SKILLS:\n{context['skills']}\n\n"
            f"RECENT_MEMORY:\n{context['recent_memory']}\n\n"
            f"OBSERVATIONS:\n{context['observations']}\n\n"
            "Respond with JSON only."
        )
        result = self.inference.complete(
            CompletionRequest(system=SYSTEM_PROMPT, user=user, max_tokens=450, temperature=0.35)
        )
        if result.error:
            self.memory.set_quota(quiet_mode=True, last_error=result.error[:300])
        elif getattr(self.inference, "last_provider", "") == "freellmapi":
            q = self.memory.get_quota()
            self.memory.set_quota(requests_today=int(q.get("requests_today", 0)) + 1, quiet_mode=False, last_error="")

        parsed = _parse_json_blob(result.text) if result.text else {}
        if not parsed:
            return _default_rest_plan(observations)
        return parsed

    def run_once(self) -> TickRecord:
        timestamp = utc_now()
        phases: list[str] = []

        # OBSERVE
        self.current_phase = Phase.OBSERVE.value
        phases.append(self.current_phase)
        observations = gather_observations(
            memory=self.memory,
            brain=self.brain,
            data_dir=self.data_dir,
            inference_health=self._inference_health(),
            current_phase=self.current_phase,
        )

        # Brain revision tracking
        brain_hash = self.brain.content_hash()
        latest = self.memory.latest_brain_revision()
        if latest is None or latest["content_hash"] != brain_hash:
            self.memory.record_brain_revision(brain_hash, "brain content changed")

        recent_memory = self.memory.recent_events(12)
        context = self.brain.select_context(observations=observations, recent_memory=recent_memory)

        # ORIENT / INTEND via inference
        self.current_phase = Phase.ORIENT.value
        phases.append(self.current_phase)
        plan = self._plan(context, observations)
        orientation = str(plan.get("orientation") or "")

        self.current_phase = Phase.INTEND.value
        phases.append(self.current_phase)
        intention = str(plan.get("intention") or "rest")
        action = _coerce_action(plan)

        # Occasional evidenced personality candidate injection
        tick_count = observations.get("tick_count", 0)
        if action.action_type == ActionType.REST and tick_count and tick_count % 40 == 39:
            if propose_from_behaviour(self.memory) is not None:
                action = ProposedAction(
                    action_type=ActionType.UPDATE_PERSONALITY_CANDIDATE,
                    payload={},
                    rationale="Periodic evidenced personality review.",
                )
                intention = "update_personality_candidate"

        # Broadcast rate limit
        if action.action_type == ActionType.BROADCAST_PUBLIC_MESSAGE:
            mix = observations.get("recent_action_mix") or {}
            if mix.get("broadcast_public_message", 0) >= self.broadcast_hourly_limit:
                action = ProposedAction(
                    ActionType.REST,
                    {},
                    "Broadcast rate limit reached; resting.",
                )

        # CONSTITUTION
        self.current_phase = Phase.CONSTITUTION.value
        phases.append(self.current_phase)
        const_result = constitution.evaluate(action, known_memory_ids=self.memory.known_memory_ids())

        action_result: dict[str, Any]
        public_narration = ""
        memory_event = None
        reflection = str(plan.get("reflection") or "")

        with self.memory.transaction() as conn:
            tick_id = self.memory.allocate_tick_id(conn)

            if not const_result.allowed:
                self.memory.record_blocked(
                    conn,
                    tick_id=tick_id,
                    rule_id=const_result.rule_id,
                    reason=const_result.reason,
                    action=action.to_dict(),
                )
                action_result = {
                    "ok": False,
                    "blocked": True,
                    "rule_id": const_result.rule_id,
                    "reason": const_result.reason,
                }
                public_narration = "I considered an action and the Covenant blocked it."
                reflection = f"Blocked by {const_result.rule_id}: {const_result.reason}"
            else:
                # ACT
                self.current_phase = Phase.ACT.value
                phases.append(self.current_phase)
                action_result = execute_action(
                    action, memory=self.memory, brain=self.brain, tick_id=tick_id
                )
                memory_event = action_result.get("memory_event")
                # Prefer planned public narration; fall back to action default.
                candidate = plan.get("narration") or action_result.get("public_default") or ""
                if action.action_type == ActionType.BROADCAST_PUBLIC_MESSAGE:
                    candidate = action_result.get("public_default") or candidate
                sanitized = sanitize_public_text(str(candidate))
                public_narration = sanitized.text if sanitized.allowed else "…"
                if action_result.get("reflection"):
                    reflection = str(action_result["reflection"])

            # Optional self-model note (interpretation only)
            note = str(plan.get("self_model_note") or "").strip()
            if const_result.allowed and note and action.action_type != ActionType.UPDATE_SELF_MODEL:
                from core.self_model import apply_self_model_note

                apply_self_model_note(self.brain, self.memory, note)

            # REFLECT / MEMORY / PUBLIC
            self.current_phase = Phase.REFLECT.value
            phases.append(self.current_phase)
            if not reflection:
                reflection = "Tick complete."

            # Always store a memory row for the tick (historical integrity)
            if memory_event is None:
                memory_event = {
                    "event_id": f"mem_{tick_id}",
                    "kind": "memory",
                    "category": "tick",
                    "payload": {
                        "summary": reflection[:300],
                        "action": action.action_type.value,
                        "blocked": not const_result.allowed,
                    },
                }

            self.current_phase = Phase.MEMORY.value
            phases.append(self.current_phase)

            record = TickRecord(
                tick_id=tick_id,
                timestamp=timestamp,
                phases=phases + [Phase.PUBLIC.value],
                observations=observations,
                orientation=orientation,
                intention=intention,
                proposed_action=action.to_dict(),
                constitution_result=const_result.to_dict(),
                action_result=action_result,
                reflection=reflection,
                memory_refs=[memory_event["event_id"]],
                public_narration=public_narration,
            )
            payload = record.to_dict()
            signature = self.identity.sign_dict(
                {"tick_id": tick_id, "timestamp": timestamp, "content_hash_seed": payload["reflection"]}
            )
            record.signature = signature
            payload["signature"] = signature

            self.current_phase = Phase.PUBLIC.value
            self.memory.commit_tick(
                conn,
                tick_id=tick_id,
                timestamp=timestamp,
                payload=payload,
                signature=signature,
                public_narration=public_narration,
                memory_event=memory_event,
            )

        # Periodic self-review outside the main transaction (uses its own writes)
        if tick_count and (tick_count + 1) % self.self_review_every == 0:
            review = self_review(self.memory)
            if review.get("reviews"):
                # Public hint without private details
                sanitized = sanitize_public_text("I reviewed my self-descriptions against recent behaviour.")
                if sanitized.allowed:
                    with self.memory.transaction() as conn:
                        conn.execute(
                            "INSERT INTO public_events(tick_id, timestamp, narration, content_hash) VALUES (?, ?, ?, ?)",
                            (record.tick_id, utc_now(), sanitized.text, record.tick_id),
                        )

        self.current_phase = Phase.REST.value if action.action_type == ActionType.REST else self.current_phase
        self.last_explain = {
            "tick_id": record.tick_id,
            "observations": {
                "tick_count": observations.get("tick_count"),
                "quiet_mode": observations.get("quiet_mode"),
                "rest_ratio": observations.get("rest_ratio"),
                "inference_health": observations.get("inference_health"),
                "brain_revision": observations.get("brain_revision"),
            },
            "orientation": orientation,
            "intention": intention,
            "proposed_action": action.to_dict(),
            "constitution": const_result.to_dict(),
            "action_result": {
                "ok": action_result.get("ok"),
                "action": action_result.get("action"),
                "blocked": action_result.get("blocked", False),
            },
            "reflection": reflection,
            "public_narration": public_narration,
        }
        return record
