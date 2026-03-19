# Assistant Continuity Instructions

Purpose: keep planning and implementation consistent across sessions while preserving existing features.

## Non-Negotiable Rules

- Additive-first: improvements must add capability, resilience, or configurability; do not remove features.
- Preserve compatibility: keep existing API/tool/channel/config behavior working unless explicitly requested otherwise.
- Prefer profile-based options over one-size-fits-all defaults.
- Keep mobile/phone-first support as a primary path, not an afterthought.

## Session Startup Checklist

1. Read `AGENTS.md` and `.planning/STATE.md`.
2. Read `.planning/SESSION_CONTEXT.md` for latest priorities and constraints.
3. Confirm current milestone and active phase before editing code.
4. For architecture-impacting work, update docs in the same change cycle.

## Mandatory Discovery-First Workflow

Before making code changes in any session:

1. Read relevant code and docs for the request scope.
2. Write/update markdown notes with findings, risks, and candidate approaches.
3. Write/update a markdown implementation plan with additive-safe steps.
4. Present findings and proposed plan before starting code edits.

Required planning artifacts (update each session when applicable):

- `.planning/RESEARCH_NOTES.md` (what was inspected, evidence paths, observations)
- `.planning/IMPLEMENTATION_PLAN.md` (phases, file targets, risks, quick wins)
- `.planning/CODE_IDEAS.md` (candidate code-level approaches and tradeoffs)
- `.planning/PLANNING_DATA_SCHEMA.md` (authoritative structure and required fields)

Rule: no code edits until discovery notes and plan are written and reported.

## Planning Data Standard

- Planning docs must follow `.planning/PLANNING_DATA_SCHEMA.md`.
- Keep sections and metadata parse-friendly for AI-to-AI handoff.
- Prefer explicit fields over prose-only updates when tracking status, risks, and evidence.

## Delivery Style

- Use small, auditable diffs.
- Keep work scoped to one logical slice at a time.
- Include file-path evidence for high-confidence claims.
- If behavior changes, include migration-safe defaults and toggles.

## Hardware and Use-Case Profiles (Additive)

- `lite`: low CPU/RAM/battery devices, older phones, unstable networks.
- `balanced`: default path for mixed desktop/mobile workflows.
- `power`: desktop/server operators with high refresh and full diagnostics.

Each profile should be additive and optional. Existing behavior remains available.

## Priority Themes

1. Phone-first dashboard responsiveness and interaction reliability.
2. Practical skill execution depth (discoverable + runnable skills).
3. Channel readiness clarity (depth over placeholder breadth).
4. OpenClaw-like practical parity through lightweight, configurable features.
