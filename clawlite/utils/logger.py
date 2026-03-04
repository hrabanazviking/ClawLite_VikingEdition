from __future__ import annotations

import json
import sys
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree

_STDERR_CONSOLE = Console(stderr=True, soft_wrap=True)

_LEVEL_STYLE = {
    "DEBUG": "dim cyan",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "bold red",
}

_CATEGORY_MAP: list[tuple[str, str, str, str]] = [
    ("gateway", "gateway", "globe_with_meridians", "cyan"),
    ("channel.telegram", "telegram", "speech_balloon", "magenta"),
    ("channel.discord", "discord", "speech_balloon", "magenta"),
    ("channel.slack", "slack", "speech_balloon", "magenta"),
    ("channel.whatsapp", "whatsapp", "speech_balloon", "magenta"),
    ("channel.", "channel", "speech_balloon", "magenta"),
    ("tool.", "tools", "hammer_and_wrench", "blue"),
    ("memory.", "memory", "card_index_dividers", "bright_cyan"),
    ("heartbeat.", "heartbeat", "heart", "bright_green"),
    ("autonomy.", "autonomy", "robot", "bright_green"),
    ("agent.loop", "autonomy", "robot", "bright_green"),
    ("provider.", "provider", "satellite_antenna", "bright_yellow"),
]


def _icon(symbol_name: str) -> str:
    icons = {
        "globe_with_meridians": "🌐",
        "speech_balloon": "💬",
        "hammer_and_wrench": "🛠",
        "card_index_dividers": "🧠",
        "heart": "💓",
        "robot": "🤖",
        "satellite_antenna": "📡",
        "info": "ℹ",
        "warning": "⚠",
        "error": "⛔",
    }
    return icons.get(symbol_name, "•")


def _detect_category(record: dict[str, Any]) -> tuple[str, str, str]:
    extra = record.get("extra") if isinstance(record.get("extra"), dict) else {}
    event = str(extra.get("event", "-") or "-").lower()
    channel = str(extra.get("channel", "-") or "-").lower()
    module_name = str(record.get("name", "-") or "-").lower()
    candidate = f"{event} {channel} {module_name}"
    for needle, category, icon_key, style in _CATEGORY_MAP:
        if needle in candidate:
            return category, _icon(icon_key), style
    return "system", _icon("info"), "white"


def _build_header(record: dict[str, Any]) -> Text:
    category, icon, category_style = _detect_category(record)
    level_name = str(getattr(record.get("level"), "name", "INFO"))
    timestamp = record["time"].strftime("%Y-%m-%d %H:%M:%S")
    header = Text()
    header.append(timestamp, style="dim")
    header.append(" ")
    header.append(icon, style=category_style)
    header.append(" ")
    header.append(category.upper(), style=f"bold {category_style}")
    header.append(" ")
    header.append(level_name, style=_LEVEL_STYLE.get(level_name, "white"))
    return header


def render_log_record(record: dict[str, Any]) -> None:
    level_name = str(getattr(record.get("level"), "name", "INFO"))
    message = str(record.get("message", ""))
    header = _build_header(record)
    body = Text()
    body.append(message)

    extra = record.get("extra") if isinstance(record.get("extra"), dict) else {}
    event = str(extra.get("event", "-") or "-")
    module_name = str(record.get("name", "-") or "-")
    body.append(f"\n[{event}] {module_name}", style="dim")

    exception = record.get("exception")
    if exception:
        body.append(f"\n{exception}", style="red")

    if level_name in {"WARNING", "ERROR", "CRITICAL"}:
        border_style = "yellow" if level_name == "WARNING" else "red"
        panel = Panel(
            body,
            title=f" {header.plain} ",
            border_style=border_style,
            padding=(0, 1),
            expand=False,
        )
        _STDERR_CONSOLE.print(panel)
        return

    _STDERR_CONSOLE.print(header, body)


def render_loguru_message(message: Any) -> None:
    record = getattr(message, "record", None)
    if isinstance(record, dict):
        render_log_record(record)
        return
    _STDERR_CONSOLE.print(str(message).rstrip("\n"))


def _semantic_record(level_name: str, message: str, category: str) -> dict[str, Any]:
    return {
        "time": datetime.now(),
        "level": type("Level", (), {"name": level_name})(),
        "name": category,
        "message": message,
        "extra": {"event": category},
        "exception": None,
    }


def log_info(message: str, *, category: str = "system") -> None:
    render_log_record(_semantic_record("INFO", message, category))


def log_warning(message: str, *, category: str = "system") -> None:
    render_log_record(_semantic_record("WARNING", message, category))


def log_error(message: str, *, category: str = "system") -> None:
    render_log_record(_semantic_record("ERROR", message, category))


def log_background(title: str, details: str) -> None:
    _STDERR_CONSOLE.print(f"[dim]{title}[/dim] [white]{details}[/white]")


def log_thought_tree(root: str, nodes: list[str]) -> None:
    tree = Tree(f"[bold cyan]{root}[/bold cyan]")
    for node in nodes:
        tree.add(node)
    _STDERR_CONSOLE.print(tree)


def stdout_text(text: str) -> None:
    sys.stdout.write(f"{text}\n")


def stdout_json(payload: Any) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")
