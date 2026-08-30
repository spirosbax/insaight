---
name: research-person
description: "Research an individual person using their LinkedIn posts AND full profile (experience, education, skills, volunteer, languages) via the Insaight MCP connector. Produces a structured intelligence brief covering their role, content themes, professional focus, decision-maker signals, outreach hooks, and uncommon commonalities for outreach. Trigger when the user asks to: research a person, look up someone on LinkedIn, understand what someone is posting about, check a founder/CEO/CTO's focus, or learn about an individual before reaching out. Trigger phrases: 'research [person]', 'look up [person] on LinkedIn', 'what is [person] posting about', 'tell me about [person]', 'check [person] on Insaight', 'find commonalities with [person]'. This skill is for individual people — for company-level research, use insaight-research-company instead."
---

# Insaight — Person Research

Build a structured intelligence brief on an individual from their LinkedIn
posts AND their full profile data (experience, education, skills, volunteer
work, languages, projects). The full profile is where **uncommon
commonalities** hide — shared schools, overlapping past employers, mutual
volunteer work, common languages — and these are the strongest cold outreach
hooks.

**Shared conventions** (all Insaight skills):
- Call `insaight:get_config()` once per session for the user's Notion pages
  and company name/slug. If it reports `unconfigured: true`, ask the user to
  edit the file at the returned path before saving to Notion.
- Read cheaply: `list_accounts` → `list_posts` (slim index) → `get_posts` on
  the few URNs worth reading (max 20 per call). `list_people` / `list_comments`
  are free; the `scrape_*` tools call Apify and cost money — only scrape when
  data is missing or stale.
- Engagement benchmarks (adjust for the niche): < 10 likes low, 10–40 normal,
  40+ high signal — read those in full.

---

## Workflow

### Step 0 — Check Notion first (always)

Before touching Apify or SQLite, check what you already know about this person
in Notion. Locations come from `insaight:get_config()`.

**0a. Existing research page:**
```
notion:search(query="[Person Name]")
```
If a page exists under [NOTION_RESEARCH_PAGE] for this person, fetch it and load
as context. Your job becomes: update, don't re-do. Note the last research date
and decide what's worth refreshing (usually: recent posts + any role changes).

**0b. Prior messages ([NOTION_OUTREACH_LOG]):**
```
notion:search(query="[NOTION_OUTREACH_LOG]")
→ notion:fetch([page_id])   # cache this for the whole conversation
```
Scan for any mention of this person. If found, surface to user:
> "⚠️ I see you already messaged [Name] on [approx date]. Is this a
> follow-up, or do you want to research someone else?"

Proceed to Step 1 only after the user confirms.

### Step 1 — Find the person

```
insaight:list_accounts()   # check if their personal profile is tracked
```

If **not tracked**, ask for the LinkedIn profile URL, then fetch their posts:
```
insaight:scrape_profile(url="https://www.linkedin.com/in/[profile-id]", max_posts=50)
```

### Step 2 — Enrich with full profile data (the commonality layer)

```
insaight:scrape_person_profile(url="https://www.linkedin.com/in/[profile-id]")
```

This pulls experience, education, skills, certifications, languages, volunteer
work, projects, recommendations — the data that makes cold messages feel human
instead of templated. Cost is ~$4/1k profiles via Apify. Always worth it for
outreach targets.

Then check what was stored:
```
insaight:list_people(account=[slug or company-slug])   # surfaces enriched fields
```

### Step 3 — Survey posts (slim scan)

```
insaight:list_posts(account=[person-slug], limit=50)
```

Group mentally by theme: thought leadership, company announcements amplified,
industry takes, personal wins, event speaking, content reshared.

### Step 4 — Deep-read selected posts

Pick 8–12 for broadest signal. Prioritise:
- Highest engagement
- Most recent (current focus)
- Oldest available (baseline)
- Strong-opinion posts
- Posts mentioning challenges, frustrations, or goals

```
insaight:get_posts(urns=[...chosen urns...])
```

Targeted searches if needed:
```
insaight:search_posts(query="challenge / hiring / roadmap", account=[slug])
```

### Step 5 — Mine for uncommon commonalities

If the user has given context about themselves (role, company, background,
schools, past employers, interests), cross-reference against the person's
full profile. Look specifically for:

- **Shared past employers** — "we both worked at X around 2019"
- **Same university / program** — rare is better than prestigious
- **Overlapping geography at overlapping time** — "you were in Berlin the same year I was"
- **Mutual volunteer / nonprofit work**
- **Shared languages** (especially non-English)
- **Similar certifications or niche skills**
- **Projects on similar domains**
- **People who recommended them** (potential mutual connection)

If the user hasn't given their own context, ask: "Anything specific about your
background I should cross-reference? (past companies, schools, volunteer work,
languages)"

### Step 6 — Build the person brief

Use these exact headings (the outreach skill expects them):

---

#### 👤 Role & Context
- Current title, company, seniority level
- How long in this role (if visible from experience[])
- Their company's sector and rough scale

#### 🧭 Career Trajectory
From their `experience` array:
- Past 3–5 roles (title, company, duration)
- Notable transitions or pivots
- Tenure patterns (job-hopper? long-timer?)

#### 🎓 Education & Credentials
From `education`, `certifications`, `languages`:
- Schools and programs
- Certifications (only if notable/relevant)
- Languages spoken (often overlooked, great for hooks)

#### 📝 Content Themes
- What topics do they post about? (rank by frequency)
- How often they post (weekly, monthly, sporadic)
- Engagement level (low/normal/high per shared benchmarks above)
- Original content vs mostly reshares

#### 🎯 Professional Focus
- What they're clearly passionate about or opinionated on
- Expertise they signal
- Contrarian or notable positions
- Industry trends they track

#### 🔑 Decision-Maker Signals
- Likely buyer, influencer, or internal champion?
- Posts about vendor selection, tool evaluation, procurement?
- Engagement with competitor content?
- Seniority / scope indicators (budget authority, team size)

#### 💎 Uncommon Commonalities
The killer section for cold outreach. Only include if the user has shared
context about themselves. List 2–5 specific overlaps with SOURCE attribution:
- "You both worked at Stripe (2018–2020) — from [experience]"
- "Same TU Delft MSc — from [education]"
- "Both volunteered with Code for NL — from [volunteer]"
- "Both speak Dutch + Portuguese — from [languages]"

If no commonalities found, say so honestly.

#### 🪝 Outreach Hooks
3–5 specific observations from their posts for opening a cold message:
- Recent achievement or milestone
- Challenge or frustration voiced
- Strong opinion you can reference
- Shared interest or connection point
- Event they attended or spoke at

Be concrete — quote or paraphrase with approximate dates.

#### ❓ Open Questions
Things you couldn't determine that would matter for outreach.

---

### Step 7 — Auto-save to Notion

After delivering the brief to the user, **always** save it to Notion. No
prompt, no confirmation — just save. Invoke the save-notion skill internally
or call `notion:create-pages` / `notion:update-page` directly.

- If an existing [NOTION_RESEARCH_PAGE] page was found in Step 0a, **update it**
  (don't create a duplicate). Append a new dated section if meaningful
  changes, otherwise overwrite the existing sections.
- If no existing page, create: `[Person Name] — [YYYY-MM-DD]` under
  [NOTION_RESEARCH_PAGE].
- Report one line after saving: `Saved to Notion: [page title]` (with link
  if the API returned one).

If Notion MCP is unavailable, tell the user once at the end — don't block
the research output.

---

## Tips

- **Full profile enrichment is cheap** (~$4/1k) — run it for anyone you
  seriously consider reaching out to. Short-mode data alone rarely justifies
  a personalized message.
- **Commonalities > flattery**: "We both studied at TU Delft" beats "I love
  your content" every time.
- **Tone matching**: Note whether this person posts formally or casually —
  match it in outreach.
- **Engagement patterns**: Check who comments on their posts. Mutual
  commenters can be outreach leverage.
- **Sparse posters**: If < 5 posts, lean harder on the full profile data —
  experience and education still give you plenty to work with.
