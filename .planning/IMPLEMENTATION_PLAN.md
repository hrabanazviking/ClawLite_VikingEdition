---
doc_type: implementation_plan
updated_on: 2026-03-19
owner: assistant
scope: additive profile-driven dashboard + practical skill execution
status: in_progress
additive_only: true
compatibility_mode: preserve
---

# Implementation Plan

Last updated: 2026-03-19

## Purpose

Define additive-safe implementation steps before editing code.

## Goal

- Improve phone-first and mixed-hardware compatibility through additive dashboard options.
- Increase practical skill utility by adding runnable paths without reducing skill discovery.
- Enforce planning-data discipline for AI continuity before coding.

## Constraints

- Additive-only changes
- Backward compatibility preserved

## Phases

1. Phase A - Dashboard profiles
   - Priority: P0
   - File targets: `clawlite/dashboard/index.html`, `clawlite/dashboard/dashboard.js`, `clawlite/dashboard/dashboard.css`
   - Changes: add `lite/balanced/power` profile switch and persisted preference.
   - Additive compatibility: keep current behavior as `balanced` default.
   - Validation: dashboard smoke on desktop + mobile viewport.

2. Phase B - Adaptive refresh and rendering
   - Priority: P0
   - File targets: `clawlite/dashboard/dashboard.js`, `clawlite/gateway/payloads.py`
   - Changes: add visibility-aware refresh, low-power cadence, and optional per-tab rendering.
   - Additive compatibility: retain existing polling cadence path as selectable mode.
   - Validation: manual timing checks + websocket reconnect behavior.

3. Phase C - Practical runnable skills
   - Priority: P0
   - File targets: `clawlite/tools/skill.py`, `clawlite/skills/notion/SKILL.md`, `clawlite/core/skills.py`
   - Changes: add first wrapper (notion) and runnable diagnostics counters.
   - Additive compatibility: keep all current skills discoverable; only add execution depth.
   - Validation: targeted tests for skill dispatch and diagnostics.

4. Phase D - Docs and planning continuity
   - Priority: P1
   - File targets: `docs/SKILLS.md`, `docs/channels.md`, `.planning/*.md`
   - Changes: document discoverable vs runnable semantics and profile usage.
   - Additive compatibility: docs clarify existing behavior and new options.
   - Validation: docs consistency pass with API/contracts.

## Risks and Mitigations

- Risk: dashboard complexity grows too quickly.
  - Mitigation: profile defaults + feature flags + incremental rollout.
- Risk: runnable wrappers may require credentials not present.
  - Mitigation: explicit precheck and clear `missing_requirements` output.
- Risk: regressions in current operator workflow.
  - Mitigation: preserve existing controls and keep `balanced` mode as baseline.

## Validation Plan

- Unit/targeted checks: `tests/core/test_skills.py`, relevant dashboard payload tests.
- Integration/smoke checks: dashboard state + ws chat flow on gateway.
- Manual verification: desktop and phone viewport profile switching and persistence.

## Quick Wins

1. Add profile selector with local persistence in dashboard UI.
2. Add visibility-aware refresh toggle.
3. Add `runnable_count` and `discoverable_count` to skills diagnostics payload.
