from __future__ import annotations

import json
from pathlib import Path

import yaml
from dotenv import dotenv_values

VALID_TYPES = frozenset({"global", "config", "secret"})


def load_env_values(
    path: Path, schema_file: Path
) -> tuple[dict[str, str], dict[str, str]]:
    raw_values = dotenv_values(path)
    values = {name: value for name, value in raw_values.items() if value is not None}
    empty = sorted(set(raw_values) - set(values))
    if empty:
        raise ValueError(f"Variables without values: {', '.join(empty)}")

    schema = _load_schema(schema_file)
    unknown = sorted(set(values) - set(schema))
    if unknown:
        raise ValueError(f"Variables without a type: {', '.join(unknown)}")
    return values, schema


def write_manifests(
    values: dict[str, str],
    schema: dict[str, str],
    configmap_file: Path,
    secret_file: Path,
    namespace: str,
) -> None:
    configmap_file.parent.mkdir(parents=True, exist_ok=True)
    config_values = {
        name: value for name, value in values.items() if schema[name] == "config"
    }
    secret_values = {
        name: value for name, value in values.items() if schema[name] == "secret"
    }
    configmap_file.write_text(
        _render("ConfigMap", f"{namespace}-config", namespace, config_values),
        encoding="utf-8",
    )
    secret_file.write_text(
        _render("Secret", f"{namespace}-secrets", namespace, secret_values),
        encoding="utf-8",
    )


def _load_schema(path: Path) -> dict[str, str]:
    raw_schema = yaml.safe_load(path.read_text(encoding="utf-8"))
    variables = raw_schema.get("variables") if isinstance(raw_schema, dict) else None
    if not isinstance(variables, dict):
        raise TypeError("Schema must contain a 'variables' mapping")
    invalid = sorted(
        name for name, value in variables.items() if value not in VALID_TYPES
    )
    if invalid:
        raise ValueError(f"Variables with invalid types: {', '.join(invalid)}")
    return dict(variables)


def _render(kind: str, name: str, namespace: str, data: dict[str, str]) -> str:
    rendered_data = "\n".join(
        f"  {key}: {json.dumps(value)}" for key, value in sorted(data.items())
    )
    return (
        "apiVersion: v1\n"
        f"kind: {kind}\nmetadata:\n  name: {name}\n  namespace: {namespace}\n"
        + ("type: Opaque\nstringData:\n" if kind == "Secret" else "data:\n")
        + rendered_data
        + "\n"
    )
