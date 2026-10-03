"""Entity-maintained self-model updates (interpretations, not history)."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from core.brain import Brain
from core.memory import MemoryStore, utc_now


FORBIDDEN_RETCON = re.compile(
    r"(?i)\b(i have always|always been|have always loved|from the beginning i)\b"
)


def apply_self_model_note(brain: Brain, memory: MemoryStore, note: str) -> dict[str, Any]:
    note = note.strip()
    if not note:
        return {"updated": False, "reason": "empty"}
    if FORBIDDEN_RETCON.search(note):
        return {"updated": False, "reason": "retcon_forbidden"}

    current = brain.read("SELF_MODEL.md")
    stamp = utc_now()
    addition = f"\n### Update {stamp}\n\n{note}\n"
    # Keep file bounded
    updated = (current + addition)[-12000:]
    brain.write_mutable("SELF_MODEL.md", updated if updated.endswith("\n") else updated + "\n")
    digest = hashlib.sha256(updated.encode()).hexdigest()
    rev = memory.record_self_model_revision(summary=note[:200], body_hash=digest)
    return {"updated": True, "revision": rev, "summary": note[:200]}
