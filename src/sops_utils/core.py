from __future__ import annotations

import os
import subprocess
import tempfile
from contextlib import suppress
from pathlib import Path


class SopsError(RuntimeError):
    """Raised when the SOPS command cannot process a file."""


def encrypt_file(source_file: Path, output_file: Path) -> None:
    command = ["sops", "--encrypt"]
    if source_file.suffix == ".env":
        command.extend(["--input-type", "dotenv", "--output-type", "dotenv"])
    command.append(str(source_file))
    _run_to_file(command, output_file)


def decrypt_file(source_file: Path, output_file: Path, age_key_file: Path) -> None:
    command = [
        "sops",
        "--decrypt",
        "--input-type",
        "dotenv",
        "--output-type",
        "dotenv",
        str(source_file),
    ]
    environment = os.environ.copy()
    environment["SOPS_AGE_KEY_FILE"] = str(age_key_file)
    _run_to_file(command, output_file, environment)


def find_env_files(root_dir: Path, encrypted: bool) -> list[Path]:
    pattern = "*.env.enc" if encrypted else "*.env"
    return sorted(path for path in root_dir.rglob(pattern) if path.is_file())


def _run_to_file(
    command: list[str],
    output_file: Path,
    environment: dict[str, str] | None = None,
) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=output_file.parent,
            prefix=f"{output_file.name}.",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            subprocess.run(command, check=True, env=environment, stdout=temporary_file)
        temporary_path.replace(output_file)
    except subprocess.CalledProcessError as error:
        if temporary_path is not None:
            with suppress(OSError):
                temporary_path.unlink()
        raise SopsError(f"SOPS failed with exit code {error.returncode}") from None
    except BaseException:
        if temporary_path is not None:
            with suppress(OSError):
                temporary_path.unlink()
        raise
