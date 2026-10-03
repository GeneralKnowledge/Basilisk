"""Local observation sensors for Phase 0 (no Discord/Twitch yet)."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.brain import Brain
from core.memory import MemoryStore


def gather_observations(
    *,
    memory: MemoryStore,
    brain: Brain,
    data_dir: Path,
    inference_health: str,
    current_phase: str = "OBSERVE",
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    birth = memory.get_meta("birth_timestamp")
    age_seconds = None
    if birth:
        try:
            born = datetime.fromisoformat(birth)
            age_seconds = int((now - born).total_seconds())
        except ValueError:
            age_seconds = None

    pause_file = data_dir / "PAUSE"
    action_counts = memory.action_counts(80)
    total_recent = sum(action_counts.values()) or 1
    rest_ratio = action_counts.get("rest", 0) / total_recent
    broadcast_ratio = action_counts.get("broadcast_public_message", 0) / total_recent

    quota = memory.get_quota()
    brain_rev = memory.latest_brain_revision()
    last_tick = memory.latest_tick()
    last_self_review = memory.get_meta("last_self_review_tick")

    return {
        "timestamp": now.isoformat(),
        "local_hour_utc": now.hour,
        "phase": current_phase,
        "tick_count": memory.tick_count(),
        "age_seconds": age_seconds,
        "brain_hash": brain.content_hash()[:16],
        "brain_revision": brain_rev["revision"] if brain_rev else 0,
        "inference_health": inference_health,
        "quiet_mode": bool(quota.get("quiet_mode")),
        "requests_today": quota.get("requests_today", 0),
        "paused": pause_file.exists(),
        "process_uptime_seconds": int(time.time() - float(memory.get_meta("process_started_at", str(time.time())) or time.time())),
        "recent_action_mix": action_counts,
        "rest_ratio": round(rest_ratio, 3),
        "broadcast_ratio": round(broadcast_ratio, 3),
        "last_tick_id": last_tick["tick_id"] if last_tick else None,
        "last_self_review_tick": last_self_review,
        "open_help_requests": len(memory.open_help_requests()),
        "host": os.uname().nodename if hasattr(os, "uname") else "unknown",
    }
