# Insaight — LinkedIn Intelligence Tool

Scrapes LinkedIn company pages and personal profiles via Apify, stores in SQLite,
and exposes them to Claude via MCP for prospect research and cold outreach.

Skills live in `skills/` — each is independently invocable and they chain
conversationally (research → outreach → save).

---

## Setup

Edit these values once before first use. All skills read them from here.

```
NOTION_WORKSPACE:     YourWorkspaceName   # your Notion workspace / team name
NOTION_RESEARCH_PAGE: Prospect Research   # parent page for research briefs
NOTION_OUTREACH_LOG:  Sent Log            # your sent-messages archive (READ-ONLY)
COMPANY_NAME:         YourCompany         # your company (used by draft-post)
COMPANY_LINKEDIN:     your-company-slug   # your LinkedIn company page slug
```

---

## Insaight MCP — Tool Reference

All tools must be loaded first via `tool_search(query="insaight")`.

| Tool | Purpose | Key params |
|------|---------|------------|
| `insaight:list_accounts` | Show all tracked accounts + slugs | — |
| `insaight:get_stats` | DB-wide overview (counts, date range, categories) | — |
| `insaight:list_posts` | Slim index: metadata + 150-char snippet, NO full text | `account`, `days_ago`, `limit`, `min_engagement` |
| `insaight:search_posts` | Full-text keyword search → returns full content | `query`, `account`, `days_ago`, `limit` |
| `insaight:get_posts` | Fetch full content for specific URNs (max 20) | `urns: string[]` |
| `insaight:scrape_profile` | Scrape fresh posts from any LinkedIn URL via Apify | `url`, `max_posts` |
| `insaight:list_people` | List stored employees/leadership from DB (instant) | `account`, `role`, `limit` |
| `insaight:scrape_people` | Scrape + store company leadership via Apify | `url`, `job_titles`, `max_items`, `full_mode` |
| `insaight:scrape_person_profile` | Enrich ONE person with full profile (experience, education, skills, etc.) | `url`, `with_email`, `company_url` |
| `insaight:scrape_post_comments` | Scrape comments on a LinkedIn post (with replies + author info) | `post_url`, `max_items`, `include_replies`, `profile_mode` |
| `insaight:list_comments` | List stored comments for a post, ranked by likes | `post_urn` or `post_url`, `limit`, `min_likes`, `include_replies` |
| `insaight:log_outreach` | Record a SENT message in the ledger (flags prior contact) | `target_url`, `message`, `target_name`, `channel`, `variant`, `hook_type` |
| `insaight:record_outcome` | Record replied/positive/meeting/ghosted; flags when reflection is due | `outreach_id` or `target_url`, `outcome`, `reply_snippet` |
| `insaight:list_outreach` | Query the outreach ledger (prior-contact checks, pending review) | `outcome`, `target`, `limit`, `full` |
| `insaight:get_outreach_stats` | Reply-rate breakdown by hook/variant/channel + reflection state | — |
| `insaight:get_memory` | Read distilled style + playbook memory (draft skills read THIS) | — |
| `insaight:update_memory` | Rewrite a memory file — only after user approval | `kind`, `content`, `mark_reflection_done` |

### Efficient reading pattern

```
1. list_accounts()                    → find the correct slug
   └─ not found? → scrape_profile(url) to fetch and store fresh posts

2. list_posts(account=slug, limit=50) → survey what exists (slim, token-cheap)

3. get_posts(urns=[...])              → read full content for chosen posts only
   OR search_posts(query=...)         → targeted lookup when you know what to look for

4. list_people(account=slug)          → check stored leadership
   └─ empty? → scrape_people(url, job_titles=["CEO","Founder","CTO","Head of"])

5. scrape_person_profile(url=...)     → enrich ONE person with full profile
   (experience, education, skills, volunteer, languages, projects, recommendations)
   Use for commonality mining — overlapping companies, schools, volunteer work.

6. list_comments(post_url=...)        → read commenters on a post (free if already scraped)
   └─ empty? → scrape_post_comments(post_url, include_replies=True)
   Use for mining a thread for warm leads, decision-makers, competitor mentions.
```

**Never call `get_posts` on all URNs at once.** Select the most signal-rich posts
to stay within the 20-URN limit per call.

### Cost warnings

`scrape_profile` and `scrape_people` call Apify (costs tokens/money). Only use
them when the account isn't tracked yet or data is stale. `list_people` is
free/instant — always try it first.

### Account slug format

- Company page: `acme-charging` (matches the LinkedIn URL slug)
- Personal profile: `jane-doe-12345678` (matches the LinkedIn profile ID)

### Engagement benchmarks (EV charging niche, NL/EU market)

- < 10 likes = low
- 10–40 likes = normal
- 40+ likes = high signal post, read in full

### Outreach memory loop

The ledger + memory system replaces re-reading a raw sent-log every session:

1. **Log every send** (`log_outreach`) with the exact sent text + `variant` + `hook_type`.
2. **Record every outcome** (`record_outcome`) when the user reports a reply,
   meeting, or gives up (`ghosted`). The user decides when something is ghosted.
3. After `REFLECT_EVERY` outcomes (env var, default 10), `record_outcome`
   returns `reflection_due: true` → offer the **insaight-reflect** skill.
4. Reflection proposes updates to `data/memory/style.md` (voice) and
   `data/memory/playbook.md` (strategies with evidence counts) — the user
   approves before `update_memory` is called. Never overwrite memory silently.
5. **draft-outreach reads `get_memory()`**, not raw history — constant token
   cost regardless of ledger size.

Playbook discipline: every claim carries its evidence ("question hooks: 4/9
replied"); below n=10 a pattern is a hypothesis, not a rule.

### Tips

- **Personal profiles vs company pages**: Personal profiles (founders, CEOs) often
  reveal more strategic signal than corporate pages. If both are tracked, read both.
- **Dutch/Flemish content**: Many Dutch CPOs post in Dutch. Translate mentally and
  include in your analysis — don't skip non-English posts.
- **Low post volume**: If the account has < 10 posts, supplement with
  `web_search("[company name] EV charging news 2025 2026")`.
- **Category field**: The `category` field in Insaight data is currently unpopulated.
  Do your own thematic grouping from snippets.
- **Time gaps**: A long gap in posting (> 3 months) is itself a signal — note it.

---

## Notion Integration

Two Notion locations matter for every skill run:

### 1. [NOTION_RESEARCH_PAGE] (read + write)

Parent page containing one sub-page per researched person/company.

- **Location**: `[NOTION_WORKSPACE]` → `[NOTION_RESEARCH_PAGE]`
- **Page naming**: `[Name] — [YYYY-MM-DD]`
- **Used by**: research skills (read existing page as context, then write updated brief), save-notion (the writer)
- **Find it**:
  ```
  notion:search(query="[NOTION_RESEARCH_PAGE]")
  ```

### 2. [NOTION_OUTREACH_LOG] (READ-ONLY — legacy fallback)

**The outreach ledger + memory system (see "Outreach memory loop") has replaced
this page.** Sends live in the SQLite `outreach` table; style lives in
`data/memory/style.md`. Only fall back to this Notion page when `get_memory()`
reports nothing learned AND `list_outreach()` is empty (fresh install with
pre-existing Notion history).

- **Location**: `[NOTION_WORKSPACE]` → `[NOTION_RESEARCH_PAGE]` → `[NOTION_OUTREACH_LOG]`
- **NEVER write to this page.** The user maintains it manually.
- **Find it**:
  ```
  notion:search(query="[NOTION_OUTREACH_LOG]")
  ```

### Workflow integration

| Skill | Before run | After run |
|-------|-----------|-----------|
| research-person / research-company | Check for existing research page (load as context). Check `list_outreach(target=...)` for prior messages to this target (warn user). | **Auto-save** brief to [NOTION_RESEARCH_PAGE]. No prompt. |
| research-post | Check for existing research page (load as context). Cross-check named commenters via `list_outreach`. | **Auto-save** brief to [NOTION_RESEARCH_PAGE]. No prompt. |
| draft-outreach | `get_memory()` for style + playbook. `list_outreach(target=...)` for prior contact. | Do not auto-save. When the user says they SENT it → log via track-outreach. |
| track-outreach | — | `log_outreach` on send; `record_outcome` on reply/ghost. Offer insaight-reflect when `reflection_due`. |
| reflect | `get_outreach_stats` + `list_outreach(full=true)` + `get_memory`. | Propose updates with evidence → on approval `update_memory` (last call: `mark_reflection_done=true`). |
| save-notion | — | Internal helper the research skills invoke. Also exposed as explicit "save to Notion" command. |

### Session caching

Fetch memory (`get_memory`) **once per conversation** and reuse it. Same for
any legacy Notion pages you had to load — never re-fetch on iteration.

### Notion MCP loading

The Notion MCP is separate from insaight. If `notion:search` / `notion:fetch` /
`notion:create-pages` aren't available, load them first:
```
tool_search(query="notion search fetch create")
```
If Notion MCP isn't connected at all, tell the user:
> "Notion MCP isn't connected. Connect it at claude.ai → Settings →
> Integrations, then retry. Research will proceed but won't auto-save."
