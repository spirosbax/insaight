---
name: insaight-reflect
description: "Reflection run over the outreach ledger: analyze recent sends and their outcomes, then propose evidence-backed updates to the two memory files (style.md — the user's voice; playbook.md — strategies that get replies). Proposals are shown to the user with their evidence and applied only on approval, never silently. Trigger when: record_outcome reports reflection_due=true (offer it), or the user asks directly. Trigger phrases: 'run a reflection', 'reflect on my outreach', 'update my style memory', 'what's working in my outreach', 'analyze my reply rates'."
---

# Insaight — Reflect

Distill raw outreach history into the two memory files that draft-outreach
reads. This is the learning loop: propose → show evidence → user approves →
save.

All tools must be loaded first via `tool_search(query="insaight")`.

---

## Step 1 — Gather evidence

```
insaight:get_outreach_stats()                          → deterministic counts
insaight:get_memory()                                  → current style + playbook
insaight:list_outreach(limit=30, full=true)            → recent messages + outcomes
```

Use the stats tool's counts as the numbers you cite — do not count rows
yourself. Read the full message text of at least the replied/positive/meeting
sends AND a sample of the ghosted ones: contrast is where the signal is.

---

## Step 2 — Analyze

**For style.md** (voice — how the user writes):
- Opening moves, tone register, typical length per channel, sign-offs,
  language choice (EN/NL), recurring phrases, what they never do.
- Style is learned from ALL sends (voice doesn't depend on outcome).

**For playbook.md** (strategy — what gets replies):
- Compare reply rates across hook_type, variant, channel from the stats.
- Look for patterns the buckets don't capture: personalization depth,
  message length vs outcome, follow-up timing, target seniority.
- Read reply snippets: what did responders actually react to?

**Statistical honesty (hard rules):**
- Every playbook claim carries its evidence inline: "question hooks: 4/9
  replied vs statement hooks: 1/8".
- Below n=10 per bucket, label the pattern a **hypothesis to keep testing**,
  not a rule. Never delete a hypothesis just because n is small — mark it.
- If the data is too thin to say anything (fewer than ~5 resolved outcomes),
  say so and stop: "not enough evidence yet, keep logging."
- Pending sends are not failures — exclude them from any rate you cite.

---

## Step 3 — Propose (do NOT save yet)

Show the user, for each file you want to change:

1. **What changes** — added / updated / removed sections, briefly.
2. **The evidence** — the counts and quotes behind each change.
3. **The full proposed file content** in a fenced block.

Format the playbook as: a "What's working" section (with evidence), a
"Hypotheses being tested" section (low-n patterns), and a "Retired" section
(things the evidence killed — keep one line each so they don't get re-tried).

Then ask: "Apply these updates?" — the user may approve one file and not
the other, or edit the proposal.

---

## Step 4 — Save on approval

```
insaight:update_memory(kind="style", content="<full file>")
insaight:update_memory(kind="playbook", content="<full file>", mark_reflection_done=true)
```

`mark_reflection_done=true` goes on the LAST call only — it resets the
outcomes-since-reflection counter. If the user approves only one file,
put it on that one.

If the user rejects everything, make no calls — the reflection stays due
and can be re-run later.
