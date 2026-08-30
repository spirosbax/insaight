---
name: track-outreach
description: "Record outreach sends and their outcomes in the local Insaight ledger using insaight:log_outreach and insaight:record_outcome. Trigger this skill whenever the user mentions — even in passing, as a throwaway aside mid-conversation — that a message went out or that a prospect responded or went quiet; these remarks are almost never phrased as requests, so act on them proactively instead of waiting to be asked. Send signals: 'I sent it', 'just fired that off', 'sent the DM to Maria', 'emailed him this morning', or the user pasting the final text of a message. Outcome signals: 'he replied', 'she got back to me', 'they said no thanks', 'meeting booked', 'call is Thursday', 'she ghosted me', 'no reply from Acme', 'never heard back'. Also triggers on explicit asks: 'log this outreach', 'record a reply', 'mark as ghosted'. Prior-contact checks, reply-rate stats and the memory reflection loop are all derived from this ledger, so an unlogged send or outcome is signal lost for good."
---

# Insaight — Track Outreach

The ledger is the only record of what the user actually sent and what came
back. Style memory, the playbook, reply-rate evidence and prior-contact
warnings are all derived from it, so a send or outcome that never gets logged
is signal the rest of the system can never recover.

Load the tools first: `tool_search(query="insaight")`.

---

## Log in the flow, without derailing the conversation

These mentions usually arrive mid-sentence, while the user is doing something
else. Treat them like a note passed across a desk: record it, confirm in one
line, and hand the conversation back.

- **Infer before asking.** Pull the target, channel, variant and hook from what
  you already have — the draft you wrote earlier, the research brief in this
  conversation, a previous ledger entry. Ask only for a field you genuinely
  cannot reconstruct.
- **Batch mentions.** If the user reports several sends or outcomes at once,
  log each one and confirm them as a short list rather than a long back-and-forth.
- **Only log what actually happened.** A draft the user is still considering is
  not a send; logging it early creates a phantom pending record that quietly
  drags down every reply rate computed later.

---

## Moment 1 — the user sent a message

```
insaight:log_outreach(
    target_url="LinkedIn profile URL or email address",
    target_name="name",
    company="company",
    channel="dm" | "email",
    variant="warm" | "direct" | "follow-up",
    hook_type="question" | "statement" | "story" | "stat" | "commonality",
    message="the EXACT text that was sent",
)
```

- **Capture the text as sent, not as drafted.** If the user edited your draft,
  ask them to paste the final version. Style memory is distilled from this
  field, so learning from an unsent draft teaches the system someone else's voice.
- **Classify honestly.** `variant` and `hook_type` are what the reply-rate
  breakdowns are grouped by. A forced label produces a confident-looking
  comparison built on miscoded rows; when a send genuinely doesn't fit the
  standard values, a short free-text label is more useful than the nearest wrong one.
- **Surface prior contact.** When the response comes back with `prior_contact`
  entries, say so plainly — "that's your second message to them, logged as a
  follow-up" — and set `variant="follow-up"` if that is what it was. The user
  may not remember, and repeated cold first-touches read badly to the recipient.
- If the message was drafted with insaight-draft-outreach in this conversation,
  the variant and hook are already known — don't re-ask.

---

## Moment 2 — the user reports an outcome

```
insaight:record_outcome(
    outreach_id=id from the log step, if known,
    target_url="or the target's URL / email",
    outcome="replied" | "positive" | "meeting" | "ghosted",
    reply_snippet="short quote from the reply, if the user shares it",
)
```

Outcome guide:

- `replied` — any human response, including a polite no
- `positive` — a reply showing real interest
- `meeting` — a call or meeting is actually booked
- `ghosted` — the user has given up waiting

Two judgement calls worth getting right:

- **Silence is not automatically a ghost.** "Still nothing from Acme" may mean
  the user is still waiting, and marking it ghosted freezes an outcome that
  might yet change. Ask whether they consider it dead before recording it; they
  decide when a thread is over, not you.
- **Ask for a reply snippet on replied/positive outcomes.** One quoted line is
  enough. Rates tell you *that* something worked; the snippet is the only
  evidence of *what* the person actually responded to, which is what reflection
  needs to say anything useful.

**Examples**

- "ok that went out to Maria this morning" → `log_outreach` with the draft from
  earlier in the conversation, after confirming the text is unchanged.
- "Maria got back to me, sounds keen, wants to talk next week" → `record_outcome`
  with `outcome="positive"` — no date is set yet, so it isn't a `meeting`.
- "no reply from that Acme guy" → check whether they're writing it off before
  recording `ghosted`.

---

## After recording — the reflection trigger

The `record_outcome` response includes `reflection_due`. When it is `true`,
enough new outcomes have accumulated for patterns to have shifted since the
last reflection:

> "That's [N] outcomes since the last reflection. Want me to run one now? I'll
> analyze what's been working and propose updates to your style and playbook
> memory — you approve before anything is saved."

If yes, run the **insaight-reflect** skill. If no, drop it; the flag returns
on the next outcome.

Ask rather than reflecting automatically. Reflection rewrites the memory that
every future draft is built on, so the user should always be the one who
decides when that happens.
