---
name: reflect
description: "Run a reflection over the Insaight outreach ledger: analyze recent sends and their outcomes, then propose evidence-backed updates to the two memory files (style.md — the user's voice; playbook.md — the strategies that get replies). Every proposal is shown with the counts and quotes behind it and is applied only on approval, never silently. Trigger this whenever insaight:record_outcome returns reflection_due=true (offer it, don't just note it), and whenever the user asks what is or isn't working in their outreach — including 'run a reflection', 'reflect on my outreach', 'update my style memory', 'analyze my reply rates', 'what's working in my outreach', 'why is nobody replying', 'should I change my approach', 'which messages actually got responses', 'is my outreach working'. Also trigger after a run of logged outcomes when the user seems ready to draw conclusions from them. This is the only thing that improves future drafts, so favor offering it over staying quiet."
---

# Insaight — Reflect

Distill raw outreach history into the two memory files that insaight-draft-outreach
reads on every draft. The loop is: gather evidence → propose → user approves →
save.

Load the tools first: `tool_search(query="insaight")`.

---

## Step 1 — Gather evidence

```
insaight:get_outreach_stats()                          → deterministic counts
insaight:get_memory()                                  → current style + playbook
insaight:list_outreach(limit=30, full=true)            → recent messages + outcomes
```

Cite the stats tool's counts rather than tallying rows yourself — hand-counted
numbers drift from what the product reports elsewhere, and the whole value of
this memory is that the user can trust its arithmetic.

Read the full text of the sends that got replies, positives and meetings, and a
sample of the ghosted ones too. A list of winners alone tells you what the user
writes; the contrast with the silent sends is the only place the signal lives.

---

## Step 2 — Analyze

**style.md — the user's voice, how they write:**

- Opening moves, tone register, typical length per channel, sign-offs, language
  choice, recurring phrases, and the things they never do.
- Learn style from *all* sends. Voice is not a function of outcome, and letting
  results shape the voice file turns a description of how the user writes into a
  theory about what wins — which is the playbook's job, not this file's.

**playbook.md — the strategies that get replies:**

- Compare reply rates across `hook_type`, `variant` and `channel` from the stats.
- Look for what the buckets miss: personalization depth, message length against
  outcome, follow-up timing, seniority of the target.
- Read the reply snippets. Rates say *that* something worked; the snippets are
  the only record of *what* the person reacted to.

**Keeping the evidence honest**

The user will act on this file for months, and an overstated pattern is worse
than no pattern — it retires an approach that was only unlucky. So:

- Carry the evidence inline with each claim: "question hooks: 4/9 replied vs
  statement hooks: 1/8". A reader who disagrees should be able to see the
  numbers without leaving the file.
- Below roughly n=10 in a bucket, a difference is as likely to be noise as
  signal, so label it a **hypothesis to keep testing** rather than a rule.
  Keep low-n hypotheses in the file — they are how the next reflection knows
  what to look for; just don't let them read as settled.
- Exclude pending sends from every rate you cite. A message sent yesterday
  hasn't failed yet, and counting it as a non-reply makes recent activity look
  like a slump.
- With fewer than about 5 resolved outcomes there is nothing to distill. Say so
  and stop: "not enough evidence yet, keep logging." Inventing a pattern here
  poisons the memory that every future draft is built on.

---

## Step 3 — Propose (nothing is saved yet)

For each file you want to change, show:

1. **What changes** — sections added, updated or removed, briefly.
2. **The evidence** — the counts and quotes behind each change.
3. **The full proposed file content**, in a fenced block.

Structure the playbook as three sections: **What's working** (with evidence),
**Hypotheses being tested** (the low-n patterns), and **Retired** (approaches
the evidence killed — one line each, so they don't quietly get re-tried later).

Then ask: "Apply these updates?" The user may approve one file and not the
other, or edit the proposal first. Show the full content rather than a summary,
because approval only means something if they can see exactly what they are
agreeing to overwrite.

---

## Step 4 — Save on approval

```
insaight:update_memory(kind="style", content="full file")
insaight:update_memory(kind="playbook", content="full file", mark_reflection_done=true)
```

`mark_reflection_done=true` belongs on the LAST call only — it resets the
outcomes-since-reflection counter. If the user approves just one file, put it
on that one.

If the user rejects everything, make no calls at all. The reflection stays due
and can be re-run once more outcomes have landed.
