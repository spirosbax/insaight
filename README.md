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
                    │          mcp_server.py (18 tools)           │
                    └──────────────┬──────────────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────────────┐
                    │   ~/.insaight/  SQLite (posts, people,      │
                    │   outreach) + memory/ (style, playbook)     │
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
                                      ~/.insaight/memory/style.md     (your voice)
                                      ~/.insaight/memory/playbook.md  (what gets replies)
```

- **Outcomes are logged manually** — you tell Claude "he replied" or "mark as
  ghosted". No inbox scraping.
- **Reflection is evidence-based** — every playbook claim carries its counts
  ("question hooks: 4/9 replied vs statement hooks: 1/8"). Below n=10 a pattern
  is labeled a hypothesis, not a rule, so the loop doesn't overfit to noise.
- **Nothing is saved silently** — reflection shows you the proposed memory
  files and their evidence; you approve, edit, or reject.
- The reflection threshold is configurable via `REFLECT_EVERY` in `~/.insaight/.env`
  (default 10 outcomes).

The ledger also powers prior-contact warnings ("you messaged this person 3
weeks ago — outcome: ghosted") whenever you research or draft.

## MCP Tools

The MCP server exposes 18 tools to Claude. Skills orchestrate these tools, but you can also call them directly in conversation.

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
| `get_config` | Read your Notion pages + company config (`~/.insaight/config.md`) |

### Why this two-step reading pattern?

`list_posts` returns slim metadata (~80 tokens per post). You scan snippets, pick the most interesting posts, then `get_posts` fetches only those in full. This avoids dumping thousands of tokens of content you'll never use.

## Setup

You need an [Apify](https://apify.com) API token (free tier is fine) and
[`uv`](https://docs.astral.sh/uv/) installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`).

### Claude Code — one plugin, everything included

```
/plugin marketplace add spirosbax/insaight
/plugin install insaight@insaight
```

That registers the MCP server (run via `uvx`, no clone or venv) **and** installs
all eight skills. Then give it your token:

```bash
mkdir -p ~/.insaight && echo "APIFY_API_TOKEN=apify_api_..." >> ~/.insaight/.env
```

Restart Claude Code. Say *"research Acme Charging on LinkedIn"* and you're off.

> **Prefer to let Claude do it?** Paste this into Claude Code:
> *"Install the insaight plugin from github.com/spirosbax/insaight, then help
> me add my Apify token and fill in ~/.insaight/config.md."*

### Claude Desktop

Add to `claude_desktop_config.json` (macOS:
`~/Library/Application Support/Claude/`, Windows: `%APPDATA%\Claude\`):

```json
{
  "mcpServers": {
    "insaight": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/spirosbax/insaight", "insaight"],
      "env": { "APIFY_API_TOKEN": "apify_api_..." }
    }
  }
}
```

Restart Claude Desktop, then add the skills: **Settings → Skills → Add skills**
and select the `SKILL.md` files under `skills/` (download the repo as a zip
first, or `git clone` it).

### Configure Notion pages and your company (optional)

The first time a skill calls `get_config`, Insaight writes
`~/.insaight/config.md` with placeholders. Edit it:

```
NOTION_WORKSPACE:     YourWorkspaceName   # your Notion workspace / team name
NOTION_RESEARCH_PAGE: Prospect Research   # parent page for research briefs
NOTION_OUTREACH_LOG:  Sent Log            # legacy/optional — see note below
COMPANY_NAME:         YourCompany         # used by draft-post
COMPANY_LINKEDIN:     your-company-slug   # your LinkedIn company page slug
```

Create `NOTION_RESEARCH_PAGE` in Notion if it doesn't exist yet — a blank page
where research briefs will be saved, one sub-page per person or company. To
let Claude write there, connect Notion under **Settings → Integrations** (Claude
Desktop) or `claude mcp add` the Notion MCP (Claude Code). Without Notion,
research still works — briefs just aren't auto-saved.

**Shared team setup:** everyone points their config at the same
`NOTION_RESEARCH_PAGE` for a shared pool of briefs. The outreach ledger and
learned memory are local per machine — each person learns their own voice.

**Note on `NOTION_OUTREACH_LOG` (legacy):** earlier versions learned your writing
style by re-reading a manually-maintained Notion page of sent messages. The
[memory loop](#the-memory-loop--learning-what-works) replaces this — style now
lives in `~/.insaight/memory/style.md`, learned from logged sends. The Notion
page is only consulted as a fallback on a fresh install with no logged history.

### Where things live

Everything Insaight stores is under `~/.insaight/` (override with
`INSAIGHT_HOME`):

```
~/.insaight/
  .env         APIFY_API_TOKEN, ANTHROPIC_API_KEY (optional), REFLECT_EVERY
  config.md    Notion pages + company (read by get_config)
  posts.db     SQLite: posts, people, comments, outreach ledger
  memory/      style.md + playbook.md (learned by the reflect skill)
```

### Developer install

```bash
git clone https://github.com/spirosbax/insaight.git && cd insaight
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pytest -q
claude mcp add insaight -s user -- "$PWD/.venv/bin/insaight"   # local checkout instead of uvx
```

A checkout with a `data/` directory uses that as `INSAIGHT_HOME`, so the DB
stays inside the repo (gitignored) while developing.

## CLI

A standalone CLI is included for batch operations outside Claude (`uvx --from git+https://github.com/spirosbax/insaight insaight-cli`, or just `insaight-cli` in a dev install):

```bash
# Scrape posts from tracked accounts
insaight-cli scrape --accounts config/accounts.txt

# Scrape without categorization (faster, no Anthropic API needed)
insaight-cli scrape --accounts config/accounts.txt --no-categorize

# Database stats
insaight-cli stats

# Export to CSV or JSON
insaight-cli export --format csv --output posts.csv
```

## Project structure

```
insaight/
  mcp_server.py    — FastMCP server: 18 tools for Claude
  db.py            — SQLite schema + CRUD (posts, people, comments, outreach)
  memory.py        — Learned style + playbook memory files
  paths.py         — Resolves INSAIGHT_HOME (~/.insaight by default)
  scraper.py       — Apify actor wrappers
  models.py        — Post model + Apify data normalization
  people.py        — Person model + Apify data normalization
  comments.py      — Comment model + post-comment scraping
  categorizer.py   — Claude-powered post categorization
  cli.py           — Click CLI for batch operations
skills/<name>/SKILL.md
  research-person, research-company, research-post, draft-outreach,
  draft-post, track-outreach, reflect, save-notion
.claude-plugin/    — Claude Code plugin + marketplace manifests
.mcp.json          — MCP server definition used by the plugin
config/accounts.txt— LinkedIn URLs for the batch CLI (one per line)
tests/             — pytest suite (hermetic, temp SQLite)
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
pytest -q
```

All tests run against temporary SQLite databases — no API calls, no credentials needed.

## License

[MIT](LICENSE)
