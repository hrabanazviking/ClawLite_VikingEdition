# ClawLite Autonomy Plan

Last updated: 2026-03-10

## Goal

Make ClawLite robust and operationally autonomous for long-lived local use while preserving its Python-native architecture.

The target is behavior parity with the best operational patterns from:

- `/root/projetos/ref/openclaw` for dashboard, gateway, onboarding, bootstrap, and heartbeat behavior
- `/root/projetos/ref/nanobot` for runtime reliability, loop contracts, bus/session patterns, and provider retry behavior

This plan is intentionally phased. The early work focuses on durability and operator control. Advanced self-improvement comes only after the platform is stable.

## Current Milestone

Phase 1 - dashboard and control-plane parity

Phase 0 established the docs/release hygiene baseline for the rest of this plan.

## Definition Of Done

ClawLite is considered "milestone complete" when it can:

- run continuously with supervised critical loops
- recover from provider, channel, or task failures without operator intervention
- preserve and replay critical state after restart
- expose enough diagnostics for an operator to understand what happened
- keep docs, changelog, and release notes aligned with shipped behavior

## Phase 0 - Docs And Release Hygiene

Goal: make the repo describe the real system before deeper parity work lands.

Work:

- sync `README.md`, `ROADMAP.md`, `CHANGELOG.md`, and docs index with the real codebase
- add `docs/STATUS.md` as the live engineering snapshot
- add `docs/RUNBOOK.md` for operator flows
- add `docs/RELEASING.md` for milestone tags and GitHub releases

Exit criteria:

- public docs match actual commands and repo state
- release workflow is explicit and repeatable

## Phase 1 - Dashboard And Control Plane

Goal: replace the simple root page with a real operational dashboard and richer WebSocket contract.

Work:

- port the dashboard shell from OpenClaw into a ClawLite-native asset bundle
- keep current compatibility endpoints intact while enriching the control-plane payloads
- preserve `GET /`, `GET /api/status`, `POST /api/message`, `GET /api/token`, and `WS /ws`
- improve operator diagnostics visibility for channels, memory, subagents, heartbeat, and autonomy

Exit criteria:

- dashboard is served locally by ClawLite
- browser reconnect and control-plane flows are stable

## Phase 2 - Onboarding, Bootstrap, And Heartbeat

Goal: make first-run and recurring proactive behavior dependable.

Work:

- align QuickStart and Advanced onboarding with live provider and Telegram probes
- keep workspace generation idempotent and visible to operators
- harden `BOOTSTRAP.md` one-shot lifecycle with durable state
- evolve heartbeat into a wake-aware `decide -> run -> notify` flow with durable state and target-aware delivery

Exit criteria:

- first-run experience is reliable
- heartbeat state survives restart and only emits actionable messages

## Phase 3 - Providers And Inference Resilience

Goal: remove single-provider fragility.

Work:

- expand provider coverage where it matters operationally
- add autodiscovery for local runtimes such as Ollama and vLLM
- implement multi-hop failover by error class with cooldown and quarantine semantics
- keep auth diagnostics secret-safe and operator-friendly

Exit criteria:

- provider failures degrade gracefully instead of stalling the runtime

## Phase 4 - Channels And Delivery Durability

Goal: make channels safe for 24/7 use, especially Telegram.

Work:

- add durable update offset handling, replay-safe delivery, and restart recovery
- implement pairing/binding persistence and media ingest parity for Telegram
- keep outbound delivery observable and idempotent across restarts
- expose clearer per-channel health and recovery signals

Exit criteria:

- channel runtime can recover after crash or restart without losing its place

## Phase 5 - Runtime Recovery And Operational Autonomy

Goal: make the runtime self-healing.

Work:

- register all critical loops with an explicit component supervisor
- persist outbound/dead-letter state and replay safely after restart
- add stronger no-progress and ping-pong guards for autonomous execution
- emit structured audit records for proactive behavior and recovery actions

Exit criteria:

- ClawLite recovers from common runtime failures without manual babysitting

## Phase 6 - Skills, Subagents, And Orchestration

Goal: make extensibility and multi-agent flows predictable.

Work:

- eliminate critical unavailable skills by adding dependency fallbacks
- add skill lifecycle controls such as enable/disable/pin/version
- harden subagent lifecycle with expiry, retry budgets, and zombie cleanup
- add stronger context boundaries and orchestration metadata between parent and child runs

Exit criteria:

- multi-agent work is durable, inspectable, and bounded

## Phase 7 - Advanced Memory And Self-Improvement

Goal: close the loop only after the platform is stable.

Work:

- improve memory recall consistency across scopes and backends
- extend working memory, episodic memory, consolidation, and decay
- add safe self-improvement pipeline: analyze, patch, test, validate, commit, notify
- keep the whole pipeline fail-closed when tests or policy checks fail

Exit criteria:

- advanced autonomy improves the system without silently damaging it

## Commit And Release Policy

- each green, reviewable slice gets its own commit
- each green commit is pushed immediately
- docs and changelog move with the code, not later
- tags and GitHub releases happen only at the end of a validated milestone

## Validation Policy

Minimum validation per slice:

- targeted pytest for touched areas first
- broader `python -m pytest tests/ -q --tb=short` for cross-cutting runtime work when feasible
- gateway/CLI smoke checks for public-surface changes
- explicit note when something remains unverified

## Current Execution Order

1. Phase 0 - docs and release hygiene
2. Phase 1 - dashboard/control-plane parity
3. Phase 2 - onboarding/bootstrap/heartbeat parity
4. Phase 3 - provider resilience
5. Phase 4 - channel durability
6. Phase 5 - runtime recovery and autonomy hardening
7. Phase 6 - skills and subagents
8. Phase 7 - advanced memory and self-improvement
