---
name: save-notion
description: "Persist an Insaight research brief (person, company, or post) to Notion as a structured page under the research parent page named by insaight:get_config, updating the existing page for that subject instead of creating a duplicate. This skill is mostly NOT triggered by the user directly — the research skills (research-person, research-company, research-post) invoke it automatically as their last step, so reach for it whenever one of those has just produced a brief, and also on 'save to Notion', 'save this research', 'store this brief in Notion', 'add this to prospect research', or 'update the Notion page for [name]'. It requires the separate Notion MCP connector: if Notion tools are not available, say so once and stop rather than writing the brief somewhere else. Research briefs only — never write outreach messages, drafts, or sent-message logs to the outreach log page, which the user maintains by hand."
---

# Insaight — Save Research to Notion

Persist a research brief to Notion so the next research run on the same
subject can build on it instead of starting cold.

**Scope**: research briefs only. The [NOTION_OUTREACH_LOG] page is the user's
own record of what they sent, kept by hand — treat it as read-only here.
Writing generated messages into it would corrupt the one record of what a real
human actually sent.

---

## Step 1 — Verify there's something to save

Look for a structured research brief in the conversation:
- Person: `👤 Role & Context`, `🧭 Career Trajectory`, …
- Company: `🏢 Company Snapshot`, `🎯 Prospect Evaluation`, …
- Post: `📌 Post Summary`, `💬 Comment Themes`, …

If there's no brief, stop and say so. Reconstructing one from memory would
save something the research skills never actually produced.

---

## Step 2 — Find the parent page

```
notion:search(query="[NOTION_RESEARCH_PAGE]")
```

If it's missing, search for [NOTION_WORKSPACE] (both names come from
`insaight:get_config()`) and create [NOTION_RESEARCH_PAGE] under it — only
with the user's confirmation, since creating pages in someone's workspace is
not reversible from here. Cache the parent page ID for the session.

---

## Step 3 — Update or create

Search for a page titled with the subject:

```
notion:search(query="[Name]")
```

If a page for this exact subject already exists under [NOTION_RESEARCH_PAGE]:
- **Update it** rather than creating a second page — duplicates split the
  history the research skills read back on the next run.
- Preserve prior content; replace only the sections the current brief covers.
- Append `Last updated: [YYYY-MM-DD]`.

Otherwise create a new page:
- Person or company: `[Name] — [YYYY-MM-DD]`
- Post: `Post — [author last name] — [topic gist] — [YYYY-MM-DD]`

---

## Step 4 — Write the page

Use Notion blocks rather than one markdown blob, so the page stays navigable
and individually editable:
- `heading_1` for the name/title
- `paragraph` (italic) for the metadata line
- `heading_2` for section headers
- `paragraph` for body text
- `bulleted_list_item` for lists
- `table` for the prospect evaluation rubric

### Page structure

```
# [Name] — Prospect Analysis
*Analysed on [date] | Source: LinkedIn via Insaight*

---

## 👤 Role & Context   (person)
## 🏢 Company Snapshot (company)
## 📌 Post Summary     (post)
...

## 🧭 Career Trajectory        (person)
## 🎓 Education & Credentials  (person)
## 📝 Content Themes
## 🎯 Professional Focus / Prospect Evaluation
## 🔭 Future                   (company)
## 💬 Comment Themes           (post)
## 🔑 Decision-Maker Signals
## 💎 Uncommon Commonalities   (person, if provided)
## 🪝 Outreach Hooks
## ❓ Open Questions
```

Mirror the sections the brief actually produced — the list above is a
superset across brief types, not a template to fill in. Inventing a section
puts empty headers in front of the user next time they open the page.

---

## Step 5 — Report and stop

One line:
> Saved to Notion: [page title] ([create | update])

**Don't re-output the brief.** The user is already reading it in the
conversation.

---

## Edge cases

- **Notion MCP not connected**: Tell the user once and let the calling skill's
  output stand — a missing integration shouldn't swallow finished research.
  Message: *"Notion MCP isn't connected — research completed but not
  auto-saved. Connect at claude.ai → Settings → Integrations."*
- **Notion tools not loaded**: Run `tool_search(query="notion search fetch create")`
  to load the schemas, then retry. Tool names vary between Notion MCP builds,
  so use the names that come back rather than assuming them.
- **Duplicate page titles**: Prefer the match under [NOTION_RESEARCH_PAGE]. If
  it's still ambiguous, ask — writing to the wrong page is harder to undo than
  asking one question.
