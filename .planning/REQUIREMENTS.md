# Requirements: ClawLite

**Defined:** 2026-03-16
**Milestone:** v0.6 — Robustness
**Core Value:** An AI agent that genuinely works in any Python environment — including mobile/Termux — without dependencies that need native compilation.

## v0.6 Requirements

### Core / Bugs

- [ ] **CORE-01**: The system does not leak session locks after sessions end
- [ ] **CORE-02**: The multi-agent worker executes commands without `shell=True` and without injection risk
- [ ] **CORE-03**: `setup_logging()` is not called at module import time, avoiding import side effects
- [ ] **CORE-04**: The engine executes independent tool calls in parallel rather than sequentially

### Providers

- [ ] **PROV-01**: When a circuit breaker opens, the agent automatically routes to the next configured provider
- [ ] **PROV-02**: The operator can configure multiple API keys per provider, each with its own quota and cooldown
- [ ] **PROV-03**: The system tracks estimated cost and consumed tokens by provider, session, and agent
- [ ] **PROV-04**: The catalog includes Bedrock (AWS), Qwen, and Mistral as native provider options

### MCP

- [ ] **MCP-01**: The agent can use local MCP servers via stdio transport (subprocess + pipes)
- [ ] **MCP-02**: The agent can consume MCP servers over SSE transport, including streamed results
- [ ] **MCP-03**: The system discovers and lists the tools exposed by an MCP server during the initialization handshake
- [ ] **MCP-04**: ClawLite exposes its own tools as an MCP server for external clients

### Gateway / Channels

- [ ] **GW-01**: The gateway applies rate limiting by IP and by token on `/api/message`
- [ ] **GW-02**: Tools and channels report real latency and errors in health checks rather than always returning `ok=True`
- [ ] **GW-03**: Signal, Matrix, and IRC channels are fully functional for sending and receiving messages
- [ ] **GW-04**: Each subagent has its own thread context, with no collisions across parallel runs

### Cron / Jobs

- [ ] **CRON-01**: A cron job can be triggered by an HTTP event (webhook trigger) as well as by time
- [ ] **CRON-02**: A failed job is retried with configurable backoff through a per-job retry policy
- [ ] **CRON-03**: Job B can be configured to start only after Job A completes successfully
- [ ] **CRON-04**: The web dashboard shows scheduled jobs, execution history, and upcoming runs

### Memory

- [ ] **MEM-01**: The system generates embeddings locally without depending on a remote API, using a lightweight local model
- [ ] **MEM-02**: The operator can export and import complete memory across workspaces and devices
- [ ] **MEM-03**: The engine automatically compresses working memory when token budget usage exceeds 80%
- [ ] **MEM-04**: Memory supports a relationship graph between entities such as people, projects, and concepts

### Skills / Tools

- [ ] **SKILL-01**: Skills can be reloaded at runtime without restarting the agent
- [ ] **TOOL-01**: The agent can perform Git operations (`status`, `diff`, `commit`, `log`) through a native tool without invoking a shell
- [ ] **TOOL-02**: The agent can run SQL queries against SQLite or Postgres through a native tool
- [ ] **SKILL-02**: The operator can install a specific version of a skill, for example `clawhub@1.2.0`

## v2 Requirements (Deferred)

### Channels

- **CHAN-01**: Fully functional QQ channel
- **CHAN-02**: Fully functional DingTalk channel
- **CHAN-03**: Fully functional Feishu channel
- **CHAN-04**: STT/TTS without an `ffmpeg` dependency, using a portable alternative to `pydub`

### Memory

- **MEM-05**: SQLite partitioning and archival for databases with millions of records
- **MEM-06**: Redis as an optional distributed memory backend

### Providers

- **PROV-05**: Multi-model ensemble voting across providers for critical responses
- **PROV-06**: Native streaming of tool results with partial results during execution

### Skills / Tools

- **TOOL-03**: Skill sandboxing with per-skill resource isolation
- **SKILL-03**: A local skill marketplace with an index of available skills

## Out of Scope

| Feature | Reason |
|---------|--------|
| Native iOS/Android/macOS/Windows apps | Outside the Python/Termux scope |
| Pydantic v2 | `maturin`/Rust does not compile on Termux |
| Dependencies that require C/Rust compilation | They break in the Android environment |
| WebRTC / voice calls | Incompatible binary dependencies |
| OAuth flow for providers | High complexity; most use cases do not need it |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CORE-01 | Phase 8 | Pending |
| CORE-02 | Phase 8 | Pending |
| CORE-03 | Phase 8 | Pending |
| CORE-04 | Phase 9 | Pending |
| PROV-01 | Phase 9 | Pending |
| GW-04 | Phase 9 | Pending |
| PROV-02 | Phase 10 | Pending |
| PROV-03 | Phase 10 | Pending |
| PROV-04 | Phase 10 | Pending |
| MCP-01 | Phase 11 | Pending |
| MCP-02 | Phase 11 | Pending |
| MCP-03 | Phase 11 | Pending |
| MCP-04 | Phase 11 | Pending |
| GW-01 | Phase 12 | Pending |
| GW-02 | Phase 12 | Pending |
| GW-03 | Phase 13 | Pending |
| CRON-01 | Phase 14 | Pending |
| CRON-02 | Phase 14 | Pending |
| CRON-03 | Phase 14 | Pending |
| CRON-04 | Phase 14 | Pending |
| MEM-01 | Phase 15 | Pending |
| MEM-02 | Phase 15 | Pending |
| MEM-03 | Phase 15 | Pending |
| MEM-04 | Phase 16 | Pending |
| SKILL-01 | Phase 17 | Pending |
| SKILL-02 | Phase 17 | Pending |
| TOOL-01 | Phase 17 | Pending |
| TOOL-02 | Phase 17 | Pending |

**Coverage:**
- v0.6 requirements: 28 total
- Mapped to phases: 28
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-16*
*Last updated: 2026-03-16 after ROADMAP.md creation (Phases 8-17)*
