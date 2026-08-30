"""
Tests for insaight/db.py — in-memory SQLite so the production DB is never touched.
"""

import pytest
from insaight import db
from insaight.models import Post
from datetime import datetime


def make_conn():
    """Return a fresh in-memory connection with schema initialised."""
    conn = db.get_connection(":memory:")
    db.init_db(conn)
    return conn


def make_post(urn="post-001", account="https://www.linkedin.com/company/acme", **kwargs):
    defaults = dict(
        post_urn=urn,
        post_url=f"https://www.linkedin.com/posts/acme_{urn}",
        author_name="ACME Corp",
        author_profile_url="https://www.linkedin.com/company/acme",
        author_headline="We make things",
        content="Hello LinkedIn",
        posted_date="2026-01-15",
        posted_time="09:00:00",
        posted_timestamp="2026-01-15T09:00:00",
        num_likes=10,
        num_comments=2,
        num_shares=1,
        media_type=None,
        media_urls=None,
        images=None,
        semantic_category=None,
        category_reasoning=None,
        raw_json="{}",
        scraped_at=datetime.now().isoformat(),
        account_url=account,
    )
    defaults.update(kwargs)
    return Post(**defaults)


# ---------------------------------------------------------------------------
# insert_post / deduplication
# ---------------------------------------------------------------------------

class TestInsertPost:
    def test_new_post_returns_true(self):
        conn = make_conn()
        assert db.insert_post(conn, make_post()) is True

    def test_duplicate_urn_returns_false(self):
        conn = make_conn()
        post = make_post()
        db.insert_post(conn, post)
        assert db.insert_post(conn, post) is False

    def test_duplicate_does_not_increase_count(self):
        conn = make_conn()
        post = make_post()
        db.insert_post(conn, post)
        db.insert_post(conn, post)
        count = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
        assert count == 1

    def test_different_urns_both_inserted(self):
        conn = make_conn()
        db.insert_post(conn, make_post("p1"))
        db.insert_post(conn, make_post("p2"))
        count = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
        assert count == 2


class TestInsertPosts:
    def test_returns_new_and_dup_counts(self):
        conn = make_conn()
        posts = [make_post("a"), make_post("b"), make_post("c")]
        new, dups = db.insert_posts(conn, posts)
        assert new == 3
        assert dups == 0

    def test_second_run_all_dups(self):
        conn = make_conn()
        posts = [make_post("a"), make_post("b")]
        db.insert_posts(conn, posts)
        new, dups = db.insert_posts(conn, posts)
        assert new == 0
        assert dups == 2

    def test_mixed_new_and_dups(self):
        conn = make_conn()
        db.insert_post(conn, make_post("existing"))
        new, dups = db.insert_posts(conn, [make_post("existing"), make_post("fresh")])
        assert new == 1
        assert dups == 1


# ---------------------------------------------------------------------------
# update_category
# ---------------------------------------------------------------------------

class TestUpdateCategory:
    def test_sets_category_and_reasoning(self):
        conn = make_conn()
        db.insert_post(conn, make_post("p1"))
        db.update_category(conn, "p1", "product", "Mentions a new feature")
        row = conn.execute("SELECT semantic_category, category_reasoning FROM posts WHERE post_urn='p1'").fetchone()
        assert row["semantic_category"] == "product"
        assert row["category_reasoning"] == "Mentions a new feature"

    def test_update_nonexistent_does_not_raise(self):
        conn = make_conn()
        db.update_category(conn, "ghost", "product", "test")  # should not raise


# ---------------------------------------------------------------------------
# get_uncategorized_posts
# ---------------------------------------------------------------------------

class TestGetUncategorized:
    def test_returns_posts_without_category(self):
        conn = make_conn()
        db.insert_post(conn, make_post("u1"))
        db.insert_post(conn, make_post("u2"))
        db.update_category(conn, "u1", "hiring", "it's a job post")
        rows = db.get_uncategorized_posts(conn)
        urns = [r["post_urn"] for r in rows]
        assert "u2" in urns
        assert "u1" not in urns

    def test_respects_limit(self):
        conn = make_conn()
        for i in range(10):
            db.insert_post(conn, make_post(f"p{i}"))
        rows = db.get_uncategorized_posts(conn, limit=3)
        assert len(rows) == 3

    def test_posts_without_content_excluded(self):
        conn = make_conn()
        db.insert_post(conn, make_post("no-content", content=None))
        rows = db.get_uncategorized_posts(conn)
        assert all(r["post_urn"] != "no-content" for r in rows)


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------

class TestGetStats:
    def test_empty_db(self):
        conn = make_conn()
        stats = db.get_stats(conn)
        assert stats["total_posts"] == 0
        assert stats["accounts"] == 0

    def test_counts_posts_and_accounts(self):
        conn = make_conn()
        db.insert_post(conn, make_post("p1", account="https://www.linkedin.com/company/a"))
        db.insert_post(conn, make_post("p2", account="https://www.linkedin.com/company/a"))
        db.insert_post(conn, make_post("p3", account="https://www.linkedin.com/company/b"))
        stats = db.get_stats(conn)
        assert stats["total_posts"] == 3
        assert stats["accounts"] == 2

    def test_categorized_count(self):
        conn = make_conn()
        db.insert_post(conn, make_post("p1"))
        db.insert_post(conn, make_post("p2"))
        db.update_category(conn, "p1", "product", "reason")
        stats = db.get_stats(conn)
        assert stats["categorized"] == 1

    def test_date_range(self):
        conn = make_conn()
        db.insert_post(conn, make_post("early", posted_timestamp="2025-01-01T00:00:00"))
        db.insert_post(conn, make_post("late",  posted_timestamp="2026-06-01T00:00:00"))
        stats = db.get_stats(conn)
        assert stats["earliest"] == "2025-01-01T00:00:00"
        assert stats["latest"] == "2026-06-01T00:00:00"


# ---------------------------------------------------------------------------
# get_all_posts
# ---------------------------------------------------------------------------

class TestGetAllPosts:
    def test_returns_all_rows(self):
        conn = make_conn()
        db.insert_post(conn, make_post("p1"))
        db.insert_post(conn, make_post("p2"))
        rows = db.get_all_posts(conn)
        assert len(rows) == 2

    def test_ordered_by_timestamp_desc(self):
        conn = make_conn()
        db.insert_post(conn, make_post("early", posted_timestamp="2025-01-01T00:00:00"))
        db.insert_post(conn, make_post("late",  posted_timestamp="2026-06-01T00:00:00"))
        rows = db.get_all_posts(conn)
        assert rows[0]["post_urn"] == "late"
        assert rows[1]["post_urn"] == "early"

    def test_empty_db_returns_empty_list(self):
        conn = make_conn()
        assert db.get_all_posts(conn) == []
