from __future__ import annotations

import asyncio
import base64
import json
import shlex
from pathlib import Path

from harbor.agents.base import BaseAgent
from harbor.agents.capabilities import AgentCapabilities
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext


REMOTE_ROOT = "/tmp/amplio-eval"
REMOTE_BIN = f"{REMOTE_ROOT}/amplio"
REMOTE_DATA = f"{REMOTE_ROOT}/data"


class AmplioAgent(BaseAgent):
    """Thin Harbor adapter for one persistent Amplio run."""

    capabilities = AgentCapabilities(resume=True)

    @staticmethod
    def name() -> str:
        return "amplio-eval"

    def version(self) -> str | None:
        return "0.1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._run_id: str | None = None
        self._round = 0

    @property
    def _model(self) -> str:
        if not self.model_name:
            raise RuntimeError("AmplioAgent requires --model")
        return self.model_name

    @property
    def _cli(self) -> str:
        return (
            f"{REMOTE_BIN} "
            f"--data-dir={REMOTE_DATA} "
            f"--lesson-search=false"
        )

    async def _exec(
        self,
        environment: BaseEnvironment,
        command: str,
        *,
        timeout: int = 60,
        env: dict[str, str] | None = None,
    ):
        result = await environment.exec(
            command,
            timeout_sec=timeout,
            env=env,
        )
        if result.return_code != 0:
            raise RuntimeError(
                f"command failed ({result.return_code}): {command}\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )
        return result

    async def _put_text(
        self,
        environment: BaseEnvironment,
        path: str,
        text: str,
    ) -> None:
        encoded = base64.b64encode(text.encode()).decode()
        await self._exec(
            environment,
            f"printf %s {shlex.quote(encoded)} | base64 -d > {shlex.quote(path)}",
        )

    async def setup(self, environment: BaseEnvironment) -> None:
        host_bin = self._get_env("AMPLIO_HOST_BIN")
        if not host_bin:
            raise RuntimeError("AMPLIO_HOST_BIN is not set")

        host_bin_path = Path(host_bin)
        if not host_bin_path.is_file():
            raise RuntimeError(f"Amplio binary not found: {host_bin}")

        await self._exec(
            environment,
            f"mkdir -p {REMOTE_ROOT} {REMOTE_DATA} /logs/agent",
        )

        await environment.upload_file(host_bin_path, REMOTE_BIN)
        await self._exec(environment, f"chmod 755 {REMOTE_BIN}")

        model = json.dumps(self._model)

        self.logs_dir.mkdir(parents=True, exist_ok=True)
        config_path = self.logs_dir / "_amplio_eval_config.toml"
        config_path.write_text(
            "\n".join(
                [
                    'listen = "127.0.0.1:26759"',
                    f"system_llm_hq = {model}",
                    f"system_llm_fast = {model}",
                    'embed_model = ""',
                    "",
                    "[run]",
                    f"llms = [{model}]",
                    "",
                    "[lessons]",
                    "search = false",
                    "",
                ]
            )
        )

        await environment.upload_file(
            config_path,
            f"{REMOTE_DATA}/config.toml",
        )

        # The model key stays in the host process environment and is passed
        # only to the Amplio server process inside the sandbox.
        key_env = self._get_env("AMPLIO_API_KEY_ENV") or "OPENAI_API_KEY"
        key_value = self._get_env(key_env)

        server_env = {}
        if key_value:
            server_env[key_env] = key_value

        start = f"""
set -eu

if [ -f {REMOTE_ROOT}/server.pid ] &&
   kill -0 "$(cat {REMOTE_ROOT}/server.pid)" 2>/dev/null; then
    :
else
    nohup {self._cli} serve --listen=127.0.0.1:26759 \
        >{REMOTE_ROOT}/server.log 2>&1 </dev/null &
    echo $! > {REMOTE_ROOT}/server.pid
fi

for i in $(seq 1 60); do
    if {self._cli} client api /api/runs/counts >/dev/null 2>&1; then
        exit 0
    fi
    sleep 0.5
done

echo "Amplio server failed to become ready" >&2
tail -n 120 {REMOTE_ROOT}/server.log >&2 || true
exit 1
"""
        await self._exec(
            environment,
            start,
            timeout=45,
            env=server_env,
        )

    async def _wait(self, environment: BaseEnvironment) -> None:
        assert self._run_id

        monitor_sec = int(
            self._get_env("AMPLIO_MONITOR_TIMEOUT_SEC") or "1700"
        )
        inner_sec = max(10, monitor_sec - 10)

        try:
            await self._exec(
                environment,
                f"{self._cli} client monitor "
                f"--interval=2s --timeout={inner_sec}s "
                f"{shlex.quote(self._run_id)}",
                timeout=monitor_sec,
            )
        except asyncio.CancelledError:
            await environment.exec(
                f"{self._cli} client cancel {shlex.quote(self._run_id)}",
                timeout_sec=30,
            )
            raise
        except Exception:
            # Snapshot API-visible run/session evidence before the ephemeral
            # sandbox disappears, even when the Amplio run crashes.
            try:
                await self._snapshot(environment)
            except Exception:
                pass

            failure_dir = self.logs_dir / "amplio_failure"
            failure_dir.mkdir(parents=True, exist_ok=True)
            try:
                await environment.download_dir(REMOTE_ROOT, failure_dir)
            except Exception:
                pass
            raise

    async def _snapshot(self, environment: BaseEnvironment) -> None:
        assert self._run_id

        prefix = f"/logs/agent/amplio-round-{self._round:02d}"

        # Preserve the complete run topology and every session's raw events.
        # This lets us reconstruct subagent traffic and total token usage later.
        await self._exec(
            environment,
            f"{self._cli} client api /api/runs/{self._run_id} "
            f"> {prefix}-run.json",
            timeout=60,
        )

        await self._exec(
            environment,
            f'''
set -eu
for sid in $(jq -r '.sessions[].session_id' {prefix}-run.json); do
    safe=$(printf '%s' "$sid" | tr -c 'A-Za-z0-9._-' '_')
    {self._cli} client api         "/api/runs/{self._run_id}/sessions/$sid/events"         > "{prefix}-session-${{safe}}-events.json"
done
''',
            timeout=120,
        )

        commands = [
            (
                f"{self._cli} client status --json "
                f"{shlex.quote(self._run_id)} > {prefix}-status.json"
            ),
            (
                f"{self._cli} client api "
                f"/api/runs/{self._run_id}/sessions/main-agent/events "
                f"> {prefix}-events.json"
            ),
            (
                f"{self._cli} client api "
                f"/api/runs/{self._run_id}/sessions/main-agent/chat "
                f"> {prefix}-chat.json"
            ),
            (
                f"printf '%s\\n' {shlex.quote(self._run_id)} "
                f"> /logs/agent/amplio-run-id.txt"
            ),
            (
                f"tail -n 2000 {REMOTE_ROOT}/server.log "
                f"> /logs/agent/amplio-server-tail.log || true"
            ),
        ]

        for command in commands:
            await self._exec(environment, command, timeout=60)

        # Daytona is ephemeral: copy raw Amplio evidence back to Harbor's
        # durable host-side agent log directory after every round.
        raw_dir = self.logs_dir / "amplio_raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        await environment.download_dir("/logs/agent", raw_dir)

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        self._round = 1

        instruction_path = f"{REMOTE_ROOT}/round-01.txt"
        await self._put_text(environment, instruction_path, instruction)

        result = await self._exec(
            environment,
            (
                f"{self._cli} client submit "
                f"--task=- "
                f"--workspace=/app "
                f"--agent=standard_agent "
                f"--llm={shlex.quote(self._model)} "
                f"< {instruction_path}"
            ),
            timeout=60,
        )

        run_id = (result.stdout or "").strip().splitlines()
        if not run_id:
            raise RuntimeError("Amplio submit returned no run id")

        self._run_id = run_id[-1].strip()

        await self._put_text(
            environment,
            f"{REMOTE_ROOT}/run_id",
            self._run_id + "\n",
        )

        await self._wait(environment)
        await self._snapshot(environment)

    async def resume(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        self._round += 1

        if not self._run_id:
            result = await self._exec(
                environment,
                f"cat {REMOTE_ROOT}/run_id",
            )
            self._run_id = (result.stdout or "").strip()

        if not self._run_id:
            raise RuntimeError("missing persistent Amplio run id")

        body_path = f"{REMOTE_ROOT}/round-{self._round:02d}-followup.json"
        body = json.dumps({"content": instruction})

        await self._put_text(environment, body_path, body)

        await self._exec(
            environment,
            (
                f"{self._cli} client api -X POST "
                f"/api/runs/{self._run_id}/sessions/main-agent/message "
                f"--data @{body_path}"
            ),
            timeout=60,
        )

        # Give the commit listener time to wake the concluded session before
        # monitor samples it. Real model turns are much slower than this.
        await asyncio.sleep(1)

        await self._wait(environment)
        await self._snapshot(environment)
