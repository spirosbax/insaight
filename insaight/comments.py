"""
Comment model — normalises output from harvestapi/linkedin-post-comments.

The actor returns a flat list where replies and top-level comments are
distinguishable by a parent reference field. Field naming varies between
actor versions, so the parser accepts several aliases.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Comment:
    comment_id: str
    post_urn: str
    post_url: str | None
    parent_comment_id: str | None
    is_reply: int  # 0 or 1, sqlite-friendly bool
    author_name: str | None
    author_profile_url: str | None
    author_headline: str | None
    text: str | None
    posted_timestamp: str | None
    num_likes: int
    num_replies: int
    raw_json: str
    scraped_at: str

    @classmethod
    def from_apify_result(
        cls,
        item: dict,
        post_urn: str,
        post_url: str | None = None,
        parent_comment_id: str | None = None,
    ) -> "Comment":
        comment_id = (
            item.get("id")
            or item.get("commentUrn")
            or item.get("urn")
            or item.get("commentId")
        )
        if not comment_id:
            # Fallback: hash author + text + timestamp so re-runs dedup
            raw = (
                (item.get("commentary") or item.get("text") or item.get("content") or "")
                + "|" + str(item.get("actor") or item.get("author") or item.get("authorProfileUrl") or "")
                + "|" + str(item.get("createdAt") or item.get("postedAt") or "")
            )
            comment_id = f"hash:{hashlib.sha256(raw.encode()).hexdigest()[:32]}"

        # Author lives under `actor` in the harvestapi shape, but other actors
        # may use a flat `author` field or top-level keys.
        actor = item.get("actor") or item.get("author")
        if isinstance(actor, dict) and actor:
            author_name = (
                actor.get("name")
                or " ".join(filter(None, [actor.get("firstName"), actor.get("lastName")])).strip()
                or None
            )
            author_profile_url = (
                actor.get("linkedinUrl")
                or actor.get("profileUrl")
                or actor.get("url")
            )
            # `position` is the headline for people; for companies it's "X followers"
            author_headline = actor.get("headline") or actor.get("position") or actor.get("subtitle")
        else:
            author_name = item.get("authorName")
            author_profile_url = item.get("authorProfileUrl") or item.get("authorUrl")
            author_headline = item.get("authorHeadline")

        text = (
            item.get("commentary")
            or item.get("text")
            or item.get("content")
            or item.get("body")
        )

        posted_timestamp = (
            item.get("createdAt")
            or item.get("postedAt")
            or item.get("postedTimestamp")
            or item.get("timestamp")
        )
        if posted_timestamp is not None:
            posted_timestamp = str(posted_timestamp)

        # Engagement: harvestapi nests counts under `engagement`, others use flat keys.
        engagement = item.get("engagement") or {}
        num_likes = (
            engagement.get("likes")
            if isinstance(engagement, dict)
            else None
        )
        if num_likes is None:
            num_likes = item.get("numLikes") or item.get("likes") or item.get("reactionsCount") or 0

        num_replies = (
            engagement.get("comments")
            if isinstance(engagement, dict)
            else None
        )
        if num_replies is None:
            # Some actors put replies as a list at top level; len() works for that
            replies_field = item.get("numReplies") or item.get("repliesCount") or item.get("replies")
            if isinstance(replies_field, list):
                num_replies = len(replies_field)
            elif isinstance(replies_field, (int, float)):
                num_replies = int(replies_field)
            else:
                num_replies = 0

        # Reply detection: explicit parent passed in (from flatten), or fields on the item.
        parent_id = parent_comment_id or (
            item.get("parentCommentUrn")
            or item.get("parentUrn")
            or item.get("parentCommentId")
            or item.get("replyToCommentUrn")
        )
        is_reply_flag = bool(item.get("isReply")) or bool(parent_id)

        def _coerce_int(v) -> int:
            if isinstance(v, bool):
                return int(v)
            if isinstance(v, int):
                return v
            if isinstance(v, float):
                return int(v)
            if isinstance(v, str) and v.isdigit():
                return int(v)
            return 0

        return cls(
            comment_id=str(comment_id),
            post_urn=post_urn,
            post_url=post_url,
            parent_comment_id=str(parent_id) if parent_id else None,
            is_reply=1 if is_reply_flag else 0,
            author_name=author_name,
            author_profile_url=author_profile_url,
            author_headline=author_headline,
            text=text,
            posted_timestamp=posted_timestamp,
            num_likes=_coerce_int(num_likes),
            num_replies=_coerce_int(num_replies),
            raw_json=json.dumps(item, default=str),
            scraped_at=datetime.now().isoformat(),
        )


def flatten_apify_items(
    items: list[dict],
    post_urn: str,
    post_url: str | None = None,
) -> list[Comment]:
    """
    The harvestapi/linkedin-post-comments actor returns top-level comments with
    nested `replies` arrays. Flatten into a single list of Comment objects with
    parent_comment_id set on replies.
    """
    out: list[Comment] = []
    for item in items:
        top = Comment.from_apify_result(item, post_urn=post_urn, post_url=post_url)
        out.append(top)
        replies = item.get("replies")
        if isinstance(replies, list):
            for reply in replies:
                if not isinstance(reply, dict):
                    continue
                out.append(
                    Comment.from_apify_result(
                        reply,
                        post_urn=post_urn,
                        post_url=post_url,
                        parent_comment_id=top.comment_id,
                    )
                )
    return out
