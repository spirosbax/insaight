---
name: draft-post
description: "Draft a LinkedIn post for the user's own company page, in that company's own voice, plus an optional visual brief. Reads COMPANY_NAME and COMPANY_LINKEDIN from insaight:get_config, loads the company's real past posts through the Insaight MCP, extracts their hook, structure, length, emoji, hashtag and language patterns, then writes two variants against that reference. If the user pastes a link, fetches the article and treats it as the brief. Use this whenever the user wants something published on LinkedIn, even when they never name a skill or their company: 'write a LinkedIn post', 'draft a post about [topic]', 'post idea for [theme]', 'create LinkedIn content', 'help me write a post', 'make a post from this article', 'turn this into a post', or a pasted URL with 'post this'. Prefer it over drafting freehand — a post written without the style reference reads generic and off-voice. For one-to-one cold DMs or emails to a prospect, use draft-outreach instead."
---

# Insaight — Draft LinkedIn Post

Write posts for the user's own company page (COMPANY_NAME and COMPANY_LINKEDIN
from `insaight:get_config()`) by loading that company's actual published posts
first and using them as the style reference. The company's own archive is the
only reliable source of their voice — anything drafted from general LinkedIn
instincts will sound like everyone else's LinkedIn.

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

## Step 1 — Load [COMPANY_NAME]'s past posts (style source of truth)

Check whether [COMPANY_LINKEDIN] posts are already in the DB:

```
insaight:list_posts(account="[COMPANY_LINKEDIN]", limit=30)
```

If the account returns no posts, scrape once (this costs Apify credits, so
avoid repeating it):

```
insaight:scrape_profile(url="https://www.linkedin.com/company/[COMPANY_LINKEDIN]/", max_posts=30)
insaight:list_posts(account="[COMPANY_LINKEDIN]", limit=30)
```

Then pull the full text of the 8–12 most recent or most engaged posts:

```
insaight:get_posts(urns=["urn:li:activity:...", ...])
```

Pick posts spanning several formats (story, insight, announcement, question).
A sample drawn from one format teaches only that format's voice.

**Cache these for the whole conversation.** Re-fetching on every iteration
burns tokens and can shift the style reference mid-thread.

---

## Step 2 — Extract style patterns

Read the fetched posts and note:

- **Hook patterns**: How does [COMPANY_NAME] open? Bold statement, question,
  surprising stat, personal story, provocation? Any recurring openers?
- **Structure**: Short staccato lines, paragraph blocks, numbered lists,
  mixed? How aggressive are the line breaks?
- **Voice register**: Corporate/formal vs conversational/peer-to-peer?
  First-person plural ("we") or impersonal? Any humour or informality?
- **Emoji usage**: None, occasional, heavy? Where — hooks, section breaks,
  bullets, CTAs?
- **CTA shape**: Does [COMPANY_NAME] close with a question, a link, a soft
  prompt, or nothing? What is the typical last line?
- **Hashtag behaviour**: How many? Inline or trailing block? Which recurring
  tags appear?
- **Language**: Which language(s) do they post in? Any code-switching between
  languages inside a single post?
- **Typical length**: Approximate line count and character count range.
- **Topics / frames**: Which themes recur (product, team, industry take,
  customer story, opinion piece)?

Write a 4–6 line internal style note before drafting. Having the pattern
stated explicitly is what keeps variant B and every later revision on-voice.

---

## Step 2b — Fetch linked content (when a URL was provided)

If the input contains a URL that is not a LinkedIn profile or post URL (those
belong to `scrape_profile` and the research skills), fetch it before drafting:

```
WebFetch(url="[pasted URL]", prompt="Return the full article or page text, preserving key facts, quotes, and data points.")
```

This can run alongside Step 1 — the two do not depend on each other.

From the fetched content, extract:
- **Core claim or finding** — the one sentence that makes this worth posting.
- **Specific data points or quotes** to anchor the post.
- **Angle for [COMPANY_NAME]** — how this connects to their domain, product,
  or point of view.

If the URL is paywalled or returns nothing useful, say so rather than
guessing at the contents:

> "I couldn't fetch the full article at [URL]. Paste the key paragraph or stat
> you want to build the post around and I'll draft from that."

Treat the fetched content as the brief for Step 3 — the URL *is* the brief,
so don't ask the user to restate it.

---

## Step 3 — Understand the brief

The user has given a topic, angle, rough idea, or URL. Before drafting,
settle internally:

- **Goal**: Awareness, thought leadership, lead gen, community, announcement,
  opinion?
- **Audience**: Prospects, peers, recruits, partners, or general?
- **Angle**: What is the non-obvious take that makes this worth posting rather
  than filler?
- **Evidence**: Is there a specific story, stat, customer, or moment to anchor
  it? Concrete anchors are what make a post land, so flag it when the user
  hasn't supplied one.

If the brief is very thin (a few words, no angle), ask one clarifying question
first — drafting twice costs more than asking once:

> "Quick question before I draft: is this meant to build [COMPANY_NAME]'s
> thought leadership on [topic], or is there a specific story / moment /
> customer angle you want to anchor it to?"

---

## Step 4 — Draft two variants

Produce **two variants**, both in [COMPANY_NAME]'s extracted voice. Two lets
the user choose a direction instead of critiquing a single draft.

### Variant A — Hook-led / insight-first
Opens with the sharpest statement, stat, or provocation and reaches the point
in line 1; the rest supports or expands it. Suits opinion pieces, contrarian
takes, industry observations.

### Variant B — Story-led / scene-first
Opens inside a moment, conversation, or situation, with the insight landing at
the end. Suits customer stories, team moments, "we learned this the hard way"
posts.

**Match the reference for each variant:**

- Line break density — don't default to dense paragraphs if their posts are
  staccato, or vice versa.
- Emoji frequency and placement.
- CTA style — if [COMPANY_NAME] never hard-sells, a "DM us" closer breaks the
  voice; only add one if the sample shows it.
- Hashtag count and placement.
- The language(s) they post in, unless the user asks for another.
- Their typical length range from Step 2.

---

## Step 5 — Visual brief (optional, on by default)

After the drafts, add a short visual brief that can go straight to a designer
or into an image generation tool:

```
🎨 Visual brief

Format: [square / landscape / portrait — match LinkedIn norms]
Style: [photography / illustration / data visual / screenshot / etc.]
Mood: [adjectives — e.g. "clean, optimistic, technical"]
Main element: [what should dominate the frame]
Text overlay: [suggested 3–8 word headline to overlay, if any]
What to avoid: [clichés this topic attracts — e.g. "no stock handshake photos"]

Image prompt (copy-paste ready):
"[full prompt]"
```

Make the image prompt specific about style, composition, subject, lighting and
mood; a generic prompt produces generic stock-looking output.

If a visual would feel bolted on (pure opinion piece, personal reflection),
say so and skip the brief.

---

## Step 6 — Show your work briefly

Lead with 2–3 lines before the drafts:
- Which style signals you're matching from the loaded posts.
- Which angle you're leading with, and why.

This lets the user course-correct before reading two full drafts.

---

## After drafting

- Offer to iterate: "Want me to sharpen the hook, change the angle, or try a
  different format?"
- Produce a third variant or a specific format (carousel, poll, video script)
  on request.
- Don't save drafts to Notion — save-notion is for research briefs, and drafts
  aren't research. Only save if the user explicitly asks.
- If the user says they published it, offer to scrape it into the Insaight DB
  so it joins the style reference for next time.
