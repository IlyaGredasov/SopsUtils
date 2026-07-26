from __future__ import annotations

import argparse
from pathlib import Path

from sops_utils.core import encrypt_file
from sops_utils.kubernetes import load_env_values, write_manifests


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate encrypted Kubernetes configuration."
    )
    parser.add_argument("--root-dir", type=Path, default=Path.cwd())
    parser.add_argument("--source-file", type=Path)
    parser.add_argument("--k8s-base-dir", type=Path)
    parser.add_argument("--configmap-file", type=Path)
    parser.add_argument("--secret-file", type=Path)
    parser.add_argument("--enc-secret-file", type=Path)
    parser.add_argument("--env-schema-file", type=Path)
    parser.add_argument("--namespace", default="riddoc")
    args = parser.parse_args()
    args.root_dir = args.root_dir.resolve()
    args.source_file = args.source_file or args.root_dir / ".env"
    args.k8s_base_dir = args.k8s_base_dir or args.root_dir / "infra" / "k8s" / "base"
    args.configmap_file = args.configmap_file or args.k8s_base_dir / "configmap.yaml"
    args.secret_file = args.secret_file or args.k8s_base_dir / "secret.yaml"
    args.enc_secret_file = args.enc_secret_file or args.k8s_base_dir / "secret.enc.yaml"
    args.env_schema_file = args.env_schema_file or args.root_dir / "env-schema.yaml"
    return args


def main() -> None:
    args = parse_arguments()
    values, schema = load_env_values(args.source_file, args.env_schema_file)
    write_manifests(
        values, schema, args.configmap_file, args.secret_file, args.namespace
    )
    encrypt_file(args.secret_file, args.enc_secret_file)


if __name__ == "__main__":
    main()
