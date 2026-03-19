# Requirements: ClawLite

**Defined:** 2026-03-16  
**Milestone:** v0.6 — Robustness  
**Core Value:** An AI agent that genuinely works in any Python environment — including mobile/Termux — without dependencies that require compiling native code.

## v0.6 Requirements

### Core / Bugs

- [ ] **CORE-01**: The system does not leak session locks after sessions end
- [ ] **CORE-02**: The multi-agent worker executes commands without `shell=True` (no injection risk)
- [ ] **CORE-03**: `setup_logging()` is not called at module level (no import-time side effects)
- [ ] **CORE-04**: The engine executes independent tool calls in parallel (not sequentially)

### Providers

- [ ] **PROV-01**: When a circuit breaker opens, the agent automatically routes to the next configured provider
- [ ] **PROV-02**: Operators can configure multiple API keys per provider with individual quotas and cooldowns
- [ ] **PROV-03**: The system tracks estimated cost and consumed tokens by provider, session, and agent
- [ ] **PROV-04**: The catalog includes Bedrock (AWS), Qwen, and Mistral as native provider options

### MCP

- [ ] **MCP-01**: The agent can use local MCP servers via stdio transport (subprocess + pipes)
- [ ] **MCP-02**: The agent can consume MCP servers through SSE transport (streaming results)
- [ ] **MCP-03**: The system discovers and lists the tools available from an MCP server via the initialization handshake
- [ ] **MCP-04**: ClawLite exposes its own tools as an MCP server for external clients

### Gateway / Channels

- [ ] **GW-01**: The gateway enforces rate limiting by IP and by token on `/api/message`
- [ ] **GW-02**: Tools and channels report real latency and real errors in health checks (not always `ok=True`)
- [ ] **GW-03**: Signal, Matrix, and IRC channels are functional for both sending and receiving messages
- [ ] **GW-04**: Each subagent has its own context thread — no collisions between parallel runs

### Cron / Jobs

- [ ] **CRON-01**: A cron job can be triggered by an HTTP event (webhook trigger) in addition to time
- [ ] **CRON-02**: A failed job is retried with configurable backoff (retry policy per job)
- [ ] **CRON-03**: Job B can be configured to start only after Job A completes successfully
- [ ] **CRON-04**: The web dashboard displays scheduled jobs, execution history, and upcoming runs

### Memory

- [ ] **MEM-01**: The system generates embeddings locally without relying on a remote API (lightweight local model)
- [ ] **MEM-02**: Operators can export and import the full memory between workspaces/devices
- [ ] **MEM-03**: The engine automatically compresses working memory when the token budget exceeds 80%
- [ ] **MEM-04**: Memory supports a graph of relationships between entities (people, projects, concepts)

### Skills / Tools

- [ ] **SKILL-01**: Skills can be reloaded at runtime without restarting the agent
- [ ] **TOOL-01**: The agent can perform git operations (`status`, `diff`, `commit`, `log`) through a native tool without using the shell
- [ ] **TOOL-02**: The agent can execute SQL queries against SQLite or Postgres through a native tool
- [ ] **SKILL-02**: Operators can install a specific version of a skill (for example, `clawhub@1.2.0`)

## v2 Requirements (Deferred)

### Channels

- **CHAN-01**: Functional QQ channel
- **CHAN-02**: Functional DingTalk channel
- **CHAN-03**: Functional Feishu channel
- **CHAN-04**: STT/TTS without an ffmpeg dependency (portable alternative to pydub)

### Memory

- **MEM-05**: SQLite partitioning/archiving for databases with millions of records
- **MEM-06**: Redis as an optional distributed memory backend

### Providers

- **PROV-05**: Multi-model ensemble — provider voting for critical responses
- **PROV-06**: Native streaming of tool results (partial results during execution)

### Skills / Tools

- **TOOL-03**: Skill sandboxing — resource isolation per skill
- **SKILL-03**: Local skill marketplace with an index of available skills

## Out of Scope

| Feature | Reason |
|---------|--------|
| Native iOS/Android/macOS/Windows apps | Outside the Python/Termux scope |
| Pydantic v2 | maturin/Rust does not compile on Termux |
| Dependencies requiring C/Rust compilation | Break the Android environment |
| WebRTC / voice calls | Incompatible binary dependencies |
| OAuth flow for providers | High complexity, and use cases rarely require it |

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
