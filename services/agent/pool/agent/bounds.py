"""Hard bounds on an agent run, enforced as a Strands hook provider.

This is the mechanism behind AGENTS.md §3.1. It is not advice to the model — it is
enforcement in the event loop:

* **Iterations** — counted on every model call. Exceeding the cap raises, which
  unwinds the run into a recorded ``loop_fault`` outcome rather than letting it spin.
* **Total tool calls** — a global circuit breaker across all tools.
* **Duplicate tool calls** — the same tool with the same arguments repeated past the
  limit is a loop, not deliberation, so it is cancelled.
* **Wall clock** — a run that stalls is killed.

Tool-level bounds use ``cancel_tool`` so the model receives an error result and can
terminate cleanly; run-level bounds raise, because at that point we no longer trust
the run to wind itself down.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field

from strands.hooks import (
    AfterModelCallEvent,
    AfterToolCallEvent,
    BeforeModelCallEvent,
    BeforeToolCallEvent,
    HookProvider,
    HookRegistry,
)

from ..config import AgentBounds
from ..domain.models import ToolCallRecord

logger = logging.getLogger(__name__)


class BoundExceeded(RuntimeError):
    """A hard run-level bound was hit. Always terminates the run loudly."""

    def __init__(self, bound: str, detail: str) -> None:
        self.bound = bound
        self.detail = detail
        super().__init__(f"agent bound exceeded [{bound}]: {detail}")


def digest_arguments(payload: object) -> str:
    """Stable short digest of tool arguments, for duplicate detection.

    Hashed rather than stored so the run log never accidentally carries a household's
    details into an artifact we might publish (AGENTS.md §4).
    """
    try:
        canonical = json.dumps(payload, sort_keys=True, default=str)
    except (TypeError, ValueError):
        canonical = repr(payload)
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]


@dataclass
class RunTelemetry:
    """Everything we record about a run. Contains no model reasoning text (§9)."""

    iterations: int = 0
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    termination_reason: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def tool_call_count(self) -> int:
        return len(self.tool_calls)


class BoundedRun(HookProvider):
    """Enforces :class:`AgentBounds` and records telemetry for one run."""

    def __init__(self, bounds: AgentBounds, telemetry: RunTelemetry | None = None) -> None:
        self.bounds = bounds
        self.telemetry = telemetry or RunTelemetry()
        self._started = time.monotonic()
        self._seen: dict[tuple[str, str], int] = {}
        self._pending: dict[str, tuple[str, str]] = {}

    # -- lifecycle ---------------------------------------------------------

    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        registry.add_callback(BeforeModelCallEvent, self.on_before_model)
        registry.add_callback(AfterModelCallEvent, self.on_after_model)
        registry.add_callback(BeforeToolCallEvent, self.on_before_tool)
        registry.add_callback(AfterToolCallEvent, self.on_after_tool)

    @property
    def elapsed_seconds(self) -> float:
        return time.monotonic() - self._started

    def _check_clock(self) -> None:
        if self.elapsed_seconds > self.bounds.workflow_timeout_seconds:
            self.telemetry.termination_reason = "timeout"
            raise BoundExceeded(
                "workflow_timeout_seconds",
                f"{self.elapsed_seconds:.1f}s exceeded {self.bounds.workflow_timeout_seconds}s",
            )

    # -- model calls -------------------------------------------------------

    def on_before_model(self, event: BeforeModelCallEvent) -> None:
        self._check_clock()
        self.telemetry.iterations += 1
        if self.telemetry.iterations > self.bounds.max_iterations:
            self.telemetry.termination_reason = "max_iterations"
            raise BoundExceeded(
                "max_iterations",
                f"reached iteration {self.telemetry.iterations} of {self.bounds.max_iterations}",
            )

    def on_after_model(self, event: AfterModelCallEvent) -> None:
        """Accumulate token usage so paid activity is visible, not discovered on a bill.

        Usage is read per model call rather than from ``AgentResult.metrics`` at the end,
        because a run aborted by a bound never produces an AgentResult — and an aborted
        run is exactly the one whose cost we most want recorded.

        ``ModelStopResponse`` exposes only ``message`` and ``stop_reason``; the usage
        block rides along in ``message["metadata"]`` (confirmed by probing a live run).
        """
        stop_response = getattr(event, "stop_response", None)
        message = getattr(stop_response, "message", None)
        if not isinstance(message, dict):
            return
        usage = (message.get("metadata") or {}).get("usage")
        if isinstance(usage, dict):
            self.telemetry.input_tokens += int(usage.get("inputTokens", 0) or 0)
            self.telemetry.output_tokens += int(usage.get("outputTokens", 0) or 0)

    # -- tool calls --------------------------------------------------------

    def on_before_tool(self, event: BeforeToolCallEvent) -> None:
        self._check_clock()
        tool_use = event.tool_use or {}
        name = str(tool_use.get("name", "unknown"))
        tool_use_id = str(tool_use.get("toolUseId", ""))
        arg_digest = digest_arguments(tool_use.get("input"))
        self._pending[tool_use_id] = (name, arg_digest)

        if self.telemetry.tool_call_count >= self.bounds.max_tool_calls:
            self.telemetry.termination_reason = "max_tool_calls"
            event.cancel_tool = (
                f"Tool budget exhausted: {self.bounds.max_tool_calls} calls already made "
                f"in this run. Stop and report what you have."
            )
            return

        key = (name, arg_digest)
        self._seen[key] = self._seen.get(key, 0) + 1
        if self._seen[key] > self.bounds.max_duplicate_tool_calls:
            self.telemetry.termination_reason = "duplicate_tool_calls"
            event.cancel_tool = (
                f"Repeated call to '{name}' with identical arguments "
                f"({self._seen[key]}x). State has not changed, so the result would not "
                f"either. Stop repeating this call."
            )

    def on_after_tool(self, event: AfterToolCallEvent) -> None:
        tool_use = event.tool_use or {}
        tool_use_id = str(tool_use.get("toolUseId", ""))
        name, arg_digest = self._pending.pop(
            tool_use_id, (str(tool_use.get("name", "unknown")), "")
        )
        result = event.result or {}
        status = str(result.get("status", "unknown"))
        self.telemetry.tool_calls.append(
            ToolCallRecord(
                name=name,
                arguments_digest=arg_digest,
                ok=status == "success",
                summary=_summarise_tool_result(result),
            )
        )


def _summarise_tool_result(result: dict) -> str:
    """One short line describing a tool result — never the full payload."""
    content = result.get("content") or []
    for block in content:
        if isinstance(block, dict) and "text" in block:
            text = str(block["text"])
            return text[:180] + ("…" if len(text) > 180 else "")
    return str(result.get("status", ""))
