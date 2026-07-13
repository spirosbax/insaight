import hashlib
import json
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Post:
    post_urn: str
    post_url: str | None
    author_name: str | None
    author_profile_url: str | None
    author_headline: str | None
    content: str | None
    posted_date: str | None
    posted_time: str | None
    posted_timestamp: str | None
    num_likes: int
    num_comments: int
    num_shares: int
    media_type: str | None
    media_urls: str | None
    images: str | None
    semantic_category: str | None
    category_reasoning: str | None
    raw_json: str
    scraped_at: str
    account_url: str

    @classmethod
    def from_apify_result(cls, item: dict, account_url: str) -> "Post":
        # harvestapi/linkedin-post-search uses nested author/engagement/postedAt dicts
        author_obj = item.get("author") or {}
        engagement_obj = item.get("engagement") or {}
        posted_at_obj = item.get("postedAt") or {}

        # Extract post URN or build a dedup key
        post_urn = (
            item.get("id")
            or item.get("urn")
            or item.get("postUrn")
            or item.get("activityUrn")
            or item.get("dashEntityUrn")
        )
        if not post_urn:
            content_preview = (item.get("text") or item.get("content") or "")[:100]
            author = item.get("authorProfileUrl") or item.get("profileUrl") or account_url
            posted = item.get("postedDate") or ""
            raw = f"{author}|{posted}|{content_preview}"
            post_urn = f"hash:{hashlib.sha256(raw.encode()).hexdigest()[:32]}"

        post_url = (
            item.get("linkedinUrl")
            or item.get("postUrl")
            or item.get("url")
        )

        # Author info — check nested author object first, then flat fields
        author_name = (
            author_obj.get("name")
            or item.get("authorName")
            or item.get("name")
            or item.get("fullName")
        )
        author_profile_url = (
            author_obj.get("linkedinUrl")
            or item.get("authorProfileUrl")
            or item.get("profileUrl")
            or item.get("authorUrl")
        )
        author_headline = (
            author_obj.get("info")
            or item.get("authorHeadline")
            or item.get("headline")
        )

        # Post content
        content = item.get("text") or item.get("content") or item.get("postText")

        # Date/time extraction — harvestapi nests postedAt as {timestamp, date}
        if isinstance(posted_at_obj, dict):
            raw_ts = posted_at_obj.get("date") or posted_at_obj.get("timestamp")
            item = {**item, "_postedAt_flat": raw_ts}
        posted_date, posted_time, posted_timestamp = _extract_datetime(item)

        # Engagement metrics — harvestapi uses nested engagement.likes/comments/shares
        num_likes = _to_int(
            engagement_obj.get("likes")
            or item.get("numLikes")
            or item.get("likesCount")
            or item.get("totalReactionCount")
            or 0
        )
        num_comments = _to_int(
            engagement_obj.get("comments")
            or item.get("numComments")
            or item.get("commentsCount")
            or 0
        )
        num_shares = _to_int(
            engagement_obj.get("shares")
            or item.get("numShares")
            or item.get("sharesCount")
            or item.get("repostsCount")
            or 0
        )

        # Media extraction
        media_type, media_urls, images = _extract_media(item)

        return cls(
            post_urn=post_urn,
            post_url=post_url,
            author_name=author_name,
            author_profile_url=author_profile_url,
            author_headline=author_headline,
            content=content,
            posted_date=posted_date,
            posted_time=posted_time,
            posted_timestamp=posted_timestamp,
            num_likes=num_likes,
            num_comments=num_comments,
            num_shares=num_shares,
            media_type=media_type,
            media_urls=media_urls,
            images=images,
            semantic_category=None,
            category_reasoning=None,
            raw_json=json.dumps(item, default=str),
            scraped_at=datetime.now().isoformat(),
            account_url=account_url,
        )


def _extract_datetime(item: dict) -> tuple[str | None, str | None, str | None]:
    """Extract date, time, and full timestamp from various Apify output formats."""
    # Try ISO timestamp fields (_postedAt_flat is set by from_apify_result for harvestapi format)
    raw_ts = (
        item.get("_postedAt_flat")
        or item.get("postedDate")
        or item.get("postedTimestamp")
        or item.get("publishedAt")
        or item.get("date")
    )

    if raw_ts:
        # Handle unix timestamps (milliseconds)
        if isinstance(raw_ts, (int, float)):
            if raw_ts > 1e12:
                raw_ts = raw_ts / 1000
            dt = datetime.fromtimestamp(raw_ts)
            return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S"), dt.isoformat()

        # Handle string timestamps
        if isinstance(raw_ts, str):
            for fmt in (
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ):
                try:
                    dt = datetime.strptime(raw_ts, fmt)
                    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S"), dt.isoformat()
                except ValueError:
                    continue
            # If parsing failed, return raw as timestamp
            return None, None, raw_ts

    # Try postedDateText like "2 days ago" — store as-is, no date parsing
    date_text = item.get("postedDateText") or item.get("timeAgo")
    if date_text:
        return None, None, date_text

    return None, None, None


def _extract_media(item: dict) -> tuple[str | None, str | None, str | None]:
    """Extract media type and URLs from Apify output."""
    # Only use "mediaType" — "type" is the post type ("post", "repost") not media type
    media_type = item.get("mediaType")

    # Collect all image URLs (postImages is harvestapi's field)
    image_list = []
    for key in ("postImages", "images", "imageUrls", "media"):
        val = item.get(key)
        if isinstance(val, list):
            for entry in val:
                if isinstance(entry, str):
                    image_list.append(entry)
                elif isinstance(entry, dict):
                    image_list.append(entry.get("url") or entry.get("src") or "")
    # Single image field
    for key in ("imageUrl", "image", "thumbnailUrl"):
        val = item.get(key)
        if isinstance(val, str) and val:
            image_list.append(val)

    # Collect all media URLs (video, document, etc.)
    media_list = []
    for key in ("videoUrl", "documentUrl", "articleUrl", "mediaUrl"):
        val = item.get(key)
        if isinstance(val, str) and val:
            media_list.append(val)
    media_list.extend(image_list)

    images = json.dumps(image_list) if image_list else None
    media_urls = json.dumps(media_list) if media_list else None

    if not media_type and image_list:
        media_type = "image"
    if not media_type and media_list:
        media_type = "media"

    return media_type, media_urls, images


def _to_int(val) -> int:
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        val = val.replace(",", "").strip()
        try:
            return int(val)
        except ValueError:
            return 0
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0
