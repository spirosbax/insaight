---
name: research-post
description: "Research a single LinkedIn post and its commenters using the Insaight MCP connector. Surfaces who engaged, what they said, recurring themes, buying signals, decision-makers in the thread, and warm leads to potentially reach out to. Trigger when the user asks to: research a post, analyze a post's comments, see who engaged with a post, find decision-makers from a thread, or extract leads from a discussion. Trigger phrases: 'research this post', 'who commented on [URL]', 'analyze the comments on', 'who engaged with this post', 'extract leads from this thread', 'what are people saying about [post]'. Input: a LinkedIn post URL."
---

# Insaight — Post Research

Analyze a single LinkedIn post: its content, its commenters, and what the
discussion reveals about the surrounding network. Useful when you want to
mine a post for warm leads, decision-makers, competitor mentions, or genuine
buying signals.

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

### Step 1 — Confirm the post URL

The user should give you a full LinkedIn post URL — either form works:
- `https://www.linkedin.com/posts/<author>_<slug>-activity-<id>-<token>`
- `https://www.linkedin.com/feed/update/urn:li:activity:<id>`

If they only described the post, ask for the URL.

### Step 2 — Fetch the post itself (if not already in DB)

```
insaight:list_posts(account=<author-slug>)  # check if already there
```

If the post isn't tracked, scrape the author's recent posts:
```
insaight:scrape_profile(url=<author-profile-or-company-url>, max_posts=30)
```

Then read the full post:
```
insaight:get_posts(urns=["urn:li:activity:..."])
```

### Step 3 — Scrape comments

```
insaight:scrape_post_comments(post_url=<url>, max_items=100, profile_mode="short")
```

`profile_mode="short"` is free and includes basic author info. Use `"main"`
($0.002/profile) only if you need deeper author data on the commenters.

### Step 4 — Read the comments

```
insaight:list_comments(post_url=<url>, limit=100)
```

For a high-engagement post (>50 comments), call once with `min_likes=2` first
to get the signal layer, then again without the filter for context.

### Step 5 — Optionally enrich top commenters

If the user wants to know more about a specific commenter (e.g. they spotted
a likely decision-maker), enrich that one person:
```
insaight:scrape_person_profile(url=<commenter-linkedin-url>)
```

Don't blanket-enrich everyone — pick the 1–3 most relevant.

### Step 6 — Build the post brief

Use these headings:

---

#### 📌 Post Summary
- Author, role, company
- Date posted, language
- Engagement: likes / comments / shares (see shared benchmarks above)
- One-line gist of what the post is about

#### 💬 Comment Themes
Group comments into 3–6 themes. For each:
- Theme name (e.g. "Agreement on pain point", "Pushback on approach",
  "Vendor recommendations", "Personal anecdotes")
- Representative quote (paraphrased, with attribution)
- How many comments fit this theme

#### 🌟 Notable Commenters
Top 5–10 by engagement (likes on their comment) or seniority. For each:
- Name, headline, why they're notable
- Their comment in 1 line
- Suggested next step (research, enrich, reach out, ignore)

#### 🎯 Buying / Pain Signals
Specific comments that reveal:
- Active problem evaluation ("we're looking at...", "thinking about...")
- Frustration with status quo
- Vendor / tool mentions (theirs and competitors')
- Budget / timing hints

#### 🤝 Warm Leads
Commenters who would be a strong outreach target based on the post topic
and their engagement. Rank by fit. For each, give 1 sentence on the hook
this thread provides.

#### ⚔️ Competitor / Vendor Mentions
Any tool, product, or company named in the comments — both alternatives to
your offering and complements.

#### ❓ Open Questions
What you'd want to know but couldn't determine from the thread alone.

---

### Step 7 — Auto-save to Notion

Same pattern as the other research skills. Save under [NOTION_RESEARCH_PAGE] with
title: `Post — [author last name] — [topic gist] — [YYYY-MM-DD]`. Don't
duplicate if the same post was previously researched.

---

## Tips

- **Reply threads are signal too**: Replies often have the most candid takes.
  Default to `include_replies=True`.
- **Low-comment posts**: If <5 comments, the post itself is more interesting
  than the discussion — focus the brief on the post's content and just
  briefly note who engaged.
- **Author's own replies**: Watch for the author replying to commenters —
  reveals who they take seriously and engage with.
- **Sentiment shift**: A post that flips from agreement to pushback at
  comment N is a signal worth calling out.
- **Don't over-enrich**: `scrape_person_profile` on every commenter burns
  Apify credits fast. Enrich only the ones you might actually contact.
