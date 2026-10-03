from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import os
import shlex
import shutil
import subprocess
import tomllib


def load_config(path: Path) -> dict:
    with path.open("rb") as f:
        return tomllib.load(f)


def resolve_harbor_bin(config: dict) -> str:
    configured = config["run"].get("harbor_bin", "harbor")
    candidate = os.environ.get("AMPLIO_BENCH_HARBOR", configured)

    # Explicit paths should exist and be executable. Bare commands may resolve via PATH.
    if "/" in candidate:
        path = Path(candidate)
        if not path.is_file() or not os.access(path, os.X_OK):
            raise FileNotFoundError(f"Harbor executable not found or not executable: {candidate}")
        return str(path)

    resolved = shutil.which(candidate)
    if resolved is None:
        raise FileNotFoundError(
            f"Harbor executable {candidate!r} not found. "
            "Set AMPLIO_BENCH_HARBOR=/absolute/path/to/harbor."
        )
    return resolved


def build_harbor_command(
    config: dict,
    task: Path,
    out: Path,
    model: str,
) -> list[str]:
    run = config["run"]
    output = config.get("output", {})

    cmd = [
        resolve_harbor_bin(config),
        "run",
        "--path", str(task),
        "--agent", run["adapter"],
        "--model", model,
        "--env", run.get("environment", "daytona"),
        "--n-attempts", str(run.get("n_attempts", 1)),
        "--n-concurrent", str(run.get("n_concurrent", 1)),
        "--jobs-dir", str(out / output.get("jobs_subdir", "harbor")),
    ]
    if run.get("resume_trajectory", True):
        cmd.append("--resume-trajectory")
    return cmd


def run_evocode(
    config_path: Path,
    task: Path,
    out: Path,
    model: str,
    dry_run: bool = False,
) -> int:
    config = load_config(config_path)
    if not task.is_dir():
        raise ValueError(f"task directory does not exist: {task}")

    out.mkdir(parents=True, exist_ok=True)
    cmd = build_harbor_command(config, task, out, model)

    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "config": str(config_path),
        "task": str(task),
        "model": model,
        "command": cmd,
        "resume_trajectory": config["run"].get("resume_trajectory", True),
    }
    (out / "run_command.json").write_text(json.dumps(manifest, indent=2) + "\n")

    print("COMMAND =", shlex.join(cmd))
    if dry_run:
        return 0

    env = os.environ.copy()
    timeout = config["run"].get("monitor_timeout_sec")
    if timeout is not None:
        env["AMPLIO_MONITOR_TIMEOUT_SEC"] = str(timeout)

    (out / "start_utc.txt").write_text(datetime.now(timezone.utc).isoformat() + "\n")

    with (out / "run.log").open("w") as log:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="")
            log.write(line)
            log.flush()
        rc = proc.wait()

    (out / "harbor_rc.txt").write_text(f"{rc}\n")
    (out / "end_utc.txt").write_text(datetime.now(timezone.utc).isoformat() + "\n")
    return rc
