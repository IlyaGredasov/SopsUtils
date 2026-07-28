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

    schema, k8s_values = _load_schema(schema_file)
    unknown = sorted(set(values) - set(schema))
    if unknown:
        raise ValueError(f"Variables without a type: {', '.join(unknown)}")
    values.update(
        {name: k8s_value for name, k8s_value in k8s_values.items() if name in values}
    )
    return values, schema


def write_manifests(
    values: dict[str, str],
    schema: dict[str, str],
    namespace_file: Path,
    configmap_file: Path,
    secret_file: Path,
    namespace: str,
    resource_prefix: str | None = None,
) -> None:
    configmap_file.parent.mkdir(parents=True, exist_ok=True)
    namespace_file.parent.mkdir(parents=True, exist_ok=True)
    namespace_file.write_text(_render_namespace(namespace), encoding="utf-8")
    config_values = {
        name: value for name, value in values.items() if schema[name] == "config"
    }
    secret_values = {
        name: value for name, value in values.items() if schema[name] == "secret"
    }
    resource_prefix = resource_prefix or namespace
    configmap_file.write_text(
        _render("ConfigMap", f"{resource_prefix}-config", namespace, config_values),
        encoding="utf-8",
    )
    secret_file.write_text(
        _render("Secret", f"{resource_prefix}-secrets", namespace, secret_values),
        encoding="utf-8",
    )


def _load_schema(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    raw_schema = yaml.safe_load(path.read_text(encoding="utf-8"))
    variables = raw_schema.get("variables") if isinstance(raw_schema, dict) else None
    if not isinstance(variables, dict):
        raise TypeError("Schema must contain a 'variables' mapping")

    schema: dict[str, str] = {}
    k8s_values: dict[str, str] = {}
    invalid_types: list[str] = []
    invalid_definitions: list[str] = []
    for name, definition in variables.items():
        if isinstance(definition, str):
            variable_type = definition
        elif isinstance(definition, dict):
            variable_type = definition.get("type")
            unknown_fields = set(definition) - {"type", "k8s_value"}
            if unknown_fields or (
                "k8s_value" in definition
                and not isinstance(definition["k8s_value"], str)
            ):
                invalid_definitions.append(name)
                continue
            if "k8s_value" in definition:
                k8s_values[name] = definition["k8s_value"]
        else:
            invalid_definitions.append(name)
            continue

        if variable_type not in VALID_TYPES:
            invalid_types.append(name)
            continue
        schema[name] = variable_type

    if invalid_types:
        raise ValueError(
            f"Variables with invalid types: {', '.join(sorted(invalid_types))}"
        )
    if invalid_definitions:
        raise ValueError(
            "Variables with invalid schema definitions: "
            f"{', '.join(sorted(invalid_definitions))}"
        )
    return schema, k8s_values


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


def _render_namespace(namespace: str) -> str:
    return f"apiVersion: v1\nkind: Namespace\nmetadata:\n  name: {namespace}\n"
