---
name: insaight-draft-outreach
description: "Draft a personalized cold outreach message (LinkedIn DM or email) using (1) intelligence from a prior Insaight research brief and (2) the user's demonstrated style from their outreach log page in Notion (configured as NOTION_OUTREACH_LOG in CLAUDE.md). That page is the source of truth for the user's voice — never write to it. Trigger when the user asks to: draft outreach, write a cold message, help reach out to someone, compose a LinkedIn DM, or write a cold email. Trigger phrases: 'draft outreach to [person/company]', 'write a cold message to', 'help me reach out to', 'cold email for', 'LinkedIn DM to', 'write an intro message'. If no research exists in conversation, suggest running insaight-research-person or insaight-research-company first."
---

# Insaight — Draft Cold Outreach

Craft personalized cold messages using two inputs:
1. The intelligence brief from a prior research skill (conversation context).
2. The user's **[NOTION_OUTREACH_LOG]** Notion page — their voice archive and style
   source of truth. (Page name configured in CLAUDE.md → Notion Setup.)

This skill does not call the Insaight MCP tools. It reads Notion and
synthesises from what's already in the conversation.

---

## Step 1 — Verify research exists

Look in the conversation for:
- `👤 Role & Context` + `🪝 Outreach Hooks` (person research), OR
- `🏢 Company Snapshot` + `🎯 Prospect Evaluation` (company research).

If **no research exists**, stop and tell the user:
> "I don't have research on this person/company yet. Want me to run
> insaight-research-person or insaight-research-company first?"

---

## Step 2 — Load [NOTION_OUTREACH_LOG] (STYLE SOURCE OF TRUTH)

Find and fetch the outreach log page. See CLAUDE.md → Notion Integration for
the configured page name.

```
notion:search(query="[NOTION_OUTREACH_LOG]")
→ notion:fetch([page_id])
```

**Cache this for the entire conversation.** Do not re-fetch on iteration.

If Notion MCP is not connected or the page can't be found, tell the user
once and fall back to the generic principles in Step 5. Prefer [NOTION_OUTREACH_LOG]
over the principles whenever possible — the user's own voice beats any
template.

---

## Step 3 — Check for prior contact

Scan [NOTION_OUTREACH_LOG] for mentions of the target person or their company. If found:

> "⚠️ [NOTION_OUTREACH_LOG] shows you messaged [Name] on [approx date]. Is this a
> follow-up? If yes, I'll draft a follow-up; if this is a mistake, tell me
> who you actually want to reach."

A follow-up requires a different structure than a first-touch — acknowledge
prior contact, reference specifically what changed, shorter CTA.

---

## Step 4 — Extract style from [NOTION_OUTREACH_LOG]

Before drafting, read the 3–5 most recent messages in [NOTION_OUTREACH_LOG] and identify:

- **Opening patterns**: Does the user open with an observation? A question?
  A direct statement? A compliment? A shared detail?
- **Tone register**: Formal / casual / peer-to-peer / deferential? Does the
  user use humour, first names, English only or mixed languages?
- **CTA shape**: "Worth a call?" / "Open to chatting?" / direct question / no
  explicit CTA?
- **Length**: Count sentences and approximate words — what's their typical
  size for a LinkedIn DM vs email?
- **Specific phrases / tics**: Any recurring words, transitions, or sign-offs?
- **Language choices**: When do they write in Dutch vs English? Do they
  switch mid-message?
- **What they DON'T do**: Do they avoid exclamation marks? Subject lines?
  Formal greetings?

These extracted patterns override the generic principles in Step 5.

---

## Step 5 — Draft (matching the user's style)

Produce **two variants**, each in the two formats expected:

### Variant A — Warm / Story-led
Opens with a specific observation or shared detail. Builds before pitch.

### Variant B — Direct / ROI-led
Opens with the pain / opportunity. Gets to the point faster.

**Formats per variant:**
- **LinkedIn DM** — matching the typical DM length observed in [NOTION_OUTREACH_LOG]
  (don't default to 5 sentences if the user's actual DMs are shorter).
- **Email** — matching the typical email length and subject-line style
  observed in [NOTION_OUTREACH_LOG].

### Fallback principles (only when [NOTION_OUTREACH_LOG] is unavailable)

- Lead with a specific observation from their posts — not generic flattery.
- Name the pain at their scale; specific enough that they think "this
  person gets my situation."
- One-sentence value prop tied to that pain.
- Social proof only if genuinely relevant.
- Soft CTA — a question or a 15-min call. Never a demo push.
- Peer-to-peer, confident. No apologetic language. No exclamation marks.
- Match the person's posting language.

---

## Step 6 — Show your work

When presenting the drafts, briefly note:
- What style signals you pulled from [NOTION_OUTREACH_LOG] (1–2 lines).
- Which commonality or hook from the research you're leading with.

This lets the user sanity-check the style match before they copy anything.

---

## After drafting

- Offer to iterate: "Want me to adjust the angle, tone, or CTA?"
- **Do NOT save anywhere.** The user logs messages to [NOTION_OUTREACH_LOG] manually.
- If the user says they sent it, remind them: "Don't forget to add it to
  [NOTION_OUTREACH_LOG] so the style bank stays current."
