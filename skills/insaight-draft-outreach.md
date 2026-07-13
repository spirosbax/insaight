---
name: insaight-draft-outreach
description: "Draft a personalized cold outreach message (LinkedIn DM or email) using (1) intelligence from a prior Insaight research brief, (2) the learned style memory (insaight:get_memory — the distilled voice + playbook), and (3) a prior-contact check against the outreach ledger. Trigger when the user asks to: draft outreach, write a cold message, help reach out to someone, compose a LinkedIn DM, or write a cold email. Trigger phrases: 'draft outreach to [person/company]', 'write a cold message to', 'help me reach out to', 'cold email for', 'LinkedIn DM to', 'write an intro message'. If no research exists in conversation, suggest running insaight-research-person or insaight-research-company first."
---

# Insaight — Draft Cold Outreach

Craft personalized cold messages using three inputs:
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

If **no research exists**, stop and tell the user:
> "I don't have research on this person/company yet. Want me to run
> insaight-research-person or insaight-research-company first?"

---

## Step 2 — Load the memory (STYLE + PLAYBOOK)

```
insaight:get_memory()
```

- If `style_learned` is true: the style file is the voice source of truth.
  Follow it exactly — it was distilled from real sends the user approved.
- If `playbook_learned` is true: prefer hooks/variants the playbook marks
  as working; treat its "hypotheses" as worth testing, and avoid anything
  in its "Retired" section.
- If **neither is learned yet** (fresh install): fall back in this order —
  (a) `insaight:list_outreach(limit=10, full=true)` to read recent real sends,
  (b) the user's Notion outreach log if one is configured (CLAUDE.md →
  NOTION_OUTREACH_LOG), (c) the generic principles in Step 4. Mention once:
  "No learned style memory yet — after a few logged sends and outcomes,
  run insaight-reflect and drafts will match your voice."

**Cache this for the entire conversation.** Do not re-fetch on iteration.

---

## Step 3 — Check for prior contact

```
insaight:list_outreach(target="<name or profile URL or company>")
```

If any records come back:

> "⚠️ The ledger shows you messaged [Name] on [date] (outcome: [outcome]).
> Is this a follow-up? If yes, I'll draft a follow-up; if this is a
> mistake, tell me who you actually want to reach."

A follow-up requires a different structure than a first-touch — acknowledge
prior contact, reference specifically what changed, shorter CTA.

---

## Step 4 — Draft (matching the learned style)

Produce **two variants**, each in the two formats expected:

### Variant A — Warm / Story-led
Opens with a specific observation or shared detail. Builds before pitch.

### Variant B — Direct / ROI-led
Opens with the pain / opportunity. Gets to the point faster.

If the playbook shows one variant or hook type clearly outperforming
(with real n), say so and lead with it — but still produce both variants
unless the user asked for one.

**Formats per variant:**
- **LinkedIn DM** — matching the typical DM length from the style memory.
- **Email** — matching the typical email length and subject-line style
  from the style memory.

### Fallback principles (only when no memory and no history exists)

- Lead with a specific observation from their posts — not generic flattery.
- Name the pain at their scale; specific enough that they think "this
  person gets my situation."
- One-sentence value prop tied to that pain.
- Social proof only if genuinely relevant.
- Soft CTA — a question or a 15-min call. Never a demo push.
- Peer-to-peer, confident. No apologetic language. No exclamation marks.
- Match the person's posting language.

---

## Step 5 — Show your work

When presenting the drafts, briefly note:
- Which style signals you followed from the memory (1–2 lines).
- Which playbook evidence influenced hook/variant choice, if any.
- Which commonality or hook from the research you're leading with.

This lets the user sanity-check the style match before they copy anything.

---

## After drafting

- Offer to iterate: "Want me to adjust the angle, tone, or CTA?"
- When the user says they **sent** a message, log it immediately via the
  **insaight-track-outreach** skill (`log_outreach` with the exact sent text,
  variant, and hook_type). That's what keeps the memory loop learning.
- Do not write to Notion.
