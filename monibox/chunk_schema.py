from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from monibox.config import KNOWLEDGE_SRC

CHUNK_SCHEMA_PATH = KNOWLEDGE_SRC / "chunk_schema.json"


def load_chunk_schema(path: Path | None = None) -> dict[str, Any]:
    schema_path = path or CHUNK_SCHEMA_PATH
    data = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("chunk_schema.json 根节点必须是对象")
    fields = data.get("fields")
    if not isinstance(fields, list) or not fields:
        raise ValueError("chunk_schema.json 缺少 fields 数组")
    return data


def canonical_field_names(schema: dict[str, Any] | None = None) -> set[str]:
    schema = schema or load_chunk_schema()
    return {
        str(item.get("name") or "").strip()
        for item in schema.get("fields", [])
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    }


def _first_present(chunk: dict[str, Any], names: list[str]) -> Any:
    for name in names:
        if name in chunk and chunk[name] is not None:
            return chunk[name]
    return None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
        return [
            item.strip() for item in text.replace("|", ",").split(",") if item.strip()
        ]
    return [value]


def _coerce_value(value: Any, field_type: str, default: Any = None) -> Any:
    if value is None:
        return deepcopy(default)

    if field_type == "string":
        return str(value).strip()
    if field_type == "string|null":
        text = str(value).strip()
        return text or None
    if field_type == "string[]":
        return [str(item).strip() for item in _as_list(value) if str(item).strip()]
    if field_type == "object[]":
        return [item for item in _as_list(value) if isinstance(item, dict)]
    if field_type == "integer":
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(default or 0)
    if field_type == "number":
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default or 0)
    if field_type == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            text = value.strip().lower()
            if text in {"1", "true", "yes", "y", "on", "是"}:
                return True
            if text in {"0", "false", "no", "n", "off", "否"}:
                return False
        return bool(default)

    return value


def normalize_chunk_fields(
    chunk: dict[str, Any], schema: dict[str, Any] | None = None
) -> dict[str, Any]:
    schema = schema or load_chunk_schema()
    for field in schema.get("fields", []):
        if not isinstance(field, dict):
            continue
        name = str(field.get("name") or "").strip()
        if not name:
            continue
        aliases = [
            str(item).strip()
            for item in field.get("legacy_names") or []
            if str(item).strip()
        ]
        default = field.get("default")
        field_type = str(field.get("type") or "")
        value = _first_present(chunk, [name, *aliases])
        chunk[name] = _coerce_value(value, field_type, default)

        # Keep legacy Chinese fields available for older build and review tools.
        if aliases and aliases[0] not in chunk:
            chunk[aliases[0]] = deepcopy(chunk[name])

    return chunk


def validate_normalized_chunk(
    chunk: dict[str, Any], schema: dict[str, Any] | None = None
) -> list[str]:
    schema = schema or load_chunk_schema()
    errors: list[str] = []
    for field in schema.get("fields", []):
        if not isinstance(field, dict):
            continue
        name = str(field.get("name") or "").strip()
        if not name:
            continue
        value = chunk.get(name)
        field_type = str(field.get("type") or "")
        required = bool(field.get("required"))
        if required and (value is None or value == "" or value == []):
            errors.append(f"{name}:required")
            continue
        if value is None:
            continue
        if field_type == "string" and not isinstance(value, str):
            errors.append(f"{name}:not_string")
        elif field_type == "string|null" and not isinstance(value, str):
            errors.append(f"{name}:not_string_or_null")
        elif field_type == "string[]" and not all(
            isinstance(item, str) for item in value
        ):
            errors.append(f"{name}:not_string_array")
        elif field_type == "object[]" and not all(
            isinstance(item, dict) for item in value
        ):
            errors.append(f"{name}:not_object_array")
        elif field_type == "integer" and not isinstance(value, int):
            errors.append(f"{name}:not_integer")
        elif field_type == "number" and not isinstance(value, (int, float)):
            errors.append(f"{name}:not_number")
        elif field_type == "boolean" and not isinstance(value, bool):
            errors.append(f"{name}:not_boolean")
    return errors

