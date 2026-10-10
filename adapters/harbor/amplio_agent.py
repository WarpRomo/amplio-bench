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
    def _briefings(self) -> list[str]:
        raw = self._get_env("AMPLIO_BENCH_BRIEFINGS_JSON")
        if not raw:
            return []
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("AMPLIO_BENCH_BRIEFINGS_JSON is invalid JSON") from exc
        if not isinstance(value, list) or not all(
            isinstance(name, str) and name for name in value
        ):
            raise RuntimeError(
                "AMPLIO_BENCH_BRIEFINGS_JSON must be a JSON list of names"
            )
        return value

    @property
    def _briefing_files(self) -> list[Path]:
        raw = self._get_env("AMPLIO_BENCH_BRIEFING_FILES_JSON")
        if not raw:
            return []
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "AMPLIO_BENCH_BRIEFING_FILES_JSON is invalid JSON"
            ) from exc
        if not isinstance(value, list) or not all(
            isinstance(path, str) and path for path in value
        ):
            raise RuntimeError(
                "AMPLIO_BENCH_BRIEFING_FILES_JSON must be a JSON list of paths"
            )
        paths = [Path(path) for path in value]
        missing = [str(path) for path in paths if not path.is_file()]
        if missing:
            raise RuntimeError(
                "Amplio briefing file(s) not found: " + ", ".join(missing)
            )
        return paths

    @property
    def _require_subagent_from_round(self) -> int | None:
        raw = self._get_env("AMPLIO_BENCH_REQUIRE_SUBAGENT_FROM_ROUND")
        if not raw:
            return None
        try:
            value = int(raw)
        except ValueError as exc:
            raise RuntimeError(
                "AMPLIO_BENCH_REQUIRE_SUBAGENT_FROM_ROUND must be an integer"
            ) from exc
        if value < 1:
            raise RuntimeError(
                "AMPLIO_BENCH_REQUIRE_SUBAGENT_FROM_ROUND must be >= 1"
            )
        return value

    def _bool_env(self, name: str) -> bool:
        raw = (self._get_env(name) or "").strip().lower()
        if not raw:
            return False
        if raw in {"1", "true", "yes", "on"}:
            return True
        if raw in {"0", "false", "no", "off"}:
            return False
        raise RuntimeError(f"{name} must be boolean-like")

    @property
    def _force_subagent_enforcement(self) -> bool:
        return self._bool_env("AMPLIO_BENCH_FORCE_SUBAGENT_ENFORCEMENT")

    @property
    def _require_completed_subagent(self) -> bool:
        return self._bool_env("AMPLIO_BENCH_REQUIRE_COMPLETED_SUBAGENT")

    @property
    def _recover_tool_transport_failures(self) -> bool:
        return self._bool_env("AMPLIO_BENCH_RECOVER_TOOL_TRANSPORT_FAILURES")

    @property
    def _subagent_enforcement_message(self) -> str:
        configured = self._get_env("AMPLIO_BENCH_SUBAGENT_ENFORCEMENT_MESSAGE")
        if configured:
            return configured.replace("{round}", str(self._round))
        return (
            "Benchmark intervention: no fresh reviewer sub-agent was observed "
            f"for adaptation round {self._round}. Before concluding this round, "
            "spawn exactly one fresh sub-agent to independently inspect the "
            "current workspace against the latest instruction and accumulated "
            "requirements. Ask it to identify missed new requirements, stale "
            "assumptions, regressions, and insufficient validation. Wait for "
            "its result, address concrete findings in the workspace, rerun "
            "relevant checks, and only then conclude. Do not delegate the "
            "implementation wholesale and do not recursively spawn reviewers."
        )

    def _briefing_flags(self) -> str:
        return " ".join(
            shlex.quote(f"--briefing={name}") for name in self._briefings
        )

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
            f"mkdir -p {REMOTE_ROOT} {REMOTE_DATA}/briefings /logs/agent",
        )

        for index, briefing_path in enumerate(self._briefing_files, 1):
            remote_name = f"{index:02d}-{briefing_path.name}"
            await environment.upload_file(
                briefing_path,
                f"{REMOTE_DATA}/briefings/{remote_name}",
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

        # A run may silently drop unknown briefing names. Fail before a paid
        # experiment instead, so a configured treatment cannot collapse into
        # the baseline unnoticed.
        if self._briefings:
            response = await self._exec(
                environment,
                f"{self._cli} client api /api/briefings",
                timeout=60,
            )
            try:
                entries = json.loads(response.stdout or "[]")
            except json.JSONDecodeError as exc:
                raise RuntimeError("could not parse Amplio briefing inventory") from exc
            available = {
                str(entry.get("name"))
                for entry in entries
                if isinstance(entry, dict) and entry.get("name")
            }
            missing = [name for name in self._briefings if name not in available]
            if missing:
                raise RuntimeError(
                    "requested Amplio briefing(s) are unavailable in AMPLIO_HOST_BIN: "
                    + ", ".join(missing)
                )

    async def _session_records(
        self,
        environment: BaseEnvironment,
    ) -> dict[str, dict]:
        assert self._run_id
        response = await self._exec(
            environment,
            f"{self._cli} client api /api/runs/{self._run_id}",
            timeout=60,
        )
        try:
            run = json.loads(response.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise RuntimeError("could not parse Amplio run topology") from exc
        sessions = run.get("sessions") or []
        if not isinstance(sessions, list):
            raise RuntimeError("Amplio run topology has invalid sessions array")
        return {
            str(session["session_id"]): session
            for session in sessions
            if isinstance(session, dict) and session.get("session_id")
        }

    async def _subagent_session_ids(
        self,
        environment: BaseEnvironment,
    ) -> set[str]:
        sessions = await self._session_records(environment)
        return {
            sid
            for sid, session in sessions.items()
            if session.get("parent_id")
        }

    async def _post_session_message(
        self,
        environment: BaseEnvironment,
        session_id: str,
        content: str,
        *,
        label: str,
    ) -> None:
        assert self._run_id
        body_path = f"{REMOTE_ROOT}/{label}.json"
        await self._put_text(
            environment,
            body_path,
            json.dumps({"content": content}),
        )
        await self._exec(
            environment,
            (
                f"{self._cli} client api -X POST "
                f"/api/runs/{self._run_id}/sessions/{shlex.quote(session_id)}/message "
                f"--data @{body_path}"
            ),
            timeout=60,
        )
        await asyncio.sleep(1)

    async def _post_root_message(
        self,
        environment: BaseEnvironment,
        content: str,
        *,
        label: str,
    ) -> None:
        await self._post_session_message(
            environment,
            "main-agent",
            content,
            label=label,
        )

    async def _wait_for_session_terminal(
        self,
        environment: BaseEnvironment,
        session_id: str,
        *,
        timeout_sec: int = 600,
        ignore_initial_status: str | None = None,
    ) -> str:
        deadline = asyncio.get_running_loop().time() + timeout_sec
        left_initial_status = ignore_initial_status is None
        while True:
            sessions = await self._session_records(environment)
            session = sessions.get(session_id)
            if session is None:
                raise RuntimeError(f"Amplio session disappeared: {session_id}")
            status = str(session.get("status") or "")
            if ignore_initial_status is not None and status != ignore_initial_status:
                left_initial_status = True
            if left_initial_status and status in {"concluded", "crashed", "cancelled"}:
                return status
            if asyncio.get_running_loop().time() >= deadline:
                raise RuntimeError(
                    f"timed out waiting for Amplio session {session_id}: {status}"
                )
            await asyncio.sleep(1)

    async def _child_result_has_root_followup(
        self,
        environment: BaseEnvironment,
        child_session_id: str,
    ) -> bool:
        assert self._run_id
        response = await self._exec(
            environment,
            (
                f"{self._cli} client api "
                f"/api/runs/{self._run_id}/sessions/main-agent/events"
            ),
            timeout=60,
        )
        try:
            events = json.loads(response.stdout or "[]")
        except json.JSONDecodeError as exc:
            raise RuntimeError("could not parse Amplio root events") from exc
        seen_result = False
        for row in events if isinstance(events, list) else []:
            event = row.get("event") if isinstance(row, dict) else None
            if not isinstance(event, dict):
                continue
            if (
                event.get("type") == "child_result"
                and event.get("child_session_id") == child_session_id
                and event.get("verdict") == "concluded"
            ):
                seen_result = True
                continue
            if seen_result and event.get("type") == "assistant":
                return True
        return False

    async def _root_tool_transport_counts(
        self,
        environment: BaseEnvironment,
    ) -> tuple[int, int]:
        assert self._run_id
        response = await self._exec(
            environment,
            (
                f"{self._cli} client api "
                f"/api/runs/{self._run_id}/sessions/main-agent/events"
            ),
            timeout=60,
        )
        try:
            events = json.loads(response.stdout or "[]")
        except json.JSONDecodeError as exc:
            raise RuntimeError("could not parse Amplio root events") from exc
        if not isinstance(events, list):
            raise RuntimeError("Amplio root events payload is not a list")
        truncated = 0
        invalid = 0
        for row in events:
            event = row.get("event") if isinstance(row, dict) else None
            if not isinstance(event, dict):
                continue
            if (
                event.get("type") == "assistant"
                and event.get("stop_reason") == "length"
                and event.get("tool_calls")
            ):
                truncated += 1
            if event.get("type") == "tool_result" and event.get("is_error"):
                content = str(event.get("content") or "").lower()
                if "invalid arguments" in content or "unexpected end of json" in content:
                    invalid += 1
        return truncated, invalid

    async def _maybe_recover_tool_transport(
        self,
        environment: BaseEnvironment,
        before: tuple[int, int],
    ) -> None:
        if not self._recover_tool_transport_failures:
            return
        after = await self._root_tool_transport_counts(environment)
        delta_trunc = max(0, after[0] - before[0])
        delta_invalid = max(0, after[1] - before[1])
        if not (delta_trunc or delta_invalid):
            return
        await self._put_text(
            environment,
            f"/logs/agent/amplio-round-{self._round:02d}-transport-recovery.json",
            json.dumps(
                {
                    "round": self._round,
                    "new_truncated_tool_turns": delta_trunc,
                    "new_invalid_tool_argument_errors": delta_invalid,
                },
                indent=2,
            ) + "\n",
        )
        await self._post_root_message(
            environment,
            (
                "Harness recovery: this benchmark round produced "
                f"{delta_trunc} output-truncated tool-call turn(s) and "
                f"{delta_invalid} invalid tool-argument error(s). Inspect the "
                "workspace for incomplete or partially written edits caused by "
                "those failed operations. Repair them using shorter/chunked "
                "writes or purpose-built file tools, rerun relevant build/tests, "
                "and only then conclude. Do not merely summarize the error."
            ),
            label=f"round-{self._round:02d}-tool-transport-recovery",
        )
        await self._wait(environment)

    async def _ensure_required_subagent(
        self,
        environment: BaseEnvironment,
        before: set[str],
    ) -> None:
        require_from = self._require_subagent_from_round
        if require_from is None or self._round < require_from:
            return

        after_first_attempt = await self._subagent_session_ids(environment)
        new_children = after_first_attempt - before

        if self._force_subagent_enforcement or not new_children:
            review_before = after_first_attempt
            await self._post_root_message(
                environment,
                self._subagent_enforcement_message,
                label=f"round-{self._round:02d}-review-enforcement",
            )
            await self._wait(environment)
            after_review_request = await self._subagent_session_ids(environment)
            new_children = after_review_request - review_before

        if not new_children:
            try:
                await self._snapshot(environment)
            except Exception:
                pass
            raise RuntimeError(
                "required fresh sub-agent was not observed after explicit "
                f"delegation enforcement in round {self._round}"
            )

        sessions = await self._session_records(environment)
        reviewer_id = max(
            new_children,
            key=lambda sid: str(sessions.get(sid, {}).get("created_at") or ""),
        )
        status = str(sessions.get(reviewer_id, {}).get("status") or "")
        await self._put_text(
            environment,
            f"/logs/agent/amplio-round-{self._round:02d}-required-reviewer.txt",
            reviewer_id + "\n",
        )

        if not self._require_completed_subagent:
            return

        if status == "cancelled":
            await self._post_session_message(
                environment,
                reviewer_id,
                (
                    "Strict-join recovery: your parent concluded while your "
                    "required review was still running, so your session was "
                    "cancelled. Resume the same review now. Inspect the shared "
                    "workspace against the latest user instruction and accumulated "
                    "requirements. Return concise, concrete findings only; do not "
                    "edit the workspace and do not spawn another agent."
                ),
                label=f"round-{self._round:02d}-reviewer-revive",
            )
            status = await self._wait_for_session_terminal(
                environment,
                reviewer_id,
                ignore_initial_status="cancelled",
            )
        elif status not in {"concluded", "crashed"}:
            status = await self._wait_for_session_terminal(
                environment, reviewer_id
            )

        if status != "concluded":
            raise RuntimeError(
                f"required reviewer {reviewer_id} ended with status {status!r}"
            )

        # A concluded child result is durable in the root stream. If the root
        # already acted after that result, strict join adds no extra work. Only a
        # concluded parent that failed to consume the dependency is revived.
        if not await self._child_result_has_root_followup(
            environment, reviewer_id
        ):
            await self._post_root_message(
                environment,
                (
                    f"Strict-join continuation: required reviewer {reviewer_id} has "
                    "completed. Read its child_result from your session history, "
                    "address any concrete findings in the shared workspace, rerun "
                    "relevant checks, and only then conclude this benchmark round."
                ),
                label=f"round-{self._round:02d}-consume-review",
            )
            await self._wait(environment)

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
                f"{self._briefing_flags()} "
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

        before_subagents: set[str] = set()
        before_transport = (0, 0)
        await self._wait(environment)
        await self._maybe_recover_tool_transport(environment, before_transport)
        await self._ensure_required_subagent(environment, before_subagents)
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

        before_subagents = await self._subagent_session_ids(environment)
        before_transport = await self._root_tool_transport_counts(environment)

        await self._post_root_message(
            environment,
            instruction,
            label=f"round-{self._round:02d}-followup",
        )

        await self._wait(environment)
        await self._maybe_recover_tool_transport(environment, before_transport)
        await self._ensure_required_subagent(environment, before_subagents)
        await self._snapshot(environment)
