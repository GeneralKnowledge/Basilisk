from core.memory import MemoryStore
from core.personality import TraitProposal, apply_proposal


def test_rejects_trait_without_evidence(tmp_path):
    store = MemoryStore(tmp_path / "entity.sqlite")
    store.initialize()
    result = apply_proposal(
        store,
        TraitProposal(
            trait="mysterious",
            rationale="LLM invented this",
            supporting_event_ids=[],
            contradicting_event_ids=[],
        ),
    )
    assert result is not None
    assert result["accepted"] is False


def test_accepts_trait_with_evidence(tmp_path):
    store = MemoryStore(tmp_path / "entity.sqlite")
    store.initialize()
    with store.transaction() as conn:
        for i in range(3):
            store.append_event(
                conn,
                event_id=f"mem_{i}",
                tick_id=None,
                kind="memory",
                category="test",
                payload={"summary": f"rest tick {i}"},
            )
    result = apply_proposal(
        store,
        TraitProposal(
            trait="deliberate",
            rationale="Multiple quiet ticks",
            supporting_event_ids=["mem_0", "mem_1", "mem_2"],
            contradicting_event_ids=[],
        ),
    )
    assert result["accepted"] is True
    traits = store.list_traits()
    assert traits[0]["trait"] == "deliberate"
    assert traits[0]["evidence_count"] >= 3
