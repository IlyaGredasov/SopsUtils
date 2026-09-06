from __future__ import annotations

import json
from pathlib import Path

import yaml
from dotenv import dotenv_values

VALID_TYPES = frozenset({"global", "config", "secret"})


def schema_file_for(env_file: Path, explicit_schema_file: Path | None = None) -> Path:
    if explicit_schema_file is not None:
        return explicit_schema_file
    if env_file.name == ".env":
        return env_file.parent / "env-schema.yaml"
    return env_file.with_name(f"{env_file.name.removesuffix('.env')}-env-schema.yaml")


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


def load_service_definitions(path: Path, root_dir: Path) -> dict[str, list[Path]]:
    if not path.is_file():
        return {}
    raw_definitions = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw_definitions, dict):
        raise TypeError("Service schema must contain a mapping")
    definitions = raw_definitions.get("services", raw_definitions)
    if not isinstance(definitions, dict):
        raise TypeError("'services' must be a mapping")

    root_dir = root_dir.resolve()
    services: dict[str, list[Path]] = {}
    for name, definition in definitions.items():
        if not isinstance(name, str) or not isinstance(definition, dict):
            raise TypeError("Each service definition must be a mapping")
        unknown_fields = set(definition) - {"env_file", "env_files"}
        env_files = definition.get("env_files", definition.get("env_file"))
        if unknown_fields or not isinstance(env_files, list) or not env_files:
            raise ValueError(f"Service '{name}' must contain a non-empty env_file list")

        resolved_files: list[Path] = []
        for env_file in env_files:
            if not isinstance(env_file, str):
                raise TypeError(f"Service '{name}' env_file entries must be strings")
            resolved_file = (root_dir / env_file).resolve()
            try:
                resolved_file.relative_to(root_dir)
            except ValueError as error:
                raise ValueError(
                    f"Service '{name}' env file must be inside {root_dir}: {env_file}"
                ) from error
            if resolved_file.suffix != ".env" or not resolved_file.is_file():
                raise FileNotFoundError(
                    f"Service '{name}' env file not found: {env_file}"
                )
            resolved_files.append(resolved_file)
        services[name] = resolved_files
    return services


def write_service_manifests(
    env_files: list[Path],
    namespace_file: Path,
    base_dir: Path,
    namespace: str,
    resource_prefix: str,
    explicit_schema_file: Path | None = None,
) -> Path | None:
    values, schema = _combine_env_values(env_files, explicit_schema_file)
    secret_file = base_dir / "secret.yaml"
    has_secret = write_manifests(
        values,
        schema,
        namespace_file,
        base_dir / "configmap.yaml",
        secret_file,
        namespace,
        resource_prefix,
    )
    return secret_file if has_secret else None


def _combine_env_values(
    env_files: list[Path], explicit_schema_file: Path | None
) -> tuple[dict[str, str], dict[str, str]]:
    combined_values: dict[str, str] = {}
    combined_schema: dict[str, str] = {}
    for env_file in env_files:
        values, schema = load_env_values(
            env_file, schema_file_for(env_file, explicit_schema_file)
        )
        duplicate_names = sorted(set(combined_values) & set(values))
        if duplicate_names:
            raise ValueError(
                f"Variables defined more than once: {', '.join(duplicate_names)}"
            )
        combined_values.update(values)
        combined_schema.update(schema)
    return combined_values, combined_schema


def write_manifests(
    values: dict[str, str],
    schema: dict[str, str],
    namespace_file: Path,
    configmap_file: Path,
    secret_file: Path,
    namespace: str,
    resource_prefix: str | None = None,
) -> bool:
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
    if config_values:
        configmap_file.write_text(
            _render("ConfigMap", f"{resource_prefix}-config", namespace, config_values),
            encoding="utf-8",
        )
    else:
        configmap_file.unlink(missing_ok=True)
    if secret_values:
        secret_file.write_text(
            _render("Secret", f"{resource_prefix}-secrets", namespace, secret_values),
            encoding="utf-8",
        )
    else:
        secret_file.unlink(missing_ok=True)
    return bool(secret_values)


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
