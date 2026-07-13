"""
Tests for the comments layer:
  - src/comments.py    (Comment model + from_apify_result)
  - src/db.py          (comments CRUD)
  - src/mcp_server.py  (scrape_post_comments + list_comments tools)
"""

import json
import pytest
from unittest.mock import patch

from src import db
from src.comments import Comment, flatten_apify_items
from src.mcp_server import (
    scrape_post_comments,
    list_comments,
    _extract_post_urn_from_url,
)


POST_URL = "https://www.linkedin.com/posts/jane-doe_customersupport-activity-7000000000000000001-aBcD"
POST_URN = "urn:li:activity:7000000000000000001"

TOP_COMMENT = {
    "commentUrn": "urn:li:comment:111",
    "author": {
        "name": "Alice Example",
        "linkedinUrl": "https://www.linkedin.com/in/alice-example",
        "headline": "Head of Customer Support at Acme",
    },
    "text": "We faced exactly this problem at scale. Curious to hear more.",
    "postedAt": "2026-04-10T10:00:00Z",
    "numLikes": 12,
    "numReplies": 3,
}

REPLY_COMMENT = {
    "commentUrn": "urn:li:comment:222",
    "parentCommentUrn": "urn:li:comment:111",
    "author": {
        "name": "Bob Reply",
        "linkedinUrl": "https://www.linkedin.com/in/bob-reply",
        "headline": "VP Ops",
    },
    "text": "Same here, would also love a deeper dive.",
    "postedAt": "2026-04-10T11:00:00Z",
    "numLikes": 2,
    "isReply": True,
}

MINIMAL_COMMENT = {
    # No id and no author object — both fallbacks should kick in
    "text": "Anonymous-ish comment",
    "postedAt": "2026-04-10T12:00:00Z",
}


# Real shape from harvestapi/linkedin-post-comments (verified live).
HARVESTAPI_TOP = {
    "id": "7451284594374443008",
    "linkedinUrl": "https://www.linkedin.com/feed/update/urn:li:activity:7000000000000000001?...",
    "commentary": "We're here to help too — most EV drivers just want to resolve their issue.",
    "createdAt": "2026-04-18T15:04:45.473Z",
    "postId": "urn:li:activity:7000000000000000001",
    "actor": {
        "type": "company",
        "universalName": "chargemate-ai",
        "name": "ChargeMate",
        "linkedinUrl": "https://www.linkedin.com/company/chargemate-ai/posts",
        "position": "613 followers",
    },
    "engagement": {"likes": 0, "comments": 1, "shares": 0},
    "replies": [
        {
            "id": "7451327176865583106",
            "commentary": "Thanks for the addition!",
            "createdAt": "2026-04-18T17:54:00Z",
            "actor": {
                "type": "person",
                "name": "Sebastian F.",
                "linkedinUrl": "https://www.linkedin.com/in/jane-doe",
                "position": "Founder at SomeCo",
            },
            "engagement": {"likes": 2, "comments": 0},
        }
    ],
}


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


# ---------------------------------------------------------------------------
# URL helper
# ---------------------------------------------------------------------------

class TestExtractPostUrn:
    def test_posts_url_form(self):
        assert _extract_post_urn_from_url(POST_URL) == POST_URN

    def test_feed_update_form(self):
        url = "https://www.linkedin.com/feed/update/urn:li:activity:7000000000000000001"
        assert _extract_post_urn_from_url(url) == POST_URN

    def test_invalid_url_returns_none(self):
        assert _extract_post_urn_from_url("https://example.com") is None


# ---------------------------------------------------------------------------
# Comment.from_apify_result
# ---------------------------------------------------------------------------

class TestCommentModel:
    def test_top_level_parsed(self):
        c = Comment.from_apify_result(TOP_COMMENT, post_urn=POST_URN, post_url=POST_URL)
        assert c.comment_id == "urn:li:comment:111"
        assert c.is_reply == 0
        assert c.parent_comment_id is None
        assert c.author_name == "Alice Example"
        assert c.author_headline.startswith("Head of Customer Support")
        assert c.text.startswith("We faced exactly this problem")
        assert c.num_likes == 12
        assert c.num_replies == 3
        assert c.post_urn == POST_URN
        assert c.post_url == POST_URL

    def test_reply_detected_from_parent_urn(self):
        c = Comment.from_apify_result(REPLY_COMMENT, post_urn=POST_URN)
        assert c.is_reply == 1
        assert c.parent_comment_id == "urn:li:comment:111"

    def test_fallback_hash_id(self):
        c = Comment.from_apify_result(MINIMAL_COMMENT, post_urn=POST_URN)
        assert c.comment_id.startswith("hash:")

    def test_hash_is_deterministic(self):
        c1 = Comment.from_apify_result(MINIMAL_COMMENT, post_urn=POST_URN)
        c2 = Comment.from_apify_result(MINIMAL_COMMENT, post_urn=POST_URN)
        assert c1.comment_id == c2.comment_id

    def test_flat_author_fields(self):
        item = {
            "id": "c1",
            "authorName": "Flat Author",
            "authorProfileUrl": "https://www.linkedin.com/in/flat",
            "authorHeadline": "Flat headline",
            "text": "hi",
        }
        c = Comment.from_apify_result(item, post_urn=POST_URN)
        assert c.author_name == "Flat Author"
        assert c.author_profile_url == "https://www.linkedin.com/in/flat"
        assert c.author_headline == "Flat headline"


# ---------------------------------------------------------------------------
# Real harvestapi shape
# ---------------------------------------------------------------------------

class TestHarvestapiShape:
    def test_top_comment_parsed(self):
        c = Comment.from_apify_result(HARVESTAPI_TOP, post_urn=POST_URN, post_url=POST_URL)
        assert c.comment_id == "7451284594374443008"
        assert c.author_name == "ChargeMate"
        assert c.author_profile_url.startswith("https://www.linkedin.com/company/chargemate-ai")
        assert c.author_headline == "613 followers"
        assert c.text.startswith("We're here")
        assert c.num_likes == 0
        assert c.num_replies == 1
        assert c.is_reply == 0
        assert c.parent_comment_id is None

    def test_flatten_replies_get_parent_id(self):
        flat = flatten_apify_items([HARVESTAPI_TOP], post_urn=POST_URN, post_url=POST_URL)
        assert len(flat) == 2
        top, reply = flat
        assert top.is_reply == 0
        assert reply.is_reply == 1
        assert reply.parent_comment_id == top.comment_id
        assert reply.author_name == "Sebastian F."
        assert reply.num_likes == 2

    def test_flatten_handles_no_replies(self):
        item = {**HARVESTAPI_TOP, "replies": []}
        flat = flatten_apify_items([item], post_urn=POST_URN)
        assert len(flat) == 1


# ---------------------------------------------------------------------------
# DB CRUD
# ---------------------------------------------------------------------------

class TestCommentsDB:
    def test_init_creates_comments_table(self, db_path):
        conn = db.get_connection(str(db_path))
        db.init_db(conn)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(comments)").fetchall()}
        for c in ("comment_id", "post_urn", "author_name", "text", "num_likes", "is_reply"):
            assert c in cols
        conn.close()

    def test_insert_and_dedup(self, db_path):
        conn = db.get_connection(str(db_path))
        db.init_db(conn)
        c = Comment.from_apify_result(TOP_COMMENT, post_urn=POST_URN)
        assert db.insert_comment(conn, c) is True
        # Second insert with same comment_id is a duplicate
        assert db.insert_comment(conn, c) is False
        conn.close()

    def test_get_comments_orders_by_likes(self, db_path):
        conn = db.get_connection(str(db_path))
        db.init_db(conn)
        a = Comment.from_apify_result(TOP_COMMENT, post_urn=POST_URN)
        b = Comment.from_apify_result(REPLY_COMMENT, post_urn=POST_URN)
        db.insert_comments(conn, [a, b])
        rows = db.get_comments(conn, post_urn=POST_URN)
        assert len(rows) == 2
        # TOP_COMMENT has 12 likes, REPLY_COMMENT has 2
        assert rows[0]["num_likes"] >= rows[1]["num_likes"]
        conn.close()


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------

class TestScrapePostCommentsTool:
    def test_missing_token_errors(self, monkeypatch):
        monkeypatch.delenv("APIFY_API_TOKEN", raising=False)
        result = scrape_post_comments(post_url=POST_URL)
        assert "APIFY_API_TOKEN" in result

    def test_invalid_url_rejected(self, monkeypatch):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake")
        result = scrape_post_comments(post_url="https://example.com/foo")
        assert "does not look like a LinkedIn post URL" in result

    def test_url_without_activity_id_rejected(self, monkeypatch):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake")
        result = scrape_post_comments(post_url="https://www.linkedin.com/feed")
        assert "Could not extract post URN" in result

    def test_scrape_and_store(self, monkeypatch, db_path):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake")
        real = db.get_connection

        def fake_scrape(token, post_urls, max_items=50, scrape_replies=True, profile_mode="short"):
            assert post_urls == [POST_URL]
            return [TOP_COMMENT, REPLY_COMMENT]

        with patch("src.mcp_server.scraper.scrape_post_comments", side_effect=fake_scrape), \
             patch("src.mcp_server.db.get_connection",
                   side_effect=lambda *a, **kw: real(str(db_path))):
            result = scrape_post_comments(post_url=POST_URL)

        payload = json.loads(result)
        assert payload["post_urn"] == POST_URN
        assert payload["scraped"] == 2
        assert payload["new_comments_stored"] == 2
        assert payload["top_comment_likes"] == 12

    def test_max_items_capped(self, monkeypatch, db_path):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake")
        real = db.get_connection
        captured = {}

        def fake_scrape(token, post_urls, max_items=50, scrape_replies=True, profile_mode="short"):
            captured["max_items"] = max_items
            return []

        with patch("src.mcp_server.scraper.scrape_post_comments", side_effect=fake_scrape), \
             patch("src.mcp_server.db.get_connection",
                   side_effect=lambda *a, **kw: real(str(db_path))):
            scrape_post_comments(post_url=POST_URL, max_items=9999)

        assert captured["max_items"] == 200


class TestListCommentsTool:
    def _seed(self, db_path):
        real = db.get_connection
        conn = real(str(db_path))
        db.init_db(conn)
        a = Comment.from_apify_result(TOP_COMMENT, post_urn=POST_URN)
        b = Comment.from_apify_result(REPLY_COMMENT, post_urn=POST_URN)
        db.insert_comments(conn, [a, b])
        conn.close()

    def test_returns_stored_comments(self, db_path, monkeypatch):
        self._seed(db_path)
        real = db.get_connection
        with patch("src.mcp_server.db.get_connection",
                   side_effect=lambda *a, **kw: real(str(db_path))):
            result = json.loads(list_comments(post_url=POST_URL))
        assert len(result) == 2
        assert result[0]["likes"] >= result[1]["likes"]

    def test_min_likes_filter(self, db_path):
        self._seed(db_path)
        real = db.get_connection
        with patch("src.mcp_server.db.get_connection",
                   side_effect=lambda *a, **kw: real(str(db_path))):
            result = json.loads(list_comments(post_url=POST_URL, min_likes=5))
        assert len(result) == 1
        assert result[0]["likes"] >= 5

    def test_exclude_replies(self, db_path):
        self._seed(db_path)
        real = db.get_connection
        with patch("src.mcp_server.db.get_connection",
                   side_effect=lambda *a, **kw: real(str(db_path))):
            result = json.loads(list_comments(post_url=POST_URL, include_replies=False))
        assert all(not r["is_reply"] for r in result)
        assert len(result) == 1

    def test_no_inputs_errors(self):
        result = list_comments()
        assert "Provide either" in result

    def test_empty_db_message(self, db_path):
        real = db.get_connection
        # Init the DB so the table exists but is empty
        conn = real(str(db_path))
        db.init_db(conn)
        conn.close()
        with patch("src.mcp_server.db.get_connection",
                   side_effect=lambda *a, **kw: real(str(db_path))):
            result = list_comments(post_url=POST_URL)
        assert "scrape_post_comments" in result
