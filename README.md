# insaight

Turn LinkedIn into a prospect intelligence engine. Research people, analyze companies, and draft personalized cold outreach — all from natural language.

Insaight scrapes LinkedIn posts and employee profiles via [Apify](https://apify.com), stores them locally in SQLite, and exposes everything to Claude through a local [MCP server](https://modelcontextprotocol.io/). On top of the data layer sit eight composable [Claude Code skills](https://docs.anthropic.com/en/docs/claude-code/skills) that turn raw LinkedIn data into structured intelligence briefs and ready-to-send outreach messages — and a **memory loop** that learns your voice and which outreach strategies actually get replies.

```
"Research Acme Charging on LinkedIn"
  → fetches company posts + CEO's personal posts
  → produces structured intelligence brief with prospect scoring

"Draft outreach to their CEO"
  → personalized cold DM + email, two variants each

"Save to Notion"
  → persists everything under your configured Notion research page

"I sent it" ... "She replied!"
  → logged in the local ledger; after enough outcomes Insaight proposes
    evidence-backed updates to its learned style guide + outreach playbook
```

## How it works

```
                    ┌─────────────────────────────────────────────┐
                    │              Claude Code / Desktop          │
                    │                                             │
                    │  skills/                                    │
                    │    research-person / research-company        │
                    │    research-post / draft-post                │
                    │    draft-outreach / track-outreach           │
                    │    reflect / save-notion                     │
                    └──────────────┬──────────────────────────────┘
                                   │ MCP (natural language → tool calls)
                    ┌──────────────▼──────────────────────────────┐
                    │          mcp_server.py (17 tools)           │
                    └──────────────┬──────────────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────────────┐
                    │   SQLite (posts + people + outreach)        │
                    │   data/memory/ (style.md + playbook.md)     │
                    └──────────────┬──────────────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────────────┐
                    │       Apify (LinkedIn scraping actors)      │
                    └─────────────────────────────────────────────┘
```

**Data flows down once, then stays local.** After the initial scrape, all queries hit SQLite — zero repeated API cost. You only call Apify again when you want fresh data.

## Skills

Insaight ships eight composable skills that chain conversationally — each skill's output feeds the next.

| Skill | What it does | Trigger examples |
|-------|-------------|------------------|
| **research-person** | Intelligence brief on an individual from their LinkedIn posts: themes, focus areas, decision-maker signals, outreach hooks | "Research Jane Doe", "What is the CTO of X posting about?" |
| **research-company** | Company analysis from company posts + up to 3 C-level executives' personal posts. Includes prospect scoring rubric | "Analyze Acme Charging", "Evaluate X as a prospect" |
| **research-post** | Mine a single post's comment thread for warm leads, decision-makers, and competitor mentions | "Who engaged with this post?", "Research this LinkedIn post" |
| **draft-outreach** | Two variants (warm + direct) x two formats (LinkedIn DM + email) using intelligence from prior research | "Draft outreach to their CEO", "Write a cold email" |
| **draft-post** | Write a LinkedIn post in your company's voice, using your past posts as the style reference (+ optional visual brief) | "Write a LinkedIn post about X", "Make a post from this article" |
| **track-outreach** | Log sent messages and their outcomes in the local ledger | "I sent it", "She replied", "Mark as ghosted", "Meeting booked" |
| **reflect** | Analyze outcomes, propose evidence-backed updates to your style + playbook memory (you approve before saving) | "Run a reflection", "What's working in my outreach?" |
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

## The memory loop — learning what works

Instead of re-reading your entire sent-message history every session, Insaight
distills it into two small memory files that drafting reads at constant cost:

```
draft → send → "I sent it"        → logged in SQLite (log_outreach)
      → "she replied" / "ghosted" → outcome recorded (record_outcome)
      → every N outcomes          → reflection proposed (insaight-reflect)
      → you approve               → memory updated:
                                      data/memory/style.md     (your voice)
                                      data/memory/playbook.md  (what gets replies)
```

- **Outcomes are logged manually** — you tell Claude "he replied" or "mark as
  ghosted". No inbox scraping.
- **Reflection is evidence-based** — every playbook claim carries its counts
  ("question hooks: 4/9 replied vs statement hooks: 1/8"). Below n=10 a pattern
  is labeled a hypothesis, not a rule, so the loop doesn't overfit to noise.
- **Nothing is saved silently** — reflection shows you the proposed memory
  files and their evidence; you approve, edit, or reject.
- The reflection threshold is configurable via `REFLECT_EVERY` in `.env`
  (default 10 outcomes).

The ledger also powers prior-contact warnings ("you messaged this person 3
weeks ago — outcome: ghosted") whenever you research or draft.

## MCP Tools

The MCP server exposes 17 tools to Claude. Skills orchestrate these tools, but you can also call them directly in conversation.

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
| `log_outreach` | Record a sent message in the local ledger (flags prior contact) |
| `record_outcome` | Record replied / positive / meeting / ghosted; flags when a reflection is due |
| `list_outreach` | Query the ledger: prior-contact checks, pending sends, recent history |
| `get_outreach_stats` | Reply-rate breakdown by hook type, variant, and channel |
| `get_memory` | Read the learned style guide + strategy playbook |
| `update_memory` | Rewrite a memory file (only after you approve a reflection proposal) |

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
- **`REFLECT_EVERY`** — outcomes between memory reflections (optional, default 10)

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

**Claude Code** — register the server with the CLI:

```bash
claude mcp add insaight -s user \
  --env PYTHONPATH=/absolute/path/to/insaight \
  -- /absolute/path/to/insaight/.venv/bin/python3 -m src.mcp_server
```

Restart Claude after adding the config. The 17 insaight tools will appear automatically.

### 4. Install skills

**Claude Desktop** — go to **Settings → Skills** and click **Add skills**. Select all the `.md` files from the `skills/` directory (or drag and drop them in). The insaight skills will appear in Claude immediately — no restart needed.

**Claude Code** — copy each skill into your skills directory as a folder containing a `SKILL.md`:

```bash
for f in skills/insaight-*.md; do
  name=$(basename "$f" .md)
  mkdir -p ~/.claude/skills/"$name"
  cp "$f" ~/.claude/skills/"$name"/SKILL.md
done
```

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
NOTION_OUTREACH_LOG:  Sent Log            # legacy/optional — see note
COMPANY_NAME:         YourCompany         # used by draft-post
COMPANY_LINKEDIN:     your-company-slug   # your LinkedIn company page slug
```

Create `NOTION_RESEARCH_PAGE` in Notion if it doesn't exist yet — a blank page
where research briefs will be saved, one sub-page per person or company.

**Shared team setup:** if you're using Insaight as a team, everyone points their `CLAUDE.md` at the same `NOTION_RESEARCH_PAGE` for a shared pool of research briefs. Note that the outreach ledger and learned memory are local per machine — each person learns their own voice.

**Note on `NOTION_OUTREACH_LOG` (legacy):** earlier versions learned your writing style by re-reading a manually-maintained Notion page of sent messages. The [memory loop](#the-memory-loop--learning-what-works) replaces this — style now lives in `data/memory/style.md`, learned from logged sends. The Notion page is only consulted as a fallback on a fresh install that has no logged history yet; if you're starting from scratch you don't need to create it.

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
  mcp_server.py    — FastMCP server: 17 tools for Claude
  db.py            — SQLite schema + CRUD (posts, people, comments, outreach)
  memory.py        — Learned style + playbook memory files
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
  insaight-track-outreach.md     — Sent-message + outcome logging skill
  insaight-reflect.md            — Memory reflection skill (propose + approve)
  insaight-save-notion.md        — Notion persistence skill
config/
  accounts.txt     — LinkedIn URLs to track (one per line)
tests/             — pytest suite (hermetic, temp SQLite)
data/              — Local SQLite DB + memory files + raw dumps (gitignored)
```

## Apify actors

| Actor | What it scrapes | Approximate cost |
|-------|----------------|-----------------|
| `harvestapi/linkedin-profile-posts` | Posts from company or personal profiles | ~$1.50 / 1k posts |
| `harvestapi/linkedin-company-employees` | Employee and leadership data | ~$4 / 1k (Short) / ~$8 / 1k (Full) |
| `harvestapi/linkedin-profile-scraper` | Single-profile enrichment | ~$4 / 1k (~$10 / 1k with email search) |
| `harvestapi/linkedin-post-comments` | Comment threads on a post | see actor page |

Costs are the actors' published rates at time of writing — check the actor pages on Apify for current pricing.

## Data, privacy & terms

- **Everything stays local.** Scraped posts, people, the outreach ledger, and the
  learned memory live in SQLite and Markdown files on your machine. Nothing is
  sent anywhere except your own Apify/Anthropic/Notion accounts.
- **No inbox access.** Outcomes are logged because you say "she replied" — the
  tool never reads your LinkedIn messages or email.
- **LinkedIn terms.** Insaight fetches public LinkedIn data through third-party
  Apify actors. Automated collection of LinkedIn data may conflict with
  LinkedIn's Terms of Service; you are responsible for how you use this tool.
  Keep volumes reasonable and respect the people behind the profiles.

## Running tests

```bash
pytest tests/ -v
```

All tests run against temporary SQLite databases — no API calls, no credentials needed.

## License

[MIT](LICENSE)
