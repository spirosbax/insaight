---
name: insaight-research-company
description: "Analyze a company's LinkedIn posts and C-level executive posts using the Insaight MCP connector to build a structured intelligence profile covering past trajectory, current priorities, and future direction — then evaluate the company as a prospect. Trigger when the user asks to: research a company, analyze what a company is focused on, evaluate a prospect, understand a company's strategy from social signals, or qualify a company for outreach. Trigger phrases: 'research [company]', 'analyze [company]', 'check Insaight for [company]', 'what is [company] posting about', 'evaluate [company] as prospect'. This skill is for companies — for individual person research, use insaight-research-person instead."
---

# Insaight — Company Research

Build a structured intelligence brief on a company from their LinkedIn posts
and their leadership's personal posts. Includes prospect evaluation.

Shared tool reference and reading patterns are in CLAUDE.md — refer to them
throughout this workflow.

---

## Workflow

### Step 0 — Check Notion first (always)

Before touching Apify or SQLite, check what you already know. See CLAUDE.md →
Notion Integration for locations.

**0a. Existing research page:**
```
notion:search(query="[Company Name]")
```
If a page exists under [NOTION_RESEARCH_PAGE], fetch it and load as context. Your
job becomes: update, don't re-do. Note the last research date and decide what
to refresh (usually: recent posts, role changes, executive personnel).

**0b. Prior messages ([NOTION_OUTREACH_LOG]):**
```
notion:search(query="[NOTION_OUTREACH_LOG]")
→ notion:fetch([page_id])   # cache for the whole conversation
```
Scan for any mention of this company or its executives. If found, surface:
> "⚠️ I see you already messaged [Name, Role] at [Company] on [approx date].
> Is this a follow-up, or do you want different entry points?"

Proceed to Step 1 only after the user confirms.

### Step 1 — Orient

```
insaight:list_accounts()   # discover what's tracked
insaight:get_stats()       # understand date range and volume
```

If the target company is **not** in the tracked accounts:
```
insaight:scrape_profile(url="https://www.linkedin.com/company/[slug]", max_posts=50)
```

### Step 2 — Survey company posts (slim scan)

```
insaight:list_posts(account=[company-slug], limit=50)
```

Group posts mentally by theme as you scan snippets:
- Product / technology announcements
- Hiring / team growth
- Partnerships / customers / logos
- Thought leadership / market takes
- Events / trade shows
- Company milestones / funding
- Pain points / challenges they surface

### Step 3 — Deep-read selected posts

Pick 8–15 posts that give the broadest signal across different themes and time
periods. Prioritise:
- Highest engagement (likes + comments + shares)
- Oldest post (anchors the "past" narrative)
- Most recent post (anchors current state)
- Any posts that hint at future direction (roadmap, hiring roles, partnerships)

```
insaight:get_posts(urns=[...chosen urns...])
```

Also run targeted searches for key topics:
```
insaight:search_posts(query="pricing / expansion / partnership / hiring / roadmap")
```

### Step 4 — C-level executive expansion

This is what distinguishes company research from a simple post scan. Executive
personal posts often reveal more strategic signal than the corporate page.

**4a. Check stored leadership:**
```
insaight:list_people(account=[company-slug])
```

If empty:
```
insaight:scrape_people(
  url="https://www.linkedin.com/company/[slug]",
  job_titles=["CEO", "Founder", "CTO", "COO", "Head of", "VP"],
  max_items=10
)
```

**4b. Select up to 3 key executives** (CEO/Founder first, then CTO, then others).

**4c. For each selected executive**, check if their personal profile is tracked:
```
insaight:list_accounts()  # look for their personal slug
```

If not tracked, ask the user before scraping (Apify cost):
> "I found [Name], [Title] at [Company]. Their personal LinkedIn posts aren't
> tracked yet. Want me to scrape their profile? This calls Apify."

If approved:
```
insaight:scrape_profile(url=[executive's linkedin_url], max_posts=30)
```

**4d. Read executive posts** using the same slim-scan → deep-read pattern:
```
insaight:list_posts(account=[executive-slug], limit=30)
insaight:get_posts(urns=[...top 5-8 posts...])
```

**Cost guardrails:**
- Max 3 executives scraped per company research
- Always try `list_people` and `list_accounts` before scraping
- Ask the user before each `scrape_profile` call on a personal profile

### Step 5 — Build the intelligence brief

Structure your output with these exact headings. Be concrete — quote or
paraphrase specific posts with approximate dates. Avoid vague generalisations.
Note where insights come from executive personal posts vs the company page.

---

#### 🏢 Company Snapshot
- What they do, who they serve, rough scale (chargers, cities, countries)
- Any stated positioning or differentiation
- Key leadership identified (names + titles)

#### 📜 Past — Where they came from
- Founding story or early milestones visible in posts
- Key pivots or product evolutions
- Historical partnerships or notable wins
- How tone/focus has shifted over time

#### ⚡ Present — What they're focused on right now
- Current product priorities (what they're shipping or promoting)
- Active geographies / markets
- Hiring signals (what roles → infer what they're building)
- Who they're partnering with
- Any friction or complaints they're surfacing publicly
- **Executive signals**: What are the CEO/CTO personally focused on?
  Anything they post about that the company page doesn't cover?

#### 🔭 Future — Where they're heading
- Explicit roadmap hints (new markets, new products, expansions)
- Hiring for roles that don't exist yet (→ build vs. buy signals)
- Conference/event presence (→ who they want to impress)
- Strategic partnerships in progress
- **Executive signals**: Forward-looking statements from personal posts

#### 🎯 Prospect Evaluation

Rate fit across these dimensions (High / Medium / Low + one-line rationale):

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| CPO scale (charger fleet) | | |
| Inbound support volume | | |
| Technical sophistication | | |
| Openness to AI / automation | | |
| Decision-maker visibility on LI | | |
| Likely entry point | | |

**Overall verdict:** Strong / Moderate / Weak prospect — and why in 2–3 sentences.

#### ❓ Open Questions
Things you couldn't determine from posts that would affect the verdict.

---

### Step 6 — Auto-save to Notion

After delivering the brief, **always** save it to Notion. No prompt, no
confirmation. Invoke the save-notion skill internally or call the Notion
MCP tools directly.

- If an existing page was found in Step 0a, **update it** (don't duplicate).
- Otherwise create: `[Company Name] — [YYYY-MM-DD]` under [NOTION_RESEARCH_PAGE].
- Report one line after saving: `Saved to Notion: [page title]`.

If Notion MCP is unavailable, tell the user once at the end — don't block
the research output.

---

## Output format guidance

- Lead with the 🎯 Prospect Evaluation if the user's primary goal is to qualify
- Lead with the full brief if they want to understand the company first
- Always end with Open Questions — it shows honest analysis
- After auto-saving, suggest: "Want me to draft outreach?"
