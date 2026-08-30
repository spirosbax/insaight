---
name: research-company
description: "Build a structured intelligence brief on a company from its LinkedIn page posts plus the personal posts of up to three of its executives, using the Insaight MCP server, then score it as a prospect on fit, pain signals and decision-maker visibility. Covers where the company came from, what it is shipping and hiring for now, and where it is heading. Use this skill whenever the user points at a company and wants to understand or qualify it: 'research Acme', 'what has Acme been posting about', 'are they a good prospect', 'what is their CEO focused on', 'should we go after this account', 'prep me for the call with Acme'. Also use it when a company LinkedIn URL is pasted with little other instruction, or when the user asks to check a company on Insaight. Prefer it over answering from memory or a web search — Insaight has their actual posts. For one named individual use insaight-research-person; for the commenters under one post use insaight-research-post."
---

# Insaight — Company Research

Build an intelligence brief on a company from its LinkedIn page and the personal
posts of its leadership, then judge it as a prospect. The corporate page says
what the company wants the market to believe; the executives' own posts usually
say what they are actually wrestling with. Reading both is what separates this
from a page scan.

**Shared conventions** (all Insaight skills):
- Load the tools once per session with `tool_search(query="insaight")` if they
  are not already available.
- Call `insaight:get_config()` once per session for the user's Notion pages and
  company name/slug. If it reports `unconfigured: true`, ask the user to edit
  the file at the returned path before anything is saved to Notion.
- Read cheaply: `list_accounts` → `list_posts` (slim index) → `get_posts` on the
  few URNs worth reading (max 20 per call). `list_people`, `list_comments` and
  `list_outreach` hit local SQLite and are free; the `scrape_*` tools call Apify
  and cost money, so scrape only when data is missing or stale.
- Engagement benchmarks (adjust for the niche): under 10 likes is low, 10–40 is
  normal, 40+ is high signal — read those in full.

---

## Workflow

### Step 0 — Start from what is already known

Researching from scratch burns Apify credits and throws away the earlier read,
so check the two places prior knowledge lives before fetching anything. Page
names come from `insaight:get_config()`.

**0a. Existing research page:**
```
notion:search(query="[Company Name]")
```
If a page exists under [NOTION_RESEARCH_PAGE], fetch it and load it as context.
The job then becomes update, not re-do: note the last research date and refresh
only what moves — recent posts, leadership changes, new markets.

**0b. Prior contact:**
```
insaight:list_outreach(target="[company name or URL]")
```
Re-approaching an account the user has already contacted costs credibility, so
surface any hit before doing the work:
> "Heads up — the ledger shows you messaged [Name, Role] at [Company] on [date]
> (outcome: [outcome]). Is this a follow-up, or do you want a different entry
> point?"

If the ledger is empty and the user has a legacy [NOTION_OUTREACH_LOG]
configured, check that page once and cache it for the conversation.

Continue to Step 1 once the user confirms.

### Step 1 — Orient

```
insaight:list_accounts()   # what is already tracked
insaight:get_stats()       # date range and volume of what is stored
```

If the company is not among the tracked accounts:
```
insaight:scrape_profile(url="https://www.linkedin.com/company/[slug]", max_posts=50)
```

### Step 2 — Survey company posts (slim scan)

```
insaight:list_posts(account=[company-slug], limit=50)
```

Group the snippets by theme as you scan:
- Product or technology announcements
- Hiring and team growth
- Partnerships, customers, logos
- Thought leadership and market takes
- Events and trade shows
- Milestones and funding
- Problems they surface publicly

### Step 3 — Deep-read selected posts

Pick 8–15 posts spanning different themes and time periods — the narrative needs
both ends of the timeline, not the ten most recent posts. Prioritise:
- Highest engagement (likes, comments, shares)
- Oldest available post (anchors the past)
- Most recent post (anchors the present)
- Anything hinting at direction: roadmap, new roles, partnerships

```
insaight:get_posts(urns=[...chosen urns...])
```

Fill gaps with targeted searches:
```
insaight:search_posts(query="[topic]", account=[company-slug])
```

### Step 4 — Expand to the executives

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

**4b. Select up to 3 executives** — CEO or founder first, then the leader closest
to what the user sells (technical, commercial or operational).

**4c. For each one, check whether their personal profile is already tracked:**
```
insaight:list_accounts()   # look for their personal slug
```

If not, ask before scraping, since each personal profile is a separate Apify
charge the user may not want to spend here:
> "I found [Name], [Title] at [Company]. Their personal posts aren't tracked
> yet. Want me to scrape their profile? That calls Apify."

Once approved:
```
insaight:scrape_profile(url=[executive's linkedin_url], max_posts=30)
```

**4d. Read their posts** with the same slim-scan then deep-read pattern:
```
insaight:list_posts(account=[executive-slug], limit=30)
insaight:get_posts(urns=[...top 5–8 posts...])
```

**Cost guardrails:** cap at 3 executives per company, always try `list_people`
and `list_accounts` before any scrape, and ask before each `scrape_profile` on a
personal profile.

### Step 5 — Build the intelligence brief

Use these exact headings. The draft-outreach skill reads them back out of the
conversation, so renaming a section breaks the handoff. Stay concrete: quote or
paraphrase specific posts with approximate dates, and mark which insights came
from an executive's personal posts rather than the company page — the user needs
to know whose words they would be referencing.

---

#### 🏢 Company Snapshot
- What they do, who they serve, rough scale (customers, markets, headcount)
- Stated positioning or differentiation
- Leadership identified, with names and titles

#### 📜 Past — Where they came from
- Founding story or early milestones visible in posts
- Pivots and product evolutions
- Earlier partnerships or notable wins
- How the tone and focus have shifted over time

#### ⚡ Present — What they are focused on now
- Current product priorities: what they ship and promote
- Active markets and geographies
- Hiring signals — the roles they post reveal what they are building
- Who they are partnering with
- Friction or complaints they surface publicly
- **Executive signals**: what leadership is personally focused on, especially
  anything the company page does not cover

#### 🔭 Future — Where they are heading
- Explicit roadmap hints: new markets, products, expansions
- Hiring for capabilities they do not have yet — a build-versus-buy signal
- Event and conference presence, which shows who they want to reach
- Partnerships in progress
- **Executive signals**: forward-looking statements from personal posts

#### 🎯 Prospect Evaluation

Rate each dimension High, Medium or Low with a one-line rationale grounded in
something you actually read:

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Fit with the user's offering (COMPANY_NAME from get_config) | | |
| Pain signals relevant to what the user sells | | |
| Technical sophistication | | |
| Openness to new tools | | |
| Decision-maker visibility on LinkedIn | | |
| Likely entry point | | |

**Overall verdict:** Strong, Moderate or Weak prospect, plus 2–3 sentences on
why. A weak verdict is a useful result — it saves the user an outreach slot.

#### ❓ Open Questions
What could not be determined from posts that would change the verdict.

---

### Step 6 — Save to Notion

Save the brief without asking. The value of research compounds only if the next
run can load it as context, and a confirmation prompt at the end of a long
report is friction with no upside. Invoke the save-notion skill or call the
Notion MCP directly.

- If Step 0a found an existing page, **update it** rather than creating a
  duplicate.
- Otherwise create `[Company Name] — [YYYY-MM-DD]` under [NOTION_RESEARCH_PAGE].
- Report one line: `Saved to Notion: [page title]`.

If the Notion MCP is unavailable, say so once at the end. Never hold back the
research output over a failed save.

---

## Output format guidance

- Lead with 🎯 Prospect Evaluation when the user's goal is to qualify or
  disqualify quickly; lead with the full brief when they want to understand the
  company first.
- Always end with Open Questions. Naming the gaps tells the user how far to
  trust the verdict.
- After saving, offer the next step: "Want me to draft outreach?"
