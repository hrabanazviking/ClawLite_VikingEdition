# Roadmap: ClawLite

## Milestones

- ✅ **v0.5 Foundation** - Phases 1-7 (shipped 2026-03-07)
- 🚧 **v0.6 Robustness** - Phases 8-17 (in progress)

## Phases

<details>
<summary>✅ v0.5 Foundation (Phases 1-7) - SHIPPED 2026-03-07</summary>

- Phase 1: FastAPI gateway + WebSocket + dashboard
- Phase 2: Multi-layer memory system
- Phase 3: Tools registry (18 tools) + providers (14+) with circuit breaker
- Phase 4: Channels (Telegram, Discord, Slack, Email, WhatsApp)
- Phase 5: Cron + Heartbeat + Jobs with persistence
- Phase 6: Multi-agent support (SubagentManager, AutonomyWakeCoordinator)
- Phase 7: Self-Evolution Engine (SourceScanner, FixProposer, PatchApplicator)

917 tests passing, 57,859 LOC.

</details>

---

### 🚧 v0.6 Robustness (In Progress)

**Milestone Goal:** Fix critical bugs, close security gaps, and complete unfinished subsystems such as MCP, channels, advanced cron, local memory, and runtime skills.

**Phase Numbering:** 8–17 (continuation of v0.5)

- [ ] **Phase 8: Critical Bugs** - Eliminate the memory leak, `shell=True`, and `setup_logging` side effects
- [ ] **Phase 9: Engine Hardening** - Parallel tools, provider failover, and subagent thread isolation
- [ ] **Phase 10: Provider Management** - Credential rotation, cost tracking, and an expanded catalog
- [ ] **Phase 11: Full MCP** - stdio + SSE transport, discovery, and a native MCP server
- [ ] **Phase 12: Gateway Security** - Rate limiting and accurate health checks
- [ ] **Phase 13: Stub Channels** - Working Signal, Matrix, and IRC support
- [ ] **Phase 14: Advanced Cron** - Webhook triggers, retry policy, job dependencies, and dashboard visibility
- [ ] **Phase 15: Local Memory** - Local embeddings, export/import, and token-budget compression
- [ ] **Phase 16: Memory Graph** - A graph of relationships between entities
- [ ] **Phase 17: Skills and Tools** - Skill hot reload, versioning, and native Git/SQL tools

## Phase Details

### Phase 8: Critical Bugs
**Goal**: The agent does not leak memory, does not execute commands with injection risk, and does not pollute the namespace during import.
**Depends on**: Phase 7 (v0.5 shipped)
**Requirements**: CORE-01, CORE-02, CORE-03
**Success Criteria** (what must be TRUE):
  1. Closed sessions do not accumulate entries in `_session_locks`; the dictionary never grows beyond active sessions
  2. The multi-agent worker launches subprocesses without `shell=True`, preventing command-name injection
  3. Importing `clawlite.core.engine` does not configure logging handlers as a side effect
**Plans**: TBD

### Phase 9: Engine Hardening
**Goal**: The engine runs tool calls in parallel, automatically switches providers when a circuit breaker opens, and keeps subagent thread contexts isolated.
**Depends on**: Phase 8
**Requirements**: CORE-04, PROV-01, GW-04
**Success Criteria** (what must be TRUE):
  1. Independent tool calls within one agent response are launched in parallel, so total time is `max(t_i)` rather than `sum(t_i)`
  2. When a provider's circuit breaker opens, the next request automatically uses the next configured provider without operator intervention
  3. Two subagents running in parallel do not mix thread context; each run is fully isolated
**Plans**: TBD

### Phase 10: Provider Management
**Goal**: The operator manages multiple API keys per provider with quotas, cooldowns, and cost tracking, while the catalog includes Bedrock, Qwen, and Mistral.
**Depends on**: Phase 9
**Requirements**: PROV-02, PROV-03, PROV-04
**Success Criteria** (what must be TRUE):
  1. The operator can register two or more API keys for the same provider, each with independent quota and cooldown settings
  2. After every LLM call, the system records consumed tokens and estimated cost by provider, session, and agent, and exposes that data via API
  3. AWS Bedrock, Qwen, and Mistral appear as native options in the provider catalog and work through the same interface as the rest
**Plans**: TBD

### Phase 11: Full MCP
**Goal**: The agent uses local MCP servers over stdio and remote MCP servers over SSE, discovers tools during handshake, and exposes its own tools as an MCP server.
**Depends on**: Phase 10
**Requirements**: MCP-01, MCP-02, MCP-03, MCP-04
**Success Criteria** (what must be TRUE):
  1. The agent starts a local MCP server through subprocess + pipes and calls tools there without relying on HTTP
  2. The agent consumes results from a remote MCP server over SSE without blocking the event loop
  3. When connecting to an MCP server, the system automatically lists available tools through the initialization handshake
  4. An external MCP client can discover and call ClawLite tools through the standard MCP protocol
**Plans**: TBD

### Phase 12: Gateway Security
**Goal**: The gateway protects `/api/message` with rate limiting, and health checks report the real state of subsystems.
**Depends on**: Phase 11
**Requirements**: GW-01, GW-02
**Success Criteria** (what must be TRUE):
  1. Requests above the configured limit on `/api/message` return HTTP 429, independently by IP and by token
  2. `GET /api/health` returns real latency and recent errors for each tool and channel rather than always returning `ok: true`
  3. A degraded tool, such as one timing out, appears as `degraded` or `error` in the health check rather than `ok`
**Plans**: TBD

### Phase 13: Stub Channels
**Goal**: Signal, Matrix, and IRC graduate from stubs to functional channels that operators can use to send and receive messages.
**Depends on**: Phase 12
**Requirements**: GW-03
**Success Criteria** (what must be TRUE):
  1. The operator configures Signal and the agent can send and receive Signal messages
  2. The operator configures Matrix and the agent can send and receive messages in a Matrix room
  3. The operator configures IRC and the agent can connect to a server, join a channel, and exchange messages
**Plans**: TBD

### Phase 14: Advanced Cron
**Goal**: Cron jobs support webhook triggers, retry with backoff, inter-job dependencies, and dashboard visibility.
**Depends on**: Phase 13
**Requirements**: CRON-01, CRON-02, CRON-03, CRON-04
**Success Criteria** (what must be TRUE):
  1. An HTTP `POST` to the webhook endpoint immediately triggers the configured job regardless of its schedule
  2. A failed job is retried automatically with configurable backoff; both retry count and retry interval are configurable per job
  3. Job B, when dependent on Job A, only starts after Job A succeeds within the same execution window
  4. The web dashboard shows scheduled jobs, recent execution history, and upcoming run times
**Plans**: TBD

### Phase 15: Local Memory
**Goal**: The system generates embeddings without a remote API, supports memory export/import, and compresses working memory automatically.
**Depends on**: Phase 14
**Requirements**: MEM-01, MEM-02, MEM-03
**Success Criteria** (what must be TRUE):
  1. Semantic memory search works without an API key because the embeddings model runs locally
  2. The operator can export complete memory to a file and import it into another workspace or device while preserving context
  3. When working memory exceeds 80% of token budget, the system compresses it automatically without operator intervention
**Plans**: TBD

### Phase 16: Memory Graph
**Goal**: Memory supports a graph of relationships between entities so people, projects, and concepts become connected and queryable.
**Depends on**: Phase 15
**Requirements**: MEM-04
**Success Criteria** (what must be TRUE):
  1. The agent can create a named relationship between two entities, for example, "João works on Project X," and retrieve it by query
  2. Graph queries return transitively related entities, for example, all of João's projects through graph traversal
  3. Relationships persist across sessions and appear in agent context when relevant
**Plans**: TBD

### Phase 17: Skills and Tools
**Goal**: Skills can be reloaded at runtime, support versioning, and the agent has native Git and SQL tools without invoking a shell.
**Depends on**: Phase 16
**Requirements**: SKILL-01, SKILL-02, TOOL-01, TOOL-02
**Success Criteria** (what must be TRUE):
  1. The operator modifies a skill file and triggers hot reload; the agent begins using the new version without restarting
  2. The operator installs a specific version of a skill, such as `clawhub@1.2.0`, and the system uses that exact version
  3. The agent executes `git status`, `git diff`, `git commit`, and `git log` through a native tool without `shell=True`
  4. The agent executes SQL queries against SQLite and Postgres through a native tool without an external subprocess
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 8 → 9 → 10 → 11 → 12 → 13 → 14 → 15 → 16 → 17

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1-7. Foundation | v0.5 | ✅ | Complete | 2026-03-07 |
| 8. Critical Bugs | v0.6 | 0/? | Not started | - |
| 9. Engine Hardening | v0.6 | 0/? | Not started | - |
| 10. Provider Management | v0.6 | 0/? | Not started | - |
| 11. Full MCP | v0.6 | 0/? | Not started | - |
| 12. Gateway Security | v0.6 | 0/? | Not started | - |
| 13. Stub Channels | v0.6 | 0/? | Not started | - |
| 14. Advanced Cron | v0.6 | 0/? | Not started | - |
| 15. Local Memory | v0.6 | 0/? | Not started | - |
| 16. Memory Graph | v0.6 | 0/? | Not started | - |
| 17. Skills and Tools | v0.6 | 0/? | Not started | - |
