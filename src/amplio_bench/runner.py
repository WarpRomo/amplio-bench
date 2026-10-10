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


def build_process_env(
    config: dict,
    config_path: Path | None = None,
) -> dict[str, str]:
    """Build the Harbor process environment for one benchmark run."""

    env = os.environ.copy()
    run = config["run"]

    timeout = run.get("monitor_timeout_sec")
    if timeout is not None:
        env["AMPLIO_MONITOR_TIMEOUT_SEC"] = str(timeout)

    briefings = run.get("briefings", [])
    if not isinstance(briefings, list) or not all(
        isinstance(name, str) and name for name in briefings
    ):
        raise ValueError("run.briefings must be a list of non-empty strings")
    if briefings:
        env["AMPLIO_BENCH_BRIEFINGS_JSON"] = json.dumps(briefings)
    else:
        env.pop("AMPLIO_BENCH_BRIEFINGS_JSON", None)

    briefing_files = run.get("briefing_files", [])
    if not isinstance(briefing_files, list) or not all(
        isinstance(path, str) and path for path in briefing_files
    ):
        raise ValueError("run.briefing_files must be a list of non-empty paths")

    resolved_briefing_files: list[str] = []
    for value in briefing_files:
        path = Path(value).expanduser()
        if not path.is_absolute():
            if config_path is None:
                raise ValueError(
                    "relative run.briefing_files require the config path"
                )
            path = config_path.parent / path
        path = path.resolve()
        if not path.is_file():
            raise FileNotFoundError(f"briefing file not found: {path}")
        resolved_briefing_files.append(str(path))

    if resolved_briefing_files:
        env["AMPLIO_BENCH_BRIEFING_FILES_JSON"] = json.dumps(
            resolved_briefing_files
        )
    else:
        env.pop("AMPLIO_BENCH_BRIEFING_FILES_JSON", None)

    require_from = run.get("require_subagent_from_round")
    if require_from is not None:
        if not isinstance(require_from, int) or require_from < 1:
            raise ValueError("run.require_subagent_from_round must be >= 1")
        env["AMPLIO_BENCH_REQUIRE_SUBAGENT_FROM_ROUND"] = str(require_from)
    else:
        env.pop("AMPLIO_BENCH_REQUIRE_SUBAGENT_FROM_ROUND", None)

    enforcement = run.get("subagent_enforcement_message")
    if enforcement is not None:
        if not isinstance(enforcement, str) or not enforcement.strip():
            raise ValueError(
                "run.subagent_enforcement_message must be a non-empty string"
            )
        env["AMPLIO_BENCH_SUBAGENT_ENFORCEMENT_MESSAGE"] = enforcement.strip()
    else:
        env.pop("AMPLIO_BENCH_SUBAGENT_ENFORCEMENT_MESSAGE", None)

    bool_controls = {
        "force_subagent_enforcement": "AMPLIO_BENCH_FORCE_SUBAGENT_ENFORCEMENT",
        "require_completed_subagent": "AMPLIO_BENCH_REQUIRE_COMPLETED_SUBAGENT",
        "recover_tool_transport_failures": "AMPLIO_BENCH_RECOVER_TOOL_TRANSPORT_FAILURES",
    }
    for key, env_name in bool_controls.items():
        value = run.get(key, False)
        if not isinstance(value, bool):
            raise ValueError(f"run.{key} must be boolean")
        if value:
            env[env_name] = "1"
        else:
            env.pop(env_name, None)

    return env


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
        "briefings": config["run"].get("briefings", []),
        "briefing_files": config["run"].get("briefing_files", []),
        "require_subagent_from_round": config["run"].get(
            "require_subagent_from_round"
        ),
        "force_subagent_enforcement": config["run"].get(
            "force_subagent_enforcement", False
        ),
        "require_completed_subagent": config["run"].get(
            "require_completed_subagent", False
        ),
        "recover_tool_transport_failures": config["run"].get(
            "recover_tool_transport_failures", False
        ),
    }
    (out / "run_command.json").write_text(json.dumps(manifest, indent=2) + "\n")

    print("COMMAND =", shlex.join(cmd))
    if dry_run:
        return 0

    env = build_process_env(config, config_path)

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
