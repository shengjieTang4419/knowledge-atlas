"""L5 层验收：画像聚合（确定性，不调 LLM）。"""
from app.layers.profile import distill, load_events, record_event


def test_distill_empty():
    prof = distill([])
    assert prof.preferences["events"] == 0
    assert prof.preferences["top_topics"] == []


def test_distill_counts_topics_and_relations():
    events = [
        {"topic": "Java多线程", "relation_type": "递进", "action": "read"},
        {"topic": "Java多线程", "relation_type": "递进", "action": "read"},
        {"topic": "Embeddings", "relation_type": "借鉴", "action": "attach"},
    ]
    prof = distill(events)
    prefs = prof.preferences
    assert prefs["events"] == 3
    assert prefs["top_topics"][0] == ("Java多线程", 2)
    assert prefs["preferred_relation"] == "递进"
    assert prefs["actions"]["read"] == 2
    assert 0.0 < prefs["topic_focus"] <= 1.0


def test_distill_ignores_malformed_events():
    prof = distill([{"topic": ""}, {"nope": 1}])  # type: ignore[list-item]
    assert prof.preferences["events"] == 2
    assert prof.preferences["top_topics"] == []


def test_record_and_load_roundtrip(tmp_path):
    path = str(tmp_path / "events.jsonl")
    record_event({"topic": "T", "action": "read"}, path)
    record_event({"topic": "T", "action": "attach"}, path)
    events = load_events(path)
    assert len(events) == 2
    assert events[0]["topic"] == "T"


def test_load_events_missing_file():
    assert load_events("/nonexistent/path/events.jsonl") == []
