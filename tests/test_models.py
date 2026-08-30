"""
Tests for insaight/models.py — Post.from_apify_result() covers both actors:
  - harvestapi/linkedin-profile-posts  (acme-charging feed)
  - harvestapi/linkedin-post-search    (keyword search, same schema)
"""

import json
import pytest
from insaight.models import Post, _extract_datetime, _to_int


# ---------------------------------------------------------------------------
# Fixtures — realistic Apify payloads
# ---------------------------------------------------------------------------

TYPICAL_POST = {
    "type": "post",
    "id": "7445054664800227328",
    "linkedinUrl": "https://www.linkedin.com/posts/acme-charging_test-activity-7445054664800227328-hi2Q",
    "content": "Acme Charging lanceert de eerste laadpaal op houtskool 🔥",
    "author": {
        "name": "Acme Charging",
        "linkedinUrl": "https://www.linkedin.com/company/acme-charging",
        "info": "Smart charging solutions",
        "universalName": "acme-charging",
        "publicIdentifier": "acme-charging",
        "type": "company",
    },
    "postedAt": {
        "timestamp": 1775039354515,
        "date": "2026-04-01T10:29:14.515Z",
        "postedAgoText": "5 days ago • Visible to anyone on or off LinkedIn",
    },
    "postImages": [
        {"url": "https://media.licdn.com/img1.jpg", "width": 1200, "height": 628}
    ],
    "engagement": {
        "id": "7445054664800227328",
        "likes": 36,
        "comments": 4,
        "shares": 0,
    },
}

REPOST = {
    **TYPICAL_POST,
    "id": "7404188628052090881",
    "author": {
        "name": "Afschrift NV",
        "linkedinUrl": "https://www.linkedin.com/company/afschrift-nv",
        "universalName": "afschrift-nv",
        "type": "company",
    },
    "engagement": {"likes": 54, "comments": 2, "shares": 4},
}

UNIX_TIMESTAMP_POST = {
    **TYPICAL_POST,
    "id": "7400000000000000000",
    "postedAt": {"timestamp": 1774530898744},  # no 'date' key — fallback to timestamp
}

MINIMAL_POST = {
    # Bare minimum: id + content, no author, no dates, no engagement
    "id": "7300000000000000001",
    "content": "Minimal post content",
}

NO_ID_POST = {
    # id missing — should generate hash URN
    "content": "Post with no ID",
    "linkedinUrl": "https://www.linkedin.com/posts/acme-charging_test",
    "postedAt": {"date": "2026-01-01T00:00:00.000Z"},
}

ACCOUNT_URL = "https://www.linkedin.com/company/acme-charging"


# ---------------------------------------------------------------------------
# Post.from_apify_result
# ---------------------------------------------------------------------------

class TestFromApifyResult:
    def test_urn_extracted_from_id(self):
        post = Post.from_apify_result(TYPICAL_POST, ACCOUNT_URL)
        assert post.post_urn == "7445054664800227328"

    def test_urn_fallback_to_hash_when_id_missing(self):
        post = Post.from_apify_result(NO_ID_POST, ACCOUNT_URL)
        assert post.post_urn.startswith("hash:")
        assert len(post.post_urn) > 10

    def test_urn_hash_is_deterministic(self):
        p1 = Post.from_apify_result(NO_ID_POST, ACCOUNT_URL)
        p2 = Post.from_apify_result(NO_ID_POST, ACCOUNT_URL)
        assert p1.post_urn == p2.post_urn

    def test_post_url_from_linkedinUrl(self):
        post = Post.from_apify_result(TYPICAL_POST, ACCOUNT_URL)
        assert post.post_url == TYPICAL_POST["linkedinUrl"]

    def test_author_name_from_nested_author(self):
        post = Post.from_apify_result(TYPICAL_POST, ACCOUNT_URL)
        assert post.author_name == "Acme Charging"

    def test_author_headline_from_nested_info(self):
        post = Post.from_apify_result(TYPICAL_POST, ACCOUNT_URL)
        assert post.author_headline == "Smart charging solutions"

    def test_author_profile_url_from_nested_linkedinUrl(self):
        post = Post.from_apify_result(TYPICAL_POST, ACCOUNT_URL)
        assert post.author_profile_url == "https://www.linkedin.com/company/acme-charging"

    def test_content_extracted(self):
        post = Post.from_apify_result(TYPICAL_POST, ACCOUNT_URL)
        assert post.content == TYPICAL_POST["content"]

    def test_engagement_from_nested_dict(self):
        post = Post.from_apify_result(TYPICAL_POST, ACCOUNT_URL)
        assert post.num_likes == 36
        assert post.num_comments == 4
        assert post.num_shares == 0

    def test_engagement_defaults_to_zero_when_missing(self):
        post = Post.from_apify_result(MINIMAL_POST, ACCOUNT_URL)
        assert post.num_likes == 0
        assert post.num_comments == 0
        assert post.num_shares == 0

    def test_timestamp_parsed_from_iso_string(self):
        post = Post.from_apify_result(TYPICAL_POST, ACCOUNT_URL)
        assert post.posted_timestamp == "2026-04-01T10:29:14.515000"
        assert post.posted_date == "2026-04-01"
        assert post.posted_time == "10:29:14"

    def test_timestamp_parsed_from_unix_milliseconds(self):
        post = Post.from_apify_result(UNIX_TIMESTAMP_POST, ACCOUNT_URL)
        # 1774530898744 ms = 2026-03-26T13:14:58.744
        assert post.posted_timestamp is not None
        assert post.posted_date is not None
        assert "2026" in post.posted_date

    def test_images_extracted_from_postImages(self):
        post = Post.from_apify_result(TYPICAL_POST, ACCOUNT_URL)
        assert post.images is not None
        imgs = json.loads(post.images)
        assert "https://media.licdn.com/img1.jpg" in imgs
        assert post.media_type == "image"

    def test_no_images_gives_none(self):
        post = Post.from_apify_result(MINIMAL_POST, ACCOUNT_URL)
        assert post.images is None
        assert post.media_urls is None

    def test_account_url_preserved(self):
        post = Post.from_apify_result(TYPICAL_POST, ACCOUNT_URL)
        assert post.account_url == ACCOUNT_URL

    def test_repost_preserves_original_author(self):
        post = Post.from_apify_result(REPOST, ACCOUNT_URL)
        assert post.author_name == "Afschrift NV"
        assert post.account_url == ACCOUNT_URL  # account is still acme-charging

    def test_raw_json_is_serialized_string(self):
        post = Post.from_apify_result(TYPICAL_POST, ACCOUNT_URL)
        parsed = json.loads(post.raw_json)
        assert isinstance(parsed, dict)

    def test_minimal_post_does_not_raise(self):
        post = Post.from_apify_result(MINIMAL_POST, ACCOUNT_URL)
        assert post.post_urn is not None
        assert post.content == "Minimal post content"

    def test_category_always_none_on_creation(self):
        post = Post.from_apify_result(TYPICAL_POST, ACCOUNT_URL)
        assert post.semantic_category is None
        assert post.category_reasoning is None


# ---------------------------------------------------------------------------
# _extract_datetime
# ---------------------------------------------------------------------------

class TestExtractDatetime:
    def test_iso_with_z_and_milliseconds(self):
        item = {"_postedAt_flat": "2026-04-01T10:29:14.515Z"}
        date, time, ts = _extract_datetime(item)
        assert date == "2026-04-01"
        assert time == "10:29:14"
        assert ts == "2026-04-01T10:29:14.515000"

    def test_iso_without_z(self):
        item = {"_postedAt_flat": "2026-04-01T10:29:14"}
        date, time, ts = _extract_datetime(item)
        assert date == "2026-04-01"
        assert ts is not None

    def test_date_only(self):
        item = {"_postedAt_flat": "2026-04-01"}
        date, time, ts = _extract_datetime(item)
        assert date == "2026-04-01"

    def test_unix_milliseconds_large_number(self):
        item = {"_postedAt_flat": 1775039354515}
        date, time, ts = _extract_datetime(item)
        assert date is not None
        assert "2026" in (ts or "")

    def test_unix_seconds(self):
        item = {"_postedAt_flat": 1775039354}  # < 1e12, treated as seconds
        date, time, ts = _extract_datetime(item)
        assert date is not None

    def test_all_none_when_no_date_fields(self):
        date, time, ts = _extract_datetime({})
        assert date is None
        assert time is None
        assert ts is None

    def test_unparseable_string_stored_as_raw_timestamp(self):
        item = {"_postedAt_flat": "some weird format"}
        date, time, ts = _extract_datetime(item)
        assert date is None
        assert ts == "some weird format"


# ---------------------------------------------------------------------------
# _to_int
# ---------------------------------------------------------------------------

class TestToInt:
    def test_int_passthrough(self):
        assert _to_int(42) == 42

    def test_string_digit(self):
        assert _to_int("123") == 123

    def test_string_with_comma(self):
        assert _to_int("1,234") == 1234

    def test_none_returns_zero(self):
        assert _to_int(None) == 0

    def test_empty_string_returns_zero(self):
        assert _to_int("") == 0

    def test_non_numeric_string_returns_zero(self):
        assert _to_int("N/A") == 0
