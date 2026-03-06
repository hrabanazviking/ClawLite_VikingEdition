# ClawLite: Gap Analysis e Plano por Fases

**Data:** 2026-03-06  
**Repositório principal analisado:** `/root/projetos/ClawLite`  
**Referências analisadas:** `/root/projetos/openclaw`, `/root/projetos/nanobot`, `/root/projetos/memU`, `/root/projetos/antfarm`

## Metodologia e premissas

- O arquivo `/root/projetos/ClawLite/CODEX_CONTEXT.md` não existe no repositório atual; a análise foi baseada no código, testes, README e estrutura real do projeto.
- A URL pedida para `antfarm` (`https://github.com/ruvnet/antfarm`) retorna `404` em `2026-03-06`. Para não deixar a fase 6 sem referência, a comparação foi feita com o repositório público atualmente disponível em `/root/projetos/antfarm`.
- Os percentuais abaixo são **estimativas de engenharia**, não benchmarks medidos em produção.
- Quando eu digo “ganho estimado”, estou falando de impacto esperado na completude da fase e na robustez prática do subsistema.

---

## FASE 1 — TELEGRAM 100% FUNCIONAL

---
### [✅ Tem] TG-1 Transporte de saída, formatação e typing keepalive

**Evidência no ClawLite:** `clawlite/channels/telegram.py` linha `955` — loop de typing keepalive; linha `1739` — webhook handler; linhas `1828-1845` e `1916-1987` — `parse_mode`, fallback de formatação e retry com `retry_after`; linha `1889` — suporte a `message_thread_id`.  
**O que falta:** nada estrutural para o requisito base de envio; este item já está em nível bom.  
**Referência:** OpenClaw faz o mesmo com mais separação por módulos em `src/telegram/send.ts` e backoff dedicado de chat action em `src/telegram/sendchataction-401-backoff.ts`.  
**Como implementar:** manter a API atual; só reforçar suíte de regressão para HTML/Markdown, reply/edit/delete/react em `tests/channels/test_telegram.py`.  
**Prioridade:** 🟢 Melhoria  
**Ganho estimado:** `0 p.p.` de completude; item já entregue.  

---
### [✅ Tem] TG-2 Polling, webhook, retry, dedupe e reconexão base

**Evidência no ClawLite:** `clawlite/channels/telegram.py` linha `402` — `drop_pending_updates`; linha `1059` — limpeza de updates pendentes; linha `1247` — `_poll_loop`; linha `1296` — pipeline central `_handle_update`; `clawlite/gateway/server.py` linha `1002` — runtime sobe com toolset e canais; testes cobrindo reconnect e webhook em `tests/channels/test_telegram.py`.  
**O que falta:** nada crítico no transporte base; o gap para 100% está nos casos avançados de offset seguro e matriz total de updates.  
**Referência:** OpenClaw adiciona watermark seguro por `botId`, serialização mais rígida e monitor dedicado em `src/telegram/bot.ts`, `src/telegram/update-offset-store.ts` e `src/telegram/monitor.ts`.  
**Como implementar:** preservar a arquitetura atual e atacar os gaps do TG-5 sem reescrever o canal inteiro.  
**Prioridade:** 🟢 Melhoria  
**Ganho estimado:** `0 p.p.` de completude; item já entregue em grande parte.  

---
### [⚠️ Parcial] TG-3 Ingestão real de mídia inbound

**Evidência no ClawLite:** `clawlite/channels/telegram.py` linha `1650` — `_extract_media_info`; linha `1680` — `_build_media_placeholder`; linha `1524` — mídia vira placeholder textual antes de entrar no fluxo.  
**O que falta:** download real de foto/áudio/documento, transcrição de voz, OCR opcional, extração de metadados útil ao agente e persistência/replay de anexos. Hoje o agente “vê que existe mídia”, mas não consome a mídia de fato.  
**Referência:** nanobot baixa foto/voz/documento, agrega media groups e transcreve áudio em `nanobot/channels/telegram.py`; OpenClaw prepara contexto rico de mensagem/mídia em `src/telegram/bot-message-context.ts`.  
**Como implementar:** modificar `_handle_update`, `_extract_media_info` e `_build_metadata` em `clawlite/channels/telegram.py`; criar `clawlite/channels/telegram_media.py` com `_download_file`, `_transcribe_voice`, `_extract_document_text`; adicionar fixtures e testes em `tests/channels/test_telegram.py` e `tests/providers/test_transcription.py`.  
**Prioridade:** 🔴 Bloqueante  
**Ganho estimado:** `+12 p.p.` na Fase 1 e `+35%` de utilidade prática do canal.  

---
### [⚠️ Parcial] TG-4 Pairing seguro e binding persistente por remetente/thread

**Evidência no ClawLite:** `clawlite/channels/telegram.py` linha `475` — `_session_id_for_chat` usa `chat_id/thread_id`; linhas `1119-1191` — autorização por remetente/grupo/tópico; não existe fluxo explícito de pairing persistente nem store de binding.  
**O que falta:** pairing DM explícito com aprovação/negação, persistência de vínculo remetente→perfil, binding por thread com TTL/expiry e reconciliação após restart. Hoje existe policy/allowlist, mas não existe onboarding seguro de remetentes.  
**Referência:** OpenClaw implementa pairing em `src/telegram/dm-access.ts` e bindings persistentes com sweep/expiry em `src/telegram/thread-bindings.ts`.  
**Como implementar:** criar `clawlite/channels/telegram_pairing.py` e `clawlite/channels/telegram_bindings.py`; modificar `_is_sender_allowed`, `_session_id_for_chat`, `_handle_update` e `start` em `clawlite/channels/telegram.py`; persistir estado em `~/.clawlite/state/telegram/`.  
**Prioridade:** 🔴 Bloqueante  
**Ganho estimado:** `+8 p.p.` na Fase 1 e `+30%` de segurança operacional do canal.  

---
### [⚠️ Parcial] TG-5 Cobertura total de updates e watermark seguro de offset

**Evidência no ClawLite:** `clawlite/channels/telegram.py` linha `1247` — `_poll_loop`; linha `1296` — `_handle_update`; linhas `1441-1494` — reactions; linha `1504` — channel posts; linha `1739` — webhook path; linha `1267` usa offset simples sem store dedicado de watermark seguro.  
**O que falta:** store atômico de watermark abaixo do menor update pendente, cobertura de `inline_query`, `poll`, `chat_member`, `my_chat_member` e outros updates menos frequentes, além de replay seguro após restart parcial.  
**Referência:** OpenClaw persiste offset com watermark seguro em `src/telegram/update-offset-store.ts` e processa callback/reaction/channel posts no mesmo pipeline em `src/telegram/bot-handlers.ts`.  
**Como implementar:** criar `clawlite/channels/telegram_offset_store.py`; expandir `_handle_update`, `_poll_loop` e `handle_webhook_update` em `clawlite/channels/telegram.py`; adicionar testes por update type em `tests/channels/test_telegram.py`.  
**Prioridade:** 🔴 Bloqueante  
**Ganho estimado:** `+10 p.p.` na Fase 1 e `+28%` de confiabilidade sob restart/reconexão.  

---

## FASE 2 — NÚCLEO 100% FUNCIONAL

### 2.1 MEMORY

---
### [✅ Tem] MEM-1 Arquitetura de memória em camadas, persistência e atomicidade

**Evidência no ClawLite:** `clawlite/core/memory.py` linhas `320-471` — memória com `resources/items/categories/users/shared/versions`; linhas `506-524` — escrita atômica com `fsync`; `clawlite/core/memory_backend.py` linhas `115-149` — backend SQLite com WAL; `clawlite/core/memory_monitor.py` linhas `55-122` — monitor independente com escrita atômica de sugestões.  
**O que falta:** nada estrutural para a base; o desenho está acima da média.  
**Referência:** nanobot usa memória mais simples e auditável em arquivo; OpenClaw organiza memória e workspace de forma robusta, mas o ClawLite já tem base local-first melhor do que o mínimo da fase.  
**Como implementar:** manter a arquitetura; focar os próximos esforços em recall semântico e backend vetorial real.  
**Prioridade:** 🟢 Melhoria  
**Ganho estimado:** `0 p.p.` de completude; item já entregue.  

---
### [⚠️ Parcial] MEM-2 Recall semântico consistente em todos os escopos

**Evidência no ClawLite:** `clawlite/core/memory.py` linha `3633` — `search`; linhas `3726-3733` — ranking retorna com `semantic_enabled=False` mesmo nos fluxos de busca com `user_id/include_shared`; `clawlite/core/engine.py` linhas `754-771` — engine já propaga `user_id` e `include_shared` para a busca.  
**O que falta:** paridade semântica real entre escopo local, usuário e memória compartilhada; hoje o plumbing existe, mas a busca final ainda cai em ranking não semântico em caminhos importantes.  
**Referência:** memU tem pipeline explícito de retrieve/rewrite/sufficiency; OpenClaw e nanobot tratam recuperação de contexto com menos ambiguidade operacional.  
**Como implementar:** alterar `MemoryStore.search` e `_rank_records` em `clawlite/core/memory.py` para respeitar `self.semantic_enabled` em todos os escopos; validar com SQLite e pgvector; adicionar testes de recall em `tests/core/test_memory*.py`.  
**Prioridade:** 🔴 Bloqueante  
**Ganho estimado:** `+8 p.p.` na Fase 2 e `+25%` de qualidade de recuperação de contexto.  

---
### [⚠️ Parcial] MEM-3 Backend pgvector presente, mas sem paridade de produção

**Evidência no ClawLite:** `clawlite/core/memory_backend.py` linhas `333-423` — `PgvectorMemoryBackend`; linhas `410-415` — embeddings ainda são armazenados como `TEXT`; linha `787` — `resolve_memory_backend("pgvector")`.  
**O que falta:** uso real de tipo/index vetorial, health checks, migrations, erro explícito de driver/URL, busca vetorial com custo previsível e cobertura de testes. Do jeito atual, o backend “existe”, mas ainda não tem o nível operacional que o nome sugere.  
**Referência:** memU trata memória semântica como eixo principal do sistema; OpenClaw privilegia robustez de runtime e integração limpa com a camada de contexto.  
**Como implementar:** evoluir `PgvectorMemoryBackend.initialize`, `upsert_embedding` e `query_similar_embeddings` em `clawlite/core/memory_backend.py` para usar `vector`, índice `ivfflat`/`hnsw`, capability probe e erros fail-fast; adicionar suíte `tests/core/test_memory_backend_pgvector.py`.  
**Prioridade:** 🔴 Bloqueante  
**Ganho estimado:** `+6 p.p.` na Fase 2 e `+20%` de robustez do backend vetorial.  

---
### [✅ Tem] AGT-1 Agente principal estável com lock de sessão e propagação de contexto

**Evidência no ClawLite:** `clawlite/core/engine.py` linha `604` — `_resolve_runtime_context`; linha `1249` — prompt recebe `channel/chat_id`; linhas `1469-1475` — tool calls propagam `session_id/channel/user_id`; linha `952` — lock por sessão; linha `1197` — `run`.  
**O que falta:** nada crítico no fluxo base do agente principal.  
**Referência:** OpenClaw e nanobot têm loops maduros; o ClawLite já está perto nesse eixo.  
**Como implementar:** manter; concentrar esforço nos gaps de loop guard e validação de persona.  
**Prioridade:** 🟢 Melhoria  
**Ganho estimado:** `0 p.p.` de completude; item já entregue.  

---
### [⚠️ Parcial] AGT-2 Loop guard completo ainda não existe

**Evidência no ClawLite:** `clawlite/core/engine.py` linhas `551-568` — `_detect_tool_loop` detecta repetição do mesmo tool outcome; linhas `1411-1452` — engine para em repetição idêntica.  
**O que falta:** detecção de ping-pong entre duas ou mais tools, detecção de “no progress” entre iterações do provider, score de progresso por delta semântico e guard específico para loops de autonomia.  
**Referência:** nanobot organiza o loop com contrato mais rígido; OpenClaw combina runtime controls com wake/heartbeat mais defensivo.  
**Como implementar:** criar `clawlite/core/loop_guard.py` com fingerprints por intenção/resultado; integrar em `AgentEngine.run` e `_inject_subagent_digest`; adicionar testes com cenários ping-pong em `tests/core/test_engine.py`.  
**Prioridade:** 🔴 Bloqueante  
**Ganho estimado:** `+7 p.p.` na Fase 2 e `+30%` de proteção contra loops improdutivos.  

---
### [⚠️ Parcial] AGT-3 Persona é normalizada depois da resposta, não validada antes de persistir

**Evidência no ClawLite:** `clawlite/core/prompt.py` linhas `41-46` — identity guard; `clawlite/core/engine.py` linha `1148` — `_normalize_identity_output`; linhas `1597-1630` — resposta é normalizada e em seguida persistida em sessão/memória.  
**O que falta:** validação formal contra SOUL/IDENTITY/USER antes de enviar e antes de memorizar; hoje existe correção textual, mas não um validator de política.  
**Referência:** OpenClaw trata workspace/persona como parte do lifecycle; nanobot tende a ser mais consistente porque o runtime é menor e menos poluído.  
**Como implementar:** criar `clawlite/workspace/policy_validator.py`; validar em `AgentEngine.run` entre `_normalize_identity_output` e `self.sessions.append`; em caso de desvio, regenerar ou bloquear persistência.  
**Prioridade:** 🟡 Importante  
**Ganho estimado:** `+5 p.p.` na Fase 2 e `+18%` de consistência de identidade.  

---
### [✅ Tem] HB-1 Heartbeat skip/run, estado atômico e coalescência básica

**Evidência no ClawLite:** `clawlite/scheduler/heartbeat.py` linhas `19-68` — contrato `run/skip`; linhas `190-217` — persistência atômica do estado; linhas `272-323` — `trigger_now` e coalescência básica de wake.  
**O que falta:** nada crítico na fundação.  
**Referência:** OpenClaw vai além conectando heartbeat ao runtime de canal e ao wake queue de maneira mais nativa.  
**Como implementar:** manter a base e focar na supervisão independente e integração com canais.  
**Prioridade:** 🟢 Melhoria  
**Ganho estimado:** `0 p.p.` de completude; item já entregue.  

---
### [⚠️ Parcial] HB-2 Supervisão independente e restart de loops críticos não estão fechados

**Evidência no ClawLite:** `clawlite/runtime/supervisor.py` linhas `25-123` — supervisor genérico por incidente/componente; `clawlite/runtime/autonomy.py` linhas `349-363` — loop próprio de autonomia; `clawlite/scheduler/heartbeat.py` linhas `292-313` — heartbeat tem backoff local, mas não registry global de componentes críticos.  
**O que falta:** supervisão formal de Telegram polling, webhook, heartbeat, cron, autonomia e subagent sweeper como loops independentes com health probes e restart explícito.  
**Referência:** OpenClaw separa `heartbeat-wake`, `monitor` e cron de modo mais operacional.  
**Como implementar:** criar `clawlite/runtime/component_supervisor.py`; registrar loops em `clawlite/gateway/server.py` e `clawlite/channels/*`; definir `health()` e `restart()` por componente.  
**Prioridade:** 🔴 Bloqueante  
**Ganho estimado:** `+8 p.p.` na Fase 2 e `+27%` de resiliência do runtime.  

---
### [⚠️ Parcial] SOUL-1 SOUL.md e USER.md entram no prompt, mas falta enforcement pós-provider

**Evidência no ClawLite:** `clawlite/workspace/loader.py` linhas `9-18` — templates `IDENTITY.md`, `SOUL.md`, `USER.md`, `HEARTBEAT.md`, `BOOTSTRAP.md`; linha `262` — `system_context`; `clawlite/core/prompt.py` linhas `243-253` — workspace é montado no system prompt.  
**O que falta:** validação de contaminação por modelo, enforcement após resposta do provider, marcação de violações e bloqueio de persistência quando o SOUL é rompido.  
**Referência:** OpenClaw trata workspace como componente de lifecycle, não só como texto concatenado.  
**Como implementar:** criar `clawlite/workspace/identity_enforcer.py`; rodar antes de `self.sessions.append` e antes de `memorize`; registrar métricas de contaminação no runtime.  
**Prioridade:** 🟡 Importante  
**Ganho estimado:** `+4 p.p.` na Fase 2 e `+15%` de fidelidade ao SOUL.  

---
### [✅ Tem] TOOLS-1 Ferramentas centrais, aliases e safety fail-closed

**Evidência no ClawLite:** `clawlite/gateway/server.py` linhas `870-1000` — 29 tools registradas; `clawlite/tools/registry.py` linhas `123-140` — fail-closed por canal; `clawlite/tools/files.py` linhas `305-313` — aliases `read/write/edit`; `clawlite/tools/memory.py` linha `301` — `memory_search`; `clawlite/tools/apply_patch.py`, `process.py`, `sessions.py` e `spawn.py` já estão presentes.  
**O que falta:** nada crítico no catálogo base da fase 2; o gap de `agents_list` pertence à fase 6.  
**Referência:** OpenClaw tem catálogo mais tipado/policiado, mas a cobertura funcional principal já existe no ClawLite.  
**Como implementar:** manter e ampliar testes de dispatch/safety; não reescrever o catálogo.  
**Prioridade:** 🟢 Melhoria  
**Ganho estimado:** `0 p.p.` de completude; item já entregue.  

---
### [⚠️ Parcial] USER-1 USER.md carregado, mas preferências ainda não são política estruturada

**Evidência no ClawLite:** `clawlite/workspace/loader.py` linha `263` inclui `USER.md`; `clawlite/core/prompt.py` linhas `243-253` insere o workspace inteiro no prompt.  
**O que falta:** parser de preferências estruturado, ligação do pairing ao perfil correto e influência explícita dessas preferências em estilo de resposta, seleção de tools e decisões autonômicas.  
**Referência:** OpenClaw usa workspace de forma mais operacional; nanobot é mais simples, mas a continuidade de perfil é mais legível.  
**Como implementar:** criar `clawlite/workspace/user_profile.py`; expor `load_user_profile()` para `PromptBuilder`, `AgentEngine` e Telegram pairing; persistir resolução por usuário em `memory/users/`.  
**Prioridade:** 🟡 Importante  
**Ganho estimado:** `+4 p.p.` na Fase 2 e `+14%` de personalização útil.  

---

## FASE 3 — PROVIDERS 100% FUNCIONAL

---
### [✅ Tem] PRV-1 Classificação base de erros e mensagens claras ao usuário

**Evidência no ClawLite:** `clawlite/providers/reliability.py` linhas `74-128` — `is_retryable_error` e `classify_provider_error`; `clawlite/core/engine.py` linhas `961-1034` — classificação interna e mensagens amigáveis ao usuário.  
**O que falta:** nada crítico neste subitem; a fundação de erro já existe.  
**Referência:** OpenClaw e nanobot fazem isso com breadth maior de providers, mas a taxonomia base do ClawLite está boa.  
**Como implementar:** manter; reutilizar esta taxonomia ao construir failover multi-hop.  
**Prioridade:** 🟢 Melhoria  
**Ganho estimado:** `0 p.p.` de completude; item já entregue.  

---
### [❌ Falta] PRV-2 Cobertura de 20+ providers

**Evidência no ClawLite:** `clawlite/providers/registry.py` linhas `43-123` — apenas `custom`, `openrouter`, `gemini`, `groq`, `deepseek`, `anthropic`, `openai`, `openai_codex`.  
**O que falta:** Ollama, vLLM, Mistral, Kilo.ai, Together, HuggingFace, Nvidia, Bedrock e demais providers citados no objetivo.  
**Referência:** OpenClaw cobre discovery/onboarding muito mais amplo em `src/agents/models-config.providers.ts`; nanobot já tem registry mais abrangente e integração moderna de provider.  
**Como implementar:** expandir `ProviderSpec` e `detect_provider_name` em `clawlite/providers/registry.py`; criar adapters específicos quando necessário (`ollama.py`, `vllm.py`) e normalizar o restante via `LiteLLMProvider`; adicionar testes em `tests/providers/`.  
**Prioridade:** 🔴 Bloqueante  
**Ganho estimado:** `+14 p.p.` na Fase 3 e `+40%` de portabilidade de modelo.  

---
### [⚠️ Parcial] PRV-3 Failover existe, mas é apenas primary→fallback

**Evidência no ClawLite:** `clawlite/providers/registry.py` linhas `449-460` — `build_provider` monta no máximo um fallback; `clawlite/providers/failover.py` linhas `14-217` — `FailoverProvider` opera só com `primary` e `fallback`.  
**O que falta:** cadeia multi-hop, dedupe de candidatos, política por classe de erro, quarantine por auth/quota e retry diferente para timeout/5xx/rate limit.  
**Referência:** OpenClaw faz fallback multi-candidato com cooldown, probing e política por erro em `src/agents/model-fallback.ts`.  
**Como implementar:** criar `clawlite/providers/fallback_chain.py` com `ProviderCandidate` e `FallbackPolicy`; alterar `build_provider` para aceitar lista ordenada de candidatos; reaproveitar `classify_provider_error()` para roteamento.  
**Prioridade:** 🔴 Bloqueante  
**Ganho estimado:** `+10 p.p.` na Fase 3 e `+45%` de disponibilidade efetiva do runtime.  

---
### [❌ Falta] PRV-4 Reuso automático de `~/.codex/auth.json`

**Evidência no ClawLite:** `clawlite/providers/registry.py` linhas `343-369` — `_resolve_codex_oauth` lê config e env vars, mas não lê o auth file do Codex.  
**O que falta:** descoberta automática de credenciais já autenticadas localmente, precedência correta e mensagem de erro que aponte exatamente a origem ausente.  
**Referência:** OpenClaw e nanobot tratam perfis/auth de forma mais próxima do ecossistema real do usuário.  
**Como implementar:** alterar `_resolve_codex_oauth` em `clawlite/providers/registry.py` para ler `~/.codex/auth.json`; adicionar testes em `tests/providers/test_registry.py` para precedência `config > auth.json > env` ou política equivalente.  
**Prioridade:** 🟡 Importante  
**Ganho estimado:** `+4 p.p.` na Fase 3 e `+20%` de ergonomia no onboarding do Codex.  

---
### [❌ Falta] PRV-5 Ollama/vLLM autodiscovery, base URL configurável e health check de startup

**Evidência no ClawLite:** `clawlite/providers/registry.py` linhas `43-123` — não há `ollama` nem `vllm` no registry; não existe bootstrap/health check dedicado no startup do runtime.  
**O que falta:** autodiscovery de endpoints locais, `/api/tags` e `/api/show` para Ollama, verificação de modelo disponível, base URL configurável e fail-fast no boot.  
**Referência:** OpenClaw implementa discovery de Ollama/vLLM em `src/agents/models-config.providers.ts`.  
**Como implementar:** criar `clawlite/providers/discovery.py`; integrar em `build_provider` e em `clawlite/gateway/server.py` durante o startup; adicionar testes e mensagens de erro claras de health check.  
**Prioridade:** 🔴 Bloqueante  
**Ganho estimado:** `+7 p.p.` na Fase 3 e `+25%` de confiabilidade em ambientes self-hosted.  

---
### [⚠️ Parcial] PRV-6 Onboarding e registry ainda não estão alinhados com a superfície oficial desejada

**Evidência no ClawLite:** `clawlite/providers/registry.py` ainda é um registry estático e curto; `clawlite/gateway/server.py` sobe provider único sem camada explícita de onboarding/discovery.  
**O que falta:** onboarding por capability, documentação/config oficial alinhada com providers reais e geração de mensagem de setup por provider ausente.  
**Referência:** OpenClaw resolve providers implicitamente por env/auth/local endpoints; nanobot também tem abordagem mais madura de registry.  
**Como implementar:** adicionar `ProviderCapabilities` em `clawlite/providers/registry.py`; expor diagnóstico em `gateway/server.py`; atualizar docs de configuração e tests de bootstrap.  
**Prioridade:** 🟡 Importante  
**Ganho estimado:** `+3 p.p.` na Fase 3 e `+15%` de DX de onboarding.  

---

## FASE 4 — SKILLS 100% FUNCIONAL

---
### [✅ Tem] SK-1 Loader, frontmatter, contratos e execução determinística

**Evidência no ClawLite:** `clawlite/core/skills.py` linhas `338-430` — descoberta e parse de `SKILL.md`; linha `460` — `diagnostics_report`; linhas `582-591` — contexto e renderização; `clawlite/tools/skill.py` linhas `24-230` — bridge de execução `command/script`.  
**O que falta:** nada crítico no núcleo do loader.  
**Referência:** OpenClaw adiciona watcher e governança mais fortes, mas a base do ClawLite já é funcional.  
**Como implementar:** preservar a API e concentrar mudanças em lifecycle/hot reload/fallbacks.  
**Prioridade:** 🟢 Melhoria  
**Ganho estimado:** `0 p.p.` de completude; item já entregue.  

---
### [⚠️ Parcial] SK-2 O alvo “0 skills indisponíveis” não é atendido hoje

**Evidência no ClawLite:** `clawlite/skills/session-logs/SKILL.md` linha `4` — requer `jq`; `clawlite/skills/summarize/SKILL.md` linha `6` — requer binário `summarize`; `SkillsLoader().diagnostics_report()` retorna `15` skills, `13` disponíveis e `2` indisponíveis.  
**O que falta:** garantir que todas as 10+ skills relevantes estejam realmente utilizáveis no runtime, com fallback quando dependência externa não existir.  
**Referência:** nanobot é melhor em expor indisponibilidade de skill à tomada de decisão do agente; OpenClaw fortalece elegibilidade/runtime gating.  
**Como implementar:** tratar indisponibilidade em `clawlite/tools/skill.py`; adicionar fallback para `session-logs` sem `jq` e para `summarize` sem binário; criar testes em `tests/core/test_skills.py`.  
**Prioridade:** 🔴 Bloqueante  
**Ganho estimado:** `+6 p.p.` na Fase 4 e `+22%` de usabilidade do ecossistema de skills.  

---
### [❌ Falta] SK-3 Hot reload com watcher dedicado e debounce

**Evidência no ClawLite:** `clawlite/core/skills.py` linhas `352-393` — cache é invalidado apenas por `mtime` do root; não há watcher nem debounce dedicado.  
**O que falta:** refresh dirigido por evento, debounce, invalidation por `SKILL.md` específico e reação a mudanças em workspace/marketplace skills sem restart.  
**Referência:** OpenClaw usa watcher focado em `SKILL.md` e plugin dirs em `src/agents/skills/refresh.ts`.  
**Como implementar:** criar `clawlite/core/skills_watcher.py`; adicionar `invalidate()` ao `SkillsLoader`; iniciar watcher em `clawlite/gateway/server.py`; cobrir debounce com testes.  
**Prioridade:** 🟡 Importante  
**Ganho estimado:** `+5 p.p.` na Fase 4 e `+18%` de fluidez operacional.  

---
### [❌ Falta] SK-4 Lifecycle de skill: enable, disable, pin e version

**Evidência no ClawLite:** não há estado de lifecycle no loader; `clawlite/core/skills.py` só descobre e prioriza source; `clawlite/tools/skill.py` só executa o que estiver disponível.  
**O que falta:** estado persistido por skill, version pinning, disable local, enable por workspace e política de precedência entre builtin/workspace/marketplace.  
**Referência:** OpenClaw tem governança mais forte de plugin skills e env overrides.  
**Como implementar:** criar `clawlite/core/skills_state.py` com `skills-state.json`; modificar `SkillsLoader._ensure_discovery_cache` e `get()`; adicionar ferramenta administrativa `clawlite/tools/skills_admin.py`; registrar em `gateway/server.py`.  
**Prioridade:** 🔴 Bloqueante  
**Ganho estimado:** `+7 p.p.` na Fase 4 e `+25%` de governança/operabilidade.  

---
### [❌ Falta] SK-5 Fallbacks de dependência para web-search, weather, github e summarize

**Evidência no ClawLite:** `clawlite/tools/skill.py` linhas `150-158` — weather usa apenas `wttr.in`; linhas `175-195` — script dispatch cai em tool único ou retorna `skill_script_unavailable`; não há cadeia DDG→Brave→SearXNG nem fallback LLM para summarize.  
**O que falta:** fallback real por skill, precheck de auth para GitHub e degradação controlada sem quebrar a skill inteira.  
**Referência:** OpenClaw é melhor em runtime eligibility; o alvo desta fase pede um sistema mais robusto que o atual e mais pragmático que o das referências.  
**Como implementar:** expandir `_dispatch_script` em `clawlite/tools/skill.py`; criar wrappers `web_search_fallback.py`, `weather_fallback.py`, `github_precheck.py`, `summarize_fallback.py`; atualizar `SKILL.md` dessas skills e adicionar testes.  
**Prioridade:** 🔴 Bloqueante  
**Ganho estimado:** `+8 p.p.` na Fase 4 e `+30%` de disponibilidade real das skills prioritárias.  

---
### [⚠️ Parcial] SK-6 Compatibilidade OpenClaw parcial na semântica de frontmatter e governança

**Evidência no ClawLite:** `clawlite/core/skills.py` parseia frontmatter e requirements, mas não implementa toda a semântica de lifecycle/plugin env hardening que existe no OpenClaw.  
**O que falta:** paridade de metadata, env overrides hardening, status de elegibilidade mais rico e melhor distinção entre “descoberta”, “instalada”, “habilitada” e “executável”.  
**Referência:** OpenClaw separa config, env-overrides e plugin-skills em módulos próprios.  
**Como implementar:** estender `SkillSpec` em `clawlite/core/skills.py`; adicionar verificação de metadata e env policy; criar testes de compatibilidade de frontmatter.  
**Prioridade:** 🟡 Importante  
**Ganho estimado:** `+4 p.p.` na Fase 4 e `+15%` de compatibilidade com o ecossistema OpenClaw.  

---

## FASE 5 — AUTONOMIA 100%

---
### [✅ Tem] AUTO-1 WakeQueue com prioridade, coalescência e backpressure

**Evidência no ClawLite:** `clawlite/runtime/autonomy.py` linhas `28-204` — `AutonomyWakeCoordinator` com fila prioritária, coalescência por chave e drop por backpressure.  
**O que falta:** nada estrutural neste item.  
**Referência:** OpenClaw tem padrão parecido em `src/infra/heartbeat-wake.ts`; aqui o ClawLite já está bem posicionado.  
**Como implementar:** manter e acoplar aos gaps de replay e supervisão.  
**Prioridade:** 🟢 Melhoria  
**Ganho estimado:** `0 p.p.` de completude; item já entregue.  

---
### [✅ Tem] AUTO-2 Base funcional de autonomia, heartbeat e cron

**Evidência no ClawLite:** `clawlite/runtime/autonomy.py` linhas `207-419` — `AutonomyService`; `clawlite/scheduler/heartbeat.py` linhas `74-345` — heartbeat service; `clawlite/scheduler/cron.py` linha `34` e linhas `299-350` — lease/timeout em cron.  
**O que falta:** nada crítico na fundação; o gap está nos mecanismos de recuperação durável e observabilidade operacional.  
**Referência:** OpenClaw integra isso com mais profundidade ao runtime mensageiro e ao cron.  
**Como implementar:** manter; evoluir os gaps AUTO-3 a AUTO-6.  
**Prioridade:** 🟢 Melhoria  
**Ganho estimado:** `0 p.p.` de completude; item já entregue.  

---
### [❌ Falta] AUTO-3 Replay durável de entregas pendentes após restart

**Evidência no ClawLite:** `clawlite/bus/queue.py` linhas `29-44` — dead letter e outbound estão em estruturas de memória; linhas `148-233` — replay existe, mas apenas sobre a fila viva do processo.  
**O que falta:** persistência de outbound/dead letter, reidratação no startup, ack idempotente e replay por canal sem duplicação.  
**Referência:** OpenClaw persiste delivery/job state no runtime/cron; antfarm trabalha com estado persistente de execução.  
**Como implementar:** criar `clawlite/bus/queue_store.py`; alterar `MessageQueue` para persistir publish/ack/dead_letter; hidratar em `clawlite/gateway/server.py`; adicionar testes de restart recovery.  
**Prioridade:** 🔴 Bloqueante  
**Ganho estimado:** `+9 p.p.` na Fase 5 e `+35%` de confiabilidade pós-restart.  

---
### [⚠️ Parcial] AUTO-4 Supervisor é genérico, mas falta supervisão independente por canal e loop

**Evidência no ClawLite:** `clawlite/runtime/supervisor.py` linhas `25-123` — supervisor de incidentes genérico; não há registry explícito de loops críticos por canal/componente.  
**O que falta:** health checks por canal, restart por tipo de loop, budget/cooldown por componente e visibilidade de “o que reiniciei, quando e por quê”.  
**Referência:** OpenClaw separa monitor/heartbeat-wake/cron de forma mais operacional; antfarm adiciona medic/checks e dashboard de estado.  
**Como implementar:** criar `clawlite/runtime/component_registry.py` e `runtime/recovery_policies.py`; registrar Telegram, heartbeat, cron, autonomy e sweeper de subagentes no startup.  
**Prioridade:** 🔴 Bloqueante  
**Ganho estimado:** `+6 p.p.` na Fase 5 e `+22%` de disponibilidade contínua.  

---
### [⚠️ Parcial] AUTO-5 Recuperação automática de provider e loop guard de autonomia ainda não estão completos

**Evidência no ClawLite:** `clawlite/core/engine.py` linhas `551-568` — loop guard só pega repetição do mesmo tool; linhas `1335-1344` — erro de provider vira mensagem ao usuário, mas não política autonômica de auto-recuperação.  
**O que falta:** retries/failover sem intervenção humana em jobs autonômicos, `no-progress` global e proteção contra ping-pong em ciclos proativos.  
**Referência:** OpenClaw combina wake/heartbeat/fallback com mais profundidade; nanobot tem loop mais contratual.  
**Como implementar:** integrar `FallbackPolicy` ao `AutonomyService`; criar guard de progresso em `clawlite/runtime/autonomy_guard.py`; registrar métricas por job e por provider.  
**Prioridade:** 🔴 Bloqueante  
**Ganho estimado:** `+7 p.p.` na Fase 5 e `+28%` de autonomia real.  

---
### [⚠️ Parcial] AUTO-6 Logs estruturados e avisos proativos ao usuário são parciais

**Evidência no ClawLite:** `clawlite/runtime/autonomy.py` linhas `396-419` — status expõe contadores/excerpt; `clawlite/tools/message.py` linhas `19-170` — ferramenta para aviso proativo existe.  
**O que falta:** trilha estruturada `ação → motivo → resultado → impacto`, retenção consultável e política universal de notificação ao usuário via Telegram.  
**Referência:** antfarm tem dashboard/medic/eventos melhores; OpenClaw integra melhor runtime e delivery.  
**Como implementar:** criar `clawlite/runtime/autonomy_audit.py` e `autonomy_notifications.py`; chamar `message` tool ou `ChannelManager.send` após ações críticas; expor consulta em skill `session-logs`/nova skill `autonomy-logs`.  
**Prioridade:** 🟡 Importante  
**Ganho estimado:** `+5 p.p.` na Fase 5 e `+20%` de observabilidade operacional.  

---

## FASE 6 — AGENTS E SUBAGENTS 100%

---
### [✅ Tem] AGS-1 Sessions API básica e síntese de subagentes

**Evidência no ClawLite:** `clawlite/tools/sessions.py` linhas `131-460` — `sessions_list`, `sessions_history`, `sessions_send`, `sessions_spawn`, `subagents`, `session_status`; `clawlite/core/subagent.py` linhas `357-398` — runs concluídos não sintetizados; `clawlite/core/subagent_synthesizer.py` — digest determinístico.  
**O que falta:** nada crítico no baseline; a lacuna está no lifecycle avançado.  
**Referência:** OpenClaw e antfarm vão além em governança e persistência de workflow.  
**Como implementar:** manter e expandir os itens AGS-2 a AGS-5.  
**Prioridade:** 🟢 Melhoria  
**Ganho estimado:** `0 p.p.` de completude; item já entregue.  

---
### [⚠️ Parcial] AGS-2 Lifecycle de subagentes sem retry budget, expiry e sweeper de zumbis

**Evidência no ClawLite:** `clawlite/core/subagent.py` linhas `13-25` — `SubagentRun` só tem `status/result/error/timestamps`; linhas `173-179` — restart marca `running/queued` como `interrupted`, mas não há expiry nem sweeper.  
**O que falta:** `retry_budget`, `expires_at`, `heartbeat_at`, sweeper de órfãos/zumbis, backoff de resume e política de terminal states.  
**Referência:** OpenClaw resolve isso em `subagent-registry.ts` e `subagent-registry-cleanup.ts`; antfarm usa `retry_count/max_retries/abandoned_count`.  
**Como implementar:** estender `SubagentRun` e `SubagentManager` em `clawlite/core/subagent.py`; criar task `sweep_async()` e registrar no runtime; adicionar testes de zombie cleanup em `tests/core/test_subagent.py`.  
**Prioridade:** 🔴 Bloqueante  
**Ganho estimado:** `+8 p.p.` na Fase 6 e `+30%` de robustez do multi-agente.  

---
### [❌ Falta] AGS-3 Tool `agents_list` com inventário completo

**Evidência no ClawLite:** `clawlite/gateway/server.py` linhas `870-1000` registram 29 tools, mas `rg "agents_list" clawlite` não retorna nenhum resultado.  
**O que falta:** inventário de agentes/subagentes/sessões-alvo, status atual, capacidades e limites.  
**Referência:** OpenClaw inclui `agents_list` no catálogo de tools.  
**Como implementar:** criar `clawlite/tools/agents.py` com `AgentsListTool`; registrar em `clawlite/gateway/server.py`; expor source de dados do `SubagentManager` e runtime principal.  
**Prioridade:** 🟡 Importante  
**Ganho estimado:** `+4 p.p.` na Fase 6 e `+15%` de observabilidade do multi-agente.  

---
### [⚠️ Parcial] AGS-4 Isolamento de contexto e coordenação paralela ainda são básicos

**Evidência no ClawLite:** `clawlite/tools/sessions.py` linhas `311-323` — `sessions_spawn` roteia para `ctx.session_id:subagent`; `clawlite/core/subagent.py` guarda `metadata`, mas sem modelo formal de contexto pai/filho.  
**O que falta:** envelopes de contexto, boundary de memória por subagente, herança seletiva de SOUL/USER/TOOLS, limites de profundidade e merge policy explícita de resultados.  
**Referência:** OpenClaw valida `agentId`, profundidade e modo de thread/session em `subagent-spawn.ts`; antfarm persiste `runs -> steps -> stories`.  
**Como implementar:** adicionar `parent_session_id`, `target_session_id`, `context_scope`, `depth` em `SubagentRun.metadata`; alterar `SessionsSpawnTool.run`, `AgentEngine._inject_subagent_digest` e `PromptBuilder.build`.  
**Prioridade:** 🔴 Bloqueante  
**Ganho estimado:** `+7 p.p.` na Fase 6 e `+25%` de previsibilidade na coordenação paralela.  

---
### [⚠️ Parcial] AGS-5 Comunicação entre agentes existe, mas sem orchestration store

**Evidência no ClawLite:** `clawlite/tools/sessions.py` linhas `213-283` — `sessions_send` envia mensagem para outra sessão; não existe store de workflow/dependência/step state no runtime.  
**O que falta:** DAG simples ou pelo menos `run/step/story state`, dependências, retries por etapa, correlação de mensagens entre pai e filhos e histórico de coordenação.  
**Referência:** antfarm é superior neste ponto com estado persistente de workflow; OpenClaw também é mais rico em governança de subagentes.  
**Como implementar:** criar `clawlite/core/agent_workflows.py` com persistência em JSON/SQLite; integrar `SessionsSendTool`, `SessionsSpawnTool` e `SubagentManager`; expor auditoria em `session_status`.  
**Prioridade:** 🔴 Bloqueante  
**Ganho estimado:** `+6 p.p.` na Fase 6 e `+22%` de coordenação multi-agente.  

---

## FASE 7 — AUTO-EVOLUÇÃO E MEMÓRIA AVANÇADA

### O que o memU oferece de diferente/superior ao estado atual do ClawLite

- Modelo de memória mais explícito e hierárquico: `Resource -> MemoryItem -> MemoryCategory -> CategoryItem`.
- Ênfase forte em memória episódica/eventos e em salience/recency/reinforcement.
- Pipeline de retrieval com query rewrite e checagem de suficiência.
- Escopos que se adaptam melhor a namespaces de usuário/agente/sessão.
- O memU ainda **não** resolve sozinho tudo o que você quer para a fase final: working memory explícita, decay de ciclo de vida completo, híbrido lexical+vetorial de produção e consolidação madura ainda precisam ser fechados.

---
### [❌ Falta] EVO-1 Pipeline de autoanálise, autocorreção, teste, commit e notificação

**Evidência no ClawLite:** `clawlite/gateway/server.py` linhas `870-1000` expõem as peças (`exec`, `apply_patch`, `process`, `message`), mas não existe orquestrador que leia o próprio código, compare com referências, aplique patch, rode testes e faça commit com policy segura.  
**O que falta:** pipeline completo `analisar -> propor -> patch -> testar -> validar -> commit -> notificar`, sem intervenção humana e com fail-closed em caso de teste vermelho.  
**Referência:** nem OpenClaw, nem nanobot, nem memU entregam isso como produto fechado; aqui está uma oportunidade própria do ClawLite.  
**Como implementar:** criar `clawlite/runtime/self_improvement.py`, `self_improvement_policies.py` e `self_improvement_audit.py`; integrar com scheduler/autonomy; usar `exec` para `pytest`, `apply_patch` para mudanças e `message` para notificação via Telegram.  
**Prioridade:** 🔴 Bloqueante  
**Ganho estimado:** `+10 p.p.` na Fase 7 e `+40%` de autonomia evolutiva quando as fases 1-6 estiverem estáveis.  

---
### [⚠️ Parcial] EVO-2 Memória avançada: boa fundação, mas faltam working memory, episódica forte, decay e busca híbrida

**Evidência no ClawLite:** `clawlite/core/memory.py` linhas `349-366` — camadas `resources/items/categories/users/shared`; linhas `4023-4071` — `recover_session_context`; linhas `3726-3733` — busca ainda cai em caminho não semântico em pontos importantes.  
**O que falta:** working memory explícita da sessão, memória episódica com `what/when/context/entities`, consolidação periódica, decay/archive, busca híbrida `semantic + temporal + entity`, compartilhamento controlado entre subagentes.  
**Referência:** memU oferece schema e retrieval mais alinhados com esta meta; OpenClaw e nanobot fornecem runtime/contexto, mas não têm a mesma ambição de memória avançada local-first.  
**Como implementar:** criar `clawlite/core/working_memory.py`, `episodic_memory.py`, `memory_consolidator.py`, `memory_decay.py` e `memory_hybrid_search.py`; estender `MemoryStore.memorize`, `search` e `consolidate`; adicionar campo de entidade/episódio nos registros e cron de consolidação.  
**Prioridade:** 🔴 Bloqueante  
**Ganho estimado:** `+12 p.p.` na Fase 7 e `+45%` de qualidade de memória/autonomia contextual.  

---
### [❌ Falta] EVO-3 Memória compartilhada seletiva entre subagentes como política explícita

**Evidência no ClawLite:** `clawlite/core/memory.py` linhas `359-361` — há `users_path` e `shared_path`; `clawlite/core/subagent.py` e `clawlite/core/engine.py` não implementam contrato explícito de memória compartilhada por grupo de agentes.  
**O que falta:** escopo compartilhado por task/grupo, ACL de leitura/escrita entre pai e filhos, handoff seletivo de memória e merge policy após conclusão.  
**Referência:** memU já aponta para namespaces/scope; antfarm reforça a necessidade de contexto compartilhado persistente por workflow.  
**Como implementar:** estender `MemoryStore` com scopes de colaboração; ligar isso a `SubagentRun.metadata` e `SessionsSpawnTool`; implementar merge controlado no retorno do subagente.  
**Prioridade:** 🟡 Importante  
**Ganho estimado:** `+5 p.p.` na Fase 7 e `+20%` de cooperação entre agentes sem vazamento de contexto.  

---

## 📊 Scorecard Atual do ClawLite

| Fase | Completude | Bloqueantes |
|---|---:|---:|
| 1 - Telegram | 72% | 3 itens |
| 2 - Núcleo | 76% | 4 itens |
| 3 - Providers | 35% | 3 itens |
| 4 - Skills | 48% | 3 itens |
| 5 - Autonomia | 62% | 3 itens |
| 6 - Agents | 58% | 3 itens |
| 7 - Auto-evolução | 22% | 2 itens |
| **TOTAL** | **54%** | **21 itens** |

---

## 🗺️ Ordem de Execução Recomendada

### Sprint 1 (semana 1): itens bloqueantes críticos

1. `PRV-3` — implementar failover multi-hop por classe de erro.
2. `PRV-2` — expandir cobertura de providers para a base de paridade.
3. `PRV-5` — adicionar autodiscovery e health check de Ollama/vLLM.
4. `TG-5` — criar watermark seguro de offset e cobertura total de updates.
5. `TG-3` — implementar ingestão real de mídia inbound.
6. `TG-4` — pairing persistente e binding seguro por thread/remetente.
7. `MEM-2` — corrigir recall semântico em todos os escopos.
8. `MEM-3` — transformar pgvector em backend realmente vetorial.
9. `AGT-2` — fechar loop guard completo.
10. `HB-2` — criar supervisão independente por loop crítico.
11. `AUTO-3` — persistir replay de outbound/dead letters após restart.

### Sprint 2 (semana 2): paridade funcional

1. `AUTO-4` — registrar recovery por canal e por componente.
2. `AUTO-5` — auto-recuperação de provider nos fluxos autonômicos.
3. `SK-2` — zerar skills indisponíveis com fallback real.
4. `SK-4` — implementar lifecycle `enable/disable/pin/version`.
5. `SK-5` — adicionar fallback chains de dependência por skill.
6. `SK-3` — hot reload com watcher + debounce.
7. `AGS-2` — retry budget, expiry e zombie sweeper de subagentes.
8. `AGS-4` — isolamento de contexto pai/filho e coordenação paralela.
9. `AGS-5` — orchestration store para comunicação entre agentes.
10. `SOUL-1` — enforcement pós-provider de SOUL/IDENTITY/USER.
11. `USER-1` — parser estruturado de preferências e associação ao pairing.
12. `PRV-4` — reuso automático de `~/.codex/auth.json`.
13. `PRV-6` — alinhar onboarding/registry oficial.

### Sprint 3 (semana 3): features avançadas

1. `AGS-3` — implementar `agents_list`.
2. `AUTO-6` — logs estruturados e avisos proativos ao usuário.
3. `SK-6` — compatibilidade OpenClaw mais completa no ecossistema de skills.
4. `AGT-3` — validação de persona antes de persistência.
5. `EVO-2` — camada de working memory + episódica + consolidação.
6. `EVO-3` — memória compartilhada seletiva entre subagentes.
7. `TG-1` — congelar baseline do Telegram com regressão ampliada.
8. `TG-2` — consolidar testes de transporte, webhook e reconnect.
9. `MEM-1` — ampliar regressão de atomicidade e monitor independente.
10. `TOOLS-1` — congelar catálogo/fail-closed com testes de segurança.

### Sprint 4 (semana 4): autonomia e auto-evolução

1. `EVO-1` — pipeline de autoanálise, patch, teste, commit e notificação.
2. `PRV-1` — consolidar taxonomia de erro e mensagens de remediation.
3. `SK-1` — congelar contrato de skills como base estável para auto-evolução.
4. `AUTO-1` — validar WakeQueue sob carga com métricas e soak tests.
5. `AUTO-2` — validar cron/heartbeat/autonomy em cenários de restart.
6. `AGS-1` — validar síntese de subagentes e APIs de sessão sob concorrência.
7. `HB-1` — soak test do heartbeat com reset e backoff.
8. `AGT-1` — soak test do agente principal com tools e recovery.

---

## ⚡ Os 10 itens que mais impactam a qualidade do ClawLite hoje

1. `PRV-3` — failover multi-hop por classe de erro.
2. `PRV-2` — cobertura real de providers.
3. `MEM-2` — recall semântico consistente em todos os escopos.
4. `TG-5` — offset seguro + matriz completa de updates do Telegram.
5. `AUTO-3` — replay durável após restart.
6. `HB-2` — supervisão independente de loops críticos.
7. `AGT-2` — loop guard completo contra ping-pong/no-progress.
8. `TG-3` — ingestão real de mídia inbound.
9. `AGS-2` — lifecycle completo de subagentes.
10. `SK-5` — fallback de dependências por skill.

---

## 🔭 O que o ClawLite terá que nenhum dos outros tem

1. **Autonomia auditável de ponta a ponta.**  
ClawLite pode unir Telegram, memória, tools, cron, skills e subagentes em um único trilho operacional com log estruturado `ação → motivo → resultado → aviso ao usuário`.

2. **Memória híbrida local-first realmente útil para agentes pessoais.**  
Com working memory + episódica + vetorial + temporal + entidades + memória compartilhada seletiva, o ClawLite pode ficar mais útil que OpenClaw e nanobot em continuidade pessoal, e mais aplicável que memU em runtime real.

3. **Subagentes thread-aware para Telegram.**  
Se você fechar pairing, thread binding e contexto por tópico, o ClawLite pode virar um runtime multiagente que opera naturalmente dentro do Telegram, algo que nenhum dos outros entrega tão bem como produto completo.

4. **Auto-evolução segura com fail-closed.**  
Ao contrário de “autonomia cega”, o diferencial pode ser: corrigir sozinho, rodar testes, só persistir se tudo passar e avisar o usuário do que foi feito. Isso é mais útil do que um agente que apenas tenta agir sem trilha segura.

5. **Governança unificada de provider + skill + memória + canal.**  
Oportunidade clara: política única de risco e contexto, onde canal, skill, provider e memória participam da mesma decisão. Hoje os projetos de referência são fortes em partes isoladas; o ClawLite pode ser forte na integração.

---

## Resumo executivo

O ClawLite já tem uma base **mais madura do que parece** em Telegram, memória, tools, heartbeat e sessions/subagents. O que mais puxa a nota para baixo hoje não é “falta de fundação”, e sim **gaps de paridade operacional**:

1. breadth de providers e failover,
2. pairing/update matrix do Telegram,
3. replay/supervisão/autonomia durável,
4. lifecycle robusto de skills e subagentes,
5. memória avançada e auto-evolução ainda não consolidadas.

Se eu tivesse que resumir em uma frase: **o ClawLite já é um runtime funcional; o próximo salto é transformá-lo em um runtime confiável sob falha, restart, múltiplos agentes e múltiplos providers.**
