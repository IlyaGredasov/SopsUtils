from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from sops_utils.core import encrypt_file
from sops_utils.kubernetes import load_env_values, write_manifests


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Encrypt an env file with SOPS.")
    parser.add_argument(
        "--root-dir", type=Path, default=Path.cwd(), help="Default: current directory."
    )
    parser.add_argument(
        "--with-k8s",
        action="store_true",
        help="Generate manifests in <root-dir>/infra/k8s/base.",
    )
    parser.add_argument(
        "--source-file", type=Path, help="Default: <root-dir>/.env."
    )
    parser.add_argument(
        "--output-file", type=Path, help="Default: <root-dir>/.env.enc."
    )
    parser.add_argument(
        "--env-schema-file", type=Path, help="Default: <root-dir>/env-schema.yaml."
    )
    parser.add_argument(
        "--namespace", help="Kubernetes namespace (required with --with-k8s)."
    )
    args = parser.parse_args()
    if args.with_k8s and not args.namespace:
        parser.error("--namespace is required with --with-k8s")
    args.root_dir = args.root_dir.resolve()
    args.source_file = args.source_file or args.root_dir / ".env"
    args.output_file = args.output_file or args.root_dir / ".env.enc"
    args.env_schema_file = args.env_schema_file or args.root_dir / "env-schema.yaml"
    return args


def main() -> None:
    args = parse_arguments()
    if shutil.which("sops") is None:
        raise RuntimeError("sops is not installed or is not available on PATH")
    encrypt_file(args.source_file, args.output_file)
    if args.with_k8s:
        values, schema = load_env_values(args.source_file, args.env_schema_file)
        base_dir = args.root_dir / "infra" / "k8s" / "base"
        secret_file = base_dir / "secret.yaml"
        write_manifests(
            values, schema, base_dir / "configmap.yaml", secret_file, args.namespace
        )
        encrypt_file(secret_file, base_dir / "secret.enc.yaml")


if __name__ == "__main__":
    main()
