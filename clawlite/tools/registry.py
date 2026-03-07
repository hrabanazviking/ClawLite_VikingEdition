from __future__ import annotations

from typing import Any

from clawlite.config.schema import ToolSafetyPolicyConfig
from clawlite.tools.base import Tool, ToolContext


class ToolRegistry:
    def __init__(self, *, safety: ToolSafetyPolicyConfig | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        self._safety = safety or ToolSafetyPolicyConfig()

    @staticmethod
    def _apply_layer(
        *,
        target_risky_tools: list[str],
        target_blocked_channels: list[str],
        target_allowed_channels: list[str],
        layer: Any,
    ) -> tuple[list[str], list[str], list[str]]:
        risky_tools = target_risky_tools
        blocked_channels = target_blocked_channels
        allowed_channels = target_allowed_channels
        if layer is None:
            return risky_tools, blocked_channels, allowed_channels
        if layer.risky_tools is not None:
            risky_tools = list(layer.risky_tools)
        if layer.blocked_channels is not None:
            blocked_channels = list(layer.blocked_channels)
        if layer.allowed_channels is not None:
            allowed_channels = list(layer.allowed_channels)
        return risky_tools, blocked_channels, allowed_channels

    @staticmethod
    def _derive_agent_from_session(session_id: str) -> str:
        raw = str(session_id or "").strip().lower()
        if not raw.startswith("agent:"):
            return ""
        parts = raw.split(":")
        if len(parts) < 3:
            return ""
        return parts[1].strip()

    def _resolve_effective_safety(self, *, session_id: str, channel: str) -> tuple[str, list[str], list[str], list[str]]:
        resolved_channel = str(channel or "").strip().lower() or self._derive_channel_from_session(session_id)
        resolved_agent = self._derive_agent_from_session(session_id)

        risky_tools = list(self._safety.risky_tools)
        blocked_channels = list(self._safety.blocked_channels)
        allowed_channels = list(self._safety.allowed_channels)

        selected_profile = str(self._safety.profile or "").strip().lower()
        if selected_profile:
            profile_layer = self._safety.profiles.get(selected_profile)
            risky_tools, blocked_channels, allowed_channels = self._apply_layer(
                target_risky_tools=risky_tools,
                target_blocked_channels=blocked_channels,
                target_allowed_channels=allowed_channels,
                layer=profile_layer,
            )

        if resolved_agent:
            agent_layer = self._safety.by_agent.get(resolved_agent)
            risky_tools, blocked_channels, allowed_channels = self._apply_layer(
                target_risky_tools=risky_tools,
                target_blocked_channels=blocked_channels,
                target_allowed_channels=allowed_channels,
                layer=agent_layer,
            )

        if resolved_channel:
            channel_layer = self._safety.by_channel.get(resolved_channel)
            risky_tools, blocked_channels, allowed_channels = self._apply_layer(
                target_risky_tools=risky_tools,
                target_blocked_channels=blocked_channels,
                target_allowed_channels=allowed_channels,
                layer=channel_layer,
            )

        return resolved_channel, risky_tools, blocked_channels, allowed_channels

    @staticmethod
    def _is_blocked_by_safety(*, tool_name: str, channel: str, risky_tools: list[str], blocked_channels: list[str], allowed_channels: list[str]) -> bool:
        normalized_tool = str(tool_name or "").strip().lower()
        if normalized_tool not in risky_tools:
            return False
        normalized_channel = str(channel or "").strip().lower()
        if not normalized_channel:
            return False
        if normalized_channel in allowed_channels:
            return False
        return normalized_channel in blocked_channels

    @staticmethod
    def _derive_channel_from_session(session_id: str) -> str:
        raw = str(session_id or "").strip().lower()
        if not raw:
            return ""
        if ":" not in raw:
            return ""
        return raw.split(":", 1)[0].strip()

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def replace(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def schema(self) -> list[dict[str, Any]]:
        return [self._tools[name].export_schema() for name in sorted(self._tools.keys())]

    @staticmethod
    def _matches_schema_type(value: Any, expected_type: str) -> bool:
        normalized = str(expected_type or "").strip().lower()
        if normalized == "string":
            return isinstance(value, str)
        if normalized == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if normalized == "number":
            return (isinstance(value, int) and not isinstance(value, bool)) or isinstance(value, float)
        if normalized == "boolean":
            return isinstance(value, bool)
        if normalized == "object":
            return isinstance(value, dict)
        if normalized == "array":
            return isinstance(value, list)
        if normalized == "null":
            return value is None
        return True

    @classmethod
    def _format_validation_error(cls, *, path: str, reason: str) -> str:
        clean_reason = str(reason or "").strip()
        if not clean_reason:
            return ""
        clean_path = str(path or "").strip()
        return f"{clean_path}:{clean_reason}" if clean_path else clean_reason

    @classmethod
    def _child_schema_path(cls, path: str, fragment: str) -> str:
        clean_fragment = str(fragment or "").strip()
        if not clean_fragment:
            return str(path or "").strip()
        clean_path = str(path or "").strip()
        if not clean_path:
            return clean_fragment
        if clean_fragment.startswith("["):
            return f"{clean_path}{clean_fragment}"
        return f"{clean_path}.{clean_fragment}"

    @classmethod
    def _validate_schema_value(cls, value: Any, schema: dict[str, Any], *, path: str = "") -> str:
        if not isinstance(schema, dict):
            return ""

        raw_type = schema.get("type")
        accepted_types = raw_type if isinstance(raw_type, list) else [raw_type] if raw_type is not None else []
        normalized_types = [str(item or "").strip().lower() for item in accepted_types if str(item or "").strip()]
        if normalized_types and not any(cls._matches_schema_type(value, item) for item in normalized_types):
            return cls._format_validation_error(path=path, reason=f"expected_{'_or_'.join(normalized_types)}")

        enum_values = schema.get("enum")
        if isinstance(enum_values, list) and enum_values and value not in enum_values:
            return cls._format_validation_error(path=path, reason="value_not_allowed")

        if value is None:
            return ""

        min_length = schema.get("minLength")
        if min_length is not None and isinstance(value, str):
            try:
                if len(value) < int(min_length):
                    return cls._format_validation_error(path=path, reason=f"min_length_{min_length}")
            except Exception:
                return cls._format_validation_error(path=path, reason="invalid_min_length")

        max_length = schema.get("maxLength")
        if max_length is not None and isinstance(value, str):
            try:
                if len(value) > int(max_length):
                    return cls._format_validation_error(path=path, reason=f"max_length_{max_length}")
            except Exception:
                return cls._format_validation_error(path=path, reason="invalid_max_length")

        minimum = schema.get("minimum")
        if minimum is not None and isinstance(value, (int, float)) and not isinstance(value, bool):
            try:
                if value < minimum:
                    return cls._format_validation_error(path=path, reason=f"minimum_{minimum}")
            except Exception:
                return cls._format_validation_error(path=path, reason="invalid_minimum")

        maximum = schema.get("maximum")
        if maximum is not None and isinstance(value, (int, float)) and not isinstance(value, bool):
            try:
                if value > maximum:
                    return cls._format_validation_error(path=path, reason=f"maximum_{maximum}")
            except Exception:
                return cls._format_validation_error(path=path, reason="invalid_maximum")

        if isinstance(value, list):
            min_items = schema.get("minItems")
            if min_items is not None:
                try:
                    if len(value) < int(min_items):
                        return cls._format_validation_error(path=path, reason=f"min_items_{min_items}")
                except Exception:
                    return cls._format_validation_error(path=path, reason="invalid_min_items")

            max_items = schema.get("maxItems")
            if max_items is not None:
                try:
                    if len(value) > int(max_items):
                        return cls._format_validation_error(path=path, reason=f"max_items_{max_items}")
                except Exception:
                    return cls._format_validation_error(path=path, reason="invalid_max_items")

            items_schema = schema.get("items")
            if isinstance(items_schema, dict):
                for index, item in enumerate(value):
                    nested_error = cls._validate_schema_value(
                        item,
                        items_schema,
                        path=cls._child_schema_path(path, f"[{index}]"),
                    )
                    if nested_error:
                        return nested_error

        if isinstance(value, dict):
            properties = schema.get("properties", {})
            property_schemas = properties if isinstance(properties, dict) else {}
            required = schema.get("required", [])
            if isinstance(required, list):
                missing = [
                    str(item).strip()
                    for item in required
                    if str(item).strip() and str(item).strip() not in value
                ]
                if missing:
                    return cls._format_validation_error(
                        path=path,
                        reason=f"missing_required:{','.join(sorted(missing))}",
                    )

            additional_properties = schema.get("additionalProperties", True)
            if additional_properties is False:
                unexpected = sorted(str(key).strip() for key in value.keys() if key not in property_schemas)
                if unexpected:
                    return cls._format_validation_error(
                        path=path,
                        reason=f"unexpected_arguments:{','.join(unexpected)}",
                    )

            for key, item in value.items():
                child_schema = property_schemas.get(key)
                if not isinstance(child_schema, dict):
                    continue
                nested_error = cls._validate_schema_value(
                    item,
                    child_schema,
                    path=cls._child_schema_path(path, str(key).strip()),
                )
                if nested_error:
                    return nested_error

        return ""

    @classmethod
    def _validate_arguments(cls, tool: Tool, arguments: Any) -> dict[str, Any]:
        if not isinstance(arguments, dict):
            raise RuntimeError(f"tool_invalid_arguments:{tool.name}:expected_object")

        schema = tool.args_schema()
        if not isinstance(schema, dict):
            return dict(arguments)

        schema_type = str(schema.get("type", "") or "").strip().lower()
        if schema_type and schema_type != "object":
            return dict(arguments)

        required = schema.get("required", [])
        if isinstance(required, list):
            missing = [str(item).strip() for item in required if str(item).strip() and str(item).strip() not in arguments]
            if missing:
                raise RuntimeError(
                    f"tool_invalid_arguments:{tool.name}:missing_required:{','.join(sorted(missing))}"
                )

        properties = schema.get("properties", {})
        property_schemas = properties if isinstance(properties, dict) else {}
        additional_properties = schema.get("additionalProperties", True)
        if additional_properties is False:
            unexpected = sorted(str(key).strip() for key in arguments.keys() if key not in property_schemas)
            if unexpected:
                raise RuntimeError(
                    f"tool_invalid_arguments:{tool.name}:unexpected_arguments:{','.join(unexpected)}"
                )

        for key, value in arguments.items():
            property_schema = property_schemas.get(key)
            if not isinstance(property_schema, dict):
                continue
            validation_error = cls._validate_schema_value(value, property_schema, path=str(key).strip())
            if validation_error:
                raise RuntimeError(f"tool_invalid_arguments:{tool.name}:{validation_error}")

        return dict(arguments)

    async def execute(self, name: str, arguments: dict[str, Any], *, session_id: str, channel: str = "", user_id: str = "") -> str:
        tool = self.get(name)
        if tool is None:
            raise KeyError(f"unknown tool: {name}")
        validated_arguments = self._validate_arguments(tool, arguments)

        resolved_channel, risky_tools, blocked_channels, allowed_channels = self._resolve_effective_safety(
            session_id=session_id,
            channel=channel,
        )
        normalized_tool = str(name or "").strip().lower()
        has_channel_restrictions = bool(allowed_channels or blocked_channels)

        if not resolved_channel and self._safety.enabled and normalized_tool in risky_tools and has_channel_restrictions:
            raise RuntimeError(f"tool_blocked_by_safety_policy:{name}:unknown")
        if self._safety.enabled and self._is_blocked_by_safety(
            tool_name=name,
            channel=resolved_channel,
            risky_tools=risky_tools,
            blocked_channels=blocked_channels,
            allowed_channels=allowed_channels,
        ):
            raise RuntimeError(f"tool_blocked_by_safety_policy:{name}:{resolved_channel}")
        return await tool.run(validated_arguments, ToolContext(session_id=session_id, channel=resolved_channel, user_id=user_id))
