from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from sops_utils.core import encrypt_file, find_env_files
from sops_utils.kubernetes import load_service_definitions, write_service_manifests


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
    processed_files: list[Path] = []
    for source_file in source_files:
        try:
            output_file = source_file.with_name(f"{source_file.name}.enc")
            encrypt_file(source_file, output_file)
            processed_files.append(source_file)
        except Exception as error:  # noqa: BLE001
            print(f"Error processing {source_file}: {error}", file=sys.stderr)
            failed = True
    if args.with_k8s:
        failed = _generate_k8s_manifests(args, processed_files) or failed
    return int(failed)


def _generate_k8s_manifests(args: argparse.Namespace, source_files: list[Path]) -> bool:
    try:
        services = load_service_definitions(
            args.root_dir / "service-schema.yaml", args.root_dir
        )
    except Exception as error:  # noqa: BLE001
        print(f"Error loading service-schema.yaml: {error}", file=sys.stderr)
        return True

    referenced_files = {
        env_file for env_files in services.values() for env_file in env_files
    }
    available_files = set(source_files)
    service_groups = []
    failed = False
    for name, env_files in services.items():
        if _report_unavailable_service_files(name, env_files, available_files):
            failed = True
        else:
            service_groups.append((name, env_files))
    manifest_groups = service_groups + [
        (_resource_prefix(args, env_file), [env_file])
        for env_file in source_files
        if env_file not in referenced_files
    ]
    for name, env_files in manifest_groups:
        try:
            base_dir = args.root_dir / "infra" / "k8s" / "base"
            if name is not None:
                base_dir /= name
            secret_file = write_service_manifests(
                env_files,
                args.root_dir / "infra" / "k8s" / "base" / "namespace.yaml",
                base_dir,
                args.namespace,
                name or args.namespace,
                args.env_schema_file,
            )
            encrypted_secret_file = base_dir / "secret.yaml.enc"
            if secret_file is not None:
                encrypt_file(secret_file, encrypted_secret_file)
            else:
                encrypted_secret_file.unlink(missing_ok=True)
        except Exception as error:  # noqa: BLE001
            print(f"Error generating manifests for {name}: {error}", file=sys.stderr)
            failed = True
    return failed


def _report_unavailable_service_files(
    name: str, env_files: list[Path], available_files: set[Path]
) -> bool:
    unavailable_files = sorted(set(env_files) - available_files)
    if not unavailable_files:
        return False
    print(
        f"Error generating manifests for {name}: env files were not processed: "
        f"{', '.join(str(path) for path in unavailable_files)}",
        file=sys.stderr,
    )
    return True


def _resource_prefix(args: argparse.Namespace, source_file: Path) -> str | None:
    if source_file.resolve() == args.root_dir / ".env":
        return None
    if source_file.name == ".env":
        return source_file.resolve().parent.name
    return source_file.name.removesuffix(".env")


if __name__ == "__main__":
    main()
