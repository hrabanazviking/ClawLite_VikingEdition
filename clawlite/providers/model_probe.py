from __future__ import annotations

from typing import Any


def strip_provider_prefix(model: str, *, provider: str = "", aliases: tuple[str, ...] = ()) -> str:
    candidate = str(model or "").strip()
    if "/" not in candidate:
        return candidate
    prefix, remainder = candidate.split("/", 1)
    normalized_prefix = prefix.strip().lower().replace("-", "_")
    allowed = {str(provider or "").strip().lower().replace("-", "_")}
    allowed.update(str(alias or "").strip().lower().replace("-", "_") for alias in aliases)
    if normalized_prefix in allowed:
        return remainder
    return candidate


def _normalize_model_name(model: str) -> str:
    candidate = str(model or "").strip()
    if not candidate:
        return ""
    return candidate.lower()


def _match_model(target: str, offered: str) -> bool:
    target_name = _normalize_model_name(target)
    offered_name = _normalize_model_name(offered)
    return bool(target_name) and bool(offered_name) and target_name == offered_name


def extract_listed_models(payload: Any) -> list[str]:
    rows: list[Any] = []
    if isinstance(payload, dict):
        for key in ("data", "models", "items"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                rows = list(candidate)
                break
    elif isinstance(payload, list):
        rows = list(payload)

    names: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if isinstance(row, dict):
            value = ""
            for key in ("id", "name", "model", "slug"):
                candidate = str(row.get(key, "") or "").strip()
                if candidate:
                    value = candidate
                    break
        else:
            value = str(row or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        names.append(value)
    return names


def evaluate_remote_model_check(
    *,
    provider: str,
    model: str,
    aliases: tuple[str, ...] = (),
    payload: Any,
    is_gateway: bool = False,
) -> dict[str, Any]:
    target_model = strip_provider_prefix(model, provider=provider, aliases=aliases).strip()
    if not target_model:
        return {
            "checked": False,
            "ok": True,
            "enforced": False,
            "detail": "model_missing",
            "available_models": [],
            "matched_model": "",
        }

    if is_gateway and target_model.lower() == "auto":
        return {
            "checked": False,
            "ok": True,
            "enforced": False,
            "detail": "router_model_auto",
            "available_models": [],
            "matched_model": "",
        }

    available_models = extract_listed_models(payload)
    if not available_models:
        return {
            "checked": False,
            "ok": True,
            "enforced": False,
            "detail": "model_list_unavailable",
            "available_models": [],
            "matched_model": "",
        }

    matched_model = next((row for row in available_models if _match_model(target_model, row)), "")
    return {
        "checked": True,
        "ok": bool(matched_model),
        "enforced": False,
        "detail": "model_listed" if matched_model else "model_not_listed",
        "available_models": available_models[:50],
        "matched_model": matched_model,
    }


def model_check_hints(model_check: dict[str, Any], *, model: str) -> list[str]:
    if not isinstance(model_check, dict):
        return []
    detail = str(model_check.get("detail", "") or "").strip().lower()
    if detail == "router_model_auto":
        return ["O modelo 'auto' usa roteamento do gateway; a lista remota nao exige match exato."]
    if not bool(model_check.get("checked", False)):
        return []
    if bool(model_check.get("ok", False)):
        return []
    model_name = str(model or "").strip()
    if detail == "model_not_listed" and model_name:
        return [f"O modelo '{model_name}' nao apareceu na lista remota do provider; valide nome, conta e permissoes."]
    if detail == "model_not_listed":
        return ["O modelo configurado nao apareceu na lista remota do provider; valide nome, conta e permissoes."]
    return []
