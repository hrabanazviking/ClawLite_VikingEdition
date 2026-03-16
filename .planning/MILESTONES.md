# Milestones

## v0.5 — Foundation (Shipped)

**Shipped:** 2026-03-07
**Phases:** 1–7

### What shipped

- Phase 1: Gateway FastAPI + WebSocket + dashboard
- Phase 2: Sistema de memória multicamada (episódica, semântica, working, shared)
- Phase 3: Tools registry (18 tools) + providers (14+) com circuit breaker
- Phase 4: Channels (Telegram completo, Discord, Slack, Email, WhatsApp)
- Phase 5: Cron + Heartbeat + Jobs com persistência
- Phase 6: Multi-agente (SubagentManager, AutonomyWakeCoordinator, journal)
- Phase 7: Self-Evolution Engine (SourceScanner, FixProposer, PatchApplicator, Validator)

### Stats

- 917 testes passando (0 falhas)
- 57,859 LOC
- CI: pytest matrix 3.10+3.12 + lint + smoke

---

## v0.6 — Robustez (Active)

**Started:** 2026-03-16
**Phases:** 8–N

### Goals

- Corrigir bugs críticos (memory leak, shell=True, setup_logging)
- MCP com stdio transport nativo
- Failover automático de providers
- Parallel tool execution
- Rotação de credenciais
- Health checks reais
- Rate limiting gateway
- Thread ownership subagentes
- Channels stub implementados
- Cost tracking por provider
- Cron com webhook triggers e retry policy
