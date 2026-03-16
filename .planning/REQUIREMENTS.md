# Requirements: ClawLite

**Defined:** 2026-03-16
**Milestone:** v0.6 — Robustez
**Core Value:** Um agente AI que funciona de verdade em qualquer ambiente Python — incluindo mobile/Termux — sem dependências que compilem código nativo.

## v0.6 Requirements

### Core / Bugs

- [ ] **CORE-01**: Sistema não sofre memory leak de session locks após sessões encerrarem
- [ ] **CORE-02**: Worker de multi-agente executa comandos sem shell=True (sem risco de injeção)
- [ ] **CORE-03**: setup_logging() não é chamado no module-level (sem efeito colateral no import)
- [ ] **CORE-04**: Engine executa tool calls independentes em paralelo (não sequencialmente)

### Providers

- [ ] **PROV-01**: Quando circuit breaker abre, agente roteia automaticamente para próximo provider configurado
- [ ] **PROV-02**: Operador pode configurar múltiplas API keys por provider com quota e cooldown individual
- [ ] **PROV-03**: Sistema rastreia custo estimado e tokens consumidos por provider, sessão e agente
- [ ] **PROV-04**: Catalog inclui providers Bedrock (AWS), Qwen e Mistral como opções nativas

### MCP

- [ ] **MCP-01**: Agente pode usar servidores MCP locais via stdio transport (subprocess + pipes)
- [ ] **MCP-02**: Agente pode consumir servidores MCP via SSE transport (streaming de resultados)
- [ ] **MCP-03**: Sistema descobre e lista tools disponíveis de um servidor MCP via handshake de inicialização
- [ ] **MCP-04**: ClawLite expõe suas próprias tools como servidor MCP para clientes externos

### Gateway / Channels

- [ ] **GW-01**: Gateway aplica rate limiting por IP e por token em /api/message
- [ ] **GW-02**: Tools e channels reportam latência real e erros em health checks (não sempre ok=True)
- [ ] **GW-03**: Canais Signal, Matrix e IRC são funcionais para envio e recebimento de mensagens
- [ ] **GW-04**: Cada subagente tem thread de contexto própria — sem colisão entre runs paralelos

### Cron / Jobs

- [ ] **CRON-01**: Cron job pode ser disparado por evento HTTP (webhook trigger) além de tempo
- [ ] **CRON-02**: Job que falha é reexecutado com backoff configurável (retry policy por job)
- [ ] **CRON-03**: Job B pode ser configurado para iniciar somente após Job A completar com sucesso
- [ ] **CRON-04**: Dashboard web exibe jobs agendados, histórico de execuções e próximas rodadas

### Memory

- [ ] **MEM-01**: Sistema gera embeddings localmente sem depender de API remota (modelo local leve)
- [ ] **MEM-02**: Operador pode exportar e importar memória completa entre workspaces/dispositivos
- [ ] **MEM-03**: Engine comprime working memory automaticamente quando token budget está acima de 80%
- [ ] **MEM-04**: Memória suporta grafo de relações entre entidades (pessoas, projetos, conceitos)

### Skills / Tools

- [ ] **SKILL-01**: Skills podem ser recarregadas em runtime sem reiniciar o agente
- [ ] **TOOL-01**: Agente pode executar operações git (status, diff, commit, log) via tool nativa sem shell
- [ ] **TOOL-02**: Agente pode executar queries SQL em banco SQLite ou Postgres via tool nativa
- [ ] **SKILL-02**: Operador pode instalar versão específica de uma skill (ex: clawhub@1.2.0)

## v2 Requirements (Deferred)

### Channels

- **CHAN-01**: Canal QQ funcional
- **CHAN-02**: Canal DingTalk funcional
- **CHAN-03**: Canal Feishu funcional
- **CHAN-04**: STT/TTS sem dependência de ffmpeg (alternativa portátil ao pydub)

### Memory

- **MEM-05**: Particionamento/archiving de SQLite para bases com milhões de registros
- **MEM-06**: Redis como backend opcional de memória distribuída

### Providers

- **PROV-05**: Ensemble multi-modelo — votação entre providers para respostas críticas
- **PROV-06**: Streaming nativo de tool results (partial results durante execução)

### Skills / Tools

- **TOOL-03**: Skill sandboxing — isolamento de recursos por skill
- **SKILL-03**: Skill marketplace local com index de skills disponíveis

## Out of Scope

| Feature | Reason |
|---------|--------|
| Apps nativos iOS/Android/macOS/Windows | Fora do escopo Python/Termux |
| Pydantic v2 | maturin/Rust não compila no Termux |
| Dependências com compilação C/Rust | Quebra no ambiente Android |
| WebRTC / chamadas de voz | Dependências binárias incompatíveis |
| OAuth flow para providers | Complexidade alta, casos de uso raramente precisam |

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
