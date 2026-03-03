# Security Policy

This document defines how to report vulnerabilities in ClawLite and the minimum baseline for secure operation.

## Vulnerability reporting

Do not publish exploitable details in a public issue.

Use:
- https://github.com/eobarretooo/ClawLite/security/advisories/new

Include:
- technical description
- practical impact
- reproduction steps
- affected commit/version
- evidence (logs, payloads, stacktrace)

## Covered scope

- CLI (`start`, `run`, `onboard`, `cron`, `skills`)
- Gateway (`/health`, `/v1/chat`, `/v1/cron/*`, `/v1/ws`)
- Providers and external API integrations
- Local tools (exec/files/web/cron/message/spawn/mcp)
- Channels and scheduler components

## Threat model

- User/channel input is untrusted.
- Tools with local execution are privileged.
- Provider keys are critical secrets.

## Recommended hardening

1. Set a gateway token and protect network access.
2. Run with a non-admin user.
3. Restrict file permissions in `~/.clawlite/` (`700` or `600` where applicable).
4. Review skills with `command/script` before enabling in production.
5. Rotate provider keys periodically.

## Responsible disclosure

After the fix, publish a patch and clear upgrade guidance.
