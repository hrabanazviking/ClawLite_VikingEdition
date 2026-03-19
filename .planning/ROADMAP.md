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
- Phase 6: Multi-agent system (SubagentManager, AutonomyWakeCoordinator)
- Phase 7: Self-Evolution Engine (SourceScanner, FixProposer, PatchApplicator)

917 tests passing, 57,859 LOC.

</details>

---

### 🚧 v0.6 Robustness (In Progress)

**Milestone Goal:** Fix critical bugs, close security gaps, and complete unfinished subsystems (MCP, channels, advanced cron, local memory, runtime skills).

**Phase Numbering:** 8–17 (continuing from v0.5)

- [ ] **Phase 8: Critical Bugs** - Close the memory leak, `shell=True`, and `setup_logging` issues
- [ ] **Phase 9: Engine Hardening** - Parallel tools, provider failover, subagent thread isolation
- [ ] **Phase 10: Provider Management** - Credential rotation, cost tracking, expanded catalog
- [ ] **Phase 11: Complete MCP** - stdio + SSE transport, discovery, native MCP server
- [ ] **Phase 12: Gateway Security** - Rate limiting and real health checks
- [ ] **Phase 13: Stub Channels** - Functional Signal, Matrix, and IRC
- [ ] **Phase 14: Advanced Cron** - Webhook triggers, retry policy, job dependencies, dashboard
- [ ] **Phase 15: Local Memory** - Local embeddings, export/import, token-budget compression
- [ ] **Phase 16: Memory Graph** - Relationship graph between entities
- [ ] **Phase 17: Skills and Tools** - Skill hot reload, versioning, native git and SQL tools

## Phase Details

### Phase 8: Critical Bugs
**Goal**: The agent has no memory leaks, does not execute commands with injection risk, and does not pollute the namespace during import
**Depends on**: Phase 7 (v0.5 shipped)
**Requirements**: CORE-01, CORE-02, CORE-03
**Success Criteria** (what must be TRUE):
  1. Ended sessions do not accumulate entries in `_session_locks` — the dictionary does not grow beyond active sessions
  2. The multi-agent worker executes subprocesses without `shell=True` — it does not accept injection through command names
  3. Importing `clawlite.core.engine` does not configure logging handlers as a side effect
**Plans**: TBD

### Phase 9: Engine Hardening
**Goal**: The engine executes tools in parallel, automatically routes to another provider when a circuit breaker opens, and subagents do not share thread context
**Depends on**: Phase 8
**Requirements**: CORE-04, PROV-01, GW-04
**Success Criteria** (what must be TRUE):
  1. Independent tool calls in an agent response are launched in parallel — total time is max(t_i), not sum(t_i)
  2. When a provider's circuit breaker opens, the next request automatically uses the next configured provider without operator intervention
  3. Two subagents running in parallel do not mix thread context — each run has complete isolation
**Plans**: TBD

### Phase 10: Provider Management
**Goal**: The operator manages multiple API keys per provider with quota, cooldown, and cost tracking; the catalog includes Bedrock, Qwen, and Mistral
**Depends on**: Phase 9
**Requirements**: PROV-02, PROV-03, PROV-04
**Success Criteria** (what must be TRUE):
  1. The operator can register two or more API keys for the same provider; each key has independent quota and cooldown
  2. After each LLM call, the system records consumed tokens and estimated cost by provider, session, and agent — queryable through the API
  3. AWS Bedrock, Qwen, and Mistral appear as native options in the provider catalog and work through the same interface as the others
**Plans**: TBD

### Phase 11: Complete MCP
**Goal**: The agent uses local MCP servers (stdio) and remote ones (SSE), discovers tools through the handshake, and exposes its own tools as an MCP server
**Depends on**: Phase 10
**Requirements**: MCP-01, MCP-02, MCP-03, MCP-04
**Success Criteria** (what must be TRUE):
  1. The agent starts a local MCP server via subprocess + pipes and calls tools on it without depending on HTTP
  2. The agent consumes results from a remote MCP server via SSE (streaming) without blocking the event loop
  3. When connecting to an MCP server, the system automatically lists the available tools through the initialization handshake
  4. An external MCP client can discover and call ClawLite tools through the standard MCP protocol
**Plans**: TBD

### Phase 12: Gateway Security
**Goal**: The gateway protects `/api/message` with rate limiting, and health checks report the real state of subsystems
**Depends on**: Phase 11
**Requirements**: GW-01, GW-02
**Success Criteria** (what must be TRUE):
  1. Requests above the configured limit on `/api/message` return 429 — independently by IP and by token
  2. `GET /api/health` returns real latency and recent errors per tool and channel — it does not always return `ok: true`
  3. A degraded tool (for example, a timeout) appears with status `degraded` or `error` in the health check, not `ok`
**Plans**: TBD

### Phase 13: Stub Channels
**Goal**: Signal, Matrix, and IRC move from stub to functional — the operator can send and receive messages through these channels
**Depends on**: Phase 12
**Requirements**: GW-03
**Success Criteria** (what must be TRUE):
  1. The operator configures Signal, and the agent sends and receives messages through Signal
  2. The operator configures Matrix, and the agent sends and receives messages in a Matrix room
  3. The operator configures IRC, and the agent connects to a server, joins a channel, and exchanges messages
**Plans**: TBD

### Phase 14: Advanced Cron
**Goal**: Cron jobs support webhook triggers, retry with backoff, job dependencies, and visibility in the web dashboard
**Depends on**: Phase 13
**Requirements**: CRON-01, CRON-02, CRON-03, CRON-04
**Success Criteria** (what must be TRUE):
  1. An HTTP POST to the webhook endpoint triggers the configured job immediately, regardless of the time-based schedule
  2. A failed job is retried automatically with configurable backoff; both retry count and interval are configurable per job
  3. Job B, when dependent on Job A, only starts after Job A completes successfully within the same execution window
  4. The web dashboard shows the list of scheduled jobs, the history of recent runs, and the next expected execution times
**Plans**: TBD

### Phase 15: Local Memory
**Goal**: The system generates embeddings without a remote API, supports memory export/import, and automatically compresses working memory
**Depends on**: Phase 14
**Requirements**: MEM-01, MEM-02, MEM-03
**Success Criteria** (what must be TRUE):
  1. Semantic memory search works without any configured API key — the embeddings model runs locally
  2. The operator exports the full memory to a file and imports it into another workspace/device, recovering the same context
  3. When working memory exceeds 80% of the token budget, the system compresses it automatically without operator intervention
**Plans**: TBD

### Phase 16: Memory Graph
**Goal**: Memory supports a graph of relationships between entities — people, projects, and concepts are connected and queryable
**Depends on**: Phase 15
**Requirements**: MEM-04
**Success Criteria** (what must be TRUE):
  1. The agent can create a named relationship between two entities (for example, "João works on Project X") and retrieve it through a query
  2. Graph queries return transitively related entities (for example, all of João's projects through the graph)
  3. Relationships persist across sessions and appear in the agent context when relevant
**Plans**: TBD

### Phase 17: Skills and Tools
**Goal**: Skills are reloadable at runtime, support versioning, and the agent has native tools for git and SQL without invoking the shell
**Depends on**: Phase 16
**Requirements**: SKILL-01, SKILL-02, TOOL-01, TOOL-02
**Success Criteria** (what must be TRUE):
  1. The operator edits a skill file and triggers hot reload — the agent uses the new version without restarting
  2. The operator installs a specific skill version (for example, `clawhub@1.2.0`), and the system uses exactly that version
  3. The agent executes `git status`, `git diff`, `git commit`, and `git log` through a native tool without a `subprocess shell=True`
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
| 11. Complete MCP | v0.6 | 0/? | Not started | - |
| 12. Gateway Security | v0.6 | 0/? | Not started | - |
| 13. Stub Channels | v0.6 | 0/? | Not started | - |
| 14. Advanced Cron | v0.6 | 0/? | Not started | - |
| 15. Local Memory | v0.6 | 0/? | Not started | - |
| 16. Memory Graph | v0.6 | 0/? | Not started | - |
| 17. Skills and Tools | v0.6 | 0/? | Not started | - |
