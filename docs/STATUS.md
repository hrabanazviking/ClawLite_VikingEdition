# ClawLite Status

Last updated: 2026-03-15

## Summary

ClawLite is a **complete, production-grade local-first autonomous agent runtime**. All originally planned features for the current milestone are implemented and the full test suite passes (1178 tests, 0 failures).

## Current Baseline

- Latest tag: `v0.5.0-beta.2`
- `main` is well ahead of that tag — contains all features described below
- Suite: `python -m pytest` → **1178 passed, 0 failed**
- CI: pytest on Python 3.10 and 3.12, Ruff lint, smoke imports, autonomy contracts

## What Is Complete

### Core Runtime
- FastAPI gateway (HTTP + WebSocket) on `:8787`
- Operator dashboard (packaged HTML/CSS/JS) with live chat, event feed, autorefresh
- Agent engine with `stream_run()` / `ProviderChunk` streaming support
- Provider failover, auth/quota suppression, manual recovery from CLI + dashboard
- Heartbeat supervisor with recovery telemetry and timezone-aware scheduling
- Cron engine (persistent, replay-safe) with dashboard visibility
- Autonomy wake coordinator — manual and scheduled wakes
- Dead-letter queue + inbound journal replay (automated and operator-triggered)
- Subagent lifecycle, orchestration, context isolation

### Memory
- Hybrid BM25 + vector similarity search
- SQLite (local) and pgvector (Postgres) backends
- FTS5 full-text indexing, temporal decay, salience scoring
- Consolidation loop (episodic → knowledge)
- Snapshot / rollback with control-plane confirmation
- Memory suggestions refresh from dashboard

### Channels
| Channel | Status |
|---------|--------|
| **Telegram** | ✅ Complete — polling + webhook, reactions, topics, reply keyboards, streaming, offset safety, pairing, dedupe, circuit breaker |
| **Discord** | ✅ Complete — gateway WS, slash commands, buttons, voice messages, webhooks, polls, streaming, embeds, threads, attachments |
| **Email** | 🟡 Usable — IMAP inbound + SMTP outbound |
| **WhatsApp** | 🟡 Usable — webhook inbound + outbound bridge |
| **Slack** | 📤 Send-only |

### Tools (17+)
`files` · `exec` · `spawn` · `process` · `web` · `browser` (Playwright)
`pdf` · `tts` · `mcp` · `sessions` · `cron` · `memory` · `skill`
`message` · `agents` · `discord_admin` · `apply_patch`

### Skills (25+)
`web-search` · `cron` · `memory` · `coding-agent` · `summarize`
`github-issues` · `notion` · `obsidian` · `spotify` · `docker`
`jira` · `linear` · `trello` · `1password` · `apple-notes`
`weather` · `tmux` · `model-usage` · `session-logs` · `skill-creator`
`github` · `gh-issues` · `healthcheck` · `clawhub` · `hub`

### Config
- Full Pydantic v2 schema (`clawlite/config/schema.py`)
- Interactive wizard: `clawlite configure --flow quickstart`
- Full field reference: [`docs/CONFIGURATION.md`](CONFIGURATION.md)

### Workspace Templates
`AGENTS.md` · `IDENTITY.md` · `SOUL.md` · `HEARTBEAT.md` · `USER.md`

## Validation

```bash
python -m pytest tests/ -q --tb=short    # 1178 passed
python -m ruff check --select=E,F,W .   # clean
clawlite validate config
```

## Reference Repositories

- Behavioral parity reference: `/root/projetos/ref/openclaw`
- Autonomy/reliability reference: `/root/projetos/ref/nanobot`
- Memory inspiration reference: `/root/projetos/memU`

## Delivery Policy

- Commit and push every green slice
- Update docs in the same cycle as behavior changes
- Reserve tags and GitHub releases for the end of a validated milestone
- Keep `CHANGELOG.md` current as work lands on `main`
