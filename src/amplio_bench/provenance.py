from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json
import subprocess


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(block)
    return digest.hexdigest()


def tree_hash(
    root: Path,
) -> tuple[str, dict[str, str]]:
    root = Path(root)
    digest = hashlib.sha256()
    entries: dict[str, str] = {}

    for path in sorted(
        item
        for item in root.rglob("*")
        if item.is_file()
    ):
        relative = path.relative_to(root).as_posix()
        file_hash = sha256_file(path)
        entries[relative] = file_hash
        digest.update(
            relative.encode()
            + b"\0"
            + file_hash.encode()
            + b"\n"
        )

    return digest.hexdigest(), entries


def git_sha(path: Path) -> str:
    return subprocess.check_output(
        [
            "git",
            "-C",
            str(path),
            "rev-parse",
            "HEAD",
        ],
        text=True,
    ).strip()


def build_manifest(
    task_dir: Path,
    adapter: Path,
    repos: dict[str, Path],
) -> dict[str, Any]:
    task_hash, files = tree_hash(task_dir)
    return {
        "created_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "task_dir": str(task_dir),
        "task_tree_sha256": task_hash,
        "task_file_count": len(files),
        "task_file_hashes": files,
        "adapter": str(adapter),
        "adapter_sha256": sha256_file(adapter),
        "repos": {
            name: git_sha(path)
            for name, path in repos.items()
        },
    }


def write_manifest(
    manifest: dict[str, Any],
    out: Path,
) -> None:
    Path(out).write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
