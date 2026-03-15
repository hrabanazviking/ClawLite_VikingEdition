from __future__ import annotations
import pytest


@pytest.fixture
def store(tmp_path):
    from clawlite.core.memory import MemoryStore
    return MemoryStore(db_path=str(tmp_path / "mem.db"), semantic_enabled=False)


def test_create_and_get_resource(store):
    from clawlite.core.memory import ResourceContext
    rid = store.create_resource(ResourceContext(name="Project X", kind="project"))
    assert isinstance(rid, str) and len(rid) > 0
    resource = store.get_resource(rid)
    assert resource is not None
    assert resource.name == "Project X"
    assert resource.kind == "project"


def test_list_resources(store):
    from clawlite.core.memory import ResourceContext
    store.create_resource(ResourceContext(name="A", kind="project"))
    store.create_resource(ResourceContext(name="B", kind="person"))
    resources = store.list_resources()
    assert len(resources) == 2
    names = {r.name for r in resources}
    assert names == {"A", "B"}


def test_delete_resource(store):
    from clawlite.core.memory import ResourceContext
    rid = store.create_resource(ResourceContext(name="Temp", kind="conversation"))
    store.delete_resource(rid)
    assert store.get_resource(rid) is None


def test_memory_record_with_resource_id(store):
    from clawlite.core.memory import ResourceContext
    rid = store.create_resource(ResourceContext(name="ClawLite Dev", kind="project"))
    record = store.add("ClawLite uses LiteLLM for providers", resource_id=rid)
    assert record is not None
    records = store.get_resource_records(rid)
    assert len(records) == 1
    assert records[0].text == "ClawLite uses LiteLLM for providers"


def test_ungrouped_records_unaffected_by_resources(store):
    from clawlite.core.memory import ResourceContext
    rid = store.create_resource(ResourceContext(name="P", kind="project"))
    store.add("ungrouped memory")
    records = store.get_resource_records(rid)
    assert len(records) == 0
