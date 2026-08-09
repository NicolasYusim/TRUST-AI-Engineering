from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def relative_label(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _reject_non_json_constant(value: str) -> None:
    raise ValueError(f"non-JSON numeric constant {value!r}")


def load_json_yaml(path: Path, root: Path) -> Any:
    """Load the strict JSON subset of YAML used by normative repository files."""

    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=_reject_non_json_constant,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(
            f"{relative_label(path, root)}: invalid strict JSON-compatible YAML: {exc}"
        ) from exc


def dotted_get(value: dict[str, Any], dotted: str) -> Any:
    current: Any = value
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(dotted)
        current = current[part]
    return current


def resolve_ref(schema_root: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValueError(f"unsupported schema reference: {ref}")
    current: Any = schema_root
    for part in ref[2:].split("/"):
        current = current[part.replace("~1", "/").replace("~0", "~")]
    if not isinstance(current, dict):
        raise ValueError(f"schema reference does not resolve to an object: {ref}")
    return current


def validate_schema(
    value: Any,
    schema: dict[str, Any],
    schema_root: dict[str, Any],
    path: str = "$",
) -> list[str]:
    """Validate the deliberately small JSON Schema subset used by this repository."""

    if "$ref" in schema:
        return validate_schema(
            value,
            resolve_ref(schema_root, schema["$ref"]),
            schema_root,
            path,
        )

    errors: list[str] = []
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected constant {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} is not one of {schema['enum']!r}")

    expected_type = schema.get("type")
    type_ok = True
    if expected_type == "object":
        type_ok = isinstance(value, dict)
    elif expected_type == "array":
        type_ok = isinstance(value, list)
    elif expected_type == "string":
        type_ok = isinstance(value, str)
    elif expected_type == "boolean":
        type_ok = isinstance(value, bool)
    elif expected_type == "number":
        type_ok = (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
        )
    elif expected_type == "integer":
        type_ok = isinstance(value, int) and not isinstance(value, bool)

    if expected_type and not type_ok:
        return [f"{path}: expected {expected_type}, got {type(value).__name__}"]

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: missing required field {key!r}")
        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for key, item in value.items():
            child_path = f"{path}.{key}"
            if key in properties:
                errors.extend(
                    validate_schema(item, properties[key], schema_root, child_path)
                )
            elif additional is False:
                errors.append(f"{child_path}: additional property is not allowed")
            elif isinstance(additional, dict):
                errors.extend(
                    validate_schema(item, additional, schema_root, child_path)
                )
        minimum_properties = schema.get("minProperties")
        if minimum_properties is not None and len(value) < minimum_properties:
            errors.append(
                f"{path}: requires at least {minimum_properties} properties"
            )

    if isinstance(value, list):
        minimum_items = schema.get("minItems")
        if minimum_items is not None and len(value) < minimum_items:
            errors.append(f"{path}: requires at least {minimum_items} items")
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, sort_keys=True) for item in value]
            if len(encoded) != len(set(encoded)):
                errors.append(f"{path}: items must be unique")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(
                    validate_schema(
                        item,
                        item_schema,
                        schema_root,
                        f"{path}[{index}]",
                    )
                )

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: string is too short")
        pattern = schema.get("pattern")
        if pattern and not re.search(pattern, value):
            errors.append(f"{path}: does not match {pattern!r}")
        if schema.get("format") == "uri":
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                errors.append(f"{path}: expected an HTTP(S) URI")
        if schema.get("format") == "date":
            try:
                dt.date.fromisoformat(value)
            except ValueError:
                errors.append(f"{path}: expected an ISO date")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(value):
            errors.append(f"{path}: numeric value must be finite")
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: must be >= {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: must be <= {schema['maximum']}")

    return errors


def repository_file(root: Path, relative: str) -> tuple[Path | None, str | None]:
    if not isinstance(relative, str):
        return None, "path must be a string"
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None, "path escapes the repository"
    if not candidate.exists():
        return None, "path does not exist"
    if not candidate.is_file():
        return None, "path is not a regular file"
    return candidate, None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
