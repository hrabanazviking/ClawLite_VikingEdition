from __future__ import annotations
import pytest


@pytest.fixture
def store(tmp_path):
    from clawlite.core.memory import MemoryStore
    return MemoryStore(db_path=str(tmp_path / "mem.db"), semantic_enabled=False)


def test_set_and_get_ttl(store):
    record = store.add("temporary fact", source="session")
    assert record is not None
    store.set_record_ttl(record.id, ttl_seconds=3600)
    policy = store.get_record_ttl(record.id)
    assert policy is not None
    assert policy["record_id"] == record.id
    assert policy["expires_at"] is not None


def test_purge_expired_records(store):
    record = store.add("will expire soon", source="session")
    store.set_record_ttl(record.id, ttl_seconds=-1)
    purged = store.purge_expired_records()
    assert purged >= 1


def test_non_expired_records_not_purged(store):
    record = store.add("long-lived fact", source="user")
    store.set_record_ttl(record.id, ttl_seconds=86400)
    purged = store.purge_expired_records()
    assert purged == 0
    recalled = store.search("long-lived", limit=5)
    assert any(r.text == "long-lived fact" for r in recalled)


def test_records_without_ttl_never_purged(store):
    store.add("permanent fact", source="user")
    purged = store.purge_expired_records()
    assert purged == 0
