---
name: draft-outreach
description: "Draft a personalized cold LinkedIn DM or email from three inputs: the intelligence in a prior Insaight research brief, the learned style memory (insaight:get_memory — the user's distilled voice plus the playbook of what actually earns replies), and a prior-contact check against the outreach ledger (insaight:list_outreach) so nobody gets cold-opened twice. Returns two angles (warm/story-led and direct/ROI-led), each as a DM and an email. Use this whenever the user needs words to send a prospect — 'draft outreach to [person]', 'write a cold message to', 'help me reach out to', 'cold email for', 'LinkedIn DM to', 'write an intro message', 'what should I say to [name]', 'how do I open with them' — including right after a research brief, when the user simply asks what to send. If no research exists in the conversation, offer insaight-research-person or insaight-research-company first rather than inventing personalization."
---

# Insaight — Draft Cold Outreach

Craft personalized cold messages from three inputs:
1. The intelligence brief from a prior research skill (conversation context).
2. The **learned memory** — `insaight:get_memory()` returns the distilled style
   guide (the user's voice) and playbook (strategies with reply-rate evidence).
3. The **outreach ledger** — prior-contact check via `insaight:list_outreach()`.

All tools must be loaded first via `tool_search(query="insaight")`.

---

## Step 1 — Verify research exists

Look in the conversation for:
- `👤 Role & Context` + `🪝 Outreach Hooks` (person research), OR
- `🏢 Company Snapshot` + `🎯 Prospect Evaluation` (company research).

Without a brief there is nothing to personalize with, and a generic message
sent under the user's name costs them more than sending nothing. Stop and
offer the research instead:

> "I don't have research on this person/company yet. Want me to run
> insaight-research-person or insaight-research-company first?"

---

## Step 2 — Load the memory (STYLE + PLAYBOOK)

```
insaight:get_memory()
```

Read the memory rather than trawling raw sent history. The memory is what
earlier reflection runs distilled from messages the user approved and from
outcomes that actually landed; raw history is unfiltered and pulls a draft
toward whatever the most recent message happened to sound like.

- If `style_learned` is true: treat the style file as the voice source of
  truth and follow it closely — it was distilled from real approved sends.
- If `playbook_learned` is true: prefer hooks and variants the playbook marks
  as working, treat its "hypotheses" as worth testing, and leave anything in
  its "Retired" section alone — it was retired because it stopped working.
- If **neither is learned yet** (fresh install): fall back in this order —
  (a) `insaight:list_outreach(limit=10, full=true)` to read recent real sends,
  (b) the user's Notion outreach log if one is configured (`get_config()` →
  NOTION_OUTREACH_LOG), (c) the fallback principles in Step 4. Mention once:
  "No learned style memory yet — after a few logged sends and outcomes,
  run insaight-reflect and drafts will match your voice."

Cache the memory for the whole conversation. Re-fetching between iterations
adds nothing (it only changes on a reflection run) and slows the loop down.

---

## Step 3 — Check for prior contact

```
insaight:list_outreach(target="name or profile URL or company")
```

Do this before drafting, not after. A second cold opener to someone already
contacted reads as spam and quietly costs the user the relationship — and the
ledger is the only place that remembers.

If records come back:

> "⚠️ The ledger shows you messaged [Name] on [date] (outcome: [outcome]).
> Is this a follow-up? If yes, I'll draft a follow-up; if this is a
> mistake, tell me who you actually want to reach."

A follow-up is a different message from a first touch: acknowledge the earlier
contact, point at what specifically changed since (new post, new funding, new
role), and keep the ask smaller than last time.

---

## Step 4 — Draft (matching the learned style)

Produce **two variants**, each in both formats:

### Variant A — Warm / Story-led
Open with a specific observation or shared detail. Build before the pitch.

### Variant B — Direct / ROI-led
Open with the pain or opportunity. Get to the point faster.

Two angles let the user pick by feel for the recipient, which they can judge
better than you can. If the playbook shows one variant or hook type clearly
outperforming on real numbers, say so and lead with it — but still offer both
unless the user asked for one.

**Formats per variant:**
- **LinkedIn DM** — matching the typical DM length from the style memory.
- **Email** — matching the typical email length and subject-line style
  from the style memory.

### Fallback principles (only when no memory and no history exists)

- Lead with a specific observation from their posts — not generic flattery.
- Name the pain at their scale, specifically enough that they think "this
  person gets my situation."
- One-sentence value prop tied to that pain.
- Social proof only when it's genuinely comparable.
- Soft CTA — a question, or fifteen minutes. Never a demo push.
- Peer-to-peer and confident: no apologizing for the message, no exclamation
  marks. Cold outreach is judged on whether the sender sounds like an equal.
- Match the language the person posts in.

---

## Step 5 — Show your work

When presenting the drafts, note briefly:
- Which style signals you followed from the memory (1–2 lines).
- Which playbook evidence drove the hook or variant choice, if any.
- Which commonality or hook from the research you're leading with.

The user is about to send this under their own name, so make the reasoning
checkable before they copy anything.

---

## After drafting

- Offer to iterate: "Want me to adjust the angle, tone, or CTA?"
- When the user says they **sent** a message, log it immediately via the
  **insaight-track-outreach** skill (`log_outreach` with the exact sent text,
  variant, and hook_type). Unlogged sends are invisible to the prior-contact
  check and never teach the memory anything.
- Do not write to Notion.
