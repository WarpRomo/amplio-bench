from __future__ import annotations

from pathlib import Path
import os


SECRET_ENV_NAMES = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "DAYTONA_API_KEY",
    "DAYTONA_API_TOKEN",
    "GOOGLE_API_KEY",
)

SKIP_PARTS = {".git", "__pycache__"}


def scan_tree(
    root: Path,
) -> dict[str, list[str]]:
    """Find literal configured credential values inside a filesystem tree."""

    secrets = {
        name: os.environ[name]
        for name in SECRET_ENV_NAMES
        if os.environ.get(name)
    }
    hits: dict[str, list[str]] = {}

    for path in Path(root).rglob("*"):
        if (
            not path.is_file()
            or any(
                part in SKIP_PARTS
                for part in path.parts
            )
            or path.suffix == ".pyc"
        ):
            continue

        try:
            content = path.read_bytes()
        except OSError:
            continue

        for name, value in secrets.items():
            if value.encode() in content:
                hits.setdefault(name, []).append(
                    str(path)
                )

    return hits
