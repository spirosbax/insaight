---
name: insaight-draft-post
description: "Draft a LinkedIn post (and optional visual brief) for your company based on a topic, angle, brief, or pasted URL. Loads your company's own past posts as the style reference to match voice, structure, hook patterns, and tone. If a URL is provided, fetches the article content and uses it as the brief. Trigger when the user asks to: write a LinkedIn post, draft a post about [topic], create content for LinkedIn, generate a post idea, write something for your company's LinkedIn, or pastes a link to an article/news story. Trigger phrases: 'write a LinkedIn post', 'draft a post about', 'write a post for my company', 'create LinkedIn content', 'post idea for', 'help me write a post', 'draft a post about this [URL]', 'make a post from this article'. Input: a topic, angle, brief, rough idea, or URL — any length is fine."
---

# Insaight — Draft LinkedIn Post

Write LinkedIn posts in your company's voice (set COMPANY_NAME and COMPANY_LINKEDIN in CLAUDE.md) by loading their actual past posts as
the style reference before drafting anything.

Shared tool reference and reading patterns are in CLAUDE.md.

---

## Step 1 — Load [COMPANY_NAME]'s past posts (style source of truth)

Check if [COMPANY_LINKEDIN] posts are already in the DB:

```
insaight:list_posts(account="[COMPANY_LINKEDIN]", limit=30)
```

If the account returns no posts, scrape first (one-time cost):

```
insaight:scrape_profile(url="https://www.linkedin.com/company/[COMPANY_LINKEDIN]/", max_posts=30)
insaight:list_posts(account="[COMPANY_LINKEDIN]", limit=30)
```

Then pull the full text of the 8–12 most recent or most engaged posts:

```
insaight:get_posts(urns=["urn:li:activity:...", ...])
```

Select posts that cover a range of formats (story, insight, announcement,
question) so the style extraction covers the full range, not just one mode.

**Cache these for the entire conversation.** Do not re-fetch on iteration.

---

## Step 2 — Extract style patterns

Read the fetched posts and extract:

- **Hook patterns**: How does [COMPANY_NAME] open? Bold statement / question /
  surprising stat / personal story / provocation? Any recurring openers?
- **Structure**: Short staccato lines? Paragraph blocks? Numbered lists?
  Mixed? How aggressive are the line breaks?
- **Voice register**: Corporate/formal vs conversational/peer-to-peer?
  First-person plural ("we") or impersonal? Any humour or informality?
- **Emoji usage**: None / occasional / heavy? Where — hooks, section
  breaks, bullets, CTAs?
- **CTA shape**: Does [COMPANY_NAME] end with a question, a link, a soft prompt,
  or nothing? What's the typical last line?
- **Hashtag behaviour**: How many? Inline or trailing block? Which
  recurring tags appear?
- **Language**: Dutch, English, or mixed? Any code-switching patterns?
- **Typical length**: Approximate line count and character count range.
- **Topics / frames**: What themes recur (product, team, industry take,
  customer story, opinion piece)?

Write a 4–6 line internal style note before drafting — this prevents
drift across iterations.

---

## Step 2b — Fetch linked content (if a URL was provided)

If the user's input includes a URL (not a LinkedIn profile URL — those are handled
by `scrape_profile`), fetch its content before doing anything else:

```
WebFetch(url="<pasted URL>", prompt="Return the full article or page text, preserving key facts, quotes, and data points.")
```

From the fetched content, extract:
- **Core claim or finding** — the one sentence that makes this worth posting about
- **Specific data points or quotes** to anchor the post
- **Angle for [COMPANY_NAME]** — how does this connect to [COMPANY_NAME]'s domain and
  industry?

If the URL is behind a paywall or returns no useful content, tell the user:
> "I couldn't fetch the full article at [URL]. Paste the key paragraph or stat
> you want to build the post around and I'll draft from that."

Use the fetched content as the brief for Step 3. The user doesn't need to repeat
themselves — the URL *is* the brief.

---

## Step 3 — Understand the brief

The user has given you a topic, angle, rough idea, or a URL. Before drafting,
clarify internally:

- **Goal**: Awareness / thought leadership / lead gen / community /
  announcement / opinion?
- **Audience**: Prospects, peers, recruits, partners, or general?
- **Angle**: What's the non-obvious take? What makes this worth posting
  vs. obvious filler?
- **Evidence**: Is there a specific story, stat, customer, or moment to
  anchor this? If the user hasn't provided one, flag it — a concrete
  anchor makes posts land harder.

If the brief is very vague (< 10 words, no angle), ask one clarifying
question before drafting:

> "Quick question before I draft: is this meant to build [COMPANY_NAME]'s
> thought leadership on [topic], or is there a specific story /
> moment / customer angle you want to anchor it to?"

---

## Step 4 — Draft two variants

Produce **two variants**, both in [COMPANY_NAME]'s extracted voice:

### Variant A — Hook-led / Insight-first
Opens with the sharpest possible statement, stat, or provocation.
Gets to the point in line 1. The rest of the post supports or expands.
Best for: opinion pieces, contrarian takes, industry observations.

### Variant B — Story-led / Scene-first
Opens by dropping the reader into a moment, conversation, or
situation. The insight lands at the end. Best for: customer stories,
team moments, "we learned this the hard way" posts.

**Format requirements for each variant:**

- Match the line break density of [COMPANY_NAME]'s actual posts — don't default
  to dense paragraphs if their posts are staccato.
- Match emoji frequency and placement exactly.
- Match CTA style — if [COMPANY_NAME] doesn't hard-sell, don't add a "DM us"
  closer unless that's in the examples.
- Match hashtag count and placement.
- Match language (EN/NL) unless the user specifies otherwise.
- Keep within [COMPANY_NAME]'s typical length range (from Step 2).

---

## Step 5 — Visual brief (optional but default ON)

After the post drafts, generate a short visual brief that could be
handed to a designer or pasted into Midjourney / DALL-E:

```
🎨 Visual brief

Format: [square / landscape / portrait — match LinkedIn norms]
Style: [photography / illustration / data visual / screenshot / etc.]
Mood: [adjectives — e.g. "clean, optimistic, EV-forward"]
Main element: [what should dominate the frame]
Text overlay: [suggested 3–8 word headline to overlay, if any]
What to avoid: [common clichés for this topic — e.g. "no stock EV charging hands"]

Midjourney prompt (copy-paste ready):
"[full prompt]"
```

The Midjourney prompt should be specific: style, composition, subject,
lighting, mood. Don't write generic prompts.

If the post is text-only and a visual would feel forced (pure opinion
piece, personal reflection), say so and skip the brief.

---

## Step 6 — Show your work briefly

Before the drafts, show 2–3 lines:
- Which style signals you're matching from the loaded posts.
- What angle you're leading with and why.

This lets the user course-correct before reading two full drafts.

---

## After drafting

- Offer to iterate: "Want me to sharpen the hook, change the angle, or
  try a different format?"
- If the user wants a 3rd variant or a specific format (carousel, poll,
  video script), produce it on request.
- Do not save drafts to Notion unless the user explicitly asks.
- If the user says they posted it, ask if they want to add it to the
  insaight DB as a reference post for future style matching.
