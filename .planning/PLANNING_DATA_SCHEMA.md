# Planning Data Schema

Last updated: 2026-03-19

Purpose: define a consistent, machine-friendly structure for planning files so humans and AIs can resume work efficiently.

## Global Rules

- All planning files use markdown with a top metadata block.
- Metadata keys use `snake_case`.
- Dates use ISO format (`YYYY-MM-DD`).
- Status values use: `pending`, `in_progress`, `completed`, `blocked`, `cancelled`.
- Evidence references should use repo-relative paths with optional line refs (example: `clawlite/dashboard/dashboard.js:1219`).
- Additive-only policy must be explicitly stated in plan constraints.

## Required Metadata Block

Use this block at top of planning artifacts:

```md
---
doc_type: research_notes | implementation_plan | code_ideas | session_context
updated_on: YYYY-MM-DD
owner: assistant
scope: <short request scope>
status: pending | in_progress | completed | blocked | cancelled
additive_only: true
compatibility_mode: preserve
---
```

## Document Contracts

### `RESEARCH_NOTES.md`

Required sections:

1. `Request Scope`
2. `Files Reviewed`
3. `Observations (Evidence-Backed)`
4. `Risks / Unknowns`
5. `Additive Opportunities`

### `IMPLEMENTATION_PLAN.md`

Required sections:

1. `Goal`
2. `Constraints`
3. `Phases`
4. `Risks and Mitigations`
5. `Validation Plan`
6. `Quick Wins`

Each phase entry should include:

- priority (`P0`, `P1`, `P2`)
- file targets
- additive compatibility note
- verification step

### `CODE_IDEAS.md`

Required fields per idea:

- summary
- file targets
- compatibility strategy
- tradeoffs
- estimated effort (`S`, `M`, `L`)

### `SESSION_CONTEXT.md`

Required sections:

1. `Current Ground Rule`
2. `Current Strategic Goals`
3. `Active Plan Shape`
4. `Constraints to Preserve`
5. `Next Execution Slice`
6. `Evidence Targets`

## Workflow Enforcement

Before code edits in any task:

1. Update `RESEARCH_NOTES.md`.
2. Update `IMPLEMENTATION_PLAN.md`.
3. Update `CODE_IDEAS.md`.
4. Present findings and plan summary.
5. Then start code changes.
