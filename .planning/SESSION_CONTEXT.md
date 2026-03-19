---
doc_type: session_context
updated_on: 2026-03-19
owner: assistant
scope: phone-first compatibility + practical skills
status: in_progress
additive_only: true
compatibility_mode: preserve
---

# Session Context

Last updated: 2026-03-19

## Current Ground Rule

- All fixes and improvements are additive.
- Do not remove existing features when implementing roadmap work.
- Discovery-first before coding: read, document findings in markdown, present plan, then edit code.

## Current Strategic Goals

1. Strengthen device compatibility for phone-first orientation.
2. Improve web dashboard interaction surfaces for multiple hardware classes.
3. Evolve into a lightweight OpenClaw-like agent with many practical runnable skills.

## Active Plan Shape

- Phase A (P0): Add dashboard hardware/use-case profiles (`lite`, `balanced`, `power`).
- Phase B (P0): Add mobile-friendly render and refresh options without replacing existing dashboard behavior.
- Phase C (P0): Convert high-value docs-only skills into runnable contracts and wrappers.
- Phase D (P1): Add readiness/diagnostic clarity for channels and skills (discoverable vs runnable).

## Constraints to Preserve

- Keep existing routes and aliases stable (HTTP + WS control plane).
- Keep existing skills discoverable while adding runnable paths.
- Keep current channel set; improve depth and diagnostics additively.
- Avoid destructive operations and compatibility-breaking changes.

## Next Execution Slice (Default)

0. Update planning artifacts (`RESEARCH_NOTES.md`, `IMPLEMENTATION_PLAN.md`, `CODE_IDEAS.md`) and present findings.
1. Introduce dashboard profile selector and persistence.
2. Add visibility-aware/low-power refresh options.
3. Add runnable-skill diagnostics counters.
4. Implement one practical skill wrapper (recommended: `notion`).

## Evidence Targets (for future reports)

- `clawlite/dashboard/index.html`
- `clawlite/dashboard/dashboard.css`
- `clawlite/dashboard/dashboard.js`
- `clawlite/tools/skill.py`
- `clawlite/core/skills.py`
- `clawlite/channels/manager.py`
- `docs/SKILLS.md`
- `docs/channels.md`
