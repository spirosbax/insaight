# insaight

Turn LinkedIn into a prospect intelligence engine. Research people, analyze companies, and draft personalized cold outreach — all from natural language.

Insaight scrapes LinkedIn posts and employee profiles via [Apify](https://apify.com), stores them locally in SQLite, and exposes everything to Claude through a local [MCP server](https://modelcontextprotocol.io/). On top of the data layer sit six composable [Claude Code skills](https://docs.anthropic.com/en/docs/claude-code/skills) that turn raw LinkedIn data into structured intelligence briefs and ready-to-send outreach messages.

```
"Research Acme Charging on LinkedIn"
  → fetches company posts + CEO's personal posts
  → produces structured intelligence brief with prospect scoring

"Draft outreach to their CEO"
  → personalized cold DM + email, two variants each

"Save to Notion"
  → persists everything under your configured Notion research page
```

## How it works

```
                    ┌─────────────────────────────────────────────┐
                    │              Claude Code / Desktop          │
                    │                                             │
                    │  skills/                                    │
                    │    insaight-research-person.md               │
                    │    insaight-research-company.md              │
                    │    insaight-research-post.md                 │
                    │    insaight-draft-outreach.md                │
                    │    insaight-save-notion.md                   │
                    └──────────────┬──────────────────────────────┘
                                   │ MCP (natural language → tool calls)
                    ┌──────────────▼──────────────────────────────┐
                    │          mcp_server.py (11 tools)           │
                    └──────────────┬──────────────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────────────┐
                    │            SQLite (posts + people)          │
                    └──────────────┬──────────────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────────────┐
                    │       Apify (LinkedIn scraping actors)      │
                    └─────────────────────────────────────────────┘
```

**Data flows down once, then stays local.** After the initial scrape, all queries hit SQLite — zero repeated API cost. You only call Apify again when you want fresh data.

## Skills

Insaight ships six composable skills that chain conversationally — each skill's output feeds the next.

| Skill | What it does | Trigger examples |
|-------|-------------|------------------|
| **research-person** | Intelligence brief on an individual from their LinkedIn posts: themes, focus areas, decision-maker signals, outreach hooks | "Research Jane Doe", "What is the CTO of X posting about?" |
| **research-company** | Company analysis from company posts + up to 3 C-level executives' personal posts. Includes prospect scoring rubric | "Analyze Acme Charging", "Evaluate X as a prospect" |
| **research-post** | Mine a single post's comment thread for warm leads, decision-makers, and competitor mentions | "Who engaged with this post?", "Research this LinkedIn post" |
| **draft-outreach** | Two variants (warm + direct) x two formats (LinkedIn DM + email) using intelligence from prior research | "Draft outreach to their CEO", "Write a cold email" |
| **draft-post** | Write a LinkedIn post in your company's voice, using your past posts as the style reference (+ optional visual brief) | "Write a LinkedIn post about X", "Make a post from this article" |
| **save-notion** | Persist the brief + outreach to Notion | "Save to Notion" |

Skills are plain Markdown files with YAML frontmatter — easy to read, fork, and customize.

### Typical flows

**Company prospecting:**
```
research company → draft outreach → save to Notion
```

**Person-first outreach:**
```
research person → draft outreach
```

**Quick qualification:**
```
research company → read the prospect evaluation → decide whether to pursue
```

## MCP Tools

The MCP server exposes 11 tools to Claude. Skills orchestrate these tools, but you can also call them directly in conversation.

| Tool | Purpose |
|------|---------|
| `list_accounts` | Discover tracked companies and personal profiles |
| `scrape_profile` | Fetch fresh posts for any LinkedIn URL (via Apify) |
| `scrape_people` | Fetch company employees and leadership (Short or Full mode) |
| `scrape_person_profile` | Enrich ONE person with full profile: experience, education, skills, volunteer, languages, projects — for commonality mining |
| `list_posts` | Token-cheap index: metadata + 150-char snippet |
| `get_posts` | Full content for selected posts by URN (max 20 per call) |
| `search_posts` | Full-text keyword search across post content |
| `list_people` | Query stored employees/leadership (instant, free) |
| `scrape_post_comments` | Fetch a post's comment thread with author info (via Apify) |
| `list_comments` | Query stored comments for a post, ranked by likes |
| `get_stats` | Database overview: counts, date range, categories |

### Why this two-step reading pattern?

`list_posts` returns slim metadata (~80 tokens per post). You scan snippets, pick the most interesting posts, then `get_posts` fetches only those in full. This avoids dumping thousands of tokens of content you'll never use.

## Setup

### 1. Clone and install

```bash
git clone https://github.com/spirosbax/insaight.git
cd insaight
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
```

Edit `.env` and add your tokens:
- **`APIFY_API_TOKEN`** — get one at [apify.com](https://apify.com) (free tier available)
- **`ANTHROPIC_API_KEY`** — only needed for post categorization (optional)

### 3. Connect to Claude

**Claude Desktop** — add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "insaight": {
      "command": "/absolute/path/to/insaight/.venv/bin/python3",
      "args": ["-m", "src.mcp_server"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/insaight"
      }
    }
  }
}
```

**Claude Code** — add to `~/.claude/settings.json` under `mcpServers`, same format.

Restart Claude after adding the config. The 8 insaight tools will appear automatically.

### 4. Install skills

Open Claude Desktop, go to **Settings → Skills** and click **Add skills**. Select all the `.md` files from the `skills/` directory (or drag and drop them in). The insaight skills will appear in Claude immediately — no restart needed.

### 5. Connect the Notion MCP

The research and save skills write briefs to Notion. To enable this, connect the Notion integration in Claude:

1. Open Claude Desktop → **Settings → Integrations**
2. Find **Notion** and click **Connect**
3. Authorize with your Notion account and grant access to the workspace you want to use

Once connected, Claude can search, read, and create pages in your Notion. No config file changes needed — it's handled entirely through the GUI.

### 6. Configure Notion pages and your company

Edit the config block at the top of `CLAUDE.md` to match your Notion workspace and company:

```
NOTION_WORKSPACE:     YourWorkspaceName
NOTION_RESEARCH_PAGE: Prospect Research
NOTION_OUTREACH_LOG:  Sent Log
COMPANY_NAME:         YourCompany         # used by draft-post
COMPANY_LINKEDIN:     your-company-slug   # your LinkedIn company page slug
```

Create the two pages in Notion if they don't exist yet:

- **`NOTION_RESEARCH_PAGE`** — a blank page where research briefs will be saved, one sub-page per person or company
- **`NOTION_OUTREACH_LOG`** — a page where you manually log every cold message you send; the draft-outreach skill reads this to match your writing style

**Shared team setup:** if you're using Insaight as a team, everyone points their `CLAUDE.md` at the same pages:

```
NOTION_WORKSPACE:     <your shared workspace name>
NOTION_RESEARCH_PAGE: Prospect Research
NOTION_OUTREACH_LOG:  Sent Log
```

This gives everyone a shared pool of research briefs under `NOTION_RESEARCH_PAGE`.

**Note on the outreach log:** `NOTION_OUTREACH_LOG` is used to learn your personal writing style when drafting cold messages. If it's a shared log, the style extraction will blend everyone's voice and drafts won't sound like any one person in particular. If that's a problem, give each person their own log and point their config at it:

```
NOTION_OUTREACH_LOG: Sent Log — Alice
```

## CLI

A standalone CLI is included for batch operations outside Claude:

```bash
# Scrape posts from tracked accounts
python -m src.cli scrape --accounts config/accounts.txt

# Scrape without categorization (faster, no Anthropic API needed)
python -m src.cli scrape --accounts config/accounts.txt --no-categorize

# Database stats
python -m src.cli stats

# Export to CSV or JSON
python -m src.cli export --format csv --output posts.csv
```

## Project structure

```
src/
  mcp_server.py    — FastMCP server: 8 tools for Claude
  db.py            — SQLite schema + CRUD (posts + people tables)
  scraper.py       — Apify actor wrappers
  models.py        — Post model + Apify data normalization
  people.py        — Person model + Apify data normalization
  comments.py      — Comment model + post-comment scraping
  categorizer.py   — Claude-powered post categorization
  cli.py           — Click CLI for batch operations
skills/
  insaight-research-person.md    — Person intelligence skill
  insaight-research-company.md   — Company intelligence skill
  insaight-research-post.md      — Post comment-thread mining skill
  insaight-draft-outreach.md     — Cold outreach drafting skill
  insaight-draft-post.md         — Company-voice LinkedIn post drafting skill
  insaight-save-notion.md        — Notion persistence skill
config/
  accounts.txt     — LinkedIn URLs to track (one per line)
tests/             — pytest suite (hermetic, in-memory SQLite)
data/              — Local SQLite DB + raw dumps (gitignored)
```

## Apify actors

| Actor | What it scrapes | Approximate cost |
|-------|----------------|-----------------|
| `harvestapi/linkedin-profile-posts` | Posts from company or personal profiles | ~$1.50 / 1k posts |
| `harvestapi/linkedin-company-employees` | Employee and leadership data | ~$4 / 1k profiles |

## Running tests

```bash
pytest tests/ -v
```

All tests use in-memory SQLite — no API calls, no credentials needed.

## License

MIT
