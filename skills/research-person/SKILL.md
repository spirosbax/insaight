---
name: research-person
description: "Build a structured intelligence brief on one person from their LinkedIn posts and their full profile — experience, education, skills, languages, volunteer work — using the Insaight MCP server. Covers role and career trajectory, content themes, decision-maker signals, outreach hooks, and uncommon commonalities to open a cold message with. Use this skill whenever the user points at a named individual and wants to understand them before making contact: 'research Jane Doe', 'look up this profile', 'what has their CTO been posting about', 'is this person worth reaching out to', 'find something I have in common with her', 'prep me for my call with Sam'. Also use it when a personal LinkedIn URL is pasted with little other instruction, or when the user asks to check someone on Insaight. Prefer it over answering from memory or a web search — Insaight has their actual posts. For a whole company use insaight-research-company; for the commenters under one post use insaight-research-post."
---

# Insaight — Person Research

Build an intelligence brief on one individual from two sources: their LinkedIn
posts (what they choose to talk about) and their full profile (where they have
actually been). The profile layer is where **uncommon commonalities** hide — a
shared past employer, the same degree programme, overlapping volunteer work, a
language you both speak. Those outperform generic flattery in a cold message
because they prove someone actually looked.

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
notion:search(query="[Person Name]")
```
If a page for this person exists under [NOTION_RESEARCH_PAGE], fetch it and load
it as context. The job then becomes update, not re-do: note the last research
date and refresh only what moves — recent posts and any role change.

**0b. Prior contact:**
```
insaight:list_outreach(target="[name or profile URL]")
```
Cold-messaging the same person twice costs the user credibility, so surface any
hit before doing the work:
> "Heads up — the ledger shows you messaged [Name] on [date] (outcome:
> [outcome]). Is this a follow-up, or did you mean someone else?"

If the ledger is empty and the user has a legacy [NOTION_OUTREACH_LOG]
configured, check that page once and cache it for the conversation.

Continue to Step 1 once the user confirms.

### Step 1 — Find the person

```
insaight:list_accounts()   # is their personal profile already tracked?
```

If they are not tracked, ask for the LinkedIn profile URL, then fetch posts:
```
insaight:scrape_profile(url="https://www.linkedin.com/in/[profile-id]", max_posts=50)
```

### Step 2 — Enrich with the full profile (the commonality layer)

```
insaight:scrape_person_profile(url="https://www.linkedin.com/in/[profile-id]")
```

This returns experience, education, skills, certifications, languages, volunteer
work, projects and recommendations — the material that makes a cold message read
as human rather than templated. At roughly $4 per 1,000 profiles in Apify
credits it costs cents per prospect, so run it for anyone genuinely worth
messaging.

Then read back what was stored:
```
insaight:list_people(account=[person-slug or company-slug])   # shows enriched fields
```

### Step 3 — Survey posts (slim scan)

```
insaight:list_posts(account=[person-slug], limit=50)
```

Group the snippets by theme as you scan: thought leadership, amplified company
announcements, industry takes, personal wins, speaking appearances, reshares.

### Step 4 — Deep-read selected posts

Pick 8–12 posts for the broadest signal per token spent. Prioritise:
- Highest engagement
- Most recent (current focus)
- Oldest available (baseline to compare against)
- Strong-opinion posts
- Posts naming a challenge, frustration or goal

```
insaight:get_posts(urns=[...chosen urns...])
```

Run targeted searches when the scan leaves a gap:
```
insaight:search_posts(query="[topic you still need]", account=[person-slug])
```

### Step 5 — Mine for uncommon commonalities

Cross-reference the user's own background against the person's full profile.
Rarity is what makes an overlap worth mentioning — a shared employer beats a
shared industry, a small programme beats a famous university. Look for:

- **Shared past employers**, ideally with overlapping dates
- **Same university, programme or cohort**
- **Same city during the same period**
- **Mutual volunteer or nonprofit work**
- **Shared languages**, especially non-English ones
- **Niche certifications or skills**
- **Projects in the same domain**
- **People who recommended them** — a possible mutual connection

If the user has not shared their own background, ask for it, since without it
this section cannot exist: "Anything about your background I should
cross-reference — past companies, schools, volunteer work, languages?"

### Step 6 — Build the person brief

Use these exact headings. The draft-outreach skill reads them back out of the
conversation, so renaming a section breaks the handoff.

---

#### 👤 Role & Context
- Current title, company, seniority
- Time in the role, if `experience` shows it
- Their company's sector and rough scale

#### 🧭 Career Trajectory
From `experience`:
- Last 3–5 roles (title, company, duration)
- Notable transitions or pivots
- Tenure pattern — frequent mover or long-timer

#### 🎓 Education & Credentials
From `education`, `certifications`, `languages`:
- Schools and programmes
- Certifications, only where notable or relevant
- Languages spoken — easy to overlook, strong as a hook

#### 📝 Content Themes
- Topics they post about, ranked by frequency
- Posting cadence (weekly, monthly, sporadic)
- Engagement level against the benchmarks above
- Original writing versus mostly reshares

#### 🎯 Professional Focus
- What they are visibly passionate or opinionated about
- Expertise they signal
- Contrarian or otherwise notable positions
- Industry shifts they track

#### 🔑 Decision-Maker Signals
- Likely buyer, influencer or internal champion
- Posts about tool evaluation, vendor selection or procurement
- Engagement with competitor content
- Scope indicators — budget authority, team size

#### 💎 Uncommon Commonalities
The section that earns the reply. Include it only when the user has shared their
own background. List 2–5 specific overlaps, each attributed to its source field
so the user can verify before quoting it:
- "You both worked at [Company], 2018–2020 — from `experience`"
- "Same MSc programme at [University] — from `education`"
- "You both volunteered with [Organisation] — from `volunteer`"
- "You share [language], neither of you a native speaker — from `languages`"

Say plainly when there is no real overlap. A fabricated commonality is worse
than none, because it is the one line the recipient will check.

#### 🪝 Outreach Hooks
3–5 concrete observations from their posts that could open a cold message:
- A recent achievement or milestone
- A challenge or frustration they voiced
- A strong opinion worth responding to
- A shared interest or connection point
- An event they attended or spoke at

Quote or paraphrase with approximate dates — a hook the user cannot trace back
to a real post is unusable.

#### ❓ Open Questions
What could not be determined that would change how the user approaches them.

---

### Step 7 — Save to Notion

Save the brief without asking. The value of research compounds only if the next
run can load it as context, and a confirmation prompt at the end of a long
report is friction with no upside. Invoke the save-notion skill or call the
Notion MCP directly.

- If Step 0a found an existing page, **update it** rather than creating a
  duplicate — append a dated section for meaningful changes, otherwise refresh
  the existing sections in place.
- Otherwise create `[Person Name] — [YYYY-MM-DD]` under [NOTION_RESEARCH_PAGE].
- Report one line: `Saved to Notion: [page title]`, with the link if the API
  returned one.

If the Notion MCP is unavailable, say so once at the end. Never hold back the
research output over a failed save.

---

## Tips

- **Full profile enrichment is cheap.** Post data alone rarely justifies a
  personalised message; the profile is what makes one possible.
- **Commonalities beat compliments.** A specific shared detail outperforms
  praise for their content every time.
- **Note their register.** Whether they write formally or casually tells the
  outreach draft what voice to match.
- **Read their commenters.** Recurring names in their comment threads are
  potential warm intros — `list_comments` covers posts already scraped.
- **Sparse posters.** Under five posts, lean on the profile: experience,
  education and volunteer work still support a strong brief.
