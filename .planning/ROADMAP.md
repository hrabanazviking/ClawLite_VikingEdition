# Roadmap: ClawLite

## Milestones

- ✅ **v0.5 Foundation** - Phases 1-7 (shipped 2026-03-07)
- 🚧 **v0.6 Robustez** - Phases 8-17 (in progress)

## Phases

<details>
<summary>✅ v0.5 Foundation (Phases 1-7) - SHIPPED 2026-03-07</summary>

- Phase 1: Gateway FastAPI + WebSocket + dashboard
- Phase 2: Sistema de memória multicamada
- Phase 3: Tools registry (18 tools) + providers (14+) com circuit breaker
- Phase 4: Channels (Telegram, Discord, Slack, Email, WhatsApp)
- Phase 5: Cron + Heartbeat + Jobs com persistência
- Phase 6: Multi-agente (SubagentManager, AutonomyWakeCoordinator)
- Phase 7: Self-Evolution Engine (SourceScanner, FixProposer, PatchApplicator)

917 testes passando, 57,859 LOC.

</details>

---

### 🚧 v0.6 Robustez (In Progress)

**Milestone Goal:** Corrigir bugs críticos, fechar falhas de segurança e completar os subsistemas incompletos (MCP, channels, cron avançado, memória local, skills runtime).

**Phase Numbering:** 8–17 (continuação de v0.5)

- [ ] **Phase 8: Bugs Críticos** - Fechar memory leak, shell=True e setup_logging
- [ ] **Phase 9: Engine Hardening** - Parallel tools, failover de provider, thread isolation de subagentes
- [ ] **Phase 10: Provider Management** - Rotação de credenciais, cost tracking, catalog expandido
- [ ] **Phase 11: MCP Completo** - stdio + SSE transport, discovery, servidor MCP próprio
- [ ] **Phase 12: Gateway Segurança** - Rate limiting e health checks reais
- [ ] **Phase 13: Channels Stub** - Signal, Matrix e IRC funcionais
- [ ] **Phase 14: Cron Avançado** - Webhook triggers, retry policy, dependência entre jobs, dashboard
- [ ] **Phase 15: Memória Local** - Embeddings locais, export/import, compressão por token budget
- [ ] **Phase 16: Memory Graph** - Grafo de relações entre entidades
- [ ] **Phase 17: Skills e Tools** - Hot-reload de skills, versionamento, tools git e SQL nativas

## Phase Details

### Phase 8: Bugs Críticos
**Goal**: O agente não tem memory leaks, não executa comandos com risco de injeção e não polui o namespace no import
**Depends on**: Phase 7 (v0.5 shipped)
**Requirements**: CORE-01, CORE-02, CORE-03
**Success Criteria** (what must be TRUE):
  1. Sessões encerradas não acumulam entradas em `_session_locks` — o dict não cresce além das sessões ativas
  2. Worker de multi-agente executa subprocessos sem `shell=True` — não aceita injeção via nome de comando
  3. Importar `clawlite.core.engine` não configura handlers de logging como efeito colateral
**Plans**: TBD

### Phase 9: Engine Hardening
**Goal**: O engine executa tools em paralelo, roteia automaticamente para outro provider quando o circuit breaker abre, e subagentes não compartilham contexto de thread
**Depends on**: Phase 8
**Requirements**: CORE-04, PROV-01, GW-04
**Success Criteria** (what must be TRUE):
  1. Tool calls independentes em uma resposta do agente são disparadas em paralelo — tempo total é max(t_i), não sum(t_i)
  2. Quando o circuit breaker de um provider abre, a próxima requisição usa automaticamente o próximo provider configurado sem intervenção do operador
  3. Dois subagentes executando em paralelo não misturam contexto de thread — cada run tem isolamento completo
**Plans**: TBD

### Phase 10: Provider Management
**Goal**: Operador gerencia múltiplas API keys por provider com quota, cooldown e rastreamento de custo; catálogo inclui Bedrock, Qwen e Mistral
**Depends on**: Phase 9
**Requirements**: PROV-02, PROV-03, PROV-04
**Success Criteria** (what must be TRUE):
  1. Operador pode registrar duas ou mais API keys para o mesmo provider; cada key tem quota e cooldown independentes
  2. Após cada chamada ao LLM, o sistema registra tokens consumidos e custo estimado por provider, sessão e agente — consultável via API
  3. AWS Bedrock, Qwen e Mistral aparecem como opções nativas no catálogo de providers e funcionam com a mesma interface dos demais
**Plans**: TBD

### Phase 11: MCP Completo
**Goal**: Agente usa servidores MCP locais (stdio) e remotos (SSE), descobre tools via handshake e expõe suas próprias tools como servidor MCP
**Depends on**: Phase 10
**Requirements**: MCP-01, MCP-02, MCP-03, MCP-04
**Success Criteria** (what must be TRUE):
  1. Agente inicia um servidor MCP local via subprocess + pipes e chama tools nele sem depender de HTTP
  2. Agente consome resultados de um servidor MCP remoto via SSE (streaming) sem bloquear o event loop
  3. Ao conectar em um servidor MCP, o sistema lista automaticamente as tools disponíveis via handshake de inicialização
  4. Cliente MCP externo pode descobrir e chamar as tools do ClawLite via protocolo MCP padrão
**Plans**: TBD

### Phase 12: Gateway Segurança
**Goal**: Gateway protege /api/message com rate limiting e health checks reportam estado real dos subsistemas
**Depends on**: Phase 11
**Requirements**: GW-01, GW-02
**Success Criteria** (what must be TRUE):
  1. Requisições acima do limite configurado em /api/message retornam 429 — por IP e por token, separadamente
  2. GET /api/health retorna latência real e erros recentes por tool e channel — não retorna sempre `ok: true`
  3. Uma tool degradada (ex: timeout) aparece com status `degraded` ou `error` no health check, não `ok`
**Plans**: TBD

### Phase 13: Channels Stub
**Goal**: Signal, Matrix e IRC saem de stub para funcionais — operador pode enviar e receber mensagens nesses canais
**Depends on**: Phase 12
**Requirements**: GW-03
**Success Criteria** (what must be TRUE):
  1. Operador configura Signal e o agente envia e recebe mensagens via Signal
  2. Operador configura Matrix e o agente envia e recebe mensagens em um room Matrix
  3. Operador configura IRC e o agente se conecta a um servidor, entra em canal e troca mensagens
**Plans**: TBD

### Phase 14: Cron Avançado
**Goal**: Jobs cron suportam webhook triggers, retry com backoff, dependência entre jobs e são visíveis no dashboard web
**Depends on**: Phase 13
**Requirements**: CRON-01, CRON-02, CRON-03, CRON-04
**Success Criteria** (what must be TRUE):
  1. Um POST HTTP no endpoint de webhook dispara o job configurado imediatamente, independente do schedule temporal
  2. Job que falha é reexecutado automaticamente com backoff configurável; número de tentativas e intervalo são configuráveis por job
  3. Job B com dependência em Job A só inicia quando Job A completa com sucesso na mesma janela de execução
  4. Dashboard web exibe lista de jobs agendados, histórico das últimas execuções e próximos horários previstos
**Plans**: TBD

### Phase 15: Memória Local
**Goal**: Sistema gera embeddings sem API remota, suporta export/import de memória e comprime working memory automaticamente
**Depends on**: Phase 14
**Requirements**: MEM-01, MEM-02, MEM-03
**Success Criteria** (what must be TRUE):
  1. Busca semântica na memória funciona sem chave de API configurada — modelo de embeddings roda localmente
  2. Operador exporta memória completa para arquivo e importa em outro workspace/dispositivo recuperando o mesmo contexto
  3. Quando working memory ultrapassa 80% do token budget, o sistema comprime automaticamente sem intervenção do operador
**Plans**: TBD

### Phase 16: Memory Graph
**Goal**: Memória suporta grafo de relações entre entidades — pessoas, projetos e conceitos são conectados e consultáveis
**Depends on**: Phase 15
**Requirements**: MEM-04
**Success Criteria** (what must be TRUE):
  1. Agente pode criar relação nomeada entre duas entidades (ex: "João trabalha em Projeto X") e recuperá-la por consulta
  2. Consulta de grafo retorna entidades relacionadas transitivamente (ex: todos os projetos de João, via grafo)
  3. Relações persistem entre sessões e aparecem no contexto do agente quando relevantes
**Plans**: TBD

### Phase 17: Skills e Tools
**Goal**: Skills são recarregáveis em runtime, suportam versionamento, e o agente tem tools nativas para git e SQL sem invocar shell
**Depends on**: Phase 16
**Requirements**: SKILL-01, SKILL-02, TOOL-01, TOOL-02
**Success Criteria** (what must be TRUE):
  1. Operador modifica um arquivo de skill e aciona hot-reload — o agente usa a versão nova sem reiniciar
  2. Operador instala uma versão específica de uma skill (ex: `clawhub@1.2.0`) e o sistema usa exatamente essa versão
  3. Agente executa `git status`, `git diff`, `git commit` e `git log` via tool nativa sem subprocess shell=True
  4. Agente executa queries SQL em SQLite e Postgres via tool nativa sem subprocesso externo
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 8 → 9 → 10 → 11 → 12 → 13 → 14 → 15 → 16 → 17

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1-7. Foundation | v0.5 | ✅ | Complete | 2026-03-07 |
| 8. Bugs Críticos | v0.6 | 0/? | Not started | - |
| 9. Engine Hardening | v0.6 | 0/? | Not started | - |
| 10. Provider Management | v0.6 | 0/? | Not started | - |
| 11. MCP Completo | v0.6 | 0/? | Not started | - |
| 12. Gateway Segurança | v0.6 | 0/? | Not started | - |
| 13. Channels Stub | v0.6 | 0/? | Not started | - |
| 14. Cron Avançado | v0.6 | 0/? | Not started | - |
| 15. Memória Local | v0.6 | 0/? | Not started | - |
| 16. Memory Graph | v0.6 | 0/? | Not started | - |
| 17. Skills e Tools | v0.6 | 0/? | Not started | - |
