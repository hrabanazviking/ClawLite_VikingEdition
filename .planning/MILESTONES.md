# Milestones

## v0.5 — Foundation (Shipped)

**Shipped:** 2026-03-07  
**Phases:** 1–7

### What shipped

- Phase 1: FastAPI gateway + WebSocket + dashboard
- Phase 2: Multi-layer memory system (episodic, semantic, working, shared)
- Phase 3: Tools registry (18 tools) + providers (14+) with circuit breaker
- Phase 4: Channels (full Telegram, Discord, Slack, Email, WhatsApp)
- Phase 5: Cron + Heartbeat + Jobs with persistence
- Phase 6: Multi-agent system (SubagentManager, AutonomyWakeCoordinator, journal)
- Phase 7: Self-Evolution Engine (SourceScanner, FixProposer, PatchApplicator, Validator)

### Stats

- 917 tests passing (0 failures)
- 57,859 LOC
- CI: pytest matrix for 3.10 + 3.12, plus lint and smoke tests

---

## v0.6 — Robustness (Active)

**Started:** 2026-03-16  
**Phases:** 8–N

### Goals

- Fix critical bugs (memory leak, shell=True, setup_logging)
- MCP with native stdio transport
- Automatic provider failover
- Parallel tool execution
- Credential rotation
- Real health checks
- Gateway rate limiting
- Subagent thread ownership
- Implemented stub channels
- Cost tracking per provider
- Cron with webhook triggers and retry policy
