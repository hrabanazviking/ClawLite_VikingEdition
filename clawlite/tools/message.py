from __future__ import annotations

from typing import Any, Protocol

from clawlite.tools.base import Tool, ToolContext


class MessageAPI(Protocol):
    async def send(
        self,
        *,
        channel: str,
        target: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> str: ...


class MessageTool(Tool):
    name = "message"
    description = "Send proactive message to a channel target."

    def __init__(self, api: MessageAPI) -> None:
        self.api = api

    def args_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "channel": {"type": "string"},
                "target": {"type": "string"},
                "text": {"type": "string"},
                "metadata": {"type": "object"},
                "buttons": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "callback_data": {"type": "string"},
                                "url": {"type": "string"},
                            },
                        },
                    },
                },
            },
            "required": ["channel", "target", "text"],
        }

    @staticmethod
    def _validate_buttons(buttons: Any) -> list[list[dict[str, str]]]:
        if not isinstance(buttons, list):
            raise ValueError("buttons must be a list of rows")
        normalized_rows: list[list[dict[str, str]]] = []
        for row in buttons:
            if not isinstance(row, list):
                raise ValueError("buttons rows must be lists")
            normalized_row: list[dict[str, str]] = []
            for button in row:
                if not isinstance(button, dict):
                    raise ValueError("each button must be an object")
                text = str(button.get("text", "")).strip()
                if not text:
                    raise ValueError("each button must include non-empty text")

                has_callback = "callback_data" in button and str(button.get("callback_data", "")).strip() != ""
                has_url = "url" in button and str(button.get("url", "")).strip() != ""
                if has_callback == has_url:
                    raise ValueError("each button must include exactly one of callback_data or url")

                normalized_button: dict[str, str] = {"text": text}
                if has_callback:
                    normalized_button["callback_data"] = str(button.get("callback_data", "")).strip()
                if has_url:
                    normalized_button["url"] = str(button.get("url", "")).strip()
                normalized_row.append(normalized_button)
            normalized_rows.append(normalized_row)
        return normalized_rows

    async def run(self, arguments: dict, ctx: ToolContext) -> str:
        channel = str(arguments.get("channel", "")).strip() or ctx.channel
        target = str(arguments.get("target", "")).strip()
        text = str(arguments.get("text", "")).strip()
        if not channel or not target or not text:
            raise ValueError("channel, target and text are required")

        raw_metadata = arguments.get("metadata")
        metadata: dict[str, Any] | None = None
        if raw_metadata is not None:
            if not isinstance(raw_metadata, dict):
                raise ValueError("metadata must be an object")
            metadata = dict(raw_metadata)

        if "buttons" in arguments and arguments.get("buttons") is not None:
            keyboard = self._validate_buttons(arguments.get("buttons"))
            metadata = dict(metadata or {})
            metadata["_telegram_inline_keyboard"] = keyboard

        return await self.api.send(channel=channel, target=target, text=text, metadata=metadata)
