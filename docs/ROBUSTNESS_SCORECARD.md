# ClawLite Robustness Scorecard

Last updated: 2026-03-16

## Purpose

This document turns the current audit into an execution backlog.

Benchmark references:

- `ref/openclaw`: boundary hardening, sandboxing, isolated cron execution, tool policy, operator controls
- `ref/nanobot`: simpler runtime contracts, predictable config/provider matching, smaller memory and cron surfaces

## Score Snapshot

| Area | Score | Notes |
|---|---:|---|
| Installation and onboarding | 8.0/10 | Good quickstart and CLI recovery now, but optional integrations still install by default |
| Providers and local runtimes | 7.5/10 | Strong coverage and failover path, but still lighter than OpenClaw in operational contracts |
| Tools and safety policy | 6.0/10 | Registry is solid, but policy is not enforced uniformly across all tool-like paths |
| Skills | 6.5/10 | Rich feature set, but parser, watcher, and script dispatch are still fragile |
| Cron and jobs | 5.0/10 | Biggest gap: ownership, cancellation, retention, and concurrency model |
| Memory | 7.0/10 | Powerful, but heavy and concentrated in a very large module |
| Config, wizard, docs | 8.0/10 | Mature enough for daily use; still needs better optional-dependency boundaries |
| Tests and regression safety | 7.5/10 | Large suite, but boundary and end-to-end coverage are still uneven |
| Architecture and maintainability | 6.0/10 | Major modules are now large enough to slow future hardening work |

Overall score: `6.8/10`

## P0 - Boundary and Runtime Safety

Goal: close cross-session access, inconsistent network policy, and runtime lifecycle bugs.

### 1. Enforce session ownership for cron and jobs

Status: completed on `main` on 2026-03-16.

Files:

- `clawlite/tools/cron.py`
- `clawlite/tools/jobs.py`
- `clawlite/scheduler/cron.py`
- `clawlite/jobs/queue.py`

Acceptance:

- one session cannot inspect, cancel, remove, enable, disable, or run another session's cron/job resources
- `list` defaults to current session and rejects foreign `session_id` overrides
- tests cover same-session and cross-session behavior

Reference signal:

- OpenClaw isolated cron runs use fresh session boundaries and explicit ownership controls

### 2. Make running-job cancellation real

Status: completed on `main` on 2026-03-16.

Files:

- `clawlite/jobs/queue.py`
- job worker call sites in `clawlite/gateway/server.py`

Acceptance:

- cancelling a running job transitions it to `cancelled`
- worker functions receive or poll a cancellation signal
- cancelled jobs do not report `done`

### 3. Route all outbound skill traffic through one network policy

Status: completed locally on 2026-03-16. Keep uncommitted until the docs batch is ready.

Files:

- `clawlite/tools/skill.py`
- `clawlite/tools/web.py`

Acceptance:

- `run_skill weather` honors proxy, allowlist, denylist, and private IP blocking
- no skill helper uses raw `httpx` for unrestricted outbound requests
- skill tests cover unavailable `web_fetch`, safety-policy blocking, and fallback to Open-Meteo
- `tests/tools/test_web.py` continues to cover allowlist, denylist, and proxy behavior for the shared network path

### 4. Fix browser lifecycle leaks

Status: completed locally on 2026-03-16. Keep uncommitted until the docs batch is ready.

Files:

- `clawlite/tools/browser.py`

Acceptance:

- Playwright controller is retained and closed explicitly
- repeated open/close cycles do not leak browser state
- browser tests cover `navigate`, `close`, and startup failure hints

## P1 - Automation and Skill Robustness

Goal: make recurring work predictable under load and make skills easier to evolve safely.

### 1. Rework cron execution around isolation and concurrency

Status: completed locally on 2026-03-16. Keep uncommitted until the docs batch is ready.

Files:

- `clawlite/scheduler/cron.py`
- `clawlite/tools/cron.py`

Acceptance:

- configurable max concurrent runs
- due jobs are not blocked behind one slow callback
- manual `run_job()` and scheduled execution share the same claim/lease semantics

Reference signal:

- OpenClaw already exposes `cron.maxConcurrentRuns` and isolated cron session handling

### 2. Add cron retention and cleanup

Status: completed locally on 2026-03-16. Keep uncommitted until the docs batch is ready.

Files:

- `clawlite/scheduler/cron.py`
- session/journal storage touched by cron runs

Acceptance:

- old completed disabled cron jobs are pruned by retention policy
- expired orphaned lease state is cleared safely
- corrupt cron stores are moved aside and recovery still starts with an empty scheduler

### 3. Replace custom skill frontmatter parsing with real YAML

Status: completed locally on 2026-03-16. Keep uncommitted until the docs batch is ready.

Files:

- `clawlite/core/skills.py`

Acceptance:

- YAML frontmatter is parsed with `PyYAML`
- nested mappings, multiline values, and lists behave consistently
- malformed frontmatter falls back to the legacy parser instead of breaking discovery

### 4. Replace polling-heavy skill watching with event-first watching

Status: completed locally on 2026-03-16. Keep uncommitted until the docs batch is ready.

Files:

- `clawlite/core/skills.py`
- optional watcher integration points

Acceptance:

- `watchfiles` is used when available
- polling remains as fallback
- debounced watchfile events still trigger a follow-up refresh without requiring another filesystem event
- watcher diagnostics expose active mode and last refresh outcome

### 5. Improve tool validation feedback

Files:

- `clawlite/tools/registry.py`

Acceptance:

- validation returns all argument issues, not only the first one
- error messages remain machine-readable for agents

Reference signal:

- Nanobot's tool validation surface is smaller but more explicit and testable

## P2 - Maintainability and Packaging

Goal: reduce installation drag and lower regression risk in the biggest modules.

### 1. Split optional integrations into extras

Status: completed locally on 2026-03-16. Keep uncommitted until the docs batch is ready.

Files:

- `pyproject.toml`
- `requirements.txt`
- docs and onboarding copy

Acceptance:

- browser, Telegram, and media dependencies can be installed separately; unused Discord/Slack package deps were removed from the base install
- base install remains usable for CLI + gateway + core runtime

### 2. Break up the largest modules

Status: in progress locally on 2026-03-17. Keep uncommitted until the docs batch is ready.

Priority modules:

- `clawlite/core/memory.py`
- `clawlite/gateway/server.py`
- `clawlite/channels/telegram.py`

Acceptance:

- each module is split by responsibility, not by arbitrary file size
- public behavior is preserved behind existing interfaces
- each extraction lands with focused regression tests
- first slices extracted provider/dashboard payload helpers into `clawlite/gateway/payloads.py`
- dashboard state summary builders now live in `clawlite/gateway/dashboard_state.py`
- dashboard memory summary now lives in `clawlite/gateway/memory_dashboard.py`
- engine diagnostics payload builders now live in `clawlite/gateway/engine_diagnostics.py`
- control-plane admin handlers now live in `clawlite/gateway/control_handlers.py`
- channel webhook handlers now live in `clawlite/gateway/webhooks.py`
- memory diagnostics/analysis helpers now live in `clawlite/core/memory_reporting.py`
- memory versioning helpers now live in `clawlite/core/memory_versions.py`
- memory quality-state helpers now live in `clawlite/core/memory_quality.py`
- memory maintenance loops and purge/consolidation helpers now live in `clawlite/core/memory_maintenance.py`

### 3. Add real end-to-end smoke coverage

Targets:

- local providers (`ollama`, `vllm`)
- cron execution
- browser tool bootstrap
- configure wizard and generated config

Acceptance:

- CI runs at least one smoke path per public runtime surface
- failures produce setup hints instead of raw tracebacks

## Recommended Execution Order

1. Session ownership for cron and jobs
2. Running-job cancellation
3. Unified outbound network policy for skills
4. Browser lifecycle fix
5. Cron concurrency + retention
6. Skills YAML + watcher cleanup
7. Tool validation aggregation
8. Packaging extras
9. Large-module extraction

## Done Definition

A backlog item is only complete when:

- behavior is enforced in code, not only documented
- targeted tests cover the regression path
- public docs match the shipped behavior
- operator-facing errors include a useful hint when setup or runtime fails
