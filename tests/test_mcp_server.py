"""
Tests for insaight/mcp_server.py — MCP tools and internal helpers.

Strategy: monkey-patch db.get_connection() to return an in-memory DB so no
production data is touched and tests are hermetic and fast.
"""

import json
import sqlite3
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from insaight import db
from insaight.mcp_server import (
    _slug,
    _resolve_account,
    _snippet,
    _days_ago_clause,
    list_accounts,
    list_posts,
    get_posts,
    search_posts,
    get_stats,
    scrape_profile,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

ACME_URL   = "https://www.linkedin.com/company/acme-corp"
GLOBO_URL  = "https://www.linkedin.com/company/globo-tech"
PERSON_URL = "https://www.linkedin.com/in/john-doe-12345678/recent-activity/all/"


def insert_raw(conn, urn, account_url, content, timestamp, likes=0, comments=0, shares=0, category=None):
    conn.execute(
        """INSERT INTO posts
           (post_urn, post_url, author_name, author_profile_url, author_headline,
            content, posted_date, posted_time, posted_timestamp,
            num_likes, num_comments, num_shares,
            media_type, media_urls, images,
            semantic_category, category_reasoning,
            raw_json, scraped_at, account_url)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (urn, f"https://li.com/p/{urn}", "Author", None, None,
         content, timestamp[:10], "00:00:00", timestamp,
         likes, comments, shares,
         None, None, None, category, None,
         "{}", datetime.now().isoformat(), account_url),
    )
    conn.commit()


@pytest.fixture
def db_path(tmp_path):
    """
    File-based temp SQLite DB with test data.

    We use a real file (not :memory:) because each MCP tool opens and closes its
    own connection. With :memory: each close() destroys the data; a file persists
    across connections within the same test.
    """
    path = tmp_path / "test.db"
    conn = db.get_connection(str(path))
    db.init_db(conn)
    now = datetime.now()
    insert_raw(conn, "p1", ACME_URL,  "ACME product launch",       (now - timedelta(days=2)).isoformat(),  likes=50)
    insert_raw(conn, "p2", ACME_URL,  "ACME hiring software devs", (now - timedelta(days=10)).isoformat(), likes=20, category="hiring")
    insert_raw(conn, "p3", ACME_URL,  "ACME old post",             (now - timedelta(days=100)).isoformat(), likes=5)
    insert_raw(conn, "p4", GLOBO_URL, "Globo new office",          (now - timedelta(days=5)).isoformat(),  likes=30)
    insert_raw(conn, "p5", GLOBO_URL, "Globo hiring engineers",    (now - timedelta(days=15)).isoformat(), likes=8,  category="hiring")
    insert_raw(conn, "p6", PERSON_URL,"John's personal update",    (now - timedelta(days=3)).isoformat(),  likes=15)
    conn.close()
    return path


@pytest.fixture(autouse=True)
def patch_db(db_path):
    """
    Route all db.get_connection() calls in MCP tools to the temp file DB.
    Each call gets a fresh connection so close() doesn't break subsequent calls.

    We capture the real function BEFORE patch() replaces it to avoid infinite
    recursion (insaight.mcp_server.db IS insaight.db — same module object).
    """
    real_get_connection = db.get_connection
    with patch("insaight.mcp_server.db.get_connection",
               side_effect=lambda *a, **kw: real_get_connection(str(db_path))):
        yield


# ---------------------------------------------------------------------------
# Slug helper
# ---------------------------------------------------------------------------

class TestSlug:
    def test_company_url(self):
        assert _slug("https://www.linkedin.com/company/acme-charging") == "acme-charging"

    def test_person_url_with_trailing_path(self):
        assert _slug(PERSON_URL) == "john-doe-12345678"

    def test_trailing_slash_removed(self):
        assert _slug("https://www.linkedin.com/company/acme-corp/") == "acme-corp"

    def test_url_with_recent_activity_suffix(self):
        url = "https://www.linkedin.com/in/jane-doe-12345678/recent-activity/all/"
        assert _slug(url) == "jane-doe-12345678"


# ---------------------------------------------------------------------------
# _snippet helper
# ---------------------------------------------------------------------------

class TestSnippet:
    def test_short_content_unchanged(self):
        assert _snippet("Hello", 150) == "Hello"

    def test_long_content_truncated_with_ellipsis(self):
        text = "A" * 200
        s = _snippet(text, 150)
        assert len(s) == 151  # 150 chars + "…"
        assert s.endswith("…")

    def test_none_returns_empty_string(self):
        assert _snippet(None) == ""

    def test_newlines_replaced_with_spaces(self):
        assert "\n" not in _snippet("line1\nline2")


# ---------------------------------------------------------------------------
# _days_ago_clause
# ---------------------------------------------------------------------------

class TestDaysAgoClause:
    def test_zero_returns_empty(self):
        clause, params = _days_ago_clause(0)
        assert clause == ""
        assert params == []

    def test_negative_returns_empty(self):
        clause, params = _days_ago_clause(-5)
        assert clause == ""

    def test_positive_returns_clause_with_naive_timestamp(self):
        clause, params = _days_ago_clause(30)
        assert "posted_timestamp" in clause
        assert len(params) == 1
        # Must be a naive ISO string (no '+' timezone suffix)
        assert "+" not in params[0]
        assert "Z" not in params[0]

    def test_cutoff_is_approximately_n_days_ago(self):
        _, params = _days_ago_clause(7)
        cutoff = datetime.fromisoformat(params[0])
        expected = datetime.now() - timedelta(days=7)
        assert abs((cutoff - expected).total_seconds()) < 5  # within 5 seconds


# ---------------------------------------------------------------------------
# list_accounts
# ---------------------------------------------------------------------------

class TestListAccounts:
    def test_returns_all_accounts(self):
        result = json.loads(list_accounts())
        slugs = {r["slug"] for r in result}
        assert "acme-corp" in slugs
        assert "globo-tech" in slugs
        assert "john-doe-12345678" in slugs

    def test_includes_post_count(self):
        result = json.loads(list_accounts())
        acme = next(r for r in result if r["slug"] == "acme-corp")
        assert acme["post_count"] == 3

    def test_includes_latest_and_earliest(self):
        result = json.loads(list_accounts())
        acme = next(r for r in result if r["slug"] == "acme-corp")
        assert acme["latest_post"] is not None
        assert acme["earliest_post"] is not None

    def test_ordered_by_latest_post_desc(self):
        result = json.loads(list_accounts())
        dates = [r["latest_post"] for r in result]
        assert dates == sorted(dates, reverse=True)


# ---------------------------------------------------------------------------
# list_posts
# ---------------------------------------------------------------------------

class TestListPosts:
    def test_returns_all_posts_by_default(self):
        result = json.loads(list_posts())
        assert len(result) == 6

    def test_slim_has_no_content_field(self):
        result = json.loads(list_posts())
        for post in result:
            assert "content" not in post

    def test_slim_has_snippet_field(self):
        result = json.loads(list_posts())
        for post in result:
            assert "snippet" in post

    def test_filter_by_slug(self):
        result = json.loads(list_posts(account="acme-corp"))
        assert len(result) == 3
        assert all(r["account_slug"] == "acme-corp" for r in result)

    def test_filter_by_full_url(self):
        result = json.loads(list_posts(account=ACME_URL))
        assert len(result) == 3

    def test_filter_by_partial_name(self):
        result = json.loads(list_posts(account="globo"))
        assert all(r["account_slug"] == "globo-tech" for r in result)

    def test_unknown_account_returns_error_message(self):
        result = list_posts(account="totally-unknown-xyz")
        assert "No account matching" in result
        assert "list_accounts()" in result  # tells agent what to do next

    def test_filter_by_category(self):
        result = json.loads(list_posts(category="hiring"))
        assert len(result) == 2
        assert all(r["category"] == "hiring" for r in result)

    def test_days_ago_filters_recent(self):
        result = json.loads(list_posts(days_ago=7))
        urns = {r["urn"] for r in result}
        assert "p3" not in urns    # 100 days old
        assert "p5" not in urns    # 15 days old

    def test_min_engagement_filter(self):
        result = json.loads(list_posts(min_engagement=25))
        for r in result:
            total = r["likes"] + r["comments"] + r["shares"]
            assert total >= 25

    def test_limit_respected(self):
        result = json.loads(list_posts(limit=2))
        assert len(result) == 2

    def test_limit_capped_at_100(self):
        result = json.loads(list_posts(limit=9999))
        assert len(result) <= 100

    def test_ordered_newest_first(self):
        result = json.loads(list_posts())
        timestamps = [r["posted"] for r in result if r["posted"]]
        assert timestamps == sorted(timestamps, reverse=True)


# ---------------------------------------------------------------------------
# get_posts
# ---------------------------------------------------------------------------

class TestGetPosts:
    def test_returns_full_content(self):
        result = json.loads(get_posts(urns=["p1"]))
        assert len(result) == 1
        assert result[0]["content"] == "ACME product launch"

    def test_batch_fetch_multiple(self):
        result = json.loads(get_posts(urns=["p1", "p4"]))
        urns = {r["urn"] for r in result}
        assert urns == {"p1", "p4"}

    def test_does_not_include_raw_json(self):
        result = json.loads(get_posts(urns=["p1"]))
        assert "raw_json" not in result[0]

    def test_does_not_include_scraped_at(self):
        result = json.loads(get_posts(urns=["p1"]))
        assert "scraped_at" not in result[0]

    def test_empty_urns_returns_error_message(self):
        result = get_posts(urns=[])
        assert "No URNs" in result

    def test_unknown_urn_returns_not_found(self):
        result = get_posts(urns=["does-not-exist"])
        assert "No posts found" in result

    def test_mixed_known_and_unknown_urns(self):
        result = json.loads(get_posts(urns=["p1", "ghost-urn"]))
        assert len(result) == 1
        assert result[0]["urn"] == "p1"

    def test_capped_at_20(self, tmp_path):
        # Insert 25 posts into a separate temp DB
        path = tmp_path / "bulk.db"
        real = db.get_connection  # capture before patch
        c = real(str(path))
        db.init_db(c)
        for i in range(25):
            insert_raw(c, f"bulk-{i}", ACME_URL, f"post {i}", datetime.now().isoformat())
        c.close()
        with patch("insaight.mcp_server.db.get_connection",
                   side_effect=lambda *a, **kw: real(str(path))):
            urns = [f"bulk-{i}" for i in range(25)]
            result = json.loads(get_posts(urns=urns))
        assert len(result) <= 20


# ---------------------------------------------------------------------------
# search_posts
# ---------------------------------------------------------------------------

class TestSearchPosts:
    def test_finds_keyword_in_content(self):
        result = json.loads(search_posts(query="hiring"))
        urns = {r["urn"] for r in result}
        assert "p2" in urns  # "ACME hiring software devs"
        assert "p5" in urns  # "Globo hiring engineers"

    def test_case_insensitive(self):
        result = json.loads(search_posts(query="ACME"))
        assert len(result) >= 1
        result2 = json.loads(search_posts(query="acme"))
        assert len(result2) == len(result)

    def test_returns_full_content(self):
        result = json.loads(search_posts(query="product launch"))
        assert len(result) == 1
        assert "content" in result[0]
        assert "ACME product launch" in result[0]["content"]

    def test_no_match_returns_message(self):
        result = search_posts(query="quantum computing blockchain")
        assert "No posts matched" in result

    def test_filter_by_account(self):
        result = json.loads(search_posts(query="hiring", account="acme-corp"))
        assert all(r["account_slug"] == "acme-corp" for r in result)

    def test_unknown_account_returns_error(self):
        result = search_posts(query="hiring", account="nonexistent")
        assert "No account matching" in result

    def test_days_ago_filter_applied(self):
        result = json.loads(search_posts(query="ACME", days_ago=5))
        # Only p1 (2 days old) should match; p2 (10 days) and p3 (100 days) should not
        urns = {r["urn"] for r in result}
        assert "p1" in urns
        assert "p2" not in urns
        assert "p3" not in urns

    def test_limit_respected(self):
        result = json.loads(search_posts(query="hiring", limit=1))
        assert len(result) == 1

    def test_limit_capped_at_50(self):
        result = json.loads(search_posts(query="hiring", limit=9999))
        assert len(result) <= 50


# ---------------------------------------------------------------------------
# scrape_profile
# ---------------------------------------------------------------------------

class TestScrapeProfile:
    LINKEDIN_URL = "https://www.linkedin.com/company/new-company-bv"

    def _fake_items(self, n=3):
        """Minimal Apify items that Post.from_apify_result can handle."""
        return [
            {
                "id": f"urn{i}",
                "content": f"Post number {i}",
                "linkedinUrl": f"https://www.linkedin.com/posts/new-company-bv_post{i}",
                "postedAt": {"date": f"2026-0{i+1}-01T10:00:00.000Z"},
                "engagement": {"likes": i * 5, "comments": 0, "shares": 0},
                "author": {"name": "New Company BV", "linkedinUrl": self.LINKEDIN_URL},
            }
            for i in range(1, n + 1)
        ]

    def test_missing_token_returns_error(self, monkeypatch):
        monkeypatch.delenv("APIFY_API_TOKEN", raising=False)
        result = scrape_profile(url=self.LINKEDIN_URL)
        assert "APIFY_API_TOKEN" in result

    def test_invalid_url_returns_error(self):
        result = scrape_profile(url="not-a-linkedin-url")
        assert "does not look like" in result

    def test_successful_scrape_stores_posts(self, monkeypatch, db_path):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
        real = db.get_connection

        with patch("insaight.mcp_server.scraper.scrape_account", return_value=self._fake_items(3)), \
             patch("insaight.mcp_server.db.get_connection",
                   side_effect=lambda *a, **kw: real(str(db_path))):
            result_str = scrape_profile(url=self.LINKEDIN_URL)

        result = json.loads(result_str)
        assert result["new_posts_stored"] == 3
        assert result["duplicates_skipped"] == 0
        assert result["account_slug"] == "new-company-bv"
        assert "list_posts" in result["message"]

    def test_second_scrape_counts_duplicates(self, monkeypatch, db_path):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
        real = db.get_connection

        with patch("insaight.mcp_server.scraper.scrape_account", return_value=self._fake_items(3)), \
             patch("insaight.mcp_server.db.get_connection",
                   side_effect=lambda *a, **kw: real(str(db_path))):
            scrape_profile(url=self.LINKEDIN_URL)  # first run
            result = json.loads(scrape_profile(url=self.LINKEDIN_URL))  # second run

        assert result["new_posts_stored"] == 0
        assert result["duplicates_skipped"] == 3

    def test_empty_response_returns_message(self, monkeypatch):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
        with patch("insaight.mcp_server.scraper.scrape_account", return_value=[]):
            result = scrape_profile(url=self.LINKEDIN_URL)
        assert "No posts returned" in result

    def test_apify_error_returns_message(self, monkeypatch):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
        with patch("insaight.mcp_server.scraper.scrape_account",
                   side_effect=Exception("network timeout")):
            result = scrape_profile(url=self.LINKEDIN_URL)
        assert "network timeout" in result

    def test_max_posts_capped_at_100(self, monkeypatch, db_path):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
        real = db.get_connection
        captured = {}

        def fake_scrape(token, url, max_posts):
            captured["max_posts"] = max_posts
            return []

        with patch("insaight.mcp_server.scraper.scrape_account", side_effect=fake_scrape), \
             patch("insaight.mcp_server.db.get_connection",
                   side_effect=lambda *a, **kw: real(str(db_path))):
            scrape_profile(url=self.LINKEDIN_URL, max_posts=9999)

        assert captured["max_posts"] == 100


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------

class TestGetStats:
    def test_total_posts_count(self):
        result = json.loads(get_stats())
        assert result["total_posts"] == 6

    def test_accounts_breakdown(self):
        result = json.loads(get_stats())
        slugs = {a["slug"] for a in result["accounts"]}
        assert "acme-corp" in slugs
        assert "globo-tech" in slugs

    def test_categories_breakdown(self):
        result = json.loads(get_stats())
        cats = {c["semantic_category"]: c["n"] for c in result["categories"]}
        assert cats.get("hiring") == 2

    def test_categorized_count(self):
        result = json.loads(get_stats())
        assert result["categorized"] == 2  # p2 and p5

    def test_date_range_present(self):
        result = json.loads(get_stats())
        assert result["earliest"] is not None
        assert result["latest"] is not None
