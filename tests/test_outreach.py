"""
Tests for the outreach memory loop — ledger CRUD (src/db.py), memory files
(src/memory.py), and the six MCP tools (src/mcp_server.py).

Same strategy as test_mcp_server.py: route db.get_connection() to a temp
file DB; route memory files to a tmp_path directory.
"""

import json
from datetime import datetime
from unittest.mock import patch

import pytest

from src import db, memory
from src.mcp_server import (
    log_outreach,
    record_outcome,
    list_outreach,
    get_outreach_stats,
    get_memory,
    update_memory,
)

TARGET_A = "https://www.linkedin.com/in/jane-doe"
TARGET_B = "https://www.linkedin.com/in/john-smith"


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.db"
    conn = db.get_connection(str(path))
    db.init_db(conn)
    conn.close()
    return path


@pytest.fixture(autouse=True)
def patch_db(db_path):
    real_get_connection = db.get_connection
    with patch("src.mcp_server.db.get_connection",
               side_effect=lambda *a, **kw: real_get_connection(str(db_path))):
        yield


@pytest.fixture(autouse=True)
def patch_memory_dir(tmp_path):
    with patch("src.memory.MEMORY_DIR", tmp_path / "memory"):
        yield tmp_path / "memory"


def _log(target=TARGET_A, name="Jane Doe", hook="question", variant="warm", **kw):
    return json.loads(log_outreach(
        target_url=target, target_name=name, company="Acme Charging",
        channel="dm", variant=variant, hook_type=hook,
        message=f"Hi {name}, quick question about your charging setup?", **kw,
    ))


# ---------------------------------------------------------------------------
# db layer
# ---------------------------------------------------------------------------

class TestDbOutreach:
    def test_insert_and_get(self, db_path):
        conn = db.get_connection(str(db_path))
        db.init_db(conn)
        oid = db.insert_outreach(
            conn, target_url=TARGET_A, message="hello",
            sent_at=datetime.now().isoformat(), target_name="Jane Doe",
        )
        assert oid == 1
        rows = db.get_outreach(conn)
        assert len(rows) == 1
        assert rows[0]["outcome"] == "pending"
        conn.close()

    def test_target_filter_matches_name_and_company(self, db_path):
        conn = db.get_connection(str(db_path))
        db.init_db(conn)
        db.insert_outreach(conn, target_url=TARGET_A, message="m1",
                           sent_at="2026-01-01T00:00:00", target_name="Jane Doe",
                           company="Acme Charging")
        db.insert_outreach(conn, target_url=TARGET_B, message="m2",
                           sent_at="2026-01-02T00:00:00", target_name="John Smith")
        assert len(db.get_outreach(conn, target="jane-doe")) == 1
        assert len(db.get_outreach(conn, target="John Smith")) == 1
        assert len(db.get_outreach(conn, target="Acme")) == 1
        assert len(db.get_outreach(conn, target="nobody")) == 0
        conn.close()

    def test_update_outcome(self, db_path):
        conn = db.get_connection(str(db_path))
        db.init_db(conn)
        oid = db.insert_outreach(conn, target_url=TARGET_A, message="m",
                                 sent_at="2026-01-01T00:00:00")
        assert db.update_outreach_outcome(
            conn, oid, "replied", outcome_at="2026-01-03T00:00:00",
            reply_snippet="sounds interesting")
        row = db.get_outreach(conn)[0]
        assert row["outcome"] == "replied"
        assert row["reply_snippet"] == "sounds interesting"
        assert not db.update_outreach_outcome(conn, 999, "replied", "2026-01-03T00:00:00")
        conn.close()

    def test_update_outcome_preserves_snippet_when_empty(self, db_path):
        conn = db.get_connection(str(db_path))
        db.init_db(conn)
        oid = db.insert_outreach(conn, target_url=TARGET_A, message="m",
                                 sent_at="2026-01-01T00:00:00")
        db.update_outreach_outcome(conn, oid, "replied", "2026-01-02T00:00:00",
                                   reply_snippet="first snippet")
        db.update_outreach_outcome(conn, oid, "positive", "2026-01-03T00:00:00")
        row = db.get_outreach(conn)[0]
        assert row["outcome"] == "positive"
        assert row["reply_snippet"] == "first snippet"
        conn.close()

    def test_breakdown_excludes_pending_and_computes_rates(self, db_path):
        conn = db.get_connection(str(db_path))
        db.init_db(conn)
        for i, (hook, outcome) in enumerate([
            ("question", "replied"), ("question", "ghosted"),
            ("statement", "ghosted"), ("question", "meeting"),
            ("statement", "pending"),
        ]):
            oid = db.insert_outreach(conn, target_url=f"https://li.com/in/p{i}",
                                     message="m", sent_at=f"2026-01-0{i+1}T00:00:00",
                                     hook_type=hook)
            if outcome != "pending":
                db.update_outreach_outcome(conn, oid, outcome, "2026-02-01T00:00:00")
        stats = db.get_outreach_breakdown(conn)
        assert stats["totals"]["total"] == 5
        assert stats["totals"]["pending"] == 1
        assert stats["totals"]["resolved"] == 4
        assert stats["totals"]["replied"] == 2  # replied + meeting
        assert stats["totals"]["reply_rate"] == 0.5
        by_hook = {b["bucket"]: b for b in stats["hook_type"]}
        assert by_hook["question"]["n"] == 3
        assert by_hook["question"]["replied"] == 2
        assert by_hook["statement"]["n"] == 1  # pending row excluded
        conn.close()

    def test_meta_roundtrip(self, db_path):
        conn = db.get_connection(str(db_path))
        db.init_db(conn)
        assert db.get_meta(conn, "missing") is None
        assert db.get_meta(conn, "missing", "0") == "0"
        db.set_meta(conn, "k", "v1")
        db.set_meta(conn, "k", "v2")
        assert db.get_meta(conn, "k") == "v2"
        conn.close()


# ---------------------------------------------------------------------------
# memory module
# ---------------------------------------------------------------------------

class TestMemoryFiles:
    def test_defaults_before_write(self):
        assert "Not learned yet" in memory.read_memory("style")
        assert "No evidence yet" in memory.read_memory("playbook")
        assert not memory.is_learned("style")

    def test_write_and_read(self):
        memory.write_memory("style", "# My voice\nShort DMs.")
        assert memory.read_memory("style") == "# My voice\nShort DMs."
        assert memory.is_learned("style")
        assert not memory.is_learned("playbook")

    def test_invalid_kind(self):
        with pytest.raises(ValueError):
            memory.read_memory("nonsense")


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------

class TestLogOutreach:
    def test_requires_target_and_message(self):
        assert "required" in log_outreach(target_url="", message="hi")
        assert "required" in log_outreach(target_url=TARGET_A, message="  ")

    def test_logs_and_returns_id(self):
        result = _log()
        assert result["logged"] is True
        assert result["outreach_id"] == 1
        assert result["prior_contact"] == []

    def test_flags_prior_contact(self):
        _log()
        result = _log()
        assert len(result["prior_contact"]) == 1
        assert "follow-up" in result["message"]


class TestRecordOutcome:
    def test_by_id(self):
        oid = _log()["outreach_id"]
        result = json.loads(record_outcome(outreach_id=oid, outcome="replied"))
        assert result["outcome"] == "replied"
        assert result["outcomes_since_last_reflection"] == 1

    def test_by_target_url_resolves_latest_pending(self):
        _log()
        oid2 = _log()["outreach_id"]
        result = json.loads(record_outcome(target_url=TARGET_A, outcome="meeting"))
        assert result["outreach_id"] == oid2  # newest pending, not the first

    def test_invalid_outcome_rejected(self):
        assert "Invalid outcome" in record_outcome(outreach_id=1, outcome="pending")
        assert "Invalid outcome" in record_outcome(outreach_id=1, outcome="banana")

    def test_missing_record(self):
        assert "No matching outreach record" in record_outcome(target_url="https://li.com/in/nobody")
        assert "No outreach record with id" in record_outcome(outreach_id=42)

    def test_reflection_due_at_threshold(self):
        with patch("src.mcp_server.REFLECT_EVERY", 2):
            id1 = _log(target=TARGET_A)["outreach_id"]
            id2 = _log(target=TARGET_B)["outreach_id"]
            r1 = json.loads(record_outcome(outreach_id=id1, outcome="ghosted"))
            assert r1["reflection_due"] is False
            r2 = json.loads(record_outcome(outreach_id=id2, outcome="replied"))
            assert r2["reflection_due"] is True
            assert "insaight-reflect" in r2["message"]


class TestListOutreach:
    def test_empty(self):
        assert "No outreach records" in list_outreach()

    def test_snippet_vs_full(self):
        _log()
        slim = json.loads(list_outreach())[0]
        assert "message_snippet" in slim and "message" not in slim
        full = json.loads(list_outreach(full=True))[0]
        assert "message" in full and "quick question" in full["message"]

    def test_outcome_filter(self):
        oid = _log()["outreach_id"]
        _log(target=TARGET_B, name="John Smith")
        record_outcome(outreach_id=oid, outcome="replied")
        assert len(json.loads(list_outreach(outcome="pending"))) == 1
        assert len(json.loads(list_outreach(outcome="replied"))) == 1


class TestStatsAndMemoryTools:
    def test_stats_shape(self):
        oid = _log()["outreach_id"]
        record_outcome(outreach_id=oid, outcome="replied")
        stats = json.loads(get_outreach_stats())
        assert stats["totals"]["reply_rate"] == 1.0
        assert stats["reflection"]["outcomes_since_last_reflection"] == 1
        assert {b["bucket"] for b in stats["hook_type"]} == {"question"}

    def test_get_memory_defaults(self):
        result = json.loads(get_memory())
        assert result["style_learned"] is False
        assert result["playbook_learned"] is False
        assert "Not learned yet" in result["style"]

    def test_update_memory_and_reflection_reset(self):
        oid = _log()["outreach_id"]
        record_outcome(outreach_id=oid, outcome="replied")

        r = json.loads(update_memory(kind="style", content="# Voice\nShort."))
        assert r["updated"] == "style"
        assert r["outcomes_since_last_reflection"] == 1  # not reset yet

        r = json.loads(update_memory(kind="playbook", content="# Playbook",
                                     mark_reflection_done=True))
        assert r["outcomes_since_last_reflection"] == 0
        assert r["last_reflection_at"] is not None

        mem = json.loads(get_memory())
        assert mem["style"] == "# Voice\nShort."
        assert mem["style_learned"] is True

    def test_update_memory_invalid_kind(self):
        assert "Unknown memory kind" in update_memory(kind="bogus", content="x")
