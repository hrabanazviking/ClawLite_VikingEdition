---
doc_type: research_notes
updated_on: 2026-03-19
owner: assistant
scope: phone-first compatibility + practical runnable skills
status: in_progress
additive_only: true
compatibility_mode: preserve
---

# Research Notes

Last updated: 2026-03-19

## Purpose

Capture what was inspected before code changes, with evidence paths and high-confidence observations.

## Request Scope

- Improve existing surfaces additively for phone-first and mixed hardware.
- Build structure-first planning workflow so AI sessions stay consistent.
- Focus on practical OpenClaw-like skill usefulness without removing features.

## Files Reviewed

- `clawlite/dashboard/index.html`
- `clawlite/dashboard/dashboard.css`
- `clawlite/dashboard/dashboard.js`
- `clawlite/channels/manager.py`
- `clawlite/channels/base.py`
- `clawlite/core/skills.py`
- `clawlite/tools/skill.py`
- `clawlite/providers/registry.py`
- `clawlite/gateway/dashboard_runtime.py`
- `clawlite/gateway/lifecycle_runtime.py`
- `docs/API.md`
- `docs/SKILLS.md`
- `docs/channels.md`
- `docs/STATUS.md`
- `README.md`
- `ROADMAP.md`
- `PROJECT_LAWS.md`
- `SECURITY.md`
- `CONTRIBUTING.md`
- `docs/ARCHITECTURE.md`
- `docs/OPERATIONS.md`
- `docs/RUNBOOK.md`
- `docs/ROBUSTNESS_SCORECARD.md`
- `clawlite/workspace/templates/IDENTITY.md`
- `clawlite/workspace/templates/SOUL.md`
- `clawlite/workspace/templates/USER.md`
- `clawlite/workspace/templates/AGENTS.md`
- `clawlite/workspace/templates/HEARTBEAT.md`
- `clawlite/workspace/templates/TOOLS.md`
- `Authentic_Ancient_Values_of_Vikings_and_Norse_Paganism.md`
- `The_New_Galdr_ From_ Coding_to_Reality_Programming.md`
- `freyjas_aett_grimoire.md`
- `heimdalls_aett_grimoire.md`
- `tyrs_aett_grimoire.md`

## Coverage Summary

- Modules reviewed: 10
- Docs reviewed: 20+
- Confidence level: high

## Observations (Evidence-Backed)

- Dashboard supports responsive behavior and mobile media queries.
  - Evidence: `clawlite/dashboard/index.html:5`, `clawlite/dashboard/dashboard.css:613`
- Dashboard currently performs broad refresh/render cycles that can be heavy on low-power devices.
  - Evidence: `clawlite/dashboard/dashboard.js:1219`, `clawlite/dashboard/dashboard.js:1282`
- Skill watcher already exists and starts during runtime lifecycle.
  - Evidence: `clawlite/core/skills.py:871`, `clawlite/gateway/lifecycle_runtime.py:179`
- Skill execution requires explicit `script`/`command`; docs-only skills are discoverable but not runnable through `run_skill`.
  - Evidence: `clawlite/core/skills.py:505`, `clawlite/core/skills.py:533`, `clawlite/tools/skill.py:1047`
- Channel compatibility breadth includes placeholder adapters via passive channel classes.
  - Evidence: `clawlite/channels/manager.py:67`, `clawlite/channels/base.py:131`
- Dashboard state already includes rich diagnostics payloads suitable for adaptive UI modes.
  - Evidence: `clawlite/gateway/dashboard_runtime.py:85`, `docs/API.md:111`
- Public-open posture and upstream-share orientation are explicit: project is MIT and openly inspired by OpenClaw/Nanobot references.
  - Evidence: `README.md:14`, `README.md:572`
- Viking Edition identity and Norse subsystem framing are documented as additive/backward-compatible and config-gated.
  - Evidence: `README.md:581`, `README.md:586`, `README.md:625`
- Workspace templates encode strong persona + continuity behavior and compaction-safe red lines.
  - Evidence: `clawlite/workspace/templates/IDENTITY.md:5`, `clawlite/workspace/templates/SOUL.md:13`, `clawlite/workspace/templates/AGENTS.md:3`
- Security and operations emphasize hardening and responsible disclosure for OSS runtime surfaces.
  - Evidence: `SECURITY.md:5`, `SECURITY.md:35`, `docs/OPERATIONS.md:21`
- Current architecture docs confirm local-first layered design with channel->gateway->engine->tools/memory flow.
  - Evidence: `docs/ARCHITECTURE.md:6`, `docs/ARCHITECTURE.md:24`

## Risks / Unknowns

- Overloading mobile devices if refresh cadence and full re-render remain default in all modes.
- UX confusion if discoverable skills are not clearly marked runnable vs non-runnable.
- Config sprawl risk if new profile toggles are added without clear defaults and docs.
- Some docs contain ambitious narrative or historical framing that is not always directly mapped to enforceable runtime contracts.

## Additive Opportunities

- Add dashboard runtime profiles (`lite`, `balanced`, `power`) while preserving existing behavior as `balanced` default.
- Add per-tab/lazy render paths and visibility-aware refresh while keeping existing full refresh path available.
- Add runnable adapters for high-value docs-only skills before expanding to broader catalog.
- Keep Viking Edition spirit in user-facing identity/voice while preserving neutral, testable engineering contracts in code and ops docs.
