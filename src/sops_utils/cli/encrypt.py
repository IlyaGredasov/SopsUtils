from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from sops_utils.core import encrypt_file, find_env_files
from sops_utils.kubernetes import load_env_values, schema_file_for, write_manifests


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Encrypt env files with SOPS.")
    parser.add_argument(
        "--root-dir", type=Path, default=Path.cwd(), help="Default: current directory."
    )
    parser.add_argument(
        "--with-k8s",
        action="store_true",
        help="Generate Kubernetes manifests.",
    )
    parser.add_argument(
        "--env-schema-file",
        type=Path,
        help="Use one schema for all files; default: env-schema.yaml beside each file.",
    )
    parser.add_argument(
        "--namespace", help="Kubernetes namespace (required with --with-k8s)."
    )
    args = parser.parse_args()
    if args.with_k8s and not args.namespace:
        parser.error("--namespace is required with --with-k8s")
    args.root_dir = args.root_dir.resolve()
    return args


def main() -> int:
    args = parse_arguments()
    if shutil.which("sops") is None:
        print(
            "Error: sops is not installed or is not available on PATH", file=sys.stderr
        )
        return 1
    source_files = find_env_files(args.root_dir, encrypted=False)
    if not source_files:
        print(f"Error: no .env files found under {args.root_dir}", file=sys.stderr)
        return 1
    failed = False
    for source_file in source_files:
        try:
            output_file = source_file.with_name(f"{source_file.name}.enc")
            encrypt_file(source_file, output_file)
            if args.with_k8s:
                schema_file = schema_file_for(source_file, args.env_schema_file)
                base_dir = _k8s_base_dir(args, source_file)
                secret_file = base_dir / "secret.yaml"
                has_secret = write_manifests(
                    *load_env_values(source_file, schema_file),
                    args.root_dir / "infra" / "k8s" / "base" / "namespace.yaml",
                    base_dir / "configmap.yaml",
                    secret_file,
                    args.namespace,
                    _resource_prefix(args, source_file),
                )
                encrypted_secret_file = base_dir / "secret.yaml.enc"
                if has_secret:
                    encrypt_file(secret_file, encrypted_secret_file)
                else:
                    encrypted_secret_file.unlink(missing_ok=True)
        except Exception as error:  # noqa: BLE001
            print(f"Error processing {source_file}: {error}", file=sys.stderr)
            failed = True
    return int(failed)


def _k8s_base_dir(args: argparse.Namespace, source_file: Path) -> Path:
    base_dir = args.root_dir / "infra" / "k8s" / "base"
    if source_file.resolve() != args.root_dir / ".env":
        if source_file.name == ".env":
            return base_dir / source_file.resolve().parent.relative_to(args.root_dir)
        return base_dir / source_file.name.removesuffix(".env")
    return base_dir


def _resource_prefix(args: argparse.Namespace, source_file: Path) -> str | None:
    if source_file.resolve() == args.root_dir / ".env":
        return None
    if source_file.name == ".env":
        return source_file.resolve().parent.name
    return source_file.name.removesuffix(".env")


if __name__ == "__main__":
    main()
