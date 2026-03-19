# ClawLite

## What This Is

ClawLite is a portable, autonomous AI agent written in Python, designed to run in constrained environments such as Android/Termux via PRoot-Distro on aarch64. It provides a FastAPI gateway, a multi-layer memory system, extensible tools, support for multiple LLM providers, and messaging channels (Telegram, Discord, etc.), along with a self-evolution engine that is unique in this ecosystem.

## Core Value

An AI agent that genuinely works in any Python environment — including mobile/Termux — without dependencies that require compiling native code.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- ✓ FastAPI gateway + WebSocket with dashboard — v0.5
- ✓ Multi-layer memory system (episodic, semantic, working, shared) — v0.5
- ✓ 18 tools with registry and schema validation — v0.5
- ✓ 14+ LLM providers via LiteLLM with circuit breaker — v0.5
- ✓ Channels: Telegram (complete), Discord, Slack, Email, WhatsApp — v0.5
- ✓ Cron/Heartbeat/Jobs with persistence — v0.5
- ✓ Self-Evolution Engine (Phase 7) — v0.5
- ✓ Multi-agent support with SubagentManager and AutonomyWakeCoordinator — v0.5
- ✓ Skills loader with frontmatter parsing — v0.5
- ✓ Pydantic v1 config with hot reload and token auditing — v0.5

### Active

<!-- Current milestone v0.6 scope -->

- [ ] Critical bugs fixed (memory leak, shell=True, setup_logging)
- [ ] MCP with native stdio transport
- [ ] Automatic failover when a circuit breaker opens
- [ ] Parallel tool execution in the engine
- [ ] Credential rotation per provider
- [ ] Real health checks in tools
- [ ] Rate limiting in the gateway
- [ ] Thread ownership in subagents
- [ ] Stub channels implemented (Signal/Matrix/IRC)
- [ ] Cost tracking per provider/session
- [ ] Cron with webhook triggers and per-job retry policy

### Out of Scope

- Native iOS/Android/macOS/Windows apps — outside the Python/Termux scope
- Pydantic v2 — maturin/Rust does not compile on Termux
- Dependencies that require compiling C/Rust — breaks in the Android environment

## Context

- **Environment:** PRoot-Distro on Android/Termux (aarch64) — no llog/lunwind, cannot compile Rust/C extensions
- **Stack:** Python 3.12, FastAPI, Uvicorn, LiteLLM, questionary, Rich, SQLite
- **Current version:** v0.5.0b2
- **Parity with the reference project (OpenClaw):** ~75% across comparable components
- **Unique differentiator:** Self-Evolution Engine (Phase 7) — no similar project has it
- **Known bugs:** `_session_locks` memory leak (`engine.py:324`), `shell=True` in `multiagent.py`, `setup_logging()` at module level (`engine.py:21`)
- **Audit:** `docs/AUDIT_CLAWLITE_vs_OPENCLAW_2026-02-27.md` (882 lines, ~35-40% overall parity)

## Constraints

- **Compatibility:** No dependencies that need compilation on Termux — always use `--only-binary=:all:`
- **Pydantic:** v1.10.21 required (v2 requires maturin/Rust)
- **Python:** 3.10+ (CI matrix: 3.10, 3.12)
- **Security:** Never use `shell=True` in new code
- **Tests:** Every test involving gateway + multiagent MUST use `_patch_db()` to isolate the database

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| LiteLLM as the provider abstraction | Supports 100+ providers without custom code per provider | ✓ Good |
| FastAPI + Uvicorn | Native async, compatible with Termux through wheels | ✓ Good |
| SQLite as the memory backend | Zero native dependencies, works in any Python environment | ✓ Good |
| Pydantic v1 (not v2) | maturin/Rust does not compile on Termux | ✓ Good (required) |
| Self-Evolution Engine disabled by default | Security — autonomous code modification requires explicit opt-in | ✓ Good |

---
*Last updated: 2026-03-16 after v0.6 milestone initialization*
