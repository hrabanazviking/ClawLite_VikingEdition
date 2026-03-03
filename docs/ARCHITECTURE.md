# Architecture

Current architecture (new runtime), no legacy:

```text
clawlite/
├── core/         # engine, prompt, memory, skills, subagent
├── tools/        # tool abc, registry, and built-in tools
├── bus/          # events and async queue
├── channels/     # manager + channels (full telegram, other adapters)
├── gateway/      # FastAPI + WebSocket
├── scheduler/    # cron + heartbeat
├── providers/    # litellm/custom/codex/transcription
├── session/      # JSONL store per session
├── config/       # schema + loader
├── workspace/    # loader + identity templates
├── skills/       # built-in markdown skills (SKILL.md)
├── cli/          # start/run/onboard/cron commands
└── utils/        # shared helpers
```

## Main flow

1. Message enters through `channels` or `gateway`.
2. `core.engine` builds prompt (workspace + memory + history + skills).
3. Provider responds; if there are tool calls, `tools.registry` executes them.
4. Final response is persisted in `session.store` and consolidated in `core.memory`.
5. `scheduler.cron` and `scheduler.heartbeat` trigger proactive runs.
