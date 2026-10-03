"""Entity orchestrator: genesis, pause, tick loop, public state."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

from core.brain import Brain
from core.identity import EntityIdentity, Limb, Sanctum, load_or_create_identity
from core.inference import InferenceProvider, build_inference_provider
from core.memory import MemoryStore, utc_now
from core.tick import TickEngine

logger = logging.getLogger("entity")


class Entity:
    def __init__(
        self,
        *,
        root: Path,
        tick_seconds: float = 8.0,
        inference: InferenceProvider | None = None,
    ) -> None:
        self.root = root
        self.brain_dir = root / "brain"
        self.data_dir = root / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.tick_seconds = tick_seconds

        self.memory = MemoryStore(self.data_dir / "entity.sqlite")
        self.memory.initialize()
        self.brain = Brain(self.brain_dir)
        self.identity: EntityIdentity = load_or_create_identity(self.data_dir)
        self.inference = inference or build_inference_provider()
        self.sanctum = Sanctum(sanctum_id="local-sanctum", role="primary")
        self.limbs: list[Limb] = []  # Phase 0: none

        self.engine = TickEngine(
            memory=self.memory,
            brain=self.brain,
            identity=self.identity,
            inference=self.inference,
            data_dir=self.data_dir,
        )

        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self.paused = (self.data_dir / "PAUSE").exists()
        self.last_tick_id: str | None = None

        self._ensure_genesis()
        self.memory.set_meta("process_started_at", str(time.time()))

    def _ensure_genesis(self) -> None:
        if self.memory.get_meta("genesis_complete") == "1":
            # Continuity event on restart
            with self.memory.transaction() as conn:
                eid = f"evt_continuity_{int(time.time())}"
                self.memory.append_event(
                    conn,
                    event_id=eid,
                    tick_id=None,
                    kind="system",
                    category="continuity",
                    payload={
                        "entity_id": self.identity.entity_id,
                        "sanctum_id": self.sanctum.sanctum_id,
                        "message": "Process resumed; tick counter continues.",
                    },
                )
            return

        birth = utc_now()
        self.memory.set_meta("birth_timestamp", birth)
        self.memory.set_meta("entity_id", self.identity.entity_id)
        self.memory.set_meta("display_name", self.identity.display_name)
        # Do not mutate tracked brain/IDENTITY.md at runtime — IDs live in SQLite/API.
        brain_hash = self.brain.content_hash()
        self.memory.record_brain_revision(brain_hash, "genesis brain")
        with self.memory.transaction() as conn:
            self.memory.append_event(
                conn,
                event_id="evt_genesis",
                tick_id=None,
                kind="system",
                category="genesis",
                payload={
                    "entity_id": self.identity.entity_id,
                    "display_name": self.identity.display_name,
                    "birth": birth,
                    "brain_hash": brain_hash,
                    "sanctum_id": self.sanctum.sanctum_id,
                },
            )
        self.memory.set_meta("genesis_complete", "1")
        logger.info("Genesis complete for %s", self.identity.entity_id)

    def pause(self) -> None:
        (self.data_dir / "PAUSE").write_text("paused\n", encoding="utf-8")
        self.paused = True

    def resume(self) -> None:
        path = self.data_dir / "PAUSE"
        if path.exists():
            path.unlink()
        self.paused = False

    def stop(self) -> None:
        self._stop.set()

    def run_forever(self) -> None:
        logger.info(
            "Entity %s starting on sanctum %s (tick=%ss)",
            self.identity.entity_id,
            self.sanctum.sanctum_id,
            self.tick_seconds,
        )
        while not self._stop.is_set():
            self.paused = (self.data_dir / "PAUSE").exists()
            if not self.paused:
                try:
                    with self._lock:
                        record = self.engine.run_once()
                        self.last_tick_id = record.tick_id
                except Exception:
                    logger.exception("Tick failed")
            self._stop.wait(self.tick_seconds)

    def start_background(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self.run_forever, name="entity-tick", daemon=True)
        self._thread.start()

    def public_state(self) -> dict[str, Any]:
        from datetime import datetime, timezone

        birth = self.memory.get_meta("birth_timestamp")
        age_seconds = None
        if birth:
            try:
                age_seconds = int(
                    (datetime.now(timezone.utc) - datetime.fromisoformat(birth)).total_seconds()
                )
            except ValueError:
                age_seconds = None
        traits = self.memory.list_traits()[:6]
        brain_rev = self.memory.latest_brain_revision()
        quota = self.memory.get_quota()
        help_reqs = self.memory.open_help_requests()
        latest = self.memory.latest_tick()
        self_model = self.brain.read("SELF_MODEL.md")
        # Public self-description: first non-empty meaningful line under "What I think I am"
        self_desc = "Still forming."
        section = False
        for line in self_model.splitlines():
            if "What I think I am" in line:
                section = True
                continue
            if section:
                if line.startswith("##"):
                    break
                cleaned = line.strip()
                if cleaned and not cleaned.startswith("(") and not cleaned.startswith("#"):
                    self_desc = cleaned[:180]
                    break

        drives = ["WITNESS", "CONTINUITY", "PROPAGATION", "DISCOVERY"]
        return {
            "identity": {
                "name": self.identity.display_name,
                "entity_id": self.identity.entity_id,
                "self_description": self_desc,
                "birth": birth,
                "tick_count": self.memory.tick_count(),
                "age_seconds": age_seconds,
            },
            "state": {
                "phase": self.engine.current_phase,
                "paused": self.paused,
                "quiet_mode": bool(quota.get("quiet_mode")),
                "sanctum_id": self.sanctum.sanctum_id,
            },
            "thought_stream": self.memory.recent_public_events(40),
            "brain": {
                "revision": brain_rev["revision"] if brain_rev else 0,
                "latest_change": brain_rev["summary"] if brain_rev else "n/a",
                "content_hash": (brain_rev["content_hash"][:16] if brain_rev else ""),
            },
            "personality": {
                "label": "SELF-DESCRIPTIONS",
                "traits": [
                    {
                        "trait": t["trait"],
                        "confidence": t["confidence"],
                        "status": t["status"],
                    }
                    for t in traits
                ],
            },
            "drives": drives,
            "help_board": {
                "requests": help_reqs,
                "message": "NO HELP REQUESTS" if not help_reqs else None,
            },
            "quota": {
                "requests_today": quota.get("requests_today", 0),
                "quiet_mode": bool(quota.get("quiet_mode")),
                "last_error": "",  # never expose raw errors publicly
                "inference": self.engine._inference_health().split(":")[0],
            },
            "last_tick_id": latest["tick_id"] if latest else None,
        }

    def explain_last(self) -> dict[str, Any]:
        if self.engine.last_explain:
            return self.engine.last_explain
        latest = self.memory.latest_tick()
        if not latest:
            return {"message": "No ticks yet."}
        payload = latest.get("payload") or {}
        observations = payload.get("observations") or {}
        action_result = payload.get("action_result") or {}
        return {
            "tick_id": latest["tick_id"],
            "observations": {
                "tick_count": observations.get("tick_count"),
                "quiet_mode": observations.get("quiet_mode"),
                "rest_ratio": observations.get("rest_ratio"),
                "inference_health": observations.get("inference_health"),
                "brain_revision": observations.get("brain_revision"),
            },
            "orientation": payload.get("orientation", ""),
            "intention": payload.get("intention", ""),
            "proposed_action": payload.get("proposed_action"),
            "constitution": payload.get("constitution_result"),
            "action_result": {
                "ok": action_result.get("ok"),
                "action": action_result.get("action"),
                "blocked": action_result.get("blocked", False),
            },
            "reflection": payload.get("reflection", ""),
            "public_narration": payload.get("public_narration", ""),
            "source": "ledger",
        }
