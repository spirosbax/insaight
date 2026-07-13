---
name: insaight-track-outreach
description: "Track sent outreach and its outcomes in the local ledger. Two moments: (1) the user says they SENT a message — log it with log_outreach; (2) the user reports what HAPPENED — record it with record_outcome (replied / positive / meeting booked / ghosted). After recording an outcome, if the response says reflection is due, offer to run insaight-reflect. Trigger phrases: 'I sent it', 'log this outreach', 'sent the DM to', 'record a reply', 'he/she replied', 'they answered', 'got a response from', 'meeting booked with', 'mark as ghosted', 'no reply from', 'never heard back'. This ledger replaces the manual Notion sent-log — it powers prior-contact checks, reply-rate stats, and the memory reflection loop."
---

# Insaight — Track Outreach

Keep the outreach ledger current. Everything else (style memory, playbook,
reply-rate evidence) is derived from this data, so log faithfully and
immediately.

All tools must be loaded first via `tool_search(query="insaight")`.

---

## Moment 1 — The user sent a message

When the user says they sent (or are about to send) a drafted message:

```
insaight:log_outreach(
    target_url="<LinkedIn profile URL or email address>",
    target_name="<name>",
    company="<company>",
    channel="dm" | "email",
    variant="warm" | "direct" | "follow-up",
    hook_type="question" | "statement" | "story" | "stat" | "commonality",
    message="<the EXACT text that was sent>",
)
```

Rules:

- **Log the message as actually sent.** If the user edited your draft before
  sending, ask them to paste the final version — the style memory must learn
  from real sends, not drafts.
- **Classify honestly.** `variant` and `hook_type` feed the reply-rate
  breakdowns; if the send doesn't fit the standard values, use a short free-text
  label rather than forcing a wrong one.
- **Surface prior contact.** If the response contains `prior_contact` entries,
  tell the user ("this is your 2nd message to them — logged as a follow-up")
  and set `variant="follow-up"` if that's what it is.
- If the user drafted with insaight-draft-outreach in this conversation, you
  already know the variant and hook — don't re-ask.

---

## Moment 2 — The user reports an outcome

When the user says the target replied, booked a meeting, or went silent:

```
insaight:record_outcome(
    outreach_id=<id from the log step, if known>,
    target_url="<or the target's URL/email>",
    outcome="replied" | "positive" | "meeting" | "ghosted",
    reply_snippet="<short quote from the reply, if the user shares it>",
)
```

Outcome guide:

- `replied` — any human response, even a "no thanks"
- `positive` — reply showing real interest
- `meeting` — call/meeting booked
- `ghosted` — the user has given up waiting (they decide when, not you)

Ask for a **reply snippet** when the outcome is replied/positive — one quoted
line is enough. It becomes evidence for reflection ("what did the replies
respond to?").

---

## After recording — check the reflection trigger

The `record_outcome` response includes `reflection_due`. When it's `true`:

> "That's [N] outcomes since the last reflection. Want me to run a
> reflection now? I'll analyze what's been working and propose updates
> to your style and playbook memory — you approve before anything is saved."

If yes → run the **insaight-reflect** skill. If no → drop it; the flag will
come back on the next outcome.

Never run a reflection without asking.
