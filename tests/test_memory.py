from core.memory import MemoryStore


def test_append_only_events(tmp_path):
    store = MemoryStore(tmp_path / "entity.sqlite")
    store.initialize()
    with store.transaction() as conn:
        store.append_event(
            conn,
            event_id="mem_1",
            tick_id=None,
            kind="memory",
            category="test",
            payload={"summary": "first"},
        )
    ids = store.known_memory_ids()
    assert "mem_1" in ids
    # No update API — re-insert should fail
    try:
        with store.transaction() as conn:
            store.append_event(
                conn,
                event_id="mem_1",
                tick_id=None,
                kind="memory",
                category="test",
                payload={"summary": "rewrite"},
            )
        raised = False
    except Exception:
        raised = True
    assert raised


def test_tick_counter_monotonic(tmp_path):
    store = MemoryStore(tmp_path / "entity.sqlite")
    store.initialize()
    with store.transaction() as conn:
        a = store.allocate_tick_id(conn)
        b = store.allocate_tick_id(conn)
    assert a == "tick_000000001"
    assert b == "tick_000000002"
