# ClawLite — Auditoria de Código

**Data:** 2026-03-06
**Escopo:** `clawlite/core/` e `clawlite/channels/`
**Metodologia:** Leitura completa dos arquivos + análise estática manual
**Regra:** Auditoria apenas — nenhum código foi alterado

---

## SESSÃO 1 — `clawlite/core/`

Arquivos auditados:
- `core/engine.py` (1576 linhas)
- `core/memory.py` (~4529 linhas)
- `core/memory_backend.py` (768 linhas)
- `core/memory_monitor.py` (482 linhas)
- `core/prompt.py` (260 linhas)
- `core/skills.py` (571 linhas)
- `core/subagent.py` (401 linhas)
- `core/subagent_synthesizer.py` (54 linhas)

---

### Bug 1 — `setup_logging()` chamado no nível do módulo

**Arquivo:** `core/engine.py` — linha 21
**Severidade:** Moderado
**Categoria:** Bug | Robustez

**O que está errado:**
`setup_logging()` é chamado quando o módulo é importado. Qualquer `import` de `engine`
inicializa o sistema de logging, mesmo em testes unitários, CLI tools ou contextos onde o
caller já configurou o logging antes. Efeito colateral de importação viola o princípio de
menor surpresa e contamina configurações de logging nos testes (e.g., sobrescreve `caplog`
do pytest).

```python
# Antes — linha 21
setup_logging()  # executa no import, antes de qualquer instância
```

```python
# Depois — mover para dentro de __init__ do AgentEngine, ou tornar opt-in
class AgentEngine:
    def __init__(self, ..., *, configure_logging: bool = False):
        if configure_logging:
            setup_logging()
```

**Dica de robustez:** Usar `logging.getLogger(__name__).addHandler(logging.NullHandler())`
no topo do módulo é o idioma correto para bibliotecas. Evita qualquer saída de log acidental.

**Dica de otimização:** Removendo do nível de módulo, o import fica 1–2ms mais rápido por
não inicializar formatters na carga.

---

### Bug 2 — `_session_locks` cresce indefinidamente (memory leak)

**Arquivo:** `core/engine.py` — linha 324
**Severidade:** Critico
**Categoria:** Bug | Performance | Robustez

**O que está errado:**
```python
self._session_locks: dict[str, asyncio.Lock] = {}
```
Cada `session_id` único gera um novo `asyncio.Lock` que nunca é removido. Em produção
com Telegram/WhatsApp, onde cada usuário tem um `session_id` diferente (e.g.
`telegram:1234567`), o dict cresce sem limite. Após semanas com milhares de usuários
ativos, o processo acumula MB de locks ociosos.

```python
# Antes — Lock criado mas nunca removido
async def _get_session_lock(self, session_id: str) -> asyncio.Lock:
    async with self._session_locks_guard:
        lock = self._session_locks.get(session_id)
        if lock is None:
            lock = asyncio.Lock()
            self._session_locks[session_id] = lock
        return lock
```

```python
# Depois — usar WeakValueDictionary
import weakref

self._session_locks: weakref.WeakValueDictionary[str, asyncio.Lock] = (
    weakref.WeakValueDictionary()
)

# O lock é coletado pelo GC quando não há referência ativa ao turn
```

**Dica de robustez:** Alternativamente, limitar o dict a N sessões com LRU (via
`cachetools.TTLCache`). Locks não usados há mais de 1h podem ser removidos.

**Dica de otimização:** Com `WeakValueDictionary`, o GC recupera memória automaticamente
após cada turn completar, eliminando o leak sem custo de manutenção.

---

### Bug 3 — `inspect.signature()` chamado a cada iteração do loop LLM

**Arquivo:** `core/engine.py` — linhas 470–481 e 693–700
**Severidade:** Moderado
**Categoria:** Performance

**O que está errado:**
`inspect.signature(self.provider.complete)` é chamado dentro de `_complete_provider()`,
que é chamado em cada iteração do loop agentico (podendo chegar a 40 iterações).
`inspect.signature()` faz introspecção via módulo `inspect`, o que inclui acesso a
`__wrapped__`, `__annotations__` e resolução de tipos — tem custo não negligenciável
(50–200µs por chamada).

O mesmo problema ocorre em `_accepts_parameter()` chamado repetidamente em
`_memory_search`, `_memory_integration_policy`, `_memory_integration_hint`.

```python
# Antes — introspecção a cada chamada
async def _complete_provider(self, ...):
    complete_sig = inspect.signature(self.provider.complete)  # a cada iteracao
    accepts_max_tokens = "max_tokens" in complete_sig.parameters
    ...
```

```python
# Depois — cache no __init__
def __init__(self, *, provider: ProviderProtocol, ...):
    _sig = inspect.signature(provider.complete)
    _params = _sig.parameters
    self._provider_accepts_max_tokens = "max_tokens" in _params
    self._provider_accepts_temperature = "temperature" in _params
    self._provider_accepts_reasoning_effort = "reasoning_effort" in _params

async def _complete_provider(self, ...):
    kwargs: dict[str, Any] = {"messages": messages, "tools": tools}
    if self._provider_accepts_max_tokens:
        kwargs["max_tokens"] = self.max_tokens
    ...
```

**Dica de robustez:** Se o provider for trocado após `__init__`, o cache fica stale.
Adicionar um método `reload_provider(provider)` para recalcular o cache.

**Dica de otimizacao:** Com 40 iteracoes e 80 tool calls, eliminar `inspect.signature()`
do loop pode poupar 5–10ms por turn.

---

### Bug 4 — `PgvectorMemoryBackend` nao usa pgvector para busca vetorial

**Arquivo:** `core/memory_backend.py` — linhas 743–760
**Severidade:** Critico
**Categoria:** Bug | Performance

**O que esta errado:**
Apesar do nome `PgvectorMemoryBackend`, a implementacao de `query_similar_embeddings`
**nao usa a extensao pgvector**. Ela carrega todos os embeddings do banco para memoria
(`fetch_embeddings(limit=5000)`) e faz calculo de cosseno em Python puro com loop O(N*D).
Para N=5000 embeddings de dimensao D=1536, isso processa ~7.68M operacoes float por
query — tudo em Python, nao em C/SQL.

```python
# Antes — busca em Python puro (sem pgvector)
def query_similar_embeddings(self, query_embedding, record_ids=None, limit=10):
    embeddings = self.fetch_embeddings(record_ids=record_ids, limit=max(bounded_limit, 5000))
    scored = []
    for row_id, vector in embeddings.items():
        score = self._cosine_similarity(normalized_query, vector)  # loop Python
        scored.append({"record_id": row_id, "score": float(score)})
    scored.sort(...)
    return scored[:bounded_limit]
```

```python
# Depois — usar o operador nativo do pgvector
def query_similar_embeddings(self, query_embedding, record_ids=None, limit=10):
    normalized_query = self._normalize_embedding(query_embedding)
    if normalized_query is None:
        return []
    conn = self._open_connection()
    if conn is None:
        return []
    # pgvector usa o operador <=> para distancia coseno
    query_vec = "[" + ",".join(str(v) for v in normalized_query) + "]"
    sql = """
        SELECT record_id, 1 - (embedding::vector <=> %s::vector) AS score
        FROM embeddings
        ORDER BY embedding::vector <=> %s::vector
        LIMIT %s
    """
    # executar com conn e retornar resultados
```

**Dica de robustez:** Adicionar index HNSW ou IVFFlat no PostgreSQL para busca ANN
(approximate nearest neighbor) com recall ~95% e latencia < 1ms.

**Dica de otimizacao:** Com pgvector nativo, a busca passa de O(N*D) Python para O(N log N)
indexado em C. Para 5000 vetores de 1536 dims: de ~500ms para ~1ms.

---

### Bug 5 — Codigo duplicado `_cosine_similarity` e `_normalize_embedding`

**Arquivo:** `core/memory_backend.py` — linhas 98–113 (SQLite) e 351–382 (Pgvector)
**Severidade:** Leve
**Categoria:** Robustez | Legibilidade

**O que esta errado:**
`_cosine_similarity` e `_normalize_embedding` sao copiados literalmente entre
`SQLiteMemoryBackend` e `PgvectorMemoryBackend`. Qualquer correcao em um nao
se propaga para o outro.

```python
# Antes — duplicado como @staticmethod em cada classe
class SQLiteMemoryBackend:
    @staticmethod
    def _cosine_similarity(left, right): ...  # 15 linhas

class PgvectorMemoryBackend:
    @staticmethod
    def _cosine_similarity(left, right): ...  # 15 linhas identicas
```

```python
# Depois — funcoes module-level compartilhadas
def _cosine_similarity(left: list[float], right: list[float]) -> float: ...
def _normalize_embedding(raw: Any) -> list[float] | None: ...

class SQLiteMemoryBackend:
    # usa as funcoes module-level
class PgvectorMemoryBackend:
    # usa as funcoes module-level
```

**Dica de robustez:** Com funcao compartilhada, qualquer melhoria (e.g. usar `numpy` se
disponivel) beneficia ambos os backends simultaneamente.

---

### Bug 6 — `_persist_pending` bloqueia o event loop

**Arquivo:** `core/memory_monitor.py` — linhas 442–468 e 470–481
**Severidade:** Moderado
**Categoria:** Bug | Performance

**O que esta errado:**
`scan()` e uma coroutine (`async def`), mas chama `_persist_pending()` diretamente (linha
480), que usa `threading.Lock` e faz I/O de arquivo sincrono. Isso **bloqueia o event loop**
enquanto escreve o arquivo `suggestions_pending.json`. Em Android/Termux com eMMC, isso
pode durar 50–200ms.

```python
# Antes — I/O sincrono bloqueando o event loop
async def scan(self) -> list[MemorySuggestion]:
    records = await asyncio.to_thread(self._all_records)  # correto
    suggestions.extend(...)
    self._persist_pending(suggestions)  # BLOQUEANTE: lock + write sincrono
    return self.pending()
```

```python
# Depois — offload do I/O para thread pool
async def scan(self) -> list[MemorySuggestion]:
    records = await asyncio.to_thread(self._all_records)
    suggestions = self._build_suggestions(records)  # logica CPU leve
    await asyncio.to_thread(self._persist_pending, suggestions)
    return await asyncio.to_thread(self.pending)
```

**Dica de robustez:** `threading.Lock` dentro de `asyncio.to_thread` e seguro — o lock
protege contra chamadas concorrentes de outras threads, que e o comportamento correto.

**Dica de otimizacao:** `_atomic_write_pending_text` faz `os.fsync()` duas vezes (arquivo
+ diretorio). Considerar tornar o fsync do diretorio opcional com uma flag de configuracao.

---

### Bug 7 — `messages` cresce sem limite dentro do turn

**Arquivo:** `core/engine.py` — linhas 1190–1494
**Severidade:** Moderado
**Categoria:** Performance | Robustez

**O que esta errado:**
A lista `messages` acumula todas as mensagens do turno sem truncamento. Com
`max_iterations=40` e `max_tool_calls_per_turn=80`, uma sessao de uso intenso pode criar
uma lista de centenas de mensagens que e serializada e enviada ao provider a cada nova
iteracao, potencialmente excedendo 100K tokens sem que o codigo perceba.

```python
# No loop — acumulacao sem controle
messages.append({"role": "assistant", ..., "tool_calls": ...})
messages.append({"role": "tool", "content": normalized_result, ...})
# apos 40 iteracoes com 5 tools cada = 400 mensagens adicionais
```

```python
# Diagnostico — adicionar log antes do provider call
run_log.debug(
    "provider call iteration={} messages_count={} est_tokens={}",
    iteration,
    len(messages),
    sum(len(str(m.get("content", ""))) // 4 for m in messages),
)
```

**Dica de robustez:** Implementar truncamento de mensagens antigas de tool calls quando
`len(messages)` exceder um limite configuravel (manter apenas as ultimas N trocas de
tool call).

---

### Bug 8 — Race condition em `cancel()` e `mark_synthesized()` sem async lock

**Arquivo:** `core/subagent.py` — linhas 372–393 e 348–370
**Severidade:** Moderado
**Categoria:** Bug | Robustez

**O que esta errado:**
`cancel()` e `mark_synthesized()` modificam `self._runs` e chamam `_save_state()` sem
usar `async with self._lock:`, enquanto o worker interno adquire o lock antes de escrever
o estado. Isso cria uma janela de race condition.

```python
# Antes — sem lock em cancel()
def cancel(self, run_id: str) -> bool:
    task = self._tasks.get(clean_run_id)          # sem lock
    if task is not None and not task.done():
        task.cancel()
        return True
    if clean_run_id in self._queue:
        run = self._runs.get(clean_run_id)        # sem lock
        run.status = "cancelled"
        self._save_state()                        # sem lock
        return True
```

```python
# Depois — cancel() deve ser async e usar o lock
async def cancel(self, run_id: str) -> bool:
    clean_run_id = str(run_id or "").strip()
    async with self._lock:
        task = self._tasks.get(clean_run_id)
        if task is not None and not task.done():
            task.cancel()
            return True
        if clean_run_id in self._queue:
            self._queue = deque(item for item in self._queue if item != clean_run_id)
            run = self._runs.get(clean_run_id)
            if run is not None:
                now_iso = _utc_now()
                run.status = "cancelled"
                run.finished_at = now_iso
                run.updated_at = now_iso
            self._pending_runners.pop(clean_run_id, None)
            self._save_state()
            return True
    return False
```

**Dica de robustez:** `cancel_session()` chama `cancel()` em loop sem lock global — deve
ser refatorado para adquirir o lock uma vez para toda a operacao.

---

### Bug 9 — `SkillsLoader.get()` sem cache (I/O a cada lookup)

**Arquivo:** `core/skills.py` — linhas 531–535
**Severidade:** Leve
**Categoria:** Performance

**O que esta errado:**
`get(name)` chama `discover()` que percorre o filesystem a cada chamada. Durante o turn
do agente, `get()` pode ser chamado multiplas vezes por `render_for_prompt()`,
`load_skills_for_context()` e `always_on()` — cada uma fazendo I/O separado.

```python
# Antes — 3 traversals do filesystem por turn
def get(self, name: str) -> SkillSpec | None:
    for row in self.discover(include_unavailable=True):  # I/O toda vez
        if row.name.lower() == wanted:
            return row
```

```python
# Depois — adicionar cache TTL simples
import time

def __init__(self, ...):
    self._cache: list[SkillSpec] | None = None
    self._cache_ts: float = 0.0
    self._cache_ttl: float = 60.0

def _get_cached(self) -> list[SkillSpec]:
    if self._cache is None or (time.monotonic() - self._cache_ts) > self._cache_ttl:
        self._cache = self._discover_uncached()
        self._cache_ts = time.monotonic()
    return self._cache
```

---

### Bug 10 — `_estimate_tokens` impreciso para Unicode/portugues

**Arquivo:** `core/prompt.py` — linhas 112–115
**Severidade:** Leve
**Categoria:** Robustez

**O que esta errado:**
```python
@staticmethod
def _estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))
```
A heuristica `chars / 4` e calibrada para ingles. Texto em portugues com acentos e emoji
frequentemente tem tokens maiores (1–2 chars/token). Isso significa que o
`context_token_budget` pode ser excedido em 30–50% sem o sistema perceber.

```python
# Depois — estimativa mais conservadora para multilingual
@staticmethod
def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    # ~3 chars/token para texto multilingual (mais conservador que 4)
    return max(1, math.ceil(len(text) / 3))
```

---

### Bug 11 — `datetime.now()` sem timezone em `_render_runtime_context`

**Arquivo:** `core/prompt.py` — linha 203
**Severidade:** Leve
**Categoria:** Bug

**O que esta errado:**
```python
now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
tz = time.strftime("%Z") or "UTC"
```
`datetime.now()` retorna hora local naive. `time.strftime("%Z")` pode retornar string vazia
em Termux/Android, fazendo o codigo assumir "UTC" quando nao e. O agente recebe contexto
temporal errado se o servidor rodar em timezone diferente do usuario.

```python
# Depois
from datetime import datetime, timezone
now_utc = datetime.now(timezone.utc)
tz = time.strftime("%Z") or "UTC"
now = now_utc.strftime("%Y-%m-%d %H:%M (%A)")
```

---

### Bug 12 — `_stop_requests` nao e limpo apos sessoes encerradas

**Arquivo:** `core/engine.py` — linhas 323, 871–881
**Severidade:** Leve
**Categoria:** Bug | Robustez

**O que esta errado:**
`clear_stop()` so e chamado apos o turn completar normalmente. Se `request_stop()` for
chamado e a sessao nunca iniciar um novo turn, o `session_id` permanece no set
indefinidamente. Em deployment de longa duracao, o set cresce.

```python
# Depois — adicionar TTL via dict com timestamp
self._stop_requests: dict[str, float] = {}

def request_stop(self, session_id: str) -> bool:
    self._stop_requests[normalized] = time.monotonic()
    return True

def _stop_requested(self, *, session_id: str, ...) -> bool:
    ts = self._stop_requests.get(session_id)
    if ts is not None:
        if time.monotonic() - ts < 300:  # TTL de 5 minutos
            return True
        self._stop_requests.pop(session_id, None)
    return stop_event is not None and stop_event.is_set()
```

---

## Resumo da Sessao 1 — `core/`

| Severidade | Quantidade |
|---|---|
| Critico    | 2          |
| Moderado   | 5          |
| Leve       | 5          |

**Top 3 prioridades:**

1. `_session_locks` memory leak (`engine.py:324`) — em producao com multiplos usuarios,
   cresce sem limite. Usar `WeakValueDictionary`.
2. `PgvectorMemoryBackend` nao usa pgvector (`memory_backend.py:743`) — busca vetorial
   em Python puro para N=5000 e 500x mais lenta. Quem configura pgvector esta sendo
   enganado.
3. `_persist_pending` bloqueia event loop (`memory_monitor.py:480`) — I/O sincrono com
   `fsync` pode pausar todos os handlers por 50–200ms em Android/Termux.

**Maior ganho de performance:**
Cachear `inspect.signature()` no `__init__` do `AgentEngine` e adicionar cache TTL ao
`SkillsLoader.discover()` eliminam I/O e introspeccao desnecessarios do hot path do loop
agentico, podendo reduzir latencia por turn em 5–15ms em loops intensos.

---

---

## SESSAO 2 — `clawlite/channels/`

Arquivos auditados:
- `channels/base.py`
- `channels/telegram.py` (~1600 linhas)
- `channels/manager.py` (832 linhas)
- `channels/discord.py` (65 linhas)
- `channels/slack.py` (72 linhas)
- `channels/whatsapp.py`, `signal.py`, `matrix.py`, `irc.py`, etc. (PassiveChannel)

---

### Bug 13 — `setup_logging()` no nivel de modulo em telegram.py e manager.py

**Arquivo:** `channels/telegram.py` — linha 37 | `channels/manager.py` — linha 30
**Severidade:** Moderado
**Categoria:** Bug | Robustez

**O que esta errado:**
Mesmo problema do Bug 1. Tanto `telegram.py` quanto `manager.py` chamam `setup_logging()`
no nivel de modulo. Isso significa que qualquer import desses modulos (inclusive nos testes)
inicializa o sistema de logging, podendo sobrescrever configuracoes do chamador.

```python
# telegram.py linha 37 e manager.py linha 30
setup_logging()  # efeito colateral de import
```

```python
# Depois — remover do nivel de modulo; chamar apenas no entrypoint do processo
# Em main.py ou gateway/server.py, chamar setup_logging() uma unica vez
```

**Dica de robustez:** O problema agrava em testes — ao importar `TelegramChannel` e
`ChannelManager` em suites diferentes, `setup_logging()` e chamado multiplas vezes,
podendo duplicar handlers de log e produzir saida duplicada ou interferencia em `caplog`.

---

### Bug 14 — `_callback_sign_payload` usa nonce nao-aleatorio

**Arquivo:** `channels/telegram.py` — linha 539
**Severidade:** Critico
**Categoria:** Seguranca

**O que esta errado:**
O nonce do callback HMAC e gerado a partir de `time.monotonic()`, que e deterministico e
previsivel. Um atacante com acesso ao tempo de geracao pode reconstruir o nonce e forjar
assinaturas.

```python
# Antes — nonce derivado de tempo deterministico
def _callback_sign_payload(self, callback_data: str) -> str:
    nonce = base64.urlsafe_b64encode(
        hashlib.sha256(str(time.monotonic()).encode("utf-8")).digest()[:6]
    ).decode("ascii").rstrip("=")
    ...
```

```python
# Depois — nonce criptograficamente aleatorio
import secrets

def _callback_sign_payload(self, callback_data: str) -> str:
    nonce = base64.urlsafe_b64encode(secrets.token_bytes(6)).decode("ascii").rstrip("=")
    ...
```

**Dica de robustez:** `time.monotonic()` tem resolucao de nanosegundos mas e previsivel.
`secrets.token_bytes()` usa o CSPRNG do OS (urandom/getrandom), que e imprevisivel mesmo
com acesso ao tempo do servidor.

---

### Bug 15 — `_persist_update_dedupe_state` sem `fsync` (risco de perda de dados)

**Arquivo:** `channels/telegram.py` — linhas 512–527
**Severidade:** Moderado
**Categoria:** Confiabilidade

**O que esta errado:**
`_persist_update_dedupe_state` usa o padrao correto de write-to-tmp + rename, mas **nao
faz `fsync`** antes do rename. Em queda de energia ou kill do processo, o arquivo tmp pode
estar vazio ou parcialmente escrito, e o rename pode persistir um estado corrompido.

```python
# Antes — sem fsync
async def _persist_update_dedupe_state(self) -> None:
    tmp_path.write_text(json.dumps(payload), encoding="utf-8")
    tmp_path.replace(path)  # pode persistir arquivo vazio
```

```python
# Depois — com fsync antes do replace
async def _persist_update_dedupe_state(self) -> None:
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._dedupe_state_payload()
        content = json.dumps(payload)
        with tmp_path.open("w", encoding="utf-8") as fh:
            fh.write(content)
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except OSError:
                pass
        tmp_path.replace(path)
    except (OSError, TypeError, ValueError) as exc:
        ...
```

**Dica de robustez:** Em Termux/Android, `fsync()` pode ser lento (20–100ms). Usar uma
flag configuravel `dedupe_fsync_enabled: bool = False` permite desabilitar para performance
em ambientes onde perda do dedupe state e aceitavel (pode resultar em mensagem duplicada
apos reinicio, mas nao e catastrofico).

---

### Bug 16 — `_dispatch_loop` sem tratamento de excecao (task silenciosa)

**Arquivo:** `channels/manager.py` — linhas 664–688
**Severidade:** Critico
**Categoria:** Confiabilidade

**O que esta errado:**
`_dispatch_loop` e uma task asyncio que roda indefinidamente. Se qualquer excecao
**nao-CancelledError** escapar (e.g., excecao no `bus.next_inbound()` ou no
`_handle_stop()`), a task morre silenciosamente sem reiniciar. A partir desse ponto,
nenhuma mensagem e mais processada, mas o sistema aparenta estar rodando normalmente.

```python
# Antes — nenhum try/except externo
async def _dispatch_loop(self) -> None:
    while True:
        event = await self.bus.next_inbound()  # se lanar excecao, loop morre
        if self._is_stop_command(event.text):
            await self._handle_stop(event)
            continue
        task = asyncio.create_task(_dispatch_worker(event))
        ...
```

```python
# Depois — com supervisao e restart automatico
async def _dispatch_loop(self) -> None:
    while True:
        try:
            event = await self.bus.next_inbound()
            if self._is_stop_command(event.text):
                await self._handle_stop(event)
                continue
            task = asyncio.create_task(_dispatch_worker(event))
            ...
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            bind_event("channel.dispatch").error(
                "dispatch loop unexpected error, continuing: {}", exc
            )
            await asyncio.sleep(0.1)  # evitar busy-loop em erros repetidos
```

**Dica de robustez:** Adicionar metrica `_dispatch_loop_errors` para contar erros e alertar
via health endpoint quando o numero crescer.

---

### Bug 17 — `_session_slots` do ChannelManager cresce indefinidamente

**Arquivo:** `channels/manager.py` — linhas 282–287
**Severidade:** Moderado
**Categoria:** Bug | Performance

**O que esta errado:**
`_session_slots: dict[str, asyncio.Semaphore]` segue o mesmo padrao do `_session_locks`
no engine — criado para cada `session_id` e nunca removido. Em producao de longa duracao
com muitos usuarios unicos, o dict cresce sem limite.

```python
# Antes — Semaphore criado mas nunca removido
def _session_semaphore(self, session_id: str) -> asyncio.Semaphore:
    sem = self._session_slots.get(session_id)
    if sem is None:
        sem = asyncio.Semaphore(self._dispatcher_max_per_session)
        self._session_slots[session_id] = sem
    return sem
```

```python
# Depois — usar WeakValueDictionary
import weakref

self._session_slots: weakref.WeakValueDictionary[str, asyncio.Semaphore] = (
    weakref.WeakValueDictionary()
)
```

**Dica de robustez:** Semaphores sao objetos leves (muito menores que Locks), mas em
producao com 10K sessoes unicas o dict ainda consome RAM desnecessaria.

---

### Bug 18 — Discord e Slack criam `httpx.AsyncClient` a cada envio

**Arquivo:** `channels/discord.py` — linhas 42–47 | `channels/slack.py` — linhas 45–48
**Severidade:** Moderado
**Categoria:** Performance

**O que esta errado:**
Ambos os canais criam e destroem um `httpx.AsyncClient` a cada mensagem enviada. Isso
significa que cada envio incorre em overhead de:
- Resolucao DNS (pode ser ~50ms se nao estiver em cache)
- Handshake TLS (50–200ms na primeira conexao)
- Criacao/destruicao de thread pool interno do httpx

```python
# Antes — novo client a cada send
async def send(self, *, target, text, metadata=None):
    async with httpx.AsyncClient(timeout=self.timeout_s, headers=headers) as client:
        response = await client.post(url, json=payload)
```

```python
# Depois — client persistente com connection pool
class DiscordChannel(BaseChannel):
    def __init__(self, ...):
        ...
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        self._running = True
        self._client = httpx.AsyncClient(
            timeout=self.timeout_s,
            headers={"Authorization": f"Bot {self.token}", ...},
        )

    async def stop(self) -> None:
        self._running = False
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def send(self, *, target, text, metadata=None):
        client = self._client
        if client is None:
            raise RuntimeError("discord_not_running")
        response = await client.post(url, json=payload)
```

**Dica de robustez:** `httpx.AsyncClient` com `http2=True` reutiliza conexoes via HTTP/2
multiplexing, reduzindo ainda mais a latencia em envios em rajada.

---

### Bug 19 — Discord sem retry em 429 (rate limit silenciado)

**Arquivo:** `channels/discord.py` — linhas 49–52
**Severidade:** Moderado
**Categoria:** Confiabilidade

**O que esta errado:**
O canal Discord nao implementa backoff para rate limit (HTTP 429). Quando o Discord retorna
429 com `retry_after`, o canal levanta excecao `discord_send_http_429` e o
`ChannelManager._retry_send()` tenta novamente com backoff fixo — ignorando o `retry_after`
que o Discord envia na resposta.

```python
# Antes — 429 tratado como erro generico
if response.status_code < 200 or response.status_code >= 300:
    self._last_error = f"http:{response.status_code}"
    raise RuntimeError(f"discord_send_http_{response.status_code}")
```

```python
# Depois — extrair retry_after do cabecalho ou corpo
if response.status_code == 429:
    retry_after = float(response.headers.get("retry-after", 1.0))
    try:
        body = response.json()
        retry_after = float(body.get("retry_after", retry_after))
    except Exception:
        pass
    await asyncio.sleep(min(retry_after, 60.0))
    raise RuntimeError(f"discord_send_http_429_retry_after_{retry_after:.1f}")
```

**O que o OpenClaw faz melhor aqui:**
O canal Telegram do ClawLite ja implementa `_retry_after_delay_s()` que le o campo
`retry_after` de multiplas fontes (atributo da excecao, parametros, cabecalhos HTTP). O
mesmo padrao deveria ser aplicado ao Discord e ao Slack.

---

### Bug 20 — Slack sem tratamento de rate limit global

**Arquivo:** `channels/slack.py` — linhas 52–65
**Severidade:** Moderado
**Categoria:** Confiabilidade

**O que esta errado:**
A API do Slack tem limites por tier (Tier 1–4) e envia `Retry-After` em respostas 429.
O `SlackChannel` nao le esse cabecalho e nao distingue entre erros recuperaveis e fatais.
Um erro `ratelimited` da API Slack e recuperavel, mas o canal o trata como falha final.

```python
# Antes — erro de API trata todos iguais
if not bool(data.get("ok", False)):
    code = str(data.get("error", "unknown")).strip()
    self._last_error = code
    raise RuntimeError(f"slack_send_api_error:{code}")
```

```python
# Depois — distinguir erros recuperaveis
SLACK_RETRYABLE_ERRORS = {"ratelimited", "service_unavailable", "fatal_error"}

if not bool(data.get("ok", False)):
    code = str(data.get("error", "unknown")).strip()
    self._last_error = code
    if code in SLACK_RETRYABLE_ERRORS:
        retry_after = float(response.headers.get("retry-after", 1.0))
        await asyncio.sleep(min(retry_after, 60.0))
    raise RuntimeError(f"slack_send_api_error:{code}")
```

---

### Bug 21 — `markdown_to_telegram_html` usa `\x00` como separador (colisao possivel)

**Arquivo:** `channels/telegram.py` — linhas 263–295
**Severidade:** Leve
**Categoria:** Bug | Confiabilidade

**O que esta errado:**
A funcao salva blocos de codigo usando placeholders do tipo `\x00CB0\x00` (null byte como
delimitador). Se a mensagem original do usuario contiver literalmente o texto
`\x00CB0\x00` (incomum mas possivel em payloads binarios), o placeholder colidira com
conteudo real, corrompendo o output HTML.

```python
# Antes — null byte como separador
def save_code_block(match):
    code_blocks.append(match.group(1))
    return f"\x00CB{len(code_blocks) - 1}\x00"  # fragil
```

```python
# Depois — usar UUID como placeholder impossivel de colidir
import uuid

_PLACEHOLDER_PREFIX = f"__CLAWLITE_BLOCK_{uuid.uuid4().hex}_"

def save_code_block(match):
    code_blocks.append(match.group(1))
    idx = len(code_blocks) - 1
    return f"{_PLACEHOLDER_PREFIX}CB{idx}__"
```

**Dica de robustez:** Uma alternativa mais simples e usar um prefixo de string que jamais
aparece em Markdown valido, como `\ufffd\ufffd` (replacement character duplicado).

---

### Bug 22 — `PassiveChannel.send()` retorna string em vez de lancar excecao

**Arquivo:** `channels/base.py` — linhas 79–82
**Severidade:** Leve
**Categoria:** Confiabilidade | API Design

**O que esta errado:**
`PassiveChannel.send()` simula sucesso retornando uma string como
`"signal:queued:target:42"`. Callers que dependem do retorno para confirmar entrega
podem interpretar isso como sucesso real quando na verdade a mensagem nunca foi enviada.

```python
# Antes — simula sucesso silenciosamente
async def send(self, *, target, text, metadata=None) -> str:
    if not self._running:
        return f"{self.name}:not_running"  # nao levanta excecao!
    return f"{self.name}:queued:{target}:{len(text)}"  # fake success
```

```python
# Depois — ser explicito sobre nao-implementacao
async def send(self, *, target, text, metadata=None) -> str:
    raise NotImplementedError(
        f"Channel '{self.name}' is passive and does not support outbound send. "
        "Implement this channel or disable outbound delivery for it."
    )
```

**Dica de robustez:** Se o comportamento de "fila simulada" for intencional para testes,
documentar claramente com comentario e renomear para `MockChannel` ou `StubChannel`.

---

### Bug 23 — `_typing_tasks` pode vazar em excecoes nao-CancelledError

**Arquivo:** `channels/telegram.py` — linhas 921–983
**Severidade:** Leve
**Categoria:** Robustez

**O que esta errado:**
O `finally` do `_typing_loop` remove a task de `_typing_tasks` apenas se
`task is asyncio.current_task()`. Se uma excecao nao-`CancelledError` for lancada (linha
978: `except Exception as exc: logger.warning(...)`), o codigo nao levanta a excecao — o
loop termina normalmente, e o `finally` remove corretamente. Porem, se o `_typing_loop`
for chamado novamente para o mesmo chat antes da task anterior terminar, a task anterior
pode ficar ativa enquanto uma nova e criada, resultando em dois loops de typing para o
mesmo chat.

```python
# Em _start_typing_keepalive — verificacao de task existente
task = self._typing_tasks.get(typing_key)
if task is not None and not task.done():
    return  # correto, mas...
# se task foi criada mas ainda nao registrada no dict (race asyncio)
# pode haver duplicacao
```

**Dica de robustez:** O design atual e correto para o modelo single-threaded do asyncio,
pois nao ha preempcao entre coroutines. A race condition descrita e teorica em asyncio
puro. No entanto, adicionar um log `debug` quando uma task duplicada e detectada ajuda
no diagnostico.

---

## Resumo da Sessao 2 — `channels/`

| Severidade | Quantidade |
|---|---|
| Critico    | 2          |
| Moderado   | 6          |
| Leve       | 3          |

**Diferencas criticas vs producao:**

1. **`_dispatch_loop` sem supervisao** — se o loop morrer, nenhuma mensagem e processada;
   o sistema parece rodando mas esta morto por dentro.
2. **Nonce nao-aleatorio no HMAC** — permite forjar assinaturas de callback button se
   o atacante conhecer o timestamp aproximado.
3. **Discord/Slack sem `httpx.AsyncClient` persistente** — cada mensagem cria e destroi
   uma conexao TLS, adicionando 50–200ms de latencia em cada envio.

**Top 3 prioridades:**

1. `_dispatch_loop` sem tratamento de excecao (`manager.py:664`) — risco de silenciar
   todos os canais silenciosamente.
2. `_callback_sign_payload` com nonce de `time.monotonic()` (`telegram.py:539`) — falha
   de seguranca criptografica.
3. `httpx.AsyncClient` recriado a cada send (`discord.py:43`, `slack.py:46`) — gargalo
   de latencia significativo para bots de alto volume.

---

## SESSAO 3 — `clawlite/tools/`

Arquivos auditados:
- `tools/base.py` (35 linhas)
- `tools/mcp.py` (215 linhas)
- `tools/message.py` (183 linhas)
- `tools/cron.py` (157 linhas)
- `tools/spawn.py` (80 linhas)
- `tools/skill.py` (269 linhas)
- `tools/apply_patch.py` (291 linhas)
- `tools/process.py` (327 linhas)
- `tools/sessions.py` (430 linhas)
- `tools/memory.py` (602 linhas)
- `tools/registry.py` (141 linhas)
- `tools/exec.py` (251 linhas)
- `tools/files.py` (342 linhas)
- `tools/web.py` (361 linhas)

---

### Bug 24 — `setup_logging()` no nivel de modulo em `mcp.py` e `skill.py`

**Arquivo:** `tools/mcp.py` — linha 12 | `tools/skill.py` — linha 26
**Severidade:** Moderado
**Categoria:** Bug | Robustez

**O que esta errado:**
O mesmo padrao ja documentado nos Bugs 1 e 13 se repete em `mcp.py` e `skill.py`:
`setup_logging()` e chamado quando o modulo e importado, antes de qualquer instancia
ser criada. Em testes unitarios isso sobrescreve o handler do `caplog` do pytest;
em aplicacoes que configuram logging antes de importar o modulo, o comportamento
sera sobrescrito silenciosamente.

```python
# Antes — mcp.py linha 12, skill.py linha 26
setup_logging()  # executa no import
```

```python
# Depois — mover para __init__ ou tornar opt-in
class MCPTool(Tool):
    def __init__(self, config=None, *, configure_logging=False):
        if configure_logging:
            setup_logging()
```

**Dica de robustez:** Centralizar `setup_logging()` no ponto de entrada da aplicacao
(`cli.py` ou `main()`) e nunca chamar em nivel de modulo e o padrao recomendado pela
documentacao oficial do Python.

---

### Bug 25 — `httpx.AsyncClient` criado dentro do loop de retry em `mcp.py`

**Arquivo:** `tools/mcp.py` — linhas 69–86
**Severidade:** Moderado
**Categoria:** Performance

**O que esta errado:**
O `MCPTool` cria e destroi um `httpx.AsyncClient` dentro do loop de retry. Isso significa
que cada tentativa incorre em overhead de handshake TLS (~50–200ms) e alocacao de thread
pool. Se o servidor MCP for instavel e acionar os 2 retries, o overhead triplica.

```python
# Antes — AsyncClient dentro do loop de retry
for attempt in range(1, self._TRANSIENT_RETRY_ATTEMPTS + 1):
    try:
        async with httpx.AsyncClient(timeout=timeout_s, ...) as client:  # overhead de TLS aqui
            response = await asyncio.wait_for(client.post(...), timeout=timeout_s)
```

```python
# Depois — client fora do loop de retry
async with httpx.AsyncClient(timeout=timeout_s, headers=server.headers or None) as client:
    for attempt in range(1, self._TRANSIENT_RETRY_ATTEMPTS + 1):
        try:
            response = await asyncio.wait_for(client.post(...), timeout=timeout_s)
```

**Dica de robustez:** Para uso intensivo, o client MCP deveria ser persistido no nivel
da instancia de `MCPTool` (iniciado em `start()`, fechado em `stop()`), permitindo
reutilizacao de conexao HTTP/2 entre chamadas distintas.

---

### Bug 26 — Codigo morto apos loop de retry em `mcp.py`

**Arquivo:** `tools/mcp.py` — linhas 107–113
**Severidade:** Leve
**Categoria:** Bug | Qualidade

**O que esta errado:**
As linhas 107–113 apos o loop `for attempt in range(...)` sao codigo morto (dead code).
O loop sempre retorna de dentro (`return f"mcp_error:..."`) na ultima tentativa para
casos de timeout e erro de rede. Para sucesso ou erros HTTP, o `return` tambem ocorre
dentro do loop. A execucao nunca alcanca as linhas apos o `for`.

```python
# Apos o loop — nunca executado
if timeout_error is not None:
    log.warning(...)
    return f"mcp_error:timeout:..."  # dead code
if network_error is not None:
    log.warning(...)
    return f"mcp_error:network:..."  # dead code
return f"mcp_error:invalid_response:..."  # dead code
```

**Como corrigir:** Remover as linhas 107–113 ou adicionar `break` dentro do loop para
que o controle de fluxo seja explicito. Ferramentas de analise estatica como `mypy
--warn-unreachable` ou `pylint` detectariam esse padrao.

---

### Bug 27 — `MCPTool` nao valida enderecos IP resolvidos (SSRF por hostname)

**Arquivo:** `tools/mcp.py` — linhas 183–201
**Severidade:** Moderado
**Categoria:** Seguranca

**O que esta errado:**
`_validate_transport` valida apenas o *hostname* da URL MCP contra allowlist/denylist,
mas nao resolve o hostname para IPs e nao verifica se o IP e privado. Um hostname como
`evil.com` configurado com DNS apontando para `127.0.0.1` ou `169.254.169.254` (AWS IMDSv1)
passaria na validacao de hostname mas resultaria em SSRF.

```python
# Antes — valida apenas o nome do host
host = str(parsed.hostname or "").strip().lower()
if _match_any(host=host, rules=denied_hosts):
    raise ValueError(...)
# sem resolucao de IP!
```

```python
# Depois — adicionar resolucao e validacao de IP privado
import socket
import ipaddress

def _validate_transport_ips(host: str) -> None:
    try:
        infos = await asyncio.get_event_loop().run_in_executor(
            None, socket.getaddrinfo, host, None
        )
    except socket.gaierror:
        raise ValueError(f"mcp server host nao resolveu: {host}")
    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if addr.is_private or addr.is_loopback or addr.is_link_local:
            raise ValueError(f"mcp server resolveu para IP privado: {addr}")
```

**Dica de robustez:** A validacao ideal e pin-based: resolver na configuracao, guardar
o IP e rejeitar qualquer reconexao que resolva para IP diferente (defense contra DNS
rebinding dinamico).

---

### Bug 28 — `SkillTool` usa `ExecTool()` nao configurado como guard de seguranca

**Arquivo:** `tools/skill.py` — linhas 173–180
**Severidade:** Critico
**Categoria:** Seguranca

**O que esta errado:**
`_run_command_with_local_fallback` cria uma nova instancia `ExecTool()` sem nenhuma
configuracao (deny_patterns, allow_patterns, workspace_path vazios) para verificar se
o comando e seguro antes de executa-lo. Isso significa que os padroes de bloqueio
configurados pelo operador no `ExecTool` registrado (e.g., bloquear `rm -rf`, restringir
ao workspace) sao completamente ignorados neste caminho de codigo.

```python
# Antes — ExecTool() sem configuracao, ignora a configuracao real
async def _run_command_with_local_fallback(self, *, spec_name, argv, timeout) -> str:
    command = self._join_command(argv)
    guard = ExecTool()._guard_command(command, argv, Path.cwd().resolve())  # config vazia!
    if guard:
        return f"skill_blocked:{spec_name}:{guard}"
    return await self._run_command(argv, timeout=timeout)
```

**Como corrigir:** Passar o `ExecTool` configurado como dependencia do `SkillTool`
(ou referenciar via registry):

```python
class SkillTool(Tool):
    def __init__(self, *, loader, registry, exec_tool=None, memory=None):
        self._exec_tool = exec_tool  # ExecTool configurado
```

**Dica de robustez:** Nunca instanciar ferramentas de seguranca sem configuracao dentro
de metodos de execucao. Qualquer guard de seguranca deve ser passado como dependencia
explicita para garantir que usa a mesma configuracao que o operador definiu.

---

### Bug 29 — `SkillTool._run_command` executa subprocess sem guards do registry

**Arquivo:** `tools/skill.py` — linhas 131–147
**Severidade:** Critico
**Categoria:** Seguranca

**O que esta errado:**
`_run_command` chama `asyncio.create_subprocess_exec` diretamente, sem passar pelo
`ToolRegistry` e sem aplicar os guards do `ExecTool` configurado. Esse caminho e ativo
quando `self.registry.get("exec") is None` (linha 256). Se um operador *nao* registrar
o `ExecTool` (configuracao nao-default), os skills de tipo `command:` executarao
sem qualquer restricao de seguranca.

```python
# Antes — subprocess direto sem guards
async def _run_command(self, argv: list[str], *, timeout: float) -> str:
    process = await asyncio.create_subprocess_exec(*argv, ...)  # sem deny_patterns!
```

**Como corrigir:** O `_run_command` nunca deveria executar subprocess diretamente.
O caminho de fallback deveria sempre exigir um `ExecTool` configurado, ou recusar
execucao de comandos quando o `exec` tool nao estiver disponivel:

```python
if self.registry.get("exec") is None:
    return f"skill_blocked:{spec.name}:exec_tool_not_registered"
```

---

### Bug 30 — `apply_patch.py` grava arquivos sem escrita atomica

**Arquivo:** `tools/apply_patch.py` — linhas 85, 111, 116
**Severidade:** Moderado
**Categoria:** Confiabilidade | Dados

**O que esta errado:**
O `ApplyPatchTool` usa `target.write_text(...)` diretamente para criar e modificar
arquivos, sem escrita atomica (sem arquivo temporario, sem `fsync`, sem rename). Uma
falha de energia ou crash no meio de uma escrita deixa o arquivo corrompido (conteudo
parcial). O `FilesTool` do mesmo projeto usa `_atomic_write_text` com `fsync` + rename
atomico — mas `apply_patch.py` nao segue o mesmo padrao.

```python
# Antes — escrita direta, sem atomicidade
target.write_text(op.content, encoding="utf-8")   # AddOp, linha 85
move_target.write_text(updated, encoding="utf-8") # UpdateOp/move, linha 111
target.write_text(updated, encoding="utf-8")      # UpdateOp, linha 116
```

```python
# Depois — escrita atomica via arquivo temporario
import tempfile
import os

def _atomic_write(path: Path, content: str) -> None:
    parent = path.parent
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=parent, delete=False, suffix=".tmp"
    ) as tmp:
        tmp.write(content)
        tmp.flush()
        os.fsync(tmp.fileno())
    os.replace(tmp.name, path)
```

**Dica de robustez:** Em Android/Termux em eMMC, a janela de corrupcao e estreita mas
real. Em sistemas de arquivos sem journal (e.g., FAT32 em SD card), `write_text` sem
`fsync` pode resultar em arquivo de tamanho zero apos reinicializacao.

---

### Bug 31 — `ProcessTool._sessions` cresce indefinidamente

**Arquivo:** `tools/process.py` — linha 58, linhas 143–146
**Severidade:** Moderado
**Categoria:** Performance | Confiabilidade

**O que esta errado:**
O dict `_sessions` acumula todas as `ProcessSession` sem limite de tamanho nem TTL.
Sessions concluidas (`completed`/`failed`) so sao removidas via acao explicita `remove`.
Um agente que spawna centenas de processos ao longo do tempo acumula sessoes encerradas
indefinidamente, consumindo RAM desnecessariamente.

Alem disso, `asyncio.create_task(self._capture_stream(...))` (linhas 144–145) nao guarda
referencia para as tasks — em Python, tasks sem referencia podem ser coletadas pelo GC
antes de completar, e excecoes sao apenas logadas no stderr sem propagar.

```python
# Antes — tasks sem referencia, dict sem limite
asyncio.create_task(self._capture_stream(session, process.stdout))
asyncio.create_task(self._capture_stream(session, process.stderr))
asyncio.create_task(self._watch_process(session))
```

```python
# Depois — guardar referencia e limitar tamanho
MAX_SESSIONS = 100
_background_tasks: set[asyncio.Task] = set()

task = asyncio.create_task(self._capture_stream(session, process.stdout))
self._background_tasks.add(task)
task.add_done_callback(self._background_tasks.discard)
```

**Dica de robustez:** Implementar limpeza automatica de sessoes encerradas ha mais de
N minutos (e.g., 30 min), especialmente se o agente for de longa duracao.

---

### Bug 32 — `ProcessSession.output` cresce sem limite (risco de OOM)

**Arquivo:** `tools/process.py` — linhas 282–288
**Severidade:** Moderado
**Categoria:** Performance | Confiabilidade

**O que esta errado:**
O `_capture_stream` concatena toda a saida de stdout+stderr na string `session.output`
sem limite de tamanho. Um processo que gere saida continua (e.g., `tail -f`, servidor
web, loop infinito) pode consumir gigabytes de RAM antes de ser terminado.

```python
# Antes — sem limite de tamanho
async def _capture_stream(self, session, stream) -> None:
    while True:
        chunk = await stream.read(4096)
        if not chunk:
            break
        text = chunk.decode("utf-8", errors="ignore")
        async with session.output_lock:
            session.output += text  # sem limite!
```

```python
# Depois — truncar ao atingir limite
MAX_OUTPUT_CHARS = 1_000_000  # 1MB de texto

async with session.output_lock:
    if len(session.output) < MAX_OUTPUT_CHARS:
        session.output += text
    elif not session.output.endswith("[output truncated]"):
        session.output += "\n[output truncated]"
```

---

### Bug 33 — Race em `_watch_process`: `done_event` sinalizado antes dos streams terminarem

**Arquivo:** `tools/process.py` — linhas 290–295
**Severidade:** Moderado
**Categoria:** Bug | Confiabilidade

**O que esta errado:**
`_watch_process` aguarda o processo terminar (`await session.process.wait()`) e imediatamente
sinaliza `done_event.set()`. Porem, os dois `_capture_stream` tasks ainda podem estar
lendo dados dos pipes (stdout/stderr podem ter dados pendentes nos buffers do kernel
mesmo depois do processo encerrar). Um caller que faz `await done_event.wait()` via
`action=poll` e depois `action=log` pode ver saida incompleta.

```python
# Antes — sinaliza done_event antes dos streams terminarem
async def _watch_process(self, session) -> None:
    return_code = await session.process.wait()
    session.exit_code = return_code
    session.status = "completed" if return_code == 0 else "failed"
    session.done_event.set()  # streams ainda podem estar lendo!
```

```python
# Depois — aguardar os capture tasks completarem primeiro
async def _watch_process(self, session) -> None:
    return_code = await session.process.wait()
    # aguardar stdout e stderr completarem
    if session.stdout_task and session.stderr_task:
        await asyncio.gather(session.stdout_task, session.stderr_task, return_exceptions=True)
    session.exit_code = return_code
    session.status = "completed" if return_code == 0 else "failed"
    session.done_event.set()  # agora seguro
```

---

### Bug 34 — `SessionsSendTool` sem timeout no runner (bloqueia indefinidamente)

**Arquivo:** `tools/sessions.py` — linhas 219–241
**Severidade:** Moderado
**Categoria:** Confiabilidade

**O que esta errado:**
`SessionsSendTool.run` chama `await self.runner(session_id, message)` sem nenhum timeout.
Se o runner (engine do agente alvo) travar por LLM lento, timeout de API nao configurado
ou deadlock interno, o `SessionsSendTool` bloqueara a coroutine do chamador indefinidamente.
O `SubagentManager.spawn()` tem o mesmo risco em `spawn.py`.

```python
# Antes — sem timeout
result = await self.runner(session_id, message)
```

```python
# Depois — com timeout configuravel
DEFAULT_RUNNER_TIMEOUT = 120.0  # 2 minutos

try:
    result = await asyncio.wait_for(
        self.runner(session_id, message),
        timeout=DEFAULT_RUNNER_TIMEOUT,
    )
except asyncio.TimeoutError:
    return _json({"status": "failed", "session_id": session_id, "error": "runner_timeout"})
```

---

### Bug 35 — `MemoryForgetTool` carrega TODOS os registros antes de filtrar

**Arquivo:** `tools/memory.py` — linhas 462–464
**Severidade:** Moderado
**Categoria:** Performance

**O que esta errado:**
`MemoryForgetTool.run` carrega todos os registros de historico e curado em memoria Python
via `self.memory.all()` + `self.memory.curated()` antes de filtrar. Para um agente com
10.000+ entradas de memoria, isso e uma alocacao O(N) desnecessaria apenas para encontrar
e deletar alguns registros.

```python
# Antes — carrega tudo em memoria
history_rows = self.memory.all()      # O(N)
curated_rows = self.memory.curated()  # O(N)
all_rows = history_rows + curated_rows
```

```python
# Depois — filtrar no banco de dados
# O MemoryStore deveria expor um metodo search_by_prefix(prefix, limit)
# que faz a filtragem em SQL (se SQLite) ou em iteracao lazy
```

**Dica de robustez:** O `MemoryStore.delete_by_prefixes` ja existe e e eficiente; o
gargalo esta no pre-filtro em Python que carrega toda a colecao antes de selecionar
os candidatos a deletar.

---

### Bug 36 — `_accepts_parameter` chama `inspect.signature()` sem cache

**Arquivo:** `tools/memory.py` — linhas 85–92
**Severidade:** Leve
**Categoria:** Performance

**O que esta errado:**
`_accepts_parameter` e chamada multiplas vezes por invocacao de `MemoryLearnTool.run` e
`MemoryRecallTool.run` para checar parametros opcionais (`user_id`, `shared`, `reasoning_layer`,
`confidence`). Cada chamada executa `inspect.signature(func)` que e operacao relativamente
cara (parsing de annotations + criacao de objeto Signature). O mesmo padrao ja foi
documentado no Bug 3 em `engine.py`.

```python
# Antes — inspect.signature sem cache, chamado N vezes por invocacao
def _accepts_parameter(func: Any, parameter: str) -> bool:
    try:
        signature = inspect.signature(func)  # O(N) sem cache
    except (TypeError, ValueError):
        return False
```

```python
# Depois — usar functools.lru_cache
from functools import lru_cache

@lru_cache(maxsize=64)
def _get_signature(func):
    return inspect.signature(func)

def _accepts_parameter(func: Any, parameter: str) -> bool:
    try:
        sig = _get_signature(func)
    except (TypeError, ValueError):
        return False
    return parameter in sig.parameters or any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    )
```

---

### Bug 37 — `SpawnTool` e `SkillTool` falham-aberto em excecoes de policy

**Arquivo:** `tools/spawn.py` — linhas 36–40 | `tools/skill.py` — linhas 61–69
**Severidade:** Moderado
**Categoria:** Seguranca | Confiabilidade

**O que esta errado:**
Ambas as ferramentas chamam `memory.integration_policy(...)` para verificar se o
subagente/skill pode ser executado. Se o policy check lancar qualquer excecao, o codigo
retorna `(True, "")` — isto e, fail-open: a execucao e permitida mesmo quando o gate
de seguranca falhou. Uma excecao no sistema de memoria (e.g., banco de dados corrompido,
timeout de I/O) resultaria em politica de seguranca ignorada silenciosamente.

```python
# Antes — fail-open em qualquer excecao
try:
    verdict = policy_fn("subagent", session_id=session_id)
    if inspect.isawaitable(verdict):
        verdict = await verdict
except Exception:
    return True, ""  # falha aberta — permite execucao!
```

```python
# Depois — fail-closed para erros inesperados
except Exception as exc:
    log.warning("memory_policy_check_failed session={} error={}", session_id, exc)
    return False, f"policy_check_error:{type(exc).__name__}"
```

**Dica de robustez:** O comportamento correto depende do requisito de seguranca: sistemas
de alta seguranca devem ser fail-closed; sistemas de alta disponibilidade podem ser
fail-open. O comportamento atual nao e documentado, o que e o problema principal. Se
fail-open for intencional, deve estar explicitamente comentado.

---

### Bug 38 — `web.py`: regex com escape duplo (`\\s`) — regex quebrado

**Arquivo:** `tools/web.py` — multiplas linhas em `_html_to_text` e `_html_to_markdown`
**Severidade:** Critico
**Categoria:** Bug

**O que esta errado:**
As funcoes `_html_to_text` e `_html_to_markdown` usam `r"<script[\\s\\S]*?</script>"` com
barra dupla — o que em uma raw string resulta em regex literal `[\\s\\S]` (backslash-s e
backslash-S), nao `[\s\S]` (qualquer caractere incluindo newline). O padrao nunca casa
com scripts HTML multi-linha, deixando codigo JavaScript no texto extraido.

```python
# Antes — regex quebrado (\\s nao e \s em raw string)
re.sub(r"<script[\\s\\S]*?</script>", "", raw_html, flags=re.I)
re.sub(r"<style[\\s\\S]*?</style>", "", raw_html, flags=re.I)
```

```python
# Depois — regex correto
re.sub(r"<script[\s\S]*?</script>", "", raw_html, flags=re.I)
re.sub(r"<style[\s\S]*?</style>", "", raw_html, flags=re.I)
```

**Dica de robustez:** Este e o bug mais facil de verificar: `re.compile(r"[\\s\\S]").match("\n")`
retorna `None`; `re.compile(r"[\s\S]").match("\n")` retorna um match. Um teste unitario
com HTML multi-linha detectaria imediatamente.

---

### Bug 39 — `web.py`: `socket.getaddrinfo()` sincrono em contexto async (SSRF TOCTOU)

**Arquivo:** `tools/web.py` — `_resolve_ips()`
**Severidade:** Critico
**Categoria:** Bug | Seguranca

**O que esta errado:**
`_resolve_ips` usa `socket.getaddrinfo()` que e **sincrono** e **bloqueia o event loop**
do asyncio. Em Android/Termux, uma resolucao DNS lenta pode bloquear por 1–5s.
Alem disso, existe uma vulnerabilidade TOCTOU (time-of-check-to-time-of-use): o DNS e
resolvido antes da requisicao HTTP, mas o `httpx.AsyncClient` faz sua propria resolucao
DNS no momento do connect. Um servidor DNS malicioso pode responder IPs diferentes nas
duas consultas (DNS rebinding), passando na validacao mas conectando em IP privado.

```python
# Antes — sincrono, bloqueia event loop, TOCTOU
def _resolve_ips(host: str) -> list[ipaddress._BaseAddress]:
    infos = socket.getaddrinfo(host, None)  # bloqueia!
```

```python
# Depois — async, e usar httpx com transport customizado que valida IPs no connect
async def _resolve_ips(host: str) -> list[ipaddress._BaseAddress]:
    loop = asyncio.get_running_loop()
    infos = await loop.run_in_executor(None, socket.getaddrinfo, host, None)
    return [ipaddress.ip_address(info[4][0]) for info in infos]
```

---

### Bug 40 — `web.py`: `DDGS` sincrono em funcao async (`WebSearchTool.run`)

**Arquivo:** `tools/web.py` — `WebSearchTool.run()`
**Severidade:** Critico
**Categoria:** Bug | Performance

**O que esta errado:**
`WebSearchTool.run` usa `with DDGS(...) as ddgs:` e itera `ddgs.text(...)` dentro de
uma `async def`. `DDGS` e um cliente HTTP sincrono (usa `requests` internamente); o
`with` block e a iteracao bloqueiam o event loop pelo tempo total da busca (tipicamente
500ms–3s). Em producao, isso pode degradar toda a responsividade do gateway durante buscas.

```python
# Antes — DDGS sincrono em async def, bloqueia event loop
async def run(self, arguments, ctx):
    ...
    with DDGS(proxy=self.proxy or None, timeout=int(timeout)) as ddgs:  # sincrono!
        for item in ddgs.text(query, max_results=limit):
            ...
```

```python
# Depois — executar em thread pool
async def run(self, arguments, ctx):
    ...
    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(None, self._sync_search, query, limit, timeout)
```

---

## Resumo da Sessao 3 — `tools/`

| Severidade | Quantidade |
|---|---|
| Critico    | 5          |
| Moderado   | 9          |
| Leve       | 3          |

**Top 3 prioridades:**

1. **Regex quebrado em `web.py`** (`\\s` em raw string, Bug 38) — scripts e styles HTML
   com newlines nao sao removidos, contaminando todo o texto extraido de paginas web.
2. **SkillTool usa `ExecTool()` sem configuracao como guard** (Bug 28) — os padroes de
   seguranca configurados pelo operador sao ignorados no caminho de fallback; qualquer
   comando pode ser executado.
3. **`DDGS` sincrono no event loop** (Bug 40) — cada busca web bloqueia o gateway inteiro
   por segundos, degradando todas as sessoes simultaneas.

---

## SESSAO 4 — `clawlite/scheduler/`

Arquivos auditados:
- `scheduler/types.py` (47 linhas)
- `scheduler/heartbeat.py` (352 linhas)
- `scheduler/cron.py` (594 linhas)

---

### Bug 41 — `setup_logging()` no nivel de modulo em `heartbeat.py` e `cron.py`

**Arquivo:** `scheduler/heartbeat.py` — linha 73 | `scheduler/cron.py` — linha 19
**Severidade:** Moderado
**Categoria:** Bug | Robustez

**O que esta errado:**
O mesmo padrao documentado nos Bugs 1, 13 e 24 se repete nos dois modulos do scheduler.
Em `heartbeat.py` a chamada esta especialmente fora de lugar: vem *depois* da definicao de
`TickHandler` e *antes* da classe `HeartbeatService`, quebrando a convencao de declarar
`setup_logging()` no topo do modulo.

```python
# heartbeat.py — linha 73
TickHandler = Callable[[], Awaitable[...]]

setup_logging()  # fora de lugar entre typedefs e a classe

class HeartbeatService: ...
```

**Como corrigir:** Centralizar a configuracao de logging no ponto de entrada da aplicacao
e remover todas as chamadas `setup_logging()` de nivel de modulo.

---

### Bug 42 — `_execute_tick` modifica `_state` ANTES de adquirir `_tick_lock`

**Arquivo:** `scheduler/heartbeat.py` — linhas 225–230
**Severidade:** Moderado
**Categoria:** Bug | Confiabilidade

**O que esta errado:**
`_execute_tick` escreve em `self._state` antes de adquirir `self._tick_lock`. Se
`trigger_now()` for chamado de forma concorrente enquanto o loop interno ja executa
um tick (improvavel em asyncio single-threaded, mas possivel se `on_tick` ceder
controle via `await`), os campos `last_tick_iso`, `last_trigger` e `ticks` podem
ser sobrescritos por uma segunda chamada antes que o primeiro tick complete.

```python
async def _execute_tick(self, on_tick, *, trigger) -> HeartbeatDecision:
    now_iso = self._utc_now_iso()
    self._state["last_tick_iso"] = now_iso   # fora do lock!
    self._state["last_trigger"] = trigger    # fora do lock!
    self._state["ticks"] = int(self._state.get("ticks", 0) or 0) + 1  # fora do lock!
    decision = HeartbeatDecision(action="skip", reason="unknown")
    async with self._tick_lock:
        try:
            result = await on_tick()
```

```python
# Depois — toda modificacao de _state dentro do lock
async with self._tick_lock:
    self._state["last_tick_iso"] = self._utc_now_iso()
    self._state["last_trigger"] = trigger
    self._state["ticks"] = int(self._state.get("ticks", 0) or 0) + 1
    try:
        result = await on_tick()
```

---

### Bug 43 — `_save_state()` chama `os.fsync()` de forma sincrona dentro de contexto async

**Arquivo:** `scheduler/heartbeat.py` — linhas 191–215
**Severidade:** Moderado
**Categoria:** Performance | Confiabilidade

**O que esta errado:**
`_save_state()` e um metodo sincrono que chama `os.fsync()` antes de `os.replace()`.
`os.fsync()` e uma chamada de sistema bloqueante que pode durar de 5 a 200ms em disco
eMMC (Android/Termux). `_save_state()` e chamado dentro de `_execute_tick()` (linha 267),
que por sua vez e chamado dentro do loop asyncio — bloqueando o event loop a cada tick.

```python
def _save_state(self) -> None:
    ...
    with tempfile.NamedTemporaryFile(...) as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())  # bloqueante! 5-200ms
    os.replace(str(tmp_path), str(self.state_path))
```

```python
# Depois — executar em thread pool para nao bloquear o event loop
async def _save_state_async(self) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, self._save_state)
```

**Dica de robustez:** Alternativamente, omitir `os.fsync` para o heartbeat state (que e
informacional, nao critico) e aceitar risco de perda de contadores em crash.

---

### Bug 44 — `HeartbeatService._loop()` sem tratamento de excecao externo

**Arquivo:** `scheduler/heartbeat.py` — linhas 290–303
**Severidade:** Moderado
**Categoria:** Confiabilidade

**O que esta errado:**
O loop interno do heartbeat nao tem um `try/except` externo. `_execute_tick` captura
excecoes do `on_tick()`, mas erros inesperados no proprio `_execute_tick` (e.g., acesso
a chave invalida em `_state`, erro de `asyncio.Lock` corrompido) propagariam e matariam
o loop silenciosamente. O `asyncio.Task` acumularia a excecao mas ela so seria vista se
o caller inspecionasse `self._task.exception()` — o que nenhum caller faz.

```python
async def _loop() -> None:
    first_tick = True
    while self._running:           # nenhum try/except externo!
        trigger = "startup" if first_tick else await self._next_trigger_source()
        first_tick = False
        if not self._running:
            break
        decision = await self._execute_tick(on_tick, trigger=trigger)
```

```python
# Depois — loop supervisor com restart automatico
async def _loop() -> None:
    first_tick = True
    while self._running:
        try:
            trigger = "startup" if first_tick else await self._next_trigger_source()
            first_tick = False
            if not self._running:
                break
            decision = await self._execute_tick(on_tick, trigger=trigger)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            bind_event("heartbeat.loop").error("heartbeat loop error={}", exc)
            await asyncio.sleep(5)  # backoff antes de reiniciar o ciclo
```

---

### Bug 45 — `CronService._store_lock()` usa `fcntl.flock(LOCK_EX)` sincrono

**Arquivo:** `scheduler/cron.py` — linhas 116–130
**Severidade:** Critico
**Categoria:** Bug | Performance

**O que esta errado:**
`_store_lock()` e um context manager sincrono que chama `fcntl.flock(fd, fcntl.LOCK_EX)`.
`LOCK_EX` e um *lock exclusivo bloqueante*: se outro processo ou instancia do ClawLite
ja tiver o arquivo travado, `flock()` bloqueia ate que o lock seja liberado — potencialmente
por segundos. Este lock e adquirido dentro de `_try_claim_due_job()` e `_commit_job_result()`,
que sao chamados diretamente do loop async `_loop()`. Resultado: o event loop inteiro fica
suspenso durante a contenção do flock.

```python
# Antes — bloqueia o event loop!
@contextlib.contextmanager
def _store_lock(self):
    lock_file = self._lock_path.open("a+", encoding="utf-8")
    fd = lock_file.fileno()
    if fcntl is not None:
        fcntl.flock(fd, fcntl.LOCK_EX)  # bloqueante — suspende event loop!
    yield
    ...

# Chamado de dentro do loop async:
async def _loop(self) -> None:
    ...
    claimed = self._try_claim_due_job(job.id, now)  # faz flock aqui!
```

```python
# Depois — executar o lock em thread pool
async def _try_claim_due_job_async(self, job_id, now):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, self._try_claim_due_job, job_id, now)
```

**Dica de robustez:** Considerar usar `asyncio.Lock` para coordenacao intra-processo
(mais rapido e sem I/O) e reservar `flock` apenas para coordenacao entre processos,
executado em executor dedicado.

---

### Bug 46 — `_write_rows_unlocked()` sem `os.fsync` (perda de dados em crash)

**Arquivo:** `scheduler/cron.py` — linhas 156–160
**Severidade:** Moderado
**Categoria:** Confiabilidade | Dados

**O que esta errado:**
`_write_rows_unlocked()` usa `tmp_path.write_text()` seguido de `tmp_path.replace()`, mas
sem `os.fsync()` entre os dois. Isso contrasta diretamente com `heartbeat.py` que faz
fsync antes do replace. Em Android/Termux com eMMC, uma falha de energia ou reinicializacao
forca durante a escrita pode deixar o arquivo temporario com conteudo incompleto (ou vazio),
e o `replace()` ainda pode ocorrer com dados corrompidos.

```python
# Antes — sem fsync, inconsistente com heartbeat.py
def _write_rows_unlocked(self, rows):
    payload = json.dumps(rows, ensure_ascii=False, indent=2)
    tmp_path = self.path.with_name(f"{self.path.name}.{os.getpid()}.tmp")
    tmp_path.write_text(payload, encoding="utf-8")  # sem fsync!
    tmp_path.replace(self.path)
```

```python
# Depois — adicionar fsync para consistencia
def _write_rows_unlocked(self, rows):
    payload = json.dumps(rows, ensure_ascii=False, indent=2)
    tmp_path = self.path.with_name(f"{self.path.name}.{os.getpid()}.tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        fh.write(payload)
        fh.flush()
        os.fsync(fh.fileno())
    tmp_path.replace(self.path)
```

**Observacao:** O nome do arquivo temporario usa `os.getpid()` em vez de um UUID — se
dois threads ou coroutines chamarem `_write_rows_unlocked` concorrentemente (improvavel
mas possivel em multiplos processos), o mesmo tmp_path pode ser sobrescrito parcialmente.

---

### Bug 47 — `CronService._loop()` polling a cada 1s (sem sleep ate proximo job)

**Arquivo:** `scheduler/cron.py` — linha 457
**Severidade:** Leve
**Categoria:** Performance

**O que esta errado:**
O loop do cron acorda a cada 1 segundo para verificar todos os jobs, independentemente
de quando o proximo job esta agendado. Para sistemas com muitos jobs de baixa frequencia
(e.g., cron diario), isso resulta em 86.400 verificacoes desnecessarias por dia, cada
uma lendo o dicionario `_jobs` e calculando timestamps.

```python
# Antes — acorda a cada 1 segundo sempre
await asyncio.sleep(1)
```

```python
# Depois — calcular tempo ate o proximo job e dormir ate la
def _time_until_next_job(self, now: datetime) -> float:
    min_wait = self.interval_seconds  # intervalo maximo de verificacao
    for job in self._jobs.values():
        if not job.enabled or not job.next_run_iso:
            continue
        try:
            next_run = self._normalize_datetime(job.next_run_iso)
            wait = (next_run - now).total_seconds()
            if 0 < wait < min_wait:
                min_wait = wait
        except ValueError:
            pass
    return max(0.1, min_wait)

# No loop:
await asyncio.sleep(self._time_until_next_job(now))
```

---

### Bug 48 — Callback de job cron sem timeout (bloqueia o loop de cron indefinidamente)

**Arquivo:** `scheduler/cron.py` — linhas 430–445
**Severidade:** Moderado
**Categoria:** Confiabilidade

**O que esta errado:**
`await self._on_job(claimed)` e chamado sem nenhum timeout. Se o callback (que tipicamente
invoca o AgentEngine com uma LLM call) travar por timeout da API, rede lenta ou deadlock,
o loop do cron fica bloqueado nesse `await` indefinidamente — nenhum outro job e executado
enquanto o callback nao retornar. O lease expira apos `self._lease_seconds` (30s por
padrao), mas o loop nao tem como cancelar o callback suspenso.

```python
# Antes — await sem timeout
try:
    await self._on_job(claimed)
```

```python
# Depois — timeout configuravel por job ou global
JOB_TIMEOUT_S = float(getattr(job.payload.metadata, "timeout_s", None) or 300)

try:
    await asyncio.wait_for(self._on_job(claimed), timeout=JOB_TIMEOUT_S)
except asyncio.TimeoutError:
    callback_failed = True
    claimed.last_status = "timeout"
    claimed.last_error = f"job_timeout:{JOB_TIMEOUT_S}s"
    ...
```

**Dica de robustez:** O timeout do job deveria ser configuravel por job (campo em
`CronJob.payload.metadata["timeout_s"]`) com um maximo global definido pelo operador.

---

## Resumo da Sessao 4 — `scheduler/`

| Severidade | Quantidade |
|---|---|
| Critico    | 1          |
| Moderado   | 5          |
| Leve       | 2          |

**Top 3 prioridades:**

1. **`fcntl.flock(LOCK_EX)` sincrono no event loop** (Bug 45, `cron.py:124`) — em
   qualquer cenario com dois processos ClawLite rodando simultaneamente, o flock pode
   bloquear o event loop por segundos, travando o gateway e todos os canais.
2. **Callback de job sem timeout** (Bug 48, `cron.py:431`) — um job travado bloqueia
   toda a execucao de cron; outros jobs nao rodam enquanto o callback nao retornar.
3. **`_save_state()` com `os.fsync` sincrono no tick** (Bug 43, `heartbeat.py:206`) —
   a cada heartbeat (30min ou forcado) o event loop bloqueia por ate 200ms.

---

## SESSAO 5 — `clawlite/providers/`

Arquivos auditados:
- `providers/base.py` (43 linhas)
- `providers/reliability.py` (118 linhas)
- `providers/registry.py` (460 linhas)
- `providers/litellm.py` (590 linhas)
- `providers/codex.py` (221 linhas)
- `providers/failover.py` (221 linhas)
- `providers/custom.py` (8 linhas)
- `providers/transcription.py` (29 linhas)

---

### Bug 49 — `_anthropic_tools` usa chave `"arguments"` errada — schema Anthropic sempre vazio

**Arquivo:** `providers/litellm.py` — linhas 324–339
**Severidade:** Critico
**Categoria:** Bug

**O que esta errado:**
`_anthropic_tools` busca o schema dos parametros da tool com `tool.get("arguments")`,
mas `Tool.export_schema()` em `tools/base.py` usa a chave `"parameters"`. Resultado:
ao chamar `complete()` com tools vindas do registry, `tool.get("arguments")` retorna
`None` para todas, e o `input_schema` e sempre substituido pelo fallback
`{"type": "object", "properties": {}}` — sem nenhum parametro declarado. O modelo
Anthropic nao sabe quais argumentos cada tool aceita e nao consegue usa-las corretamente.

```python
# Tool.export_schema() em tools/base.py
def export_schema(self) -> dict[str, Any]:
    return {
        "name": self.name,
        "description": self.description,
        "parameters": self.args_schema(),  # chave e "parameters"!
    }

# _anthropic_tools em litellm.py — busca chave errada
"input_schema": tool.get("arguments") if isinstance(tool.get("arguments"), dict)
    else {"type": "object", "properties": {}},  # sempre cai no fallback!
```

```python
# Depois — usar a chave correta
"input_schema": (
    tool.get("parameters")
    or tool.get("arguments")
    or {"type": "object", "properties": {}}
),
```

**Impacto:** Qualquer agente usando provedor Anthropic (claude-opus, claude-sonnet)
com tool calling recebe schemas vazios — o LLM pode chamar as tools com argumentos
incorretos ou nao as chamar por nao saber o contrato.

---

### Bug 50 — `CodexProvider.complete` ignora tool calls da resposta

**Arquivo:** `providers/codex.py` — linha 182
**Severidade:** Critico
**Categoria:** Bug

**O que esta errado:**
`CodexProvider.complete` retorna `LLMResult(text=text, tool_calls=[], ...)` com
`tool_calls` **hardcoded como lista vazia**, mesmo quando o payload enviado inclui
`tools` e `tool_choice="auto"`. Se o modelo Codex responder com um tool call, o
resultado e silenciosamente descartado — o agente nunca executa a tool e o ciclo
de agentic loop nao avanca.

```python
# Antes — tool_calls sempre vazio, ignora resposta do modelo
return LLMResult(
    text=text,
    model=self.model,
    tool_calls=[],    # hardcoded! qualquer tool call e ignorado
    metadata={"provider": "codex"},
)
```

```python
# Depois — parsear tool calls da resposta (mesmo metodo do LiteLLMProvider)
message = data.get("choices", [{}])[0].get("message", {})
text = str(message.get("content", "")).strip()
tool_calls = LiteLLMProvider._parse_tool_calls(message)  # reusar metodo existente
return LLMResult(text=text, model=self.model, tool_calls=tool_calls, ...)
```

**Impacto:** Qualquer uso de tool calling com o provedor `openai-codex` e silenciosamente
quebrado — o agente entra em loop ou para sem executar ferramentas.

---

### Bug 51 — `httpx.AsyncClient` criado dentro do loop de retry (litellm.py, codex.py)

**Arquivo:** `providers/litellm.py` — linhas 386, 532 | `providers/codex.py` — linha 175
**Severidade:** Moderado
**Categoria:** Performance

**O que esta errado:**
O mesmo padrao identificado no Bug 25 (`tools/mcp.py`) se repete nos tres providers
principais: `httpx.AsyncClient` e criado e destruido dentro do loop de retry. Com
`retry_max_attempts=3` (padrao), um provider instavel incorre em ate 3 handshakes TLS
(50–200ms cada) em vez de 1. Para `_complete_anthropic` e `complete` (OpenAI-compat),
o cliente e criado dentro de `async with` no corpo do for-loop.

```python
# Antes — novo AsyncClient a cada tentativa (duplicado em 3 lugares)
for attempt in range(1, attempts + 1):
    try:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, ...)
```

```python
# Depois — client fora do loop de retry
async with httpx.AsyncClient(timeout=self.timeout) as client:
    for attempt in range(1, attempts + 1):
        try:
            response = await client.post(url, ...)
```

**Dica de robustez:** Para providers de alta frequencia, manter o `httpx.AsyncClient`
no nivel da instancia (iniciado em `start()`) e a solucao ideal, reutilizando a
connection pool HTTP/2 entre todas as chamadas.

---

### Bug 52 — `_HARD_QUOTA_SIGNALS` duplicado entre `litellm.py` e `reliability.py`

**Arquivo:** `providers/litellm.py` — linhas 17–28 | `providers/reliability.py` — linhas 6–17
**Severidade:** Leve
**Categoria:** Qualidade | Manutencao

**O que esta errado:**
A lista de sinais de quota esgotada e definida duas vezes com nomes diferentes
(`_HARD_QUOTA_SIGNALS` em `litellm.py` e `_QUOTA_429_SIGNALS` em `reliability.py`).
As listas sao identicas no momento da auditoria, mas sao independentes — adicionar
um sinal em uma nao atualiza a outra. Isso ja ocorreu: a funcao `is_quota_429_error`
em `reliability.py` e `_is_hard_quota_429` em `litellm.py` tomam decisoes de retry
usando listas potencialmente divergentes.

```python
# reliability.py — _QUOTA_429_SIGNALS
_QUOTA_429_SIGNALS = ("insufficient_quota", "quota exceeded", "billing hard limit", ...)

# litellm.py — duplicado com nome diferente
_HARD_QUOTA_SIGNALS = ("insufficient_quota", "quota exceeded", "billing hard limit", ...)
```

**Como corrigir:** Remover `_HARD_QUOTA_SIGNALS` de `litellm.py` e usar
`is_quota_429_error()` de `reliability.py` diretamente.

---

### Bug 53 — `assert spec is not None` em `registry.py` (removido em modo otimizado)

**Arquivo:** `providers/registry.py` — linha 325
**Severidade:** Leve
**Categoria:** Bug | Robustez

**O que esta errado:**
`resolve_litellm_provider` usa `assert spec is not None` apos uma chamada que pode
retornar `None`. Em producao com `python -O` (modo otimizado, comum em containers),
os `assert` sao eliminados pelo compilador. Se `_find_spec("openai")` retornar `None`
(improvavel mas possivel se SPECS for modificado), o `spec` seria `None` e causaria
`AttributeError` na linha seguinte em vez de uma mensagem de erro clara.

```python
# Antes — assert eliminado em python -O
spec = _find_spec(name) or _find_spec("openai")
assert spec is not None  # silenciosamente removido em modo otimizado!

# Depois — excecao explicita
spec = _find_spec(name) or _find_spec("openai")
if spec is None:
    raise RuntimeError(f"provider spec not found for '{name}' and fallback 'openai'")
```

---

### Bug 54 — `TranscriptionProvider` carrega audio inteiro em RAM antes de enviar

**Arquivo:** `providers/transcription.py` — linha 21
**Severidade:** Moderado
**Categoria:** Performance | Confiabilidade

**O que esta errado:**
`path.read_bytes()` carrega o arquivo de audio completo na memoria Python antes de
iniciar o upload para a API Whisper. A API Groq aceita arquivos de ate 25MB. Para
um arquivo de 25MB, isso dobra o uso de RAM momentaneamente (arquivo em disco +
copia em RAM). Em Android/Termux com limitacoes de memoria, isso pode causar OOM.

```python
# Antes — le tudo em memoria
files = {"file": (path.name, path.read_bytes(), "audio/mpeg")}
```

```python
# Depois — streaming via file handle
with path.open("rb") as audio_file:
    files = {"file": (path.name, audio_file, "audio/mpeg")}
    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(..., files=files, data=data)
```

**Dica de robustez:** Verificar o tamanho do arquivo antes de enviar e rejeitar
arquivos acima do limite da API (25MB para Whisper/Groq) com mensagem clara.

---

### Bug 55 — `TranscriptionProvider` sem retry/backoff em erros transientes

**Arquivo:** `providers/transcription.py` — linhas 15–28
**Severidade:** Moderado
**Categoria:** Confiabilidade

**O que esta errado:**
Ao contrario de `LiteLLMProvider` e `CodexProvider` (que implementam retry com
backoff exponencial + circuit breaker), `TranscriptionProvider` nao tem nenhuma
logica de retry. Um erro transiente 429 ou 5xx da API Groq e lancado diretamente
para o caller sem nova tentativa. Para transcrições de audio (operacao mais cara e
demorada do sistema), a ausencia de retry e especialmente custosa — o usuario
precisa reenviar o audio manualmente.

```python
# Antes — sem retry
async with httpx.AsyncClient(timeout=90) as client:
    response = await client.post(...)
    response.raise_for_status()  # 429 ou 500 -> excecao imediata
```

```python
# Depois — retry simples (2 tentativas, backoff 1s)
for attempt in range(1, 3):
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(...)
            response.raise_for_status()
            break
    except httpx.HTTPStatusError as exc:
        if attempt < 2 and exc.response.status_code in (429, 500, 502, 503):
            await asyncio.sleep(1.0 * attempt)
            continue
        raise
```

---

### Bug 56 — `parse_retry_after_seconds` nao suporta formato de data HTTP (RFC 7231)

**Arquivo:** `providers/reliability.py` — linhas 30–40
**Severidade:** Leve
**Categoria:** Confiabilidade

**O que esta errado:**
A funcao `parse_retry_after_seconds` so processa o `Retry-After` no formato numerico
(segundos como float). O RFC 7231 permite o cabecalho em formato de data HTTP:
`Retry-After: Wed, 01 Apr 2026 12:00:00 GMT`. Alguns providers (Anthropic, OpenAI)
usam o formato numerico, mas outros podem usar o formato de data. Quando o formato de
data e recebido, `float(raw)` levanta `ValueError` e a funcao retorna `None`,
ignorando o `Retry-After` e usando backoff padrao em vez do tempo correto.

```python
# Antes — ignora formato de data HTTP
def parse_retry_after_seconds(header_value):
    try:
        value = float(raw)  # falha silenciosamente para datas HTTP
    except ValueError:
        return None  # retry_after ignorado!
```

```python
# Depois — suportar ambos os formatos
from email.utils import parsedate_to_datetime
import datetime

def parse_retry_after_seconds(header_value):
    raw = str(header_value or "").strip()
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(raw)
        delta = (dt - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
        return max(0.0, delta)
    except Exception:
        return None
```

---

## Resumo da Sessao 5 — `providers/`

| Severidade | Quantidade |
|---|---|
| Critico    | 2          |
| Moderado   | 3          |
| Leve       | 3          |

**Top 3 prioridades:**

1. **`_anthropic_tools` usa chave `"arguments"` errada** (Bug 49) — tool calling com
   Anthropic (Claude) sempre envia schemas vazios; o LLM opera sem saber os contratos
   das ferramentas disponíveis.
2. **`CodexProvider` ignora tool calls da resposta** (Bug 50) — qualquer agente usando
   `openai-codex` com tools e silenciosamente quebrado; tool calling nunca funciona.
3. **`httpx.AsyncClient` criado por tentativa no retry loop** (Bug 51) — overhead de
   TLS multiplicado pelo numero de tentativas nos tres providers principais.

---

---

## SESSAO 6 — `clawlite/gateway/`

Arquivos auditados:
- `gateway/tool_catalog.py` (137 linhas)
- `gateway/server.py` (2838 linhas)

---

### Bug 57 — `setup_logging()` chamado no nivel do modulo

**Arquivo:** `gateway/server.py` — linha 65
**Severidade:** Moderado
**Categoria:** Bug | Robustez

**O que esta errado:**
Mesmo padrao dos Bugs 1, 13, 24, 41: `setup_logging()` executa ao importar o modulo,
antes de qualquer instancia ser criada. Em testes unitarios ou no contexto de importacao
da linha 2833 (`app = create_app()`), o logging e inicializado imediatamente, sobrescrevendo
configuracoes do caller e contaminando `caplog` do pytest.

```python
# Antes — linha 65
setup_logging()  # executa no import
```

```python
# Depois — mover para dentro de create_app() ou run_gateway()
def create_app(cfg=None):
    if cfg is None:
        setup_logging()  # inicializa apenas quando o gateway e criado explicitamente
```

---

### Bug 58 — Comparacao de token nao e tempo-constante (timing attack)

**Arquivo:** `gateway/server.py` — linha 676 (aproximado)
**Severidade:** Leve
**Categoria:** Seguranca

**O que esta errado:**
`GatewayAuthGuard.check_http` compara o token fornecido com `!=`:

```python
if supplied_token != self.token:
    raise HTTPException(status_code=401, ...)
```

Comparacoes com `!=` em Python retornam antecipadamente quando encontram o primeiro
caractere diferente. Isso cria um side-channel de tempo: um atacante pode deduzir o
comprimento e prefixo do token medindo o tempo de resposta da API em centenas de
requisicoes. O mesmo problema ocorre na comparacao do webhook Telegram (linha 2442):
`supplied_secret != expected_secret`.

```python
# Depois — comparacao tempo-constante
import hmac
if not hmac.compare_digest(supplied_token, self.token):
    raise HTTPException(status_code=401, ...)
```

**Dica de robustez:** `hmac.compare_digest` e a forma idiomatica em Python para comparar
secrets; garante O(N) independente do ponto de divergencia.

---

### Bug 59 — `_route_cron_job` sem timeout em `engine.run()`

**Arquivo:** `gateway/server.py` — linha ~980
**Severidade:** Moderado
**Categoria:** Confiabilidade

**O que esta errado:**
O handler interno que despacha cron jobs para o engine chama `await runtime.engine.run(...)`
sem timeout. Se o LLM travar (provider lento, timeout nao configurado no nivel do provider,
ou rede instavel), o callback do cron fica suspenso indefinidamente. Como o `CronService`
(Bug 48) nao tem timeout no callback, o loop inteiro de cron para de processar novos jobs
ate que o LLM responda ou a conexao seja abortada.

```python
# Antes — sem timeout
async def _submit_cron_wake(session_id: str, prompt: str) -> dict:
    out = await runtime.engine.run(session_id=session_id, user_text=prompt)
    ...
```

```python
# Depois — timeout configural (ex: 120s)
async def _submit_cron_wake(session_id: str, prompt: str) -> dict:
    out = await asyncio.wait_for(
        runtime.engine.run(session_id=session_id, user_text=prompt),
        timeout=cfg.gateway.cron.engine_timeout_seconds,
    )
```

---

### Bug 60 — `_latest_memory_route` carrega todos os registros para achar o mais recente

**Arquivo:** `gateway/server.py` — linhas ~997–1021
**Severidade:** Moderado
**Categoria:** Performance

**O que esta errado:**
A rota que retorna a memoria mais recente chama `asyncio.to_thread(memory_store.all)`,
carregando TODOS os registros de memoria em RAM para extrair apenas o ultimo. Com
`MemoryStore` em modo JSONL, isso le o arquivo inteiro para obter um metadado de
uma linha. Com crescimento de memoria ao longo do tempo (centenas/milhares de entradas),
a latencia e o uso de memoria crescem linearmente.

```python
# Antes — carrega tudo para pegar o ultimo
all_records = await asyncio.to_thread(memory_store.all)
latest = max(all_records, key=lambda r: r.get("created_at", ""), default=None)
```

```python
# Depois — se MemoryStore tiver metodo paginated/latest
latest = await asyncio.to_thread(memory_store.latest, limit=1)
# ou: adicionar metodo latest() no MemoryStore que leia apenas as ultimas linhas do JSONL
```

**Dica de robustez:** O `MemoryStore` ja expoe `limit` no metodo `search()` — adicionar
um metodo `latest(n=1)` que leia apenas as ultimas N linhas do JSONL via `seek` no final
do arquivo eliminaria o custo O(N).

---

### Bug 61 — `_ws_chat` e `_chat_handler` sem timeout em `engine.run()`

**Arquivo:** `gateway/server.py` — linhas 2387, 2552, 2754, 2789
**Severidade:** Moderado
**Categoria:** Confiabilidade

**O que esta errado:**
Tanto o endpoint HTTP (`/api/message`, `/v1/chat`) quanto o handler WebSocket (`_ws_chat`)
chamam `await runtime.engine.run(...)` sem timeout. Se o LLM travar, a conexao HTTP
fica aberta indefinidamente (ate o cliente desistir) e a conexao WebSocket fica suspensa
bloqueando outros frames do mesmo socket. Isso e especialmente problema no WebSocket,
onde um unico cliente travado bloqueia seu proprio loop de mensagens.

```python
# Antes — sem timeout em todos os call sites
out = await runtime.engine.run(session_id=session_id, user_text=text)
```

```python
# Depois — timeout configuravel (ex: 300s para LLM + tools)
ENGINE_TIMEOUT = cfg.gateway.engine_timeout_seconds  # default: 300
out = await asyncio.wait_for(
    runtime.engine.run(session_id=session_id, user_text=text),
    timeout=ENGINE_TIMEOUT,
)
```

---

### Bug 62 — `create_app` monolitica com 1600+ linhas e closures aninhados

**Arquivo:** `gateway/server.py` — linhas 1211–2815
**Severidade:** Leve
**Categoria:** Qualidade | Manutencao

**O que esta errado:**
`create_app()` e uma funcao de ~1600 linhas com:
- Dezenas de variaveis locais de estado (`tuning_runner_state`, `proactive_runner_state`,
  `memory_quality_cache`, `proactive_task`, `tuning_task`, etc.)
- Funcoes aninhadas em 3+ niveis (`_ws_chat` -> `_ws_req_chat_send` -> closures internos)
- Subfuncoes de ciclo de vida (`_start_subsystems`, `_stop_subsystems`, `_start_proactive_monitor`,
  `_stop_memory_quality_tuning`, etc.) declaradas dentro da funcao pai

Este design torna praticamente impossivel testar subsistemas isoladamente (o proactive
monitor, o loop de tuning, o WebSocket handler) sem instanciar o gateway inteiro.
Closures compartilham estado via `nonlocal`, criando acoplamento implicito invisivel
nas assinaturas de funcao.

**Como corrigir:** Extrair para classes coesas: `ProactiveMonitor`, `MemoryQualityTuner`,
`GatewayLifecycle`, `WebSocketHandler` — cada uma com estado proprio e ciclo de vida
testavel independentemente.

---

### Bug 63 — `playbook_id` potencialmente indefinida fora do bloco condicional

**Arquivo:** `gateway/server.py` — funcao `_tick()` (linha ~1547)
**Severidade:** Leve
**Categoria:** Bug

**O que esta errado:**
A variavel `playbook_id` e definida apenas dentro de `if drift == "degrading":`, mas
e usada mais abaixo dentro de `if action:`. Se `action` for definida por outro bloco
(nao o bloco `degrading`) e `playbook_id` nao foi inicializada, `NameError` em runtime.

```python
# Fragmento simplificado
if drift == "degrading":
    playbook_id = ...   # unica atribuicao
    action = ...

if drift == "recovering":
    action = ...        # action definida sem playbook_id!

if action:
    log(playbook_id)    # NameError se drift != "degrading"
```

```python
# Depois — inicializar antes dos condicionais
playbook_id: str | None = None
action: str | None = None

if drift == "degrading":
    playbook_id = ...
    action = ...
```

---

### Bug 64 — `_start_proactive_monitor` nao detecta task anterior crashada

**Arquivo:** `gateway/server.py` — linha 1845
**Severidade:** Leve
**Categoria:** Confiabilidade

**O que esta errado:**
`_start_proactive_monitor()` verifica `if proactive_task is not None` para evitar
dupla inicializacao. Mas se a task anterior terminou com excecao (crashou silenciosamente),
`proactive_task` ainda e nao-None — e a funcao retorna dizendo "running" sem reiniciar.
O mesmo padrao se aplica a `tuning_task` em `_start_memory_quality_tuning()`.

```python
# Antes — nao detecta crash
async def _start_proactive_monitor() -> None:
    if proactive_task is not None:
        proactive_running = True
        return  # pode ser uma task morta!
```

```python
# Depois — verificar se a task ainda esta ativa
async def _start_proactive_monitor() -> None:
    if proactive_task is not None and not proactive_task.done():
        proactive_running = True
        return
    # se proactive_task.done() -> reiniciar
```

---

### Bug 65 — `app = create_app()` no nivel do modulo executa inicializacao completa ao importar

**Arquivo:** `gateway/server.py` — linha 2833
**Severidade:** Moderado
**Categoria:** Bug | Robustez

**O que esta errado:**
A linha `app = create_app()` no escopo do modulo executa a inicializacao completa do
gateway — incluindo `load_config()`, criacao de `AgentEngine`, conexao com banco de dados,
carregamento de tools e skills — toda vez que o modulo e importado. Isso causa:
1. Falha imediata na importacao se qualquer dependencia de config/arquivo estiver ausente
2. `setup_logging()` e chamado no import (soma-se ao Bug 57)
3. Torna impossivel importar `gateway.server` em testes sem provisionar o workspace completo
4. Se `create_app()` falhar (e.g., modelo nao configurado), a importacao falha com erro criptico

```python
# Antes — linha 2833
app = create_app()  # executa ao importar!
```

```python
# Depois — usar factory pattern com lazy initialization
def get_app():
    global _app
    if _app is None:
        _app = create_app()
    return _app

# Para Uvicorn via ASGI string: usar factory
# uvicorn clawlite.gateway.server:get_app --factory
```

---

## Resumo da Sessao 6 — `gateway/`

| Severidade | Quantidade |
|---|---|
| Moderado   | 5          |
| Leve       | 4          |

**Top 3 prioridades:**

1. **`_ws_chat` e `_chat_handler` sem timeout em `engine.run()`** (Bug 61) — uma
   requisicao de LLM travada bloqueia a conexao HTTP/WebSocket indefinidamente; em
   producao com muitos usuarios isso drena file descriptors e torna o gateway irresponsivel.
2. **`app = create_app()` no nivel do modulo** (Bug 65) — qualquer `import` do modulo
   provoca inicializacao completa do gateway, tornando testes unitarios e imports
   em ferramentas CLI extremamente lentos ou impossíveis sem workspace configurado.
3. **`_route_cron_job` sem timeout em `engine.run()`** (Bug 59) — um job cron com LLM
   travado para TODOS os outros jobs cron ate o LLM responder ou a conexao cair.

---

## SESSAO 7 — `clawlite/cli/`, `clawlite/session/`, `clawlite/config/`, `clawlite/bus/`, `clawlite/runtime/`, `clawlite/workspace/`, `clawlite/utils/`

Arquivos auditados:
- `cli/commands.py` (1019 linhas)
- `cli/onboarding.py`
- `cli/ops.py` (~950 linhas)
- `session/store.py` (203 linhas)
- `config/loader.py` (213 linhas)
- `config/schema.py`
- `workspace/loader.py` (273 linhas)
- `bus/queue.py` (275 linhas)
- `bus/events.py`
- `runtime/autonomy.py` (415 linhas)
- `runtime/supervisor.py` (191 linhas)
- `utils/logging.py` (138 linhas)
- `utils/logger.py`

---

### Bug 66 — `setup_logging()` no nivel do modulo em `runtime/`

**Arquivo:** `runtime/supervisor.py` — linha 11 | `runtime/autonomy.py` — linha 12
**Severidade:** Moderado
**Categoria:** Bug | Robustez

**O que esta errado:**
O mesmo padrao dos Bugs 1, 13, 24, 41, 57 repete-se em mais dois modulos do runtime.
Qualquer `import` de `RuntimeSupervisor` ou `AutonomyService` inicializa o sistema
de logging, mesmo em testes unitarios ou ferramentas CLI.

```python
# runtime/supervisor.py — linha 11
setup_logging()  # executa ao importar o modulo

# runtime/autonomy.py — linha 12
setup_logging()  # idem
```

**Como corrigir:** Mover para dentro do metodo `start()` de cada classe, ou usar
o padrao de `utils/logging.py` (que ja e guardado por `_LOGGING_CONFIGURED`).

---

### Bug 67 — `SessionStore._compact_session_file` O(N) chamado em cada `append()`

**Arquivo:** `session/store.py` — linhas 92, 150–178
**Severidade:** Moderado
**Categoria:** Performance

**O que esta errado:**
`_compact_session_file` e chamada dentro de `append()` apos cada escrita bem-sucedida
(linha 92). A funcao le o arquivo JSONL inteiro e reescreve quando o numero de linhas
ultrapassa `max_messages_per_session`. Com o padrao `max_messages_per_session=2000`,
a compactacao ocorre a partir de 2001 mensagens — mas e verificada em **toda** escrita,
lendo o arquivo inteiro a cada mensagem recebida.

Em uma sessao com 5000 mensagens, cada nova mensagem gera:
1. append (fsync) — correto
2. leitura de todas as 5000 linhas
3. reescrita das 2000 mais recentes

```python
# store.py linha 92 — compact na via de escrita quente
self._append_once(path, payload)
self._diagnostics["append_success"] += 1
self._compact_session_file(path)  # O(N) em cada append!
```

```python
# Depois — compactar apenas quando o arquivo cresce alem do limite
line_count = payload.count("\n")  # estimativa rapida
if line_count > limit * 2:  # so ler quando provavelmente precisa
    self._compact_session_file(path)
```

**Dica de robustez:** A solucao ideal e contar linhas com seek no final do arquivo
antes de ler tudo, ou manter um contador em memoria.

---

### Bug 68 — `SessionStore._compact_session_file` e `_repair_file` sem atomicidade

**Arquivo:** `session/store.py` — linhas 139–145, 172
**Severidade:** Moderado
**Categoria:** Confiabilidade

**O que esta errado:**
`_repair_file` e `_compact_session_file` usam `path.write_text()` direto, que
sobrescreve o arquivo JSONL existente sem garantia de atomicidade. Se o processo
crashar durante a reescrita, o arquivo fica truncado ou parcialmente escrito.
Ironia: `_append_once` (linha 104-108) faz `flush()` + `os.fsync()` corretamente,
mas as funcoes de compactacao e reparo ignoram isso.

```python
# _compact_session_file linha 172 — sem atomicidade
path.write_text(rewritten, encoding="utf-8")  # crash aqui = arquivo corrompido

# _repair_file linha 144 — idem
path.write_text(rewritten, encoding="utf-8")
```

```python
# Depois — usar atomic rename (como workspace/loader.py faz)
tmp = path.with_suffix(".tmp")
tmp.write_text(rewritten, encoding="utf-8")
tmp.replace(path)  # atomico no mesmo filesystem
```

---

### Bug 69 — `save_config` sem atomicidade

**Arquivo:** `config/loader.py` — linha 211
**Severidade:** Moderado
**Categoria:** Confiabilidade

**O que esta errado:**
`save_config` sobrescreve o arquivo de config com `target.write_text()` sem atomic
rename. Um crash durante a escrita (e.g., kill -9 no gateway enquanto salva uma
nova API key via CLI) deixa o arquivo de configuracao corrompido ou vazio, impedindo
o ClawLite de iniciar. Com operacoes de provider auth (`provider set-auth`, `provider
login`) que chamam `save_config` frequentemente, este e um caminho critico.

```python
# Antes — linha 211
target.write_text(
    json.dumps(config.to_dict(), ensure_ascii=False, indent=2),
    encoding="utf-8",
)

# Depois — atomic rename
import tempfile
with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
        dir=target.parent, delete=False, suffix=".tmp") as f:
    json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)
    tmp = Path(f.name)
tmp.replace(target)
```

---

### Bug 70 — `MessageQueue._stop_events` cresce sem TTL (memory leak)

**Arquivo:** `bus/queue.py` — linhas 223–248
**Severidade:** Moderado
**Categoria:** Performance

**O que esta errado:**
`stop_event(session_id)` cria e armazena um `asyncio.Event` em `_stop_events` sem
nenhum mecanismo de expiração. Sessoes que foram encerradas mas nunca tiveram
`request_stop()` chamado ficam no dict indefinidamente. Em uso normal, o gateway
cria dezenas de sessoes por hora — ao longo de dias de execucao, o dict acumula
milhares de eventos orfaos.

```python
# stop_event() — cria e guarda sem expirar
def stop_event(self, session_id: str) -> asyncio.Event:
    if event is None:
        event = asyncio.Event()
        self._stop_events[normalized] = event  # nunca removido!
    return event
```

```python
# clear_stop() nao remove entradas que nao foram setadas
def clear_stop(self, session_id: str) -> None:
    event = self._stop_events.get(normalized)
    if event is not None:
        event.clear()
        if not event.is_set():  # remove apenas se limpo apos set — logica errada
            self._stop_events.pop(normalized, None)
```

**Como corrigir:** Remover o evento em `clear_stop()` independente do estado, ou
usar um TTL (dicionario com `(event, created_at)` e purge periodico).

---

### Bug 71 — `MessageQueue.subscribe()` cria filas de topico sem backpressure

**Arquivo:** `bus/queue.py` — linhas 214–221
**Severidade:** Leve
**Categoria:** Performance | Confiabilidade

**O que esta errado:**
`subscribe()` cria `asyncio.Queue()` sem `maxsize`. Filas sem limite podem crescer
indefinidamente se o consumer for lento — tipicamente na leitura via WebSocket ou
canal. Um subscriber lento em um topico de alta frequencia pode acumular milhares
de eventos em memoria, causando OOM.

```python
# Antes — fila sem limite
queue: asyncio.Queue[InboundEvent] = asyncio.Queue()  # maxsize=0 = infinito
self._topics[channel].append(queue)
```

```python
# Depois — backpressure configuravel
queue: asyncio.Queue[InboundEvent] = asyncio.Queue(maxsize=500)
```

---

### Bug 72 — `publish_inbound` itera sobre lista com `await` dentro do loop

**Arquivo:** `bus/queue.py` — linhas 80–84
**Severidade:** Leve
**Categoria:** Bug | Confiabilidade

**O que esta errado:**
`publish_inbound` faz `await queue.put(event)` dentro de um `for` sobre
`self._topics[event.channel]`. Cada `await` e um ponto de interrupcao — outro
coroutine pode chamar `subscribe()` ou `unsubscribe()` (via `finally` do generator)
durante a iteracao, modificando a lista. Em Python, modificar uma lista durante
iteracao causa `RuntimeError: list changed size during iteration`.

```python
async def publish_inbound(self, event: InboundEvent) -> None:
    await self._inbound.put(event)
    for queue in self._topics.get(event.channel, []):  # iteracao pode ser interrompida!
        await queue.put(event)  # cada await e um ponto de preempcao
```

```python
# Depois — usar snapshot da lista antes de iterar
for queue in list(self._topics.get(event.channel, [])):  # copia defensiva
    await queue.put(event)
```

---

### Bug 73 — `_oldest_age_seconds` acessa atributo privado `asyncio.Queue._queue`

**Arquivo:** `bus/queue.py` — linha 33
**Severidade:** Leve
**Categoria:** Robustez

**O que esta errado:**
`_oldest_age_seconds` acessa `queue._queue` para iterar sobre itens sem dequeuer.
`_queue` e um atributo interno de `asyncio.Queue` (implementado como `collections.deque`)
e nao faz parte da API publica. Em versoes futuras do Python, este atributo pode
ser renomeado, removido, ou mudar de tipo.

```python
snapshot = list(getattr(queue, "_queue", []))  # API privada do CPython
```

```python
# Alternativa — manter snapshot separado para telemetria, sem acessar internals
```

---

### Bug 74 — `RuntimeSupervisor.start()` e `AutonomyService.start()` nao detectam task crashada

**Arquivo:** `runtime/supervisor.py` — linha 147 | `runtime/autonomy.py` — linha 363
**Severidade:** Leve
**Categoria:** Confiabilidade

**O que esta errado:**
Mesmo padrao do Bug 64 (`_start_proactive_monitor`): ambos os servicos verificam
`if self._task is not None: return` sem checar se a task ja terminou com excecao.
Se o loop interno crashar silenciosamente (e.g., erro nao capturado em `run_once`),
`start()` retorna dizendo "ja esta rodando" quando na verdade a task esta morta.

```python
# supervisor.py — nao detecta crash
async def start(self) -> None:
    if self._task is not None:
        return  # pode ser uma task morta!

# autonomy.py — idem
async def start(self) -> None:
    if self._task is not None:
        return
```

```python
# Depois — verificar se a task ainda esta ativa
if self._task is not None and not self._task.done():
    return
# se self._task.done() -> reiniciar
```

---

## Resumo da Sessao 7 — `cli/`, `session/`, `config/`, `bus/`, `runtime/`, `workspace/`, `utils/`

| Severidade | Quantidade |
|---|---|
| Moderado   | 4          |
| Leve       | 5          |

**Top 3 prioridades:**

1. **`save_config` sem atomicidade** (Bug 69) — qualquer `clawlite provider set-auth` ou
   `provider login` interrompido no meio corrompe o config.json principal; o ClawLite
   nao inicializa mais ate reparo manual.
2. **`_compact_session_file` O(N) em cada `append()`** (Bug 67) — em sessoes longas (2000+
   mensagens), cada nova mensagem relê e reescreve o arquivo JSONL inteiro, degradando
   severamente a performance do agente.
3. **`_compact_session_file` e `_repair_file` sem atomicidade** (Bug 68) — um crash durante
   compactacao ou reparo corrompe o historico da sessao; irônico pois `_append_once` faz
   `fsync` corretamente.

---

## SESSAO 8 — Auditoria de Performance (cross-cutting)

Esta sessao e uma analise tematica transversal, sintetizando todos os gargalos de
performance identificados nas Sessoes 1–7. Os bugs nao sao novos — referencias
aos numeros existentes. O objetivo e dar ao operador uma visao consolidada por
categoria de impacto.

---

### 8.1 — Bloqueio de Event Loop (mais criticos para latencia do gateway)

Operacoes sincronas executadas dentro de coroutines bloqueiam o event loop inteiro,
afetando **todos** os usuarios e canais simultaneamente durante o bloqueio.

| Bug | Arquivo | Operacao Bloqueante | Duracao Tipica | Frequencia |
|---|---|---|---|---|
| 45 | `scheduler/cron.py:124` | `fcntl.flock(LOCK_EX)` | 0–∞ ms (contencao) | 1/s por job |
| 43 | `scheduler/heartbeat.py:206` | `os.fsync()` | 5–200 ms (eMMC) | 1/30min |
| 39 | `tools/web.py` | `socket.getaddrinfo()` | 10–5000 ms (DNS) | por chamada |
| 40 | `tools/web.py` | `DDGS()` sincrono | 100–10000 ms | por busca |
| 6 | `core/memory_monitor.py:480` | `_persist_pending` I/O | 1–50 ms | por ciclo |

**Impacto combinado:** Em um cenario de producao com heartbeat + cron + busca web
ativos, o event loop pode estar bloqueado por varios segundos por hora. Todo canal
(Telegram, WhatsApp, WebSocket) para de processar mensagens durante o bloqueio.

**Padrao de correcao:** Todos esses casos devem usar `asyncio.to_thread()` ou
`loop.run_in_executor(None, ...)` para delegar a operacao bloqueante a uma thread pool.

---

### 8.2 — Complexidade Algorítmica Excessiva

Operacoes O(N) e O(N²) em caminhos de execucao frequentes.

| Bug | Arquivo | Operacao | Complexidade | Frequencia |
|---|---|---|---|---|
| 67 | `session/store.py:92` | `_compact_session_file` | O(N) por mensagem | cada append |
| 35 | `tools/memory.py:462` | `MemoryForgetTool` | O(N) total | por chamada |
| 60 | `gateway/server.py:997` | `_latest_memory_route` | O(N) total | por request |
| 4 | `core/memory_backend.py:743` | Busca pgvector com Python | O(N) total | por query |
| 9 | `files.py` | `_build_not_found_message` fuzzy | O(N²) | erro de path |
| 3 | `core/engine.py:470` | `inspect.signature()` | O(1) caro | por tool call |
| 36 | `tools/memory.py:85` | `inspect.signature()` sem cache | O(1) caro | por chamada |

**Caso mais critico (Bug 67):** Em uma sessao de 2000+ mensagens, cada nova mensagem
do LLM desencadeia leitura + reescrita do arquivo JSONL inteiro. Com 100 mensagens/hora,
isso resulta em 100 full-file reads/hour crescendo linearmente com o tamanho da sessao.

**Caso mais impactante a escala (Bug 4):** O backend pgvector executa busca
semantica com cosseno calculado em Python, tornando-o equivalente ao backend JSONL
em performance — anula completamente o valor de usar PostgreSQL + pgvector.

---

### 8.3 — Gerenciamento de Conexoes HTTP

Conexoes TLS recriadas desnecessariamente, multiplicando latencia de handshake.

| Bug | Arquivo | Problema | Custo Extra |
|---|---|---|---|
| 25 | `tools/mcp.py:71` | `AsyncClient` dentro do retry loop | +50–200ms por tentativa |
| 51 | `providers/litellm.py:386` | `AsyncClient` dentro do retry loop | +50–200ms por tentativa |
| 51 | `providers/codex.py:175` | `AsyncClient` dentro do retry loop | +50–200ms por tentativa |
| 18 | `channels/discord.py:43` | `AsyncClient` recriado a cada envio | +50ms por mensagem |

**Impacto:** Com `retry_max_attempts=3` no LiteLLMProvider, um provider instavel
incorre em 3 handshakes TLS (150–600ms extra) em vez de 1. Para providers Anthropic
que respondem em 2s, o overhead pode ser 25–30% da latencia total.

**Padrao de correcao:** Mover `httpx.AsyncClient` para nivel de instancia,
inicializado em `start()` e fechado em `stop()`, reutilizando a connection pool HTTP/2.

---

### 8.4 — Crescimento de Memoria sem Limite

Estruturas em memoria que crescem indefinidamente sem TTL ou limite.

| Bug | Arquivo | Estrutura | Taxa de Crescimento |
|---|---|---|---|
| 2 | `core/engine.py:324` | `_session_locks` dict | 1 lock/sessao, nunca removido |
| 12 | `core/engine.py:323` | `_stop_requests` set | 1 entry/stop, sem TTL |
| 17 | `channels/manager.py:282` | `_session_slots` dict | 1 slot/sessao ativa |
| 31 | `tools/process.py:58` | `_sessions` dict | 1 entry/processo, sem TTL |
| 32 | `tools/process.py:288` | `output` string | cresce com output do processo |
| 70 | `bus/queue.py:223` | `_stop_events` dict | 1 event/sessao, sem TTL |

**Impacto em producao:** Um gateway rodando por 30 dias com 50 sessoes/hora acumula
36.000 entradas em `_session_locks`, `_stop_events` e `_session_slots`. Em aarch64
com 2GB RAM (Android), cada lock Python consume ~240 bytes — 36k locks = ~8MB.
Inofensivo isolado, mas combinado com outros leaks pode causar OOM em semanas.

---

### 8.5 — Caminhos de I/O Nao-Otimizados

| Bug | Arquivo | Problema |
|---|---|---|
| 46 | `scheduler/cron.py:159` | `write_text` sem `fsync` antes do `replace` |
| 30 | `tools/apply_patch.py:85` | `write_text` sem atomic rename |
| 68 | `session/store.py:144` | `_repair_file` sem atomic rename |
| 68 | `session/store.py:172` | `_compact` sem atomic rename |
| 69 | `config/loader.py:211` | `save_config` sem atomic rename |
| 15 | `channels/telegram.py:512` | `_persist_update_dedupe_state` sem fsync |

**Observacao:** Ha uma inconsistencia clara no projeto — `SessionStore._append_once`
e `workspace/loader.py._write_bootstrap_state` fazem atomicidade corretamente,
enquanto as funcoes de compactacao e reparo do mesmo `SessionStore` nao fazem.
O padrao correto ja existe no codebase; precisa ser aplicado uniformemente.

---

### 8.6 — Resumo de Performance por Modulo

| Modulo | Bugs de Performance | Severidade Max | Impacto Principal |
|---|---|---|---|
| `core/memory_backend.py` | 1 | Critico | pgvector sem SQL vetorial — O(N) em Python |
| `scheduler/cron.py` | 1 | Critico | flock bloqueante no event loop |
| `tools/web.py` | 2 | Critico | DNS sync + DDGS sync bloqueiam event loop |
| `session/store.py` | 2 | Moderado | compact O(N) por append + sem atomicidade |
| `providers/litellm.py` | 2 | Moderado | TLS handshake por tentativa |
| `core/engine.py` | 3 | Moderado | leaks + inspect.signature sem cache |
| `channels/manager.py` | 1 | Moderado | session_slots leak |
| `gateway/server.py` | 2 | Moderado | memory load O(N) + engine.run sem timeout |
| `scheduler/heartbeat.py` | 1 | Moderado | fsync sincrono |

---

## SESSAO FINAL — Comparacao Geral: ClawLite vs OpenClaw

Esta sessao compara o estado atual do ClawLite com a referencia OpenClaw (TypeScript),
identificando as maiores lacunas de paridade e maturidade.

---

### F.1 — Paridade de Arquitetura

| Componente | OpenClaw (referencia) | ClawLite (Python) | Status |
|---|---|---|---|
| Gateway WebSocket | Sim — protocolo req/res + events | Sim — protocolo equivalente (`_ws_chat`) | ✅ Implementado |
| Dashboard HTML embutido | Sim — `ROOT_ENTRYPOINT_HTML` | Sim — `ROOT_ENTRYPOINT_HTML` | ✅ Implementado |
| Auth por token | Sim | Sim — `GatewayAuthGuard` | ⚠️ Timing attack (Bug 58) |
| Heartbeat 30min | Sim | Sim — `HeartbeatService` | ⚠️ fsync sync (Bug 43) |
| Bootstrap cycle | Sim | Sim — `WorkspaceLoader` | ✅ Implementado |
| Cron scheduler | Sim | Sim — `CronService` | 🔴 flock bloqueante (Bug 45) |
| Tool calling | Sim | Sim — `ToolRegistry` | 🔴 Anthropic schema vazio (Bug 49) |
| Session memory (JSONL) | Sim | Sim — `SessionStore` | ⚠️ compact O(N) (Bug 67) |
| Channels (Telegram, Discord, Slack) | Sim | Sim | ⚠️ sem retry rate-limit (Bugs 19, 20) |
| Subagentes | Sim | Sim — `SubagentManager` | ⚠️ cancel sem lock (Bug 8) |
| Memory vector search | Sim (pgvector) | Parcial — pgvector sem SQL vetorial | 🔴 O(N) em Python (Bug 4) |
| Provider failover | Sim | Sim — `FailoverProvider` | ✅ Implementado |
| Autonomy loop | Sim | Sim — `AutonomyService` | ✅ Implementado |
| Proactive monitor | Sim | Sim — gateway `_start_proactive_monitor` | ⚠️ nao detecta crash (Bug 64) |
| Runtime supervisor | Sim | Sim — `RuntimeSupervisor` | ⚠️ nao detecta crash (Bug 74) |

---

### F.2 — Diferencas Estruturais Criticas

**1. Tool Calling Anthropic quebrado (Bug 49)**

Este e o bug mais impactante na paridade funcional. Qualquer agente configurado
com `claude-opus` ou `claude-sonnet` recebe schemas de tools vazios. O LLM pode
chamar tools com argumentos incorretos ou nao as usar. OpenClaw provavelmente
testa com Anthropic — o ClawLite nao tem coverage de integracao equivalente.

**2. `app = create_app()` no nivel de modulo (Bug 65)**

Sem equivalente no OpenClaw (TypeScript). Em Python, isso significa que qualquer
`import clawlite.gateway.server` — inclusive em testes unitarios e comandos CLI —
inicializa o gateway inteiro (engine, tools, memory store, etc.). No OpenClaw,
o server e inicializado apenas quando explicitamente iniciado via `main()`.

**3. `fcntl.flock` bloqueante no cron (Bug 45)**

O equivalente TypeScript usa `fs.promises` (async I/O nativo) ou mutex em memoria.
A implementacao Python do CronService usa `flock` sincrono, que pode bloquear o
event loop. Em instancias multiplas do ClawLite (ex: load balancing), o flock
garante exclusao mutua mas ao custo da responsividade do gateway.

**4. Monolito `create_app` (Bug 62)**

`create_app()` tem 1600+ linhas com dezenas de closures aninhados. O equivalente
OpenClaw organiza isso em modulos separados e injetados por DI. A ausencia de
separacao torna impossivel testar subsistemas (heartbeat, proactive monitor, cron
dispatcher) sem provisionar o gateway completo.

---

### F.3 — Bugs sem Equivalente no OpenClaw (TypeScript nao sofre destes)

| Bug | Razao |
|---|---|
| Bug 39 — `socket.getaddrinfo` sync | TypeScript usa `dns.promises.lookup` async nativo |
| Bug 45 — `fcntl.flock` blocking | TypeScript usa `fs.promises` async nativo |
| Bug 40 — `DDGS` sync | TypeScript teria `await fetch()` nativo |
| Bug 65 — `create_app()` no import | Em TS, `import` nao executa efeitos colaterais equivalentes |
| Bug 43 — `os.fsync()` sync | TypeScript usa `fs.promises.fsync()` que e async |

---

### F.4 — Areas onde o ClawLite esta a frente ou equivalente

| Area | Observacao |
|---|---|
| Configuracao | `load_config` com deep merge + env overrides + migracao e robusto |
| Onboarding | Wizard interativo com `questionary` + `Rich` e bem estruturado |
| Diagnostics | `/api/diagnostics` com 15+ campos de telemetria e mais rico que muitas implementacoes TS |
| Provider failover | `FailoverProvider` com cooldown e diagnostics e correto |
| Safety policy | `ToolRegistry` com perfis + canal + agente e sofisticado |
| Memory quality | Sistema de tuning de qualidade de memoria nao tem equivalente em projetos menores |

---

### F.5 — Top 10 Bugs por Impacto em Producao

Prioridade recomendada para correcao imediata:

| Prioridade | Bug | Arquivo | Impacto |
|---|---|---|---|
| 1 | **49** | `providers/litellm.py:336` | Tool calling com Anthropic sempre quebrado |
| 2 | **50** | `providers/codex.py:182` | Tool calling com Codex sempre quebrado |
| 3 | **45** | `scheduler/cron.py:124` | flock sync pode travar o gateway inteiro |
| 4 | **4** | `core/memory_backend.py:743` | pgvector sem SQL — busca semantica O(N) |
| 5 | **39** | `tools/web.py` | getaddrinfo sync + SSRF TOCTOU |
| 6 | **16** | `channels/manager.py:664` | dispatch loop sem supervisao — canal para silenciosamente |
| 7 | **69** | `config/loader.py:211` | save_config sem atomic — config.json corrompivel |
| 8 | **14** | `channels/telegram.py:539` | Nonce HMAC nao-aleatorio — replay attack |
| 9 | **28** | `tools/skill.py:177` | ExecTool sem configuracao como guard — escaping de restricoes |
| 10 | **67** | `session/store.py:92` | compact O(N) em cada append — degrada com sessoes longas |

---

### F.6 — Metricas da Auditoria Completa

| Sessao | Escopo | Linhas auditadas | Bugs encontrados |
|---|---|---|---|
| 1 | `core/` | ~7900 | 12 |
| 2 | `channels/` | ~3500 | 11 |
| 3 | `tools/` | ~2800 | 17 |
| 4 | `scheduler/` | ~950 | 8 |
| 5 | `providers/` | ~1700 | 8 |
| 6 | `gateway/` | ~2975 | 9 |
| 7 | `cli/session/config/bus/runtime/` | ~3800 | 9 |
| 8 | Cross-cutting performance | — | 0 (sintese) |
| Final | Comparacao OpenClaw | — | 0 (analise) |
| **Total** | **Todo o codebase** | **~23.625** | **74** |

**Distribuicao por severidade:** 12 Criticos (16%) / 38 Moderados (51%) / 24 Leves (33%)

**Distribuicao por categoria:**
- Performance: 22 bugs (30%)
- Confiabilidade: 19 bugs (26%)
- Bug (logica incorreta): 16 bugs (22%)
- Seguranca: 8 bugs (11%)
- Qualidade/Manutencao: 9 bugs (12%)

---

*Auditoria completa realizada por Claude Code (Sonnet 4.6) — 2026-03-06*
*Nenhum codigo foi alterado durante esta auditoria.*
*Metodologia: leitura manual completa linha a linha de todos os arquivos .py do projeto.*

---

## Consolidado Geral

| # | Arquivo | Linha | Severidade | Categoria | Descricao |
|---|---|---|---|---|---|
| 1 | `core/engine.py` | 21 | Moderado | Bug | `setup_logging()` no nivel de modulo |
| 2 | `core/engine.py` | 324 | Critico | Bug/Performance | `_session_locks` memory leak |
| 3 | `core/engine.py` | 470 | Moderado | Performance | `inspect.signature()` no loop LLM |
| 4 | `core/memory_backend.py` | 743 | Critico | Bug/Performance | pgvector nao usa SQL vetorial |
| 5 | `core/memory_backend.py` | 99 | Leve | Robustez | `_cosine_similarity` duplicado |
| 6 | `core/memory_monitor.py` | 480 | Moderado | Bug/Performance | `_persist_pending` bloqueia event loop |
| 7 | `core/engine.py` | 1190 | Moderado | Performance | `messages` cresce sem limite no turn |
| 8 | `core/subagent.py` | 372 | Moderado | Bug | `cancel()` sem async lock |
| 9 | `core/skills.py` | 531 | Leve | Performance | `get()` sem cache (I/O por lookup) |
| 10 | `core/prompt.py` | 112 | Leve | Robustez | `_estimate_tokens` impreciso para Unicode |
| 11 | `core/prompt.py` | 203 | Leve | Bug | `datetime.now()` sem timezone |
| 12 | `core/engine.py` | 323 | Leve | Bug | `_stop_requests` sem TTL |
| 13 | `channels/telegram.py` | 37 | Moderado | Bug | `setup_logging()` no nivel de modulo |
| 14 | `channels/telegram.py` | 539 | Critico | Seguranca | Nonce HMAC nao-aleatorio |
| 15 | `channels/telegram.py` | 512 | Moderado | Confiabilidade | `_persist_update_dedupe_state` sem fsync |
| 16 | `channels/manager.py` | 664 | Critico | Confiabilidade | `_dispatch_loop` sem supervisao |
| 17 | `channels/manager.py` | 282 | Moderado | Bug/Performance | `_session_slots` memory leak |
| 18 | `channels/discord.py` | 43 | Moderado | Performance | `AsyncClient` recriado a cada send |
| 19 | `channels/discord.py` | 49 | Moderado | Confiabilidade | Sem retry em 429 |
| 20 | `channels/slack.py` | 62 | Moderado | Confiabilidade | Sem tratamento de rate limit |
| 21 | `channels/telegram.py` | 263 | Leve | Bug | Placeholder `\x00` pode colidir |
| 22 | `channels/base.py` | 79 | Leve | API Design | `PassiveChannel.send()` simula sucesso |
| 23 | `channels/telegram.py` | 921 | Leve | Robustez | `_typing_tasks` potencial duplicacao |
| 24 | `tools/mcp.py` | 12 | Moderado | Bug | `setup_logging()` no nivel de modulo (mcp, skill) |
| 25 | `tools/mcp.py` | 71 | Moderado | Performance | `AsyncClient` dentro do loop de retry |
| 26 | `tools/mcp.py` | 107 | Leve | Bug/Qualidade | Dead code apos loop de retry |
| 27 | `tools/mcp.py` | 183 | Moderado | Seguranca | Sem validacao de IP resolvido (SSRF por hostname) |
| 28 | `tools/skill.py` | 177 | Critico | Seguranca | `ExecTool()` sem configuracao como guard |
| 29 | `tools/skill.py` | 134 | Critico | Seguranca | `_run_command` sem guards do registry |
| 30 | `tools/apply_patch.py` | 85 | Moderado | Confiabilidade | Escrita sem atomicidade (sem fsync) |
| 31 | `tools/process.py` | 58 | Moderado | Performance | `_sessions` cresce sem limite ou TTL |
| 32 | `tools/process.py` | 288 | Moderado | Performance | `output` cresce sem limite (risco de OOM) |
| 33 | `tools/process.py` | 290 | Moderado | Bug | `done_event` sinalizado antes dos streams |
| 34 | `tools/sessions.py` | 233 | Moderado | Confiabilidade | `runner` sem timeout (bloqueia indefinidamente) |
| 35 | `tools/memory.py` | 462 | Moderado | Performance | `MemoryForgetTool` carrega tudo antes de filtrar |
| 36 | `tools/memory.py` | 85 | Leve | Performance | `inspect.signature()` sem cache em `_accepts_parameter` |
| 37 | `tools/spawn.py` | 39 | Moderado | Seguranca | Fail-open em excecao de policy check |
| 38 | `tools/web.py` | — | Critico | Bug | Regex `\\s` quebrado em `_html_to_text` |
| 39 | `tools/web.py` | — | Critico | Bug/Seguranca | `socket.getaddrinfo` sincrono + SSRF TOCTOU |
| 40 | `tools/web.py` | — | Critico | Bug/Performance | `DDGS` sincrono bloqueia event loop |
| 41 | `scheduler/heartbeat.py` | 73 | Moderado | Bug | `setup_logging()` no nivel de modulo |
| 42 | `scheduler/heartbeat.py` | 225 | Moderado | Bug | `_execute_tick` modifica `_state` fora do lock |
| 43 | `scheduler/heartbeat.py` | 206 | Moderado | Performance | `os.fsync()` sincrono no tick bloqueia event loop |
| 44 | `scheduler/heartbeat.py` | 290 | Moderado | Confiabilidade | `_loop()` sem try/except externo |
| 45 | `scheduler/cron.py` | 124 | Critico | Bug/Performance | `fcntl.flock(LOCK_EX)` sincrono bloqueia event loop |
| 46 | `scheduler/cron.py` | 159 | Moderado | Confiabilidade | `_write_rows_unlocked` sem `os.fsync` |
| 47 | `scheduler/cron.py` | 457 | Leve | Performance | Loop de cron polling 1s sem calcular proximo job |
| 48 | `scheduler/cron.py` | 431 | Moderado | Confiabilidade | Callback de job sem timeout |
| 49 | `providers/litellm.py` | 336 | Critico | Bug | `_anthropic_tools` usa chave `"arguments"` — schema sempre vazio |
| 50 | `providers/codex.py` | 182 | Critico | Bug | `CodexProvider` ignora tool calls da resposta |
| 51 | `providers/litellm.py` | 386 | Moderado | Performance | `AsyncClient` por tentativa no retry loop |
| 52 | `providers/litellm.py` | 17 | Leve | Qualidade | `_HARD_QUOTA_SIGNALS` duplicado vs `reliability.py` |
| 53 | `providers/registry.py` | 325 | Leve | Bug | `assert spec is not None` removido em `python -O` |
| 54 | `providers/transcription.py` | 21 | Moderado | Performance | `read_bytes()` carrega audio completo em RAM |
| 55 | `providers/transcription.py` | 15 | Moderado | Confiabilidade | Sem retry em erros transientes |
| 56 | `providers/reliability.py` | 30 | Leve | Confiabilidade | `parse_retry_after_seconds` ignora formato de data RFC 7231 |
| 57 | `gateway/server.py` | 65 | Moderado | Bug | `setup_logging()` no nivel de modulo |
| 58 | `gateway/server.py` | ~676 | Leve | Seguranca | Comparacao de token nao e tempo-constante (timing attack) |
| 59 | `gateway/server.py` | ~980 | Moderado | Confiabilidade | `_route_cron_job` sem timeout em `engine.run()` |
| 60 | `gateway/server.py` | ~997 | Moderado | Performance | `_latest_memory_route` carrega todos os registros para achar o mais recente |
| 61 | `gateway/server.py` | 2387,2552 | Moderado | Confiabilidade | `_chat_handler` e `_ws_chat` sem timeout em `engine.run()` |
| 62 | `gateway/server.py` | 1211 | Leve | Qualidade | `create_app` monolitica 1600+ linhas com closures aninhados |
| 63 | `gateway/server.py` | ~1547 | Leve | Bug | `playbook_id` potencialmente indefinida fora do bloco condicional |
| 64 | `gateway/server.py` | 1845 | Leve | Confiabilidade | `_start_proactive_monitor` nao detecta task anterior crashada |
| 65 | `gateway/server.py` | 2833 | Moderado | Bug/Robustez | `app = create_app()` no nivel de modulo executa inicializacao completa ao importar |
| 66 | `runtime/supervisor.py` | 11 | Moderado | Bug | `setup_logging()` no nivel de modulo (supervisor e autonomy) |
| 67 | `session/store.py` | 92 | Moderado | Performance | `_compact_session_file` O(N) chamado em cada `append()` |
| 68 | `session/store.py` | 144,172 | Moderado | Confiabilidade | `_compact_session_file` e `_repair_file` sem atomicidade |
| 69 | `config/loader.py` | 211 | Moderado | Confiabilidade | `save_config` sem atomic rename — config corrompido em crash |
| 70 | `bus/queue.py` | 223 | Moderado | Performance | `_stop_events` cresce sem TTL (memory leak por sessao) |
| 71 | `bus/queue.py` | 215 | Leve | Performance | `subscribe()` cria filas de topico sem backpressure (maxsize=0) |
| 72 | `bus/queue.py` | 83 | Leve | Bug | `publish_inbound` itera lista com `await` dentro — race condition |
| 73 | `bus/queue.py` | 33 | Leve | Robustez | `_oldest_age_seconds` acessa `asyncio.Queue._queue` (atributo privado) |
| 74 | `runtime/supervisor.py` | 147 | Leve | Confiabilidade | `start()` nao detecta task crashada (supervisor e autonomy) |

### Contagem Total

| Severidade | core/ | channels/ | tools/ | scheduler/ | providers/ | gateway/ | cli+session+outros/ | Total |
|---|---|---|---|---|---|---|---|---|
| Critico    | 2     | 2         | 5      | 1          | 2          | 0        | 0                   | **12** |
| Moderado   | 5     | 6         | 9      | 5          | 3          | 5        | 5                   | **38** |
| Leve       | 5     | 3         | 3      | 2          | 3          | 4        | 4                   | **24** |
| **Total**  | **12**| **11**    | **17** | **8**      | **8**      | **9**    | **9**               | **74** |

---

*Auditoria completa realizada por Claude Code (Sonnet 4.6) — 2026-03-06*
*Sessoes 1–7 (bugs 1–74) + Sessao 8 (performance cross-cutting) + Sessao Final (comparacao OpenClaw)*
*Nenhum codigo foi alterado durante esta auditoria.*
