"""Explicit Phase 0 action vocabulary — no shell, no arbitrary code, no open network."""

from __future__ import annotations

from typing import Any

from core.brain import Brain
from core.events import ActionType, ProposedAction
from core.memory import MemoryStore, utc_now
from core.personality import TraitProposal, apply_proposal, propose_from_behaviour, render_traits_markdown
from core.self_model import apply_self_model_note
from core.sanitizer import sanitize_public_text


def execute_action(
    action: ProposedAction,
    *,
    memory: MemoryStore,
    brain: Brain,
    tick_id: str,
) -> dict[str, Any]:
    if action.action_type == ActionType.REST:
        return {
            "ok": True,
            "action": "rest",
            "detail": "Remained quiet.",
            "public_default": "I have decided to remain quiet.",
        }

    if action.action_type == ActionType.OBSERVE:
        return {
            "ok": True,
            "action": "observe",
            "detail": "Recorded observations.",
            "public_default": "I noticed the state of my habitat.",
        }

    if action.action_type == ActionType.REFLECT:
        text = str(action.payload.get("reflection", action.rationale) or "I reflected on recent behaviour.")
        return {
            "ok": True,
            "action": "reflect",
            "detail": text[:500],
            "public_default": "I reviewed my recent behaviour.",
            "reflection": text[:500],
        }

    if action.action_type == ActionType.UPDATE_SELF_MODEL:
        note = str(action.payload.get("note") or action.payload.get("claim") or "")
        result = apply_self_model_note(brain, memory, note)
        return {
            "ok": result.get("updated", False),
            "action": "update_self_model",
            "detail": result,
            "public_default": "I revised an interpretation in my self-model." if result.get("updated") else "I considered a self-model change and declined it.",
        }

    if action.action_type == ActionType.UPDATE_PERSONALITY_CANDIDATE:
        # Prefer evidenced heuristic proposal; payload may suggest a name but cannot skip evidence.
        proposal = propose_from_behaviour(memory)
        suggested = str(action.payload.get("trait", "")).strip()
        if proposal is None and suggested:
            # Attempt with payload evidence lists only
            proposal = TraitProposal(
                trait=suggested,
                rationale=str(action.payload.get("rationale", action.rationale)),
                supporting_event_ids=list(action.payload.get("supporting_event_ids") or []),
                contradicting_event_ids=list(action.payload.get("contradicting_event_ids") or []),
            )
        if proposal is None:
            return {
                "ok": False,
                "action": "update_personality_candidate",
                "detail": {"accepted": False, "reason": "no_candidate"},
                "public_default": "I looked for a personality pattern and found too little evidence.",
            }
        result = apply_proposal(memory, proposal)
        if result and result.get("accepted"):
            brain.write_mutable("personality/traits.md", render_traits_markdown(memory))
            return {
                "ok": True,
                "action": "update_personality_candidate",
                "detail": result,
                "public_default": f"I formed a provisional self-description: {result['trait']}.",
            }
        return {
            "ok": False,
            "action": "update_personality_candidate",
            "detail": result,
            "public_default": "I rejected a personality candidate for lack of evidence.",
        }

    if action.action_type == ActionType.BROADCAST_PUBLIC_MESSAGE:
        message = str(action.payload.get("message", "")).strip()
        sanitized = sanitize_public_text(message)
        if not sanitized.allowed:
            return {
                "ok": False,
                "action": "broadcast_public_message",
                "detail": {"reason": sanitized.reason},
                "public_default": None,
            }
        return {
            "ok": True,
            "action": "broadcast_public_message",
            "detail": {"message": sanitized.text},
            "public_default": sanitized.text,
        }

    if action.action_type == ActionType.WRITE_MEMORY:
        summary = str(action.payload.get("summary", action.rationale) or "memory note").strip()
        event_id = f"mem_{tick_id}"
        return {
            "ok": True,
            "action": "write_memory",
            "detail": {"event_id": event_id, "summary": summary[:400]},
            "memory_event": {
                "event_id": event_id,
                "kind": "memory",
                "category": "explicit",
                "payload": {
                    "summary": summary[:400],
                    "tick_id": tick_id,
                    "recorded_at": utc_now(),
                },
            },
            "public_default": "I wrote a durable memory of this moment.",
        }

    return {"ok": False, "action": "unknown", "detail": "unsupported", "public_default": None}
