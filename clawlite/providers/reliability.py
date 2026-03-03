from __future__ import annotations

from dataclasses import dataclass


_QUOTA_429_SIGNALS = (
    "insufficient_quota",
    "quota exceeded",
    "quota_exceeded",
    "exceeded your current quota",
    "billing hard limit",
    "billing_hard_limit",
    "credit balance is too low",
    "out of credits",
    "payment required",
    "billing exhausted",
)


@dataclass(slots=True, frozen=True)
class ReliabilitySettings:
    retry_max_attempts: int = 3
    retry_initial_backoff_s: float = 0.5
    retry_max_backoff_s: float = 8.0
    retry_jitter_s: float = 0.2
    circuit_failure_threshold: int = 3
    circuit_cooldown_s: float = 30.0


def parse_retry_after_seconds(header_value: str | None) -> float | None:
    raw = str(header_value or "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    if value < 0:
        return None
    return value


def parse_http_status(error_message: str, *, prefixes: tuple[str, ...] = ("provider_http_error:", "codex_http_error:")) -> int | None:
    text = str(error_message or "")
    for prefix in prefixes:
        if text.startswith(prefix):
            suffix = text[len(prefix) :]
            code_raw = suffix.split(":", 1)[0].strip()
            try:
                return int(code_raw)
            except ValueError:
                return None
    return None


def is_quota_429_error(error_message: str) -> bool:
    lowered = str(error_message or "").lower()
    if not lowered:
        return False
    return any(token in lowered for token in _QUOTA_429_SIGNALS)


def is_retryable_error(error_message: str) -> bool:
    text = str(error_message or "").strip()
    if not text:
        return False
    if text.startswith("provider_circuit_open:"):
        return True
    if text.startswith("provider_network_error:") or text.startswith("codex_network_error:"):
        return True
    status = parse_http_status(text)
    if status is None:
        return False
    if status == 429:
        return not is_quota_429_error(text)
    return 500 <= status <= 599
