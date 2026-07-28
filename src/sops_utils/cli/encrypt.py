from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from sops_utils.core import encrypt_file, find_env_files
from sops_utils.kubernetes import load_env_values, write_manifests


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Encrypt an env file with SOPS.")
    parser.add_argument(
        "--root-dir", type=Path, default=Path.cwd(), help="Default: current directory."
    )
    parser.add_argument(
        "--with-k8s",
        action="store_true",
        help="Generate Kubernetes manifests.",
    )
    input_mode = parser.add_mutually_exclusive_group(required=True)
    input_mode.add_argument(
        "--source-file",
        type=Path,
        help="Encrypt one env file.",
    )
    input_mode.add_argument(
        "--project",
        action="store_true",
        help="Encrypt every *.env file under <root-dir>.",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        help="Default: <source-file>.enc (requires --source-file).",
    )
    parser.add_argument(
        "--env-schema-file",
        type=Path,
        help="Default: <root-dir>/env-schema.yaml (requires --source-file).",
    )
    parser.add_argument(
        "--namespace", help="Kubernetes namespace (required with --with-k8s)."
    )
    args = parser.parse_args()
    if args.with_k8s and not args.namespace:
        parser.error("--namespace is required with --with-k8s")
    if args.output_file and not args.source_file:
        parser.error("--output-file requires --source-file")
    if args.env_schema_file and not args.source_file:
        parser.error("--env-schema-file requires --source-file")
    args.root_dir = args.root_dir.resolve()
    if args.source_file:
        args.output_file = args.output_file or args.source_file.with_name(
            f"{args.source_file.name}.enc"
        )
        args.env_schema_file = args.env_schema_file or args.root_dir / "env-schema.yaml"
    return args


def main() -> None:
    args = parse_arguments()
    if shutil.which("sops") is None:
        raise RuntimeError("sops is not installed or is not available on PATH")
    source_files = (
        [args.source_file]
        if args.source_file
        else find_env_files(args.root_dir, encrypted=False)
    )
    if not source_files:
        raise FileNotFoundError(f"No .env files found under {args.root_dir}")
    for source_file in source_files:
        output_file = args.output_file or source_file.with_name(
            f"{source_file.name}.enc"
        )
        encrypt_file(source_file, output_file)
        if args.with_k8s:
            schema_file = args.env_schema_file or source_file.parent / "env-schema.yaml"
            base_dir = _k8s_base_dir(args, source_file)
            secret_file = base_dir / "secret.yaml"
            write_manifests(
                *load_env_values(source_file, schema_file),
                args.root_dir / "infra" / "k8s" / "base" / "namespace.yaml",
                base_dir / "configmap.yaml",
                secret_file,
                args.namespace,
                _resource_prefix(args, source_file),
            )
            encrypt_file(secret_file, base_dir / "secret.enc.yaml")


def _k8s_base_dir(args: argparse.Namespace, source_file: Path) -> Path:
    base_dir = args.root_dir / "infra" / "k8s" / "base"
    if args.project:
        return base_dir / source_file.parent.relative_to(args.root_dir)
    return base_dir


def _resource_prefix(args: argparse.Namespace, source_file: Path) -> str | None:
    return (
        source_file.stem
        if args.project and source_file.parent != args.root_dir
        else None
    )


if __name__ == "__main__":
    main()
