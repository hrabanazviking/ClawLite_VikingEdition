---
doc_type: code_ideas
updated_on: 2026-03-19
owner: assistant
scope: additive dashboard modes + first practical skill wrapper
status: in_progress
additive_only: true
compatibility_mode: preserve
---

# Code Ideas

Last updated: 2026-03-19

## Purpose

Track concrete code-level implementation ideas and tradeoffs before writing production changes.

## Idea 1

- Summary: Add dashboard performance profiles (`lite`, `balanced`, `power`) with persisted selection.
- Files: `clawlite/dashboard/index.html`, `clawlite/dashboard/dashboard.js`, `clawlite/dashboard/dashboard.css`
- Compatibility: default to `balanced` behavior matching current baseline.
- Tradeoffs: extra UI/config state but significant flexibility across hardware.
- Estimated effort: M

## Idea 2

- Summary: Add adaptive refresh strategy (visibility-aware + low-power + manual mode).
- Files: `clawlite/dashboard/dashboard.js`
- Compatibility: preserve current timer loop path as existing mode.
- Tradeoffs: more state branches; lower battery/network usage on phones.
- Estimated effort: M

## Idea 3

- Summary: Add first docs-only-to-runnable skill wrapper (`notion`) and extend diagnostics with runnable counts.
- Files: `clawlite/tools/skill.py`, `clawlite/core/skills.py`, `clawlite/skills/notion/SKILL.md`
- Compatibility: keep current discovery and non-runnable skill listing intact.
- Tradeoffs: introduces more script dispatch logic; improves practical utility immediately.
- Estimated effort: M
