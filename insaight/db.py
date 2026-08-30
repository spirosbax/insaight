import os
import sqlite3
from pathlib import Path

from . import paths


def _default_db_path() -> Path:
    """INSAIGHT_DB_PATH env var overrides the default <INSAIGHT_HOME>/posts.db."""
    env = os.environ.get("INSAIGHT_DB_PATH", "")
    return Path(env) if env else paths.home() / "posts.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_urn TEXT UNIQUE NOT NULL,
    post_url TEXT,
    author_name TEXT,
    author_profile_url TEXT,
    author_headline TEXT,
    content TEXT,
    posted_date TEXT,
    posted_time TEXT,
    posted_timestamp TEXT,
    num_likes INTEGER DEFAULT 0,
    num_comments INTEGER DEFAULT 0,
    num_shares INTEGER DEFAULT 0,
    media_type TEXT,
    media_urls TEXT,
    images TEXT,
    semantic_category TEXT,
    category_reasoning TEXT,
    raw_json TEXT,
    scraped_at TEXT,
    account_url TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_posts_account ON posts(account_url);
CREATE INDEX IF NOT EXISTS idx_posts_category ON posts(semantic_category);
CREATE INDEX IF NOT EXISTS idx_posts_posted ON posts(posted_timestamp);

CREATE TABLE IF NOT EXISTS people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT UNIQUE NOT NULL,
    linkedin_url TEXT,
    company_url TEXT NOT NULL,
    name TEXT,
    first_name TEXT,
    last_name TEXT,
    headline TEXT,
    current_titles TEXT,
    current_companies TEXT,
    location TEXT,
    scraped_at TEXT NOT NULL,
    raw_json TEXT,
    about TEXT,
    experience TEXT,
    education TEXT,
    skills TEXT,
    top_skills TEXT,
    certifications TEXT,
    languages TEXT,
    volunteer TEXT,
    projects TEXT,
    recommendations TEXT,
    follower_count INTEGER,
    connections_count INTEGER
);

CREATE INDEX IF NOT EXISTS idx_people_company ON people(company_url);

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comment_id TEXT UNIQUE NOT NULL,
    post_urn TEXT NOT NULL,
    post_url TEXT,
    parent_comment_id TEXT,
    is_reply INTEGER DEFAULT 0,
    author_name TEXT,
    author_profile_url TEXT,
    author_headline TEXT,
    text TEXT,
    posted_timestamp TEXT,
    num_likes INTEGER DEFAULT 0,
    num_replies INTEGER DEFAULT 0,
    raw_json TEXT,
    scraped_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_urn);
CREATE INDEX IF NOT EXISTS idx_comments_author ON comments(author_profile_url);

CREATE TABLE IF NOT EXISTS outreach (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_url TEXT NOT NULL,
    target_name TEXT,
    company TEXT,
    channel TEXT DEFAULT 'dm',
    variant TEXT,
    hook_type TEXT,
    message TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    outcome TEXT DEFAULT 'pending',
    reply_snippet TEXT,
    outcome_at TEXT,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_outreach_target ON outreach(target_url);
CREATE INDEX IF NOT EXISTS idx_outreach_outcome ON outreach(outcome);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

# Columns added after the initial release. Applied idempotently on every connection
# via ALTER TABLE so existing databases upgrade without manual migration.
PEOPLE_EXTENDED_COLUMNS = [
    ("about", "TEXT"),
    ("experience", "TEXT"),
    ("education", "TEXT"),
    ("skills", "TEXT"),
    ("top_skills", "TEXT"),
    ("certifications", "TEXT"),
    ("languages", "TEXT"),
    ("volunteer", "TEXT"),
    ("projects", "TEXT"),
    ("recommendations", "TEXT"),
    ("follower_count", "INTEGER"),
    ("connections_count", "INTEGER"),
]


def _migrate_people_columns(conn):
    existing = {row[1] for row in conn.execute("PRAGMA table_info(people)").fetchall()}
    for col, col_type in PEOPLE_EXTENDED_COLUMNS:
        if col not in existing:
            conn.execute(f"ALTER TABLE people ADD COLUMN {col} {col_type}")
    conn.commit()


def get_connection(db_path=None):
    db_path = Path(db_path) if db_path else _default_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn):
    conn.executescript(SCHEMA)
    conn.commit()
    _migrate_people_columns(conn)


def insert_post(conn, post):
    """Insert a post, returns True if new, False if duplicate."""
    try:
        cur = conn.execute(
            """INSERT OR IGNORE INTO posts
            (post_urn, post_url, author_name, author_profile_url, author_headline,
             content, posted_date, posted_time, posted_timestamp,
             num_likes, num_comments, num_shares,
             media_type, media_urls, images,
             semantic_category, category_reasoning,
             raw_json, scraped_at, account_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                post.post_urn,
                post.post_url,
                post.author_name,
                post.author_profile_url,
                post.author_headline,
                post.content,
                post.posted_date,
                post.posted_time,
                post.posted_timestamp,
                post.num_likes,
                post.num_comments,
                post.num_shares,
                post.media_type,
                post.media_urls,
                post.images,
                post.semantic_category,
                post.category_reasoning,
                post.raw_json,
                post.scraped_at,
                post.account_url,
            ),
        )
        conn.commit()
        # rowcount == 0 when INSERT OR IGNORE skips a duplicate URN
        return cur.rowcount > 0
    except sqlite3.IntegrityError:
        return False


def insert_posts(conn, posts):
    """Insert multiple posts, returns (new_count, duplicate_count)."""
    new = 0
    for post in posts:
        if insert_post(conn, post):
            new += 1
    return new, len(posts) - new


def update_category(conn, post_urn, category, reasoning):
    conn.execute(
        "UPDATE posts SET semantic_category = ?, category_reasoning = ? WHERE post_urn = ?",
        (category, reasoning, post_urn),
    )
    conn.commit()


def get_uncategorized_posts(conn, limit=50):
    return conn.execute(
        "SELECT post_urn, content FROM posts WHERE semantic_category IS NULL AND content IS NOT NULL LIMIT ?",
        (limit,),
    ).fetchall()


def get_stats(conn):
    row = conn.execute(
        """SELECT
            COUNT(*) as total_posts,
            COUNT(DISTINCT account_url) as accounts,
            COUNT(DISTINCT semantic_category) as categories,
            MIN(posted_timestamp) as earliest,
            MAX(posted_timestamp) as latest,
            SUM(CASE WHEN semantic_category IS NOT NULL THEN 1 ELSE 0 END) as categorized
        FROM posts"""
    ).fetchone()
    return dict(row)


def get_all_posts(conn):
    return conn.execute("SELECT * FROM posts ORDER BY posted_timestamp DESC").fetchall()


# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------

_PERSON_COLUMNS = (
    "profile_id", "linkedin_url", "company_url",
    "name", "first_name", "last_name",
    "headline", "current_titles", "current_companies",
    "location", "scraped_at", "raw_json",
    "about", "experience", "education", "skills", "top_skills",
    "certifications", "languages", "volunteer", "projects",
    "recommendations", "follower_count", "connections_count",
)


def _person_values(person) -> tuple:
    return tuple(getattr(person, col) for col in _PERSON_COLUMNS)


def insert_person(conn, person) -> bool:
    """Insert a person, returns True if new, False if duplicate profile_id."""
    placeholders = ", ".join(["?"] * len(_PERSON_COLUMNS))
    columns = ", ".join(_PERSON_COLUMNS)
    cur = conn.execute(
        f"INSERT OR IGNORE INTO people ({columns}) VALUES ({placeholders})",
        _person_values(person),
    )
    conn.commit()
    return cur.rowcount > 0


def upsert_person(conn, person) -> bool:
    """Insert or update a person by profile_id. Updates are partial:
    only non-None fields on the incoming Person overwrite existing data.
    This lets a Short-mode refresh coexist with a prior Full-mode enrichment
    without blanking out experience/education/etc.
    Returns True if a new row was inserted, False if updated.
    """
    existing = conn.execute(
        "SELECT profile_id FROM people WHERE profile_id = ?", (person.profile_id,)
    ).fetchone()

    if existing:
        updatable = [c for c in _PERSON_COLUMNS if c != "profile_id"]
        set_clauses = []
        values: list = []
        for col in updatable:
            val = getattr(person, col)
            if val is None:
                continue
            set_clauses.append(f"{col}=?")
            values.append(val)
        if set_clauses:
            values.append(person.profile_id)
            conn.execute(
                f"UPDATE people SET {', '.join(set_clauses)} WHERE profile_id=?",
                values,
            )
            conn.commit()
        return False
    return insert_person(conn, person)


def insert_people(conn, people) -> tuple[int, int]:
    """Upsert multiple people. Returns (new_count, updated_count)."""
    new = 0
    updated = 0
    for person in people:
        if upsert_person(conn, person):
            new += 1
        else:
            updated += 1
    return new, updated


def get_people(conn, company_url: str, role_query: str = "", limit: int = 50) -> list:
    """Return people for a company, optionally filtered by role keyword in headline or titles."""
    if role_query:
        rows = conn.execute(
            """SELECT * FROM people
               WHERE company_url = ?
               AND (headline LIKE ? OR current_titles LIKE ? OR name LIKE ?)
               ORDER BY name ASC LIMIT ?""",
            (company_url, f"%{role_query}%", f"%{role_query}%", f"%{role_query}%", limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM people WHERE company_url = ? ORDER BY name ASC LIMIT ?",
            (company_url, limit),
        ).fetchall()
    return rows


def get_people_stats(conn) -> dict:
    """Return people-related DB stats."""
    row = conn.execute(
        """SELECT
               COUNT(*) AS total_people,
               COUNT(DISTINCT company_url) AS companies_with_people,
               MAX(scraped_at) AS last_scraped
           FROM people"""
    ).fetchone()
    return dict(row)


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

_COMMENT_COLUMNS = (
    "comment_id", "post_urn", "post_url", "parent_comment_id", "is_reply",
    "author_name", "author_profile_url", "author_headline",
    "text", "posted_timestamp", "num_likes", "num_replies",
    "raw_json", "scraped_at",
)


def insert_comment(conn, comment) -> bool:
    """Insert a comment, returns True if new, False if duplicate comment_id."""
    placeholders = ", ".join(["?"] * len(_COMMENT_COLUMNS))
    columns = ", ".join(_COMMENT_COLUMNS)
    cur = conn.execute(
        f"INSERT OR IGNORE INTO comments ({columns}) VALUES ({placeholders})",
        tuple(getattr(comment, c) for c in _COMMENT_COLUMNS),
    )
    conn.commit()
    return cur.rowcount > 0


def insert_comments(conn, comments) -> tuple[int, int]:
    """Insert many. Returns (new_count, duplicate_count)."""
    new = 0
    for c in comments:
        if insert_comment(conn, c):
            new += 1
    return new, len(comments) - new


def get_comments(conn, post_urn: str, limit: int = 200) -> list:
    """Return all stored comments for a post, ordered by likes desc then time."""
    return conn.execute(
        """SELECT * FROM comments
           WHERE post_urn = ?
           ORDER BY num_likes DESC, posted_timestamp DESC
           LIMIT ?""",
        (post_urn, limit),
    ).fetchall()


# ---------------------------------------------------------------------------
# Outreach log + meta
# ---------------------------------------------------------------------------

# Outcomes that count as "got a reply" for rate calculations.
REPLIED_OUTCOMES = ("replied", "positive", "meeting")
VALID_OUTCOMES = ("pending", "replied", "positive", "meeting", "ghosted")


def get_meta(conn, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row else default


def set_meta(conn, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


def insert_outreach(
    conn,
    target_url: str,
    message: str,
    sent_at: str,
    target_name: str = "",
    company: str = "",
    channel: str = "dm",
    variant: str = "",
    hook_type: str = "",
    notes: str = "",
) -> int:
    """Insert an outreach record, returns the new row id."""
    cur = conn.execute(
        """INSERT INTO outreach
           (target_url, target_name, company, channel, variant, hook_type,
            message, sent_at, outcome, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
        (target_url, target_name, company, channel, variant, hook_type,
         message, sent_at, notes),
    )
    conn.commit()
    return cur.lastrowid


def update_outreach_outcome(
    conn,
    outreach_id: int,
    outcome: str,
    outcome_at: str,
    reply_snippet: str = "",
    notes: str = "",
) -> bool:
    """Set the outcome of an outreach record. Returns False if the id doesn't exist."""
    cur = conn.execute(
        """UPDATE outreach
           SET outcome = ?, outcome_at = ?,
               reply_snippet = CASE WHEN ? != '' THEN ? ELSE reply_snippet END,
               notes = CASE WHEN ? != '' THEN ? ELSE notes END
           WHERE id = ?""",
        (outcome, outcome_at, reply_snippet, reply_snippet, notes, notes, outreach_id),
    )
    conn.commit()
    return cur.rowcount > 0


def get_outreach(
    conn,
    outcome: str = "",
    target: str = "",
    limit: int = 30,
) -> list:
    """Query outreach records, newest first. target matches URL or name (substring)."""
    clauses = ["1=1"]
    params: list = []
    if outcome:
        clauses.append("outcome = ?")
        params.append(outcome)
    if target:
        clauses.append("(target_url LIKE ? OR target_name LIKE ? OR company LIKE ?)")
        params.extend([f"%{target}%"] * 3)
    params.append(limit)
    return conn.execute(
        f"""SELECT * FROM outreach
            WHERE {' AND '.join(clauses)}
            ORDER BY sent_at DESC LIMIT ?""",
        params,
    ).fetchall()


def get_outreach_breakdown(conn) -> dict:
    """Reply-rate breakdown by hook_type, variant, and channel.

    Only rows with a resolved outcome (not 'pending') enter the denominators,
    so freshly-sent messages don't drag rates down before they had a chance
    to be answered.
    """
    replied_case = (
        "SUM(CASE WHEN outcome IN ({}) THEN 1 ELSE 0 END)".format(
            ",".join(f"'{o}'" for o in REPLIED_OUTCOMES)
        )
    )
    result: dict = {}
    for dim in ("hook_type", "variant", "channel"):
        rows = conn.execute(
            f"""SELECT COALESCE(NULLIF({dim}, ''), 'unspecified') AS bucket,
                       COUNT(*) AS n,
                       {replied_case} AS replied
                FROM outreach
                WHERE outcome != 'pending'
                GROUP BY bucket ORDER BY n DESC"""
        ).fetchall()
        result[dim] = [
            {"bucket": r["bucket"], "n": r["n"], "replied": r["replied"],
             "reply_rate": round(r["replied"] / r["n"], 2) if r["n"] else 0.0}
            for r in rows
        ]
    totals = conn.execute(
        f"""SELECT COUNT(*) AS total,
                   SUM(CASE WHEN outcome = 'pending' THEN 1 ELSE 0 END) AS pending,
                   SUM(CASE WHEN outcome != 'pending' THEN 1 ELSE 0 END) AS resolved,
                   {replied_case} AS replied
            FROM outreach"""
    ).fetchone()
    result["totals"] = dict(totals)
    resolved = totals["resolved"] or 0
    result["totals"]["reply_rate"] = (
        round((totals["replied"] or 0) / resolved, 2) if resolved else 0.0
    )
    return result


def get_commenters_for_account(conn, account_url: str, limit: int = 50) -> list:
    """Return distinct commenters across all posts for an account, ranked by activity."""
    return conn.execute(
        """SELECT
               c.author_profile_url,
               MAX(c.author_name)     AS author_name,
               MAX(c.author_headline) AS author_headline,
               COUNT(*)               AS comment_count,
               SUM(c.num_likes)       AS total_likes
           FROM comments c
           JOIN posts p ON c.post_urn = p.post_urn
           WHERE p.account_url = ?
             AND c.author_profile_url IS NOT NULL
           GROUP BY c.author_profile_url
           ORDER BY comment_count DESC, total_likes DESC
           LIMIT ?""",
        (account_url, limit),
    ).fetchall()
