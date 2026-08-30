---
name: research-post
description: "Mine a LinkedIn post AND its comment thread for leads, using the Insaight MCP connector: who engaged, what they said, recurring themes, buying signals, decision-makers hiding in the replies, competitor and vendor mentions, and ranked warm leads with the hook each one hands you. Use this whenever a LinkedIn post URL appears and the user is curious about the reaction to it — 'research this post', 'who commented on [URL]', 'analyze the comments on', 'who engaged with this post', 'find the decision-makers in this thread', 'extract leads from this thread', 'anyone here worth reaching out to?', 'what are people saying about [post]'. Trigger it even when the user never says 'research' or 'leads' — a pasted post URL plus any question about its audience is enough, and the comment thread is where prospects self-identify. Input: a LinkedIn post URL. For a whole person or company rather than one post, use insaight-research-person or insaight-research-company instead."
---

# Insaight — Post Research

Turn a single LinkedIn post into a map of the people around it. The post is
usually the least interesting part: the comment thread is where prospects
self-identify — describing their own pain in their own words, naming the tools
they already pay for, arguing with the author. Read the thread as a lead list,
not as a conversation.

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

### Step 1 — Get the post URL

Either form works:
- `https://www.linkedin.com/posts/AUTHOR_SLUG-activity-ID-TOKEN`
- `https://www.linkedin.com/feed/update/urn:li:activity:ID`

If the user only described the post, ask for the URL — comment scraping is
keyed on it, and there is no reliable way to search your way back to a
specific post from a description.

### Step 2 — Load the post itself

Check what is already stored before spending anything:

```
insaight:list_posts(account="author-slug")
```

If the post isn't tracked, scrape the author. This stores their whole recent
feed, so any later work on the same author is free:

```
insaight:scrape_profile(url="author profile or company page URL", max_posts=30)
```

Then read the full text:

```
insaight:get_posts(urns=["urn:li:activity:..."])
```

Read the post before the comments. The same remark ("we've been fighting this
for months") means something different under a hiring announcement than under
a product launch, and you can only grade the comments against what prompted
them.

### Step 3 — Scrape the comments

```
insaight:scrape_post_comments(post_url="...", max_items=100, profile_mode="short")
```

`profile_mode="short"` is free and already carries each commenter's name and
headline — usually enough to judge seniority. Step up to `"main"`
($0.002/profile) only when the headlines leave you unable to tell who these
people are.

Leave `include_replies=True` (the default). Replies hold the candid takes:
people hedge in a top-level comment and say what they actually think two
levels down.

### Step 4 — Read the comments

```
insaight:list_comments(post_url="...", limit=100)
```

This reads from the local DB and costs nothing, so re-query freely. On a busy
thread (50+ comments), call once with `min_likes=2` to see what the audience
itself endorsed, then again unfiltered — a quiet, unliked comment from a
senior buyer is often the most valuable line in the thread, and a likes filter
alone would hide it.

### Step 5 — Enrich selectively

When a commenter looks like a genuine prospect but their headline leaves the
deciding question open (do they own a budget? is their company the right
shape?), pull the full profile:

```
insaight:scrape_person_profile(url="commenter LinkedIn URL")
```

Pick the 1–3 that matter. Blanket-enriching a hundred-comment thread burns
Apify credits on data nobody will ever act on.

### Step 6 — Write the brief

Use these headings:

---

#### 📌 Post Summary
- Author, role, company
- Date posted, language
- Engagement: likes / comments / shares (see shared benchmarks above)
- One-line gist of what the post is about

#### 💬 Comment Themes
Group the comments into 3–6 themes — e.g. agreement on a pain point, pushback
on the approach, vendor recommendations, personal anecdotes. For each: the
theme, a representative quote with attribution, and how many comments fall
under it. Theme sizes tell the user which reaction is the market's, not one
loud person's.

#### 🌟 Notable Commenters
The top 5–10 by comment engagement or seniority. For each: name, headline,
why they stand out, their comment in a line, and the next step you'd take
(research, enrich, reach out, ignore).

#### 🎯 Buying / Pain Signals
Quote the comments that reveal active evaluation ("we're looking at…",
"thinking about…"), frustration with the status quo, tools they currently use,
or budget and timing hints. Quote them rather than summarizing — the user's
next message will borrow their words.

#### 🤝 Warm Leads
Commenters worth contacting, ranked by fit against the post's topic and their
engagement. Give each one sentence naming the hook this thread hands you.

#### ⚔️ Competitor / Vendor Mentions
Every tool, product, or company named in the comments — alternatives and
complements both.

#### ❓ Open Questions
What you'd want to know but couldn't determine from the thread alone.

---

### Step 7 — Save to Notion

Same pattern as the other research skills: save under [NOTION_RESEARCH_PAGE]
with the title `Post — [author last name] — [topic gist] — [YYYY-MM-DD]`.
Check for an existing page on the same post first and update it rather than
creating a duplicate.

---

## Judgment calls

- **Thin threads**: under ~5 comments, the discussion has little to say. Center
  the brief on the post and note who engaged, and tell the user plainly that
  there is no lead list here instead of padding one out.
- **Author replies**: whoever the author bothers to answer is someone they
  value — a possible warm-intro path, and a read on the author themselves.
- **Sentiment shifts**: a thread that turns from agreement to pushback partway
  through marks a real fault line in how the market sees the topic. Call it out.
- **Names beat adjectives**: "three commenters named [tool] as what they use
  today" is something the user can act on; "some interest in tooling" is not.
