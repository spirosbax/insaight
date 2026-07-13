import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "posts.db"

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
    db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
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
