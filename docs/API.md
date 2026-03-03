# API (Gateway)

Base URL padrão: `http://127.0.0.1:8787`

## Auth (resumo)

- `gateway.auth.mode=off`: sem autenticação.
- `gateway.auth.mode=optional`: aceita sem token, mas token inválido retorna `401`.
- `gateway.auth.mode=required`: exige token (com exceção de loopback se `allow_loopback_without_auth=true`).
- Token pode ser enviado por header configurável (padrão `Authorization`, com ou sem prefixo `Bearer `) ou query param configurável (padrão `token`).
- `/health` só exige auth quando `gateway.auth.protect_health=true` e modo `required`.
- `/v1/diagnostics` depende de `gateway.diagnostics.enabled` e pode exigir auth com `gateway.diagnostics.require_auth=true`.

## `GET /health`

Resposta exemplo:

```json
{
  "ok": true,
  "ready": true,
  "phase": "running",
  "channels": {},
  "queue": {
    "inbound_size": 0,
    "outbound_size": 0,
    "outbound_dropped": 0,
    "dead_letter_size": 0,
    "topics": 0,
    "stop_sessions": 0
  }
}
```

## `GET /v1/status`

Resposta exemplo:

```json
{
  "ready": true,
  "phase": "running",
  "components": {
    "channels": {"enabled": true, "running": true, "last_error": ""},
    "cron": {"enabled": true, "running": true, "last_error": ""},
    "heartbeat": {"enabled": true, "running": true, "last_error": ""},
    "engine": {"enabled": true, "running": true, "last_error": ""}
  },
  "auth": {
    "posture": "open",
    "mode": "off",
    "allow_loopback_without_auth": true,
    "protect_health": false,
    "token_configured": false,
    "header_name": "Authorization",
    "query_param": "token"
  }
}
```

## `GET /v1/diagnostics`

Se `gateway.diagnostics.enabled=false`, retorna `404` com `{"error":"diagnostics_disabled","status":404}`.

Resposta exemplo:

```json
{
  "schema_version": "2026-03-02",
  "control_plane": {"ready": true, "phase": "running", "components": {}, "auth": {}},
  "queue": {
    "inbound_size": 0,
    "outbound_size": 0,
    "outbound_dropped": 0,
    "dead_letter_size": 0,
    "topics": 0,
    "stop_sessions": 0
  },
  "channels": {},
  "cron": {},
  "heartbeat": {},
  "environment": {}
}
```

## `POST /v1/control/heartbeat/trigger`

Sem body.

Resposta exemplo:

```json
{
  "ok": true,
  "decision": {
    "action": "skip",
    "reason": "nothing_to_do",
    "text": "HEARTBEAT_OK"
  }
}
```

Se heartbeat estiver desligado (`gateway.heartbeat.enabled=false`), retorna `409` com `{"error":"heartbeat_disabled","status":409}`.

## `POST /v1/chat`

Request:

```json
{
  "session_id": "telegram:123",
  "text": "me lembra de beber agua"
}
```

Response:

```json
{
  "text": "...",
  "model": "gemini/gemini-2.5-flash"
}
```

## `POST /v1/cron/add`

Request:

```json
{
  "session_id": "telegram:123",
  "expression": "every 120",
  "prompt": "me lembra de alongar",
  "name": "alongar"
}
```

Response:

```json
{
  "ok": true,
  "status": "created",
  "id": "job_xxx"
}
```

## `GET /v1/cron/list?session_id=...`

Resposta exemplo:

```json
{
  "jobs": []
}
```

## `DELETE /v1/cron/{job_id}`

Resposta exemplo:

```json
{
  "ok": true,
  "status": "removed"
}
```

## `WS /v1/ws`

WebSocket para chat.

Mensagem de entrada:

```json
{"session_id":"cli:ws","text":"oi"}
```

Mensagem de saída:

```json
{"text":"...","model":"gemini/gemini-2.5-flash"}
```
