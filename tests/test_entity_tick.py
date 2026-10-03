from __future__ import annotations

import shutil
from pathlib import Path

from core.entity import Entity
from core.inference import MockInferenceProvider


ROOT = Path(__file__).resolve().parents[1]


def _seed_entity(tmp_path: Path) -> Entity:
    brain_src = ROOT / "brain"
    brain_dst = tmp_path / "brain"
    shutil.copytree(brain_src, brain_dst)
    entity = Entity(
        root=tmp_path,
        tick_seconds=0.01,
        inference=MockInferenceProvider(),
    )
    return entity


def test_tick_state_machine_and_public_boundary(tmp_path):
    entity = _seed_entity(tmp_path)
    record = entity.engine.run_once()
    assert record.tick_id.startswith("tick_")
    assert "OBSERVE" in record.phases
    assert "CONSTITUTION" in record.phases
    assert "PUBLIC" in record.phases
    assert record.signature

    state = entity.public_state()
    blob = str(state)
    assert "FREELLMAPI" not in blob
    assert "private prompt" not in blob.lower()
    assert "payload_json" not in blob
    # private memory bodies not exposed
    assert "recent_events" not in state
    assert "thought_stream" in state


def test_pause_file(tmp_path):
    entity = _seed_entity(tmp_path)
    entity.pause()
    assert (tmp_path / "data" / "PAUSE").exists()
    entity.resume()
    assert not (tmp_path / "data" / "PAUSE").exists()


def test_explain_last(tmp_path):
    entity = _seed_entity(tmp_path)
    entity.engine.run_once()
    explain = entity.explain_last()
    assert explain["tick_id"]
    assert "constitution" in explain
    assert "reflection" in explain
