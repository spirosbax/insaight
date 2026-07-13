---
name: insaight-save-notion
description: "Persist an Insaight research brief to Notion under the configured NOTION_RESEARCH_PAGE (see CLAUDE.md → Notion Setup). Primarily invoked automatically by the research skills after they finish — the user rarely triggers this explicitly. Trigger phrases (rare): 'save to Notion', 'save this research', 'store in Notion', 'add to prospect research'. Requires the Notion MCP. Outreach messages are NEVER saved here — the user maintains the NOTION_OUTREACH_LOG page manually."
---

# Insaight — Save Research to Notion

Persist a research brief to Notion. Usually invoked internally by
insaight-research-person and insaight-research-company after they finish.
Can also be called explicitly by the user.

**Scope**: research briefs only. Never writes outreach messages — those live
in the [NOTION_OUTREACH_LOG] page, which the user maintains manually and is read-only
from this skill system.

---

## Step 1 — Verify there's something to save

Look for a structured research brief in the conversation:
- Person: `👤 Role & Context`, `🧭 Career Trajectory`, etc.
- Company: `🏢 Company Snapshot`, `🎯 Prospect Evaluation`, etc.

If nothing to save, stop and tell the user.

---

## Step 2 — Find the parent page

```
notion:search(query="[NOTION_RESEARCH_PAGE]")
```

If missing, search for `[NOTION_WORKSPACE]` (configured in CLAUDE.md → Notion Setup)
and create `[NOTION_RESEARCH_PAGE]` under it (only if the user confirms).
Cache the parent page ID for the session.

---

## Step 3 — Check for existing page (update vs create)

Search for a page titled with the subject's name:
```
notion:search(query="[Name]")
```

If a page exists under [NOTION_RESEARCH_PAGE] for this exact subject:
- **Update it**, don't create a duplicate.
- Preserve prior content; replace only the sections the current brief covers.
- Append a timestamp line: `Last updated: [YYYY-MM-DD]`.

Otherwise create a new page with title: `[Name] — [YYYY-MM-DD]`.

---

## Step 4 — Write the page

Use Notion blocks (not a markdown blob):
- `heading_1` for the name/title
- `paragraph` (italic) for the metadata line
- `heading_2` for section headers (Company Snapshot / Past / Present / etc.)
- `paragraph` for body text
- `bulleted_list_item` for lists
- `table` for the prospect evaluation rubric

### Page structure

```
# [Name] — Prospect Analysis
*Analysed on [date] | Source: LinkedIn via Insaight*

---

## 👤 Role & Context   (person research)
## 🏢 Company Snapshot (company research)
...

## 🧭 Career Trajectory   (person, from experience[])
## 🎓 Education & Credentials (person)
## 📝 Content Themes
## 🎯 Professional Focus / Prospect Evaluation
## 🔭 Future  (company only)
## 🔑 Decision-Maker Signals
## 💎 Uncommon Commonalities (person, if provided)
## 🪝 Outreach Hooks (person)
## ❓ Open Questions
```

The exact section list depends on the brief type (person vs company). Mirror
what's in the conversation — don't invent sections the brief didn't produce.

---

## Step 5 — Report and stop

One-line report:
> Saved to Notion: [page title] ([create | update])

**Do NOT re-output the brief.** The user already has it in the conversation.

---

## Edge cases

- **Notion MCP not connected**: Tell the user once, don't block the calling
  skill's output. Message: *"Notion MCP isn't connected — research completed
  but not auto-saved. Connect at claude.ai → Settings → Integrations."*
- **Notion tools not loaded**: Run `tool_search(query="notion search fetch create")`
  to load schemas, then retry.
- **Duplicate page titles**: If multiple matches, pick the one under Prospect
  Research. If still ambiguous, ask the user.
