# ClawLite

## What This Is

ClawLite is a portable, autonomous AI agent written in Python and designed to run in constrained environments such as Android/Termux through PRoot-Distro on aarch64. It provides a FastAPI gateway, a multi-layer memory system, extensible tools, support for multiple LLM providers, and messaging channels such as Telegram and Discord, along with a self-evolution engine that remains unusual in this ecosystem.

## Core Value

An AI agent that genuinely works in any Python environment — including mobile/Termux — without dependencies that need native compilation.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- ✓ FastAPI gateway + WebSocket dashboard — v0.5
- ✓ Multi-layer memory system (episodic, semantic, working, shared) — v0.5
- ✓ 18 tools with registry and schema validation — v0.5
- ✓ 14+ LLM providers through LiteLLM with circuit breaker support — v0.5
- ✓ Channels: Telegram (complete), Discord, Slack, Email, WhatsApp — v0.5
- ✓ Cron/Heartbeat/Jobs with persistence — v0.5
- ✓ Self-Evolution Engine (Phase 7) — v0.5
- ✓ Multi-agent runtime with SubagentManager and AutonomyWakeCoordinator — v0.5
- ✓ Skills loader with frontmatter parsing — v0.5
- ✓ Pydantic v1 configuration with hot reload and token auditing — v0.5

### Active

<!-- Current milestone v0.6 scope -->

- [ ] Critical bugs fixed (`memory leak`, `shell=True`, `setup_logging`)
- [ ] MCP with native stdio transport
- [ ] Automatic failover when a circuit breaker opens
- [ ] Parallel tool execution in the engine
- [ ] Credential rotation per provider
- [ ] Accurate health checks for tools
- [ ] Rate limiting in the gateway
- [ ] Thread ownership for subagents
- [ ] Stub channels implemented (Signal/Matrix/IRC)
- [ ] Cost tracking by provider and session
- [ ] Cron with webhook triggers and per-job retry policy

### Out of Scope

- Native iOS/Android/macOS/Windows apps — outside the Python/Termux scope
- Pydantic v2 — `maturin`/Rust does not compile on Termux
- Dependencies that require C/Rust compilation — they break in the Android environment

## Context

- **Environment:** PRoot-Distro on Android/Termux (aarch64) — no `llog`/`lunwind`, so Rust/C extensions do not compile
- **Stack:** Python 3.12, FastAPI, Uvicorn, LiteLLM, questionary, Rich, SQLite
- **Current version:** v0.5.0b2
- **Reference parity (OpenClaw):** ~75% across comparable components
- **Unique differentiator:** Self-Evolution Engine (Phase 7) — uncommon among similar projects
- **Known bugs:** `_session_locks` memory leak (`engine.py:324`), `shell=True` in `multiagent.py`, `setup_logging()` at module level (`engine.py:21`)
- **Audit:** `docs/AUDIT_CLAWLITE_vs_OPENCLAW_2026-02-27.md` (882 lines, ~35-40% overall parity)

## Constraints

- **Compatibility:** No dependencies that need compilation on Termux — always use `--only-binary=:all:`
- **Pydantic:** v1.10.21 is mandatory (`v2` requires `maturin`/Rust)
- **Python:** 3.10+ (CI matrix: 3.10, 3.12)
- **Security:** Never use `shell=True` in new code
- **Tests:** Every test involving gateway + multiagent MUST use `_patch_db()` to isolate the database

## Planning Protocol

- Discovery-first workflow is mandatory for implementation sessions:
  1. inspect relevant code/docs,
  2. update planning artifacts,
  3. present findings and plan,
  4. then implement code changes.
- Planning artifacts must follow `.planning/PLANNING_DATA_SCHEMA.md`.
- Improvements are additive-first and compatibility-preserving by default.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| LiteLLM as the provider abstraction | Supports 100+ providers without custom code per provider | ✓ Good |
| FastAPI + Uvicorn | Native async stack, compatible with Termux through wheels | ✓ Good |
| SQLite as the memory backend | Zero native dependencies; works in any Python environment | ✓ Good |
| Pydantic v1 instead of v2 | `maturin`/Rust does not compile on Termux | ✓ Good (required) |
| Self-Evolution Engine disabled by default | Safety — autonomous code modification requires explicit opt-in | ✓ Good |

---
*Last updated: 2026-03-16 after milestone v0.6 initialization*
