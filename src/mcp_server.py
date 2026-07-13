"""
MCP server for insaight — exposes LinkedIn posts stored in SQLite to Claude Desktop.

Tool calling order the agent should follow:
  1. list_accounts()                    → discover what companies/profiles are tracked + slugs
  2. scrape_profile(url, max_posts)     → fetch fresh posts from LinkedIn via Apify, store in DB
  3. scrape_people(url, ...)            → fetch company employees/leadership via Apify, store in DB
  4. scrape_person_profile(url, ...)    → enrich ONE person with full profile (experience, education, skills)
  5. list_posts(account, ...)           → slim index: metadata + 150-char snippet, NO full content
  6. get_posts([urn, urn, ...])         → batch-fetch full content only for chosen posts
  7. search_posts(query, ...)           → keyword search; returns full content (only matches)
  8. list_people(account, ...)          → query stored employees/leadership for a company
  9. scrape_post_comments(post_url, ...) → fetch comments + replies on a single post
 10. list_comments(post_url|post_urn, ...) → query stored comments for a post
 11. get_stats()                        → DB-wide overview

This staged approach avoids dumping thousands of tokens of post content up front.
"""

import json
import os
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from . import db, models, people as people_module, scraper, comments as comments_module

# Load APIFY_API_TOKEN (and any other vars) from the project .env
load_dotenv(Path(__file__).parent.parent / ".env")

mcp = FastMCP("insaight")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slug(url: str) -> str:
    """Extract a short human-readable slug from a LinkedIn URL.

    https://www.linkedin.com/company/acme-charging  →  acme-charging
    https://www.linkedin.com/in/jane-doe-12345678/recent-activity/all/  →  jane-doe-12345678
    """
    url = url.rstrip("/")
    # Remove trailing path segments like /recent-activity/all
    url = re.sub(r"/(recent-activity|posts|detail|activity).*$", "", url)
    return url.rstrip("/").split("/")[-1]


def _resolve_account(conn: sqlite3.Connection, account: str) -> str | None:
    """Accept a slug OR a full URL, return the exact stored account_url, or None."""
    if not account:
        return None
    account = account.strip()
    # Try exact match first
    row = conn.execute(
        "SELECT account_url FROM posts WHERE account_url = ? LIMIT 1", (account,)
    ).fetchone()
    if row:
        return row[0]
    # Try slug match (account_url ends with /<slug> or contains it)
    rows = conn.execute("SELECT DISTINCT account_url FROM posts").fetchall()
    for row in rows:
        if _slug(row[0]) == account or account in row[0]:
            return row[0]
    return None


def _snippet(content: str | None, chars: int = 150) -> str:
    if not content:
        return ""
    text = content.replace("\n", " ").strip()
    return text[:chars] + ("…" if len(text) > chars else "")


def _slim_row(row: dict) -> dict:
    """Metadata + short snippet — NO full content. ~80 tokens per post."""
    return {
        "urn": row["post_urn"],
        "url": row["post_url"],
        "account_slug": _slug(row["account_url"]),
        "author": row["author_name"],
        "posted": row["posted_timestamp"] or row["posted_date"],
        "likes": row["num_likes"],
        "comments": row["num_comments"],
        "shares": row["num_shares"],
        "category": row["semantic_category"],
        "snippet": _snippet(row["content"]),
    }


def _full_row(row: dict) -> dict:
    """Full content + metadata. Omit raw storage fields."""
    return {
        "urn": row["post_urn"],
        "url": row["post_url"],
        "account_slug": _slug(row["account_url"]),
        "author": row["author_name"],
        "posted": row["posted_timestamp"] or row["posted_date"],
        "likes": row["num_likes"],
        "comments": row["num_comments"],
        "shares": row["num_shares"],
        "category": row["semantic_category"],
        "content": row["content"],
    }


def _days_ago_clause(days_ago: int | None) -> tuple[str, list]:
    """Build a WHERE fragment for filtering by recency.

    Stored timestamps are naive ISO strings (no timezone) so the cutoff must
    also be naive — mixing tz-aware ISO (e.g. '+00:00') breaks SQLite string
    comparison when values are near the boundary.
    """
    if not days_ago or days_ago <= 0:
        return "", []
    cutoff = (datetime.now() - timedelta(days=days_ago)).isoformat()
    return "AND posted_timestamp >= ?", [cutoff]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def list_accounts() -> str:
    """
    List all tracked LinkedIn accounts (companies and profiles) in the database.

    Returns each account's slug (short name), full URL, post count, and date of
    most recent post. ALWAYS call this first to discover what accounts are
    available and learn the correct slugs to use in other tools.
    """
    conn = db.get_connection()
    db.init_db(conn)
    rows = conn.execute(
        """
        SELECT
            account_url,
            COUNT(*) AS post_count,
            MAX(posted_timestamp) AS latest_post,
            MIN(posted_timestamp) AS earliest_post
        FROM posts
        GROUP BY account_url
        ORDER BY latest_post DESC
        """
    ).fetchall()
    conn.close()

    if not rows:
        return "No accounts in the database yet."

    accounts = [
        {
            "slug": _slug(r["account_url"]),
            "full_url": r["account_url"],
            "post_count": r["post_count"],
            "latest_post": r["latest_post"],
            "earliest_post": r["earliest_post"],
        }
        for r in rows
    ]
    return json.dumps(accounts, ensure_ascii=False, indent=2)


@mcp.tool()
def list_posts(
    account: str = "",
    category: str = "",
    days_ago: int = 0,
    min_engagement: int = 0,
    limit: int = 30,
) -> str:
    """
    Return a slim index of posts (metadata + 150-char snippet, NO full content).

    Use this to survey what posts exist before deciding which ones to read in full
    via get_posts(). Fetching slim records first is far more token-efficient.

    Args:
        account:        Slug (e.g. "acme-charging") or full LinkedIn URL.
                        Empty = all accounts. Use list_accounts() to find slugs.
        category:       Filter by semantic category (e.g. "product", "hiring").
        days_ago:       Only posts from the last N days (0 = no limit).
        min_engagement: Only posts where likes+comments+shares >= this value.
        limit:          Max posts to return (default 30, max 100).
    """
    limit = min(limit, 100)
    conn = db.get_connection()
    db.init_db(conn)

    clauses = ["1=1"]
    params: list = []

    resolved = _resolve_account(conn, account)
    if account and not resolved:
        conn.close()
        return f"No account matching '{account}'. Call list_accounts() to see available accounts."
    if resolved:
        clauses.append("account_url = ?")
        params.append(resolved)

    if category:
        clauses.append("semantic_category = ?")
        params.append(category)

    recency_clause, recency_params = _days_ago_clause(days_ago)
    if recency_clause:
        clauses.append(recency_clause.lstrip("AND "))
        params.extend(recency_params)

    if min_engagement > 0:
        clauses.append("(num_likes + num_comments + num_shares) >= ?")
        params.append(min_engagement)

    sql = f"""
        SELECT * FROM posts
        WHERE {' AND '.join(clauses)}
        ORDER BY posted_timestamp DESC
        LIMIT ?
    """
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    if not rows:
        return "No posts matched the given filters."

    return json.dumps([_slim_row(dict(r)) for r in rows], ensure_ascii=False, indent=2)


@mcp.tool()
def get_posts(urns: list[str]) -> str:
    """
    Fetch full content for a specific list of posts by their URNs.

    Use this after list_posts() to read only the posts you actually need.
    Accepts up to 20 URNs per call. URNs come from the 'urn' field in list_posts results.

    Args:
        urns: List of post URN strings to fetch (max 20).
    """
    if not urns:
        return "No URNs provided."
    urns = urns[:20]

    conn = db.get_connection()
    db.init_db(conn)
    placeholders = ",".join("?" * len(urns))
    rows = conn.execute(
        f"SELECT * FROM posts WHERE post_urn IN ({placeholders}) ORDER BY posted_timestamp DESC",
        urns,
    ).fetchall()
    conn.close()

    if not rows:
        return "No posts found for the given URNs."

    return json.dumps([_full_row(dict(r)) for r in rows], ensure_ascii=False, indent=2)


@mcp.tool()
def search_posts(
    query: str,
    account: str = "",
    days_ago: int = 0,
    limit: int = 15,
) -> str:
    """
    Full-text search across post content (case-insensitive keyword/phrase match).

    Returns full content for matched posts only — use for targeted lookups
    rather than open-ended browsing (use list_posts for that).

    Args:
        query:    Word or phrase to search for in post text.
        account:  Slug or full URL to restrict search to one account (optional).
        days_ago: Only search posts from the last N days (0 = no limit).
        limit:    Max results (default 15, max 50).
    """
    limit = min(limit, 50)
    conn = db.get_connection()
    db.init_db(conn)

    clauses = ["content LIKE ?"]
    params: list = [f"%{query}%"]

    resolved = _resolve_account(conn, account)
    if account and not resolved:
        conn.close()
        return f"No account matching '{account}'. Call list_accounts() to see available accounts."
    if resolved:
        clauses.append("account_url = ?")
        params.append(resolved)

    recency_clause, recency_params = _days_ago_clause(days_ago)
    if recency_clause:
        clauses.append(recency_clause.lstrip("AND "))
        params.extend(recency_params)

    sql = f"""
        SELECT * FROM posts
        WHERE {' AND '.join(clauses)}
        ORDER BY posted_timestamp DESC
        LIMIT ?
    """
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    if not rows:
        return f"No posts matched '{query}'."

    return json.dumps([_full_row(dict(r)) for r in rows], ensure_ascii=False, indent=2)


@mcp.tool()
def get_stats() -> str:
    """
    Return a DB-wide overview: total posts, accounts, date range, category breakdown.
    Useful for a quick orientation before diving into posts.
    """
    conn = db.get_connection()
    db.init_db(conn)
    stats = db.get_stats(conn)

    accounts = conn.execute(
        "SELECT account_url, COUNT(*) as n FROM posts GROUP BY account_url ORDER BY n DESC"
    ).fetchall()
    cats = conn.execute(
        """SELECT semantic_category, COUNT(*) as n FROM posts
           WHERE semantic_category IS NOT NULL
           GROUP BY semantic_category ORDER BY n DESC"""
    ).fetchall()
    conn.close()

    stats["accounts"] = [
        {"slug": _slug(r["account_url"]), "url": r["account_url"], "posts": r["n"]}
        for r in accounts
    ]
    stats["categories"] = [dict(r) for r in cats]
    return json.dumps(stats, ensure_ascii=False, indent=2)


@mcp.tool()
def scrape_profile(
    url: str,
    max_posts: int = 30,
) -> str:
    """
    Scrape fresh LinkedIn posts from any company or personal profile URL via Apify
    and store them in the database. Works for profiles NOT yet in the database.

    Use this when the user asks about a LinkedIn account that list_accounts() doesn't
    return, or when they want up-to-date posts for an existing account.

    Requires APIFY_API_TOKEN to be set in the project .env file.

    Args:
        url:       Full LinkedIn URL of the company or person to scrape.
                   Examples:
                     https://www.linkedin.com/company/acme-charging
                     https://www.linkedin.com/in/williamhgates
        max_posts: Maximum number of posts to fetch (default 30, max 100).
    """
    max_posts = min(max_posts, 100)

    api_token = os.environ.get("APIFY_API_TOKEN", "")
    if not api_token:
        return (
            "APIFY_API_TOKEN is not set. "
            "Add it to the .env file at the project root and restart the MCP server."
        )

    url = url.strip()
    if not url.startswith("https://www.linkedin.com/"):
        return f"'{url}' does not look like a LinkedIn URL. Expected https://www.linkedin.com/..."

    try:
        items = scraper.scrape_account(api_token, url, max_posts)
    except Exception as e:
        return f"Apify scrape failed: {e}"

    if not items:
        return f"No posts returned for {url}. The profile may be private or the URL may be incorrect."

    posts = [models.Post.from_apify_result(item, url) for item in items]

    conn = db.get_connection()
    db.init_db(conn)
    new_count, dup_count = db.insert_posts(conn, posts)
    conn.close()

    account_slug = _slug(url)
    return json.dumps({
        "account_slug": account_slug,
        "url": url,
        "scraped": len(items),
        "new_posts_stored": new_count,
        "duplicates_skipped": dup_count,
        "message": (
            f"Scraped {len(items)} posts from {account_slug}: "
            f"{new_count} new, {dup_count} already in DB. "
            f"Call list_posts(account='{account_slug}') to browse them."
        ),
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def scrape_people(
    url: str,
    job_titles: list[str] | None = None,
    max_items: int = 50,
    full_mode: bool = False,
) -> str:
    """
    Scrape and store company employees/leadership from LinkedIn via Apify.

    Results are stored in the database so subsequent calls to list_people() are
    instant without any Apify cost. Run this once per company; re-run only when
    you need fresher data (people data is updated by upsert, not duplicated).

    Args:
        url:        Full LinkedIn company URL.
                    Example: https://www.linkedin.com/company/acme-charging
        job_titles: Optional list of job titles to filter by on LinkedIn.
                    Example: ["CEO", "Founder", "CTO", "Head of", "Director"]
                    Leave empty to scrape all visible employees (up to max_items).
        max_items:  Maximum number of profiles to fetch (default 50, max 200).
                    For leadership only, use 10–20 with specific job_titles.
        full_mode:  If True, uses Full profile scraper mode ($8/1k) to also fetch
                    about, experience, education, skills, certifications, languages,
                    volunteer, projects, recommendations. Default False (Short mode,
                    $4/1k) which returns only name, headline, location, current role.
                    Use True when you need commonality-mining data for outreach.
    """
    max_items = min(max_items, 200)

    api_token = os.environ.get("APIFY_API_TOKEN", "")
    if not api_token:
        return (
            "APIFY_API_TOKEN is not set. "
            "Add it to the .env file at the project root and restart the MCP server."
        )

    url = url.strip()
    if not url.startswith("https://www.linkedin.com/"):
        return f"'{url}' does not look like a LinkedIn URL. Expected https://www.linkedin.com/..."

    try:
        items = scraper.scrape_people(
            api_token, url, job_titles or None, max_items, full_mode=full_mode
        )
    except Exception as e:
        return f"Apify scrape failed: {e}"

    if not items:
        return (
            f"No people returned for {url}. "
            "The company page may have no visible employees, or job_titles filter was too narrow."
        )

    persons = [people_module.Person.from_apify_result(item, url) for item in items]

    conn = db.get_connection()
    db.init_db(conn)
    new_count, updated_count = db.insert_people(conn, persons)
    conn.close()

    slug = _slug(url)
    mode_label = "Full" if full_mode else "Short"
    return json.dumps({
        "account_slug": slug,
        "url": url,
        "mode": mode_label,
        "scraped": len(items),
        "new_people_stored": new_count,
        "updated": updated_count,
        "message": (
            f"Scraped {len(items)} people from {slug} ({mode_label} mode): "
            f"{new_count} new, {updated_count} updated. "
            f"Call list_people(account='{slug}') to browse them."
        ),
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def scrape_person_profile(
    url: str,
    with_email: bool = False,
    company_url: str = "",
) -> str:
    """
    Enrich ONE LinkedIn profile with full data (experience, education, skills,
    certifications, languages, volunteer, projects, recommendations, about).

    Use this when you need commonality hooks for outreach — e.g. overlapping
    past employers, shared schools, mutual volunteer work, common languages.
    The result is upserted into the people table, so existing short-mode data
    is preserved and the extended fields are merged in.

    Uses harvestapi/linkedin-profile-scraper ($4/1k without email, $10/1k with).

    Args:
        url:         Full LinkedIn profile URL.
                     Example: https://www.linkedin.com/in/williamhgates
        with_email:  If True, also runs email search ($10/1k instead of $4/1k).
                     Default False.
        company_url: Optional LinkedIn company URL to associate this person with.
                     If empty, uses the person's current company from Apify (or
                     falls back to the profile URL itself).
    """
    api_token = os.environ.get("APIFY_API_TOKEN", "")
    if not api_token:
        return (
            "APIFY_API_TOKEN is not set. "
            "Add it to the .env file at the project root and restart the MCP server."
        )

    url = url.strip()
    if not url.startswith("https://www.linkedin.com/"):
        return f"'{url}' does not look like a LinkedIn URL. Expected https://www.linkedin.com/..."

    try:
        item = scraper.scrape_person_profile(api_token, url, with_email=with_email)
    except Exception as e:
        return f"Apify scrape failed: {e}"

    if not item:
        return f"No profile returned for {url}. The profile may be private or the URL may be incorrect."

    # Pick a company_url to associate: explicit param > first currentPosition company > profile URL
    assoc = company_url.strip() if company_url else ""
    if not assoc:
        cp = item.get("currentPosition") or []
        if cp and isinstance(cp, list):
            assoc = cp[0].get("companyLinkedinUrl") or cp[0].get("companyUrl") or ""
    if not assoc:
        assoc = url  # fallback so the NOT NULL constraint is satisfied

    person = people_module.Person.from_apify_result(item, assoc)

    conn = db.get_connection()
    db.init_db(conn)
    is_new = db.upsert_person(conn, person)
    conn.close()

    enriched_fields = [
        f for f in ("about", "experience", "education", "skills", "top_skills",
                    "certifications", "languages", "volunteer", "projects",
                    "recommendations")
        if getattr(person, f)
    ]

    return json.dumps({
        "linkedin_url": person.linkedin_url,
        "name": person.name,
        "headline": person.headline,
        "location": person.location,
        "company_url": person.company_url,
        "stored_as": "new" if is_new else "updated",
        "enriched_fields": enriched_fields,
        "follower_count": person.follower_count,
        "connections_count": person.connections_count,
        "message": (
            f"Enriched {person.name or 'profile'} with fields: "
            f"{', '.join(enriched_fields) or 'none'}. "
            f"Call list_people(account='{_slug(person.company_url)}') to see full data."
        ),
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def list_people(
    account: str,
    role: str = "",
    limit: int = 50,
) -> str:
    """
    List stored employees/leadership for a company from the local database.

    This is instant (no Apify call). If the result is empty, call scrape_people()
    first to populate the database for this company.

    Args:
        account: Slug (e.g. "acme-charging") or full LinkedIn company URL.
                 Use list_accounts() to discover available slugs.
        role:    Optional keyword to filter by — matched against name, headline,
                 and job titles. Examples: "CEO", "founder", "sales", "engineer".
                 Leave empty to return all stored people.
        limit:   Max results to return (default 50).
    """
    conn = db.get_connection()
    db.init_db(conn)

    resolved = _resolve_account(conn, account)
    if not resolved:
        # Also check the people table directly (company may have people but no posts)
        slug = account.strip().rstrip("/").split("/")[-1]
        row = conn.execute(
            "SELECT DISTINCT company_url FROM people WHERE company_url LIKE ?",
            (f"%{slug}%",),
        ).fetchone()
        resolved = row[0] if row else None

    if not resolved:
        conn.close()
        return (
            f"No account matching '{account}'. "
            "Call list_accounts() to see tracked accounts, or call scrape_people(url=...) "
            "to fetch people for a new company."
        )

    rows = db.get_people(conn, resolved, role_query=role, limit=limit)
    conn.close()

    if not rows:
        msg = f"No people stored for '{_slug(resolved)}'"
        if role:
            msg += f" matching role '{role}'"
        return msg + ". Call scrape_people() to populate the database."

    def _parse_json(raw):
        if not raw:
            return None
        try:
            val = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
        return val or None

    # JSON-array columns that belong to the Full-mode enrichment.
    JSON_COLS = (
        "current_titles", "current_companies",
        "experience", "education", "skills", "top_skills",
        "certifications", "languages", "volunteer", "projects",
        "recommendations",
    )
    SCALAR_COLS = ("about", "follower_count", "connections_count")

    result = []
    for r in rows:
        entry = {
            "name": r["name"],
            "headline": r["headline"],
            "linkedin_url": r["linkedin_url"],
            "location": r["location"],
            "scraped_at": r["scraped_at"],
        }
        for col in JSON_COLS:
            try:
                val = _parse_json(r[col])
            except (IndexError, KeyError):
                val = None
            if val:
                entry[col] = val
        for col in SCALAR_COLS:
            try:
                val = r[col]
            except (IndexError, KeyError):
                val = None
            if val:
                entry[col] = val
        result.append(entry)

    return json.dumps(result, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Post comments
# ---------------------------------------------------------------------------

def _extract_post_urn_from_url(url: str) -> str | None:
    """LinkedIn post URLs include the activity URN. Two common shapes:
       .../posts/<author>_<slug>-activity-7451209045283254272-XYZ
       .../feed/update/urn:li:activity:7451209045283254272
    """
    m = re.search(r"activity[:-](\d+)", url)
    if m:
        return f"urn:li:activity:{m.group(1)}"
    return None


@mcp.tool()
def scrape_post_comments(
    post_url: str,
    max_items: int = 50,
    include_replies: bool = True,
    profile_mode: str = "short",
) -> str:
    """
    Scrape and store comments on a LinkedIn post via Apify.

    Use this to research who is engaging with a specific post — comments often
    reveal warm leads, decision-makers, competitor mentions, and pain points.

    Args:
        post_url:        Full LinkedIn post URL. Either /posts/<author>_<slug>-activity-XXX
                         or /feed/update/urn:li:activity:XXX form is accepted.
        max_items:       Max comments (and replies) to fetch (default 50, capped at 200).
        include_replies: If True, also fetch nested replies (default True).
        profile_mode:    "short" (free profile data attached to each comment) or
                         "main" ($0.002/profile, more author detail). Default "short".
    """
    max_items = min(max_items, 200)

    api_token = os.environ.get("APIFY_API_TOKEN", "")
    if not api_token:
        return (
            "APIFY_API_TOKEN is not set. "
            "Add it to the .env file at the project root and restart the MCP server."
        )

    post_url = post_url.strip()
    if not post_url.startswith("https://www.linkedin.com/"):
        return f"'{post_url}' does not look like a LinkedIn post URL."

    post_urn = _extract_post_urn_from_url(post_url)
    if not post_urn:
        return (
            f"Could not extract post URN from '{post_url}'. "
            "Expected an activity ID in the URL (e.g. ...activity-7451209045283254272-XYZ)."
        )

    try:
        items = scraper.scrape_post_comments(
            api_token,
            [post_url],
            max_items=max_items,
            scrape_replies=include_replies,
            profile_mode=profile_mode,
        )
    except Exception as e:
        return f"Apify scrape failed: {e}"

    if not items:
        return f"No comments returned for {post_url}. The post may have no comments or may be inaccessible."

    parsed = comments_module.flatten_apify_items(items, post_urn=post_urn, post_url=post_url)

    conn = db.get_connection()
    db.init_db(conn)
    new_count, dup_count = db.insert_comments(conn, parsed)
    conn.close()

    top_likes = max((c.num_likes for c in parsed), default=0)
    return json.dumps({
        "post_url": post_url,
        "post_urn": post_urn,
        "scraped": len(items),
        "new_comments_stored": new_count,
        "duplicates_skipped": dup_count,
        "top_comment_likes": top_likes,
        "message": (
            f"Scraped {len(items)} comments: {new_count} new, {dup_count} already in DB. "
            f"Call list_comments(post_urn='{post_urn}') to read them."
        ),
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def list_comments(
    post_urn: str = "",
    post_url: str = "",
    limit: int = 100,
    min_likes: int = 0,
    include_replies: bool = True,
) -> str:
    """
    List stored comments for a post, ranked by likes desc then time.

    Provide either post_urn (e.g. "urn:li:activity:7451209045283254272") or
    post_url (the full LinkedIn URL — the URN is extracted automatically).

    Args:
        post_urn:        Post URN. Use this OR post_url.
        post_url:        Full LinkedIn post URL. The URN is extracted from it.
        limit:           Max comments returned (default 100).
        min_likes:       Only return comments with at least this many likes.
        include_replies: If False, only top-level comments are returned.
    """
    if not post_urn and post_url:
        post_urn = _extract_post_urn_from_url(post_url) or ""
    if not post_urn:
        return "Provide either post_urn or post_url. Call scrape_post_comments() first if you haven't."

    conn = db.get_connection()
    db.init_db(conn)
    rows = db.get_comments(conn, post_urn, limit=limit)
    conn.close()

    if not rows:
        return (
            f"No comments stored for {post_urn}. "
            f"Call scrape_post_comments(post_url=...) first."
        )

    result = []
    for r in rows:
        if r["num_likes"] < min_likes:
            continue
        if not include_replies and r["is_reply"]:
            continue
        result.append({
            "comment_id": r["comment_id"],
            "is_reply": bool(r["is_reply"]),
            "parent_comment_id": r["parent_comment_id"],
            "author": r["author_name"],
            "author_headline": r["author_headline"],
            "author_url": r["author_profile_url"],
            "posted": r["posted_timestamp"],
            "likes": r["num_likes"],
            "replies": r["num_replies"],
            "text": r["text"],
        })

    return json.dumps(result, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run()
