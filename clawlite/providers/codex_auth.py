from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _codex_auth_path(path: str | Path | None = None) -> Path:
    raw = str(path or os.getenv("CLAWLITE_CODEX_AUTH_PATH", "") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".codex" / "auth.json"


def _pick_value(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        text = str(value or "").strip()
        if text:
            return text
    return ""


def load_codex_auth_file(path: str | Path | None = None) -> dict[str, str]:
    auth_path = _codex_auth_path(path)
    empty = {
        "access_token": "",
        "account_id": "",
        "auth_mode": "",
        "source": "",
        "path": str(auth_path),
    }

    try:
        payload = json.loads(auth_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return dict(empty)

    if not isinstance(payload, dict):
        return dict(empty)

    tokens_payload = payload.get("tokens")
    tokens = dict(tokens_payload) if isinstance(tokens_payload, dict) else {}
    access_token = _pick_value(tokens, "access_token", "accessToken", "token") or _pick_value(
        payload,
        "access_token",
        "accessToken",
        "token",
    )
    account_id = _pick_value(tokens, "account_id", "accountId", "org_id", "orgId", "organization") or _pick_value(
        payload,
        "account_id",
        "accountId",
        "org_id",
        "orgId",
        "organization",
    )
    auth_mode = _pick_value(payload, "auth_mode", "authMode")

    return {
        "access_token": access_token,
        "account_id": account_id,
        "auth_mode": auth_mode,
        "source": f"file:{auth_path}" if access_token else "",
        "path": str(auth_path),
    }
