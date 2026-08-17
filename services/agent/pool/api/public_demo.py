"""Public judge mode — the narrow surface Pool exposes to an anonymous browser.

The local API (``pool/api/app.py``) is a full four-surface application: 45 endpoints
covering buyer, host, operator, and demo flows, plus a payment webhook. That is the
right shape for development and for the test suite. It is **not** the right shape to
put on the open internet with no authentication, so this module reduces it.

Turned on with ``POOL_PUBLIC_DEMO=true``. What it changes, and why each one matters:

1. **Route allowlist.** Fourteen paths are reachable; everything else 404s before it
   reaches a handler. Supplier-offer mutation, the operator pickup override, the
   payment webhook, direct ``lock``/``purchase``/``open-distribution`` calls, and the
   private message threads are all outside it. The lifecycle still reaches those code
   paths — the scenario runs them server-side — but no anonymous request can drive
   them directly.

2. **No prompt surface.** ``PoolCoordinator.run()`` substitutes ``instruction`` for the
   *entire* run prompt, so an endpoint that forwards a client string is an endpoint
   that lets a stranger write the agent's instructions. In public mode the client sends
   a *trigger name from a fixed set* and the server supplies the prompt. A request
   carrying ``instruction`` is refused rather than ignored, so the refusal is visible.

3. **Bounded spend.** Two quota buckets — cheap deterministic actions, and the one
   action that spends Bedrock tokens — each capped per session and per UTC day, with
   the day counter held in DynamoDB so the cap survives across Lambda containers.

4. **One honest live action.** ``POST /api/demo/agentcore`` really invokes the deployed
   AgentCore Runtime with a freshly generated session id and a server-built payload. It
   never fabricates a result: if the call fails or a cap is hit, it says so
   (AGENTS.md §8). It returns no account id and no runtime ARN.

The browser holds no AWS credential in any of this. The bridge signs with the Lambda's
execution role, which is why the runtime can keep ``AWS_IAM`` inbound auth (§4).
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

#: Session workspaces the public client is allowed to ask for. Deliberately narrower
#: than the API's own ``WORKSPACE_RE``: the public client generates exactly this shape,
#: so anything else is either a mistake or someone probing.
PUBLIC_WORKSPACE_RE = re.compile(r"^w[a-z0-9]{8,32}$")

#: Never reachable as a workspace prefix — ``WORKSPACE_RE`` requires a leading
#: ``[a-z0-9]`` — so quota rows cannot collide with a session's data.
QUOTA_PK_PREFIX = "_quota"

_ID = r"[A-Za-z0-9_-]{1,64}"

ALLOWED_GET = frozenset(
    {
        "/api/health",
        "/api/state",
        "/api/map",
        "/api/needs",
        "/api/operator",
        "/api/pickup-sites",
        "/api/demo/config",
    }
)

ALLOWED_GET_PATTERNS = tuple(
    re.compile(p)
    for p in (
        rf"^/api/pools/{_ID}$",
        rf"^/api/pools/{_ID}/checklist$",
        rf"^/api/pools/{_ID}/allocations$",
        rf"^/api/runs/{_ID}$",
    )
)

ALLOWED_POST = frozenset(
    {
        "/api/agent/run",
        "/api/demo/reset",
        "/api/demo/scenario",
        "/api/demo/agentcore",
    }
)

ALLOWED_POST_PATTERNS = tuple(
    re.compile(p)
    for p in (
        rf"^/api/decisions/{_ID}/respond$",
        rf"^/api/pools/{_ID}/pickup-credential/{_ID}$",
        rf"^/api/pools/{_ID}/redeem$",
    )
)

#: Trigger name → the run prompt the *server* supplies for it. ``None`` means the
#: coordinator's own default discovery prompt. This map is the entire public prompt
#: surface: a public caller selects a key, never a value.
PUBLIC_TRIGGERS: dict[str, str | None] = {
    "manual_scan": None,
    "manual_advance": (
        "Advance every pool that is blocked: recruit a host, refresh the supplier "
        "quote, issue final offers, recover lost demand, and lock anything that is "
        "fully funded and viable."
    ),
}

#: Trigger the live AgentCore action sends. Must be in the runtime entrypoint's own
#: ``ALLOWED_TRIGGERS`` (``services/agent/agentcore_app.py``).
LIVE_TRIGGER = "manual"


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class PublicDemoSettings:
    """Everything public mode needs, all of it environment-driven.

    Every cap can be tightened — and the two kill switches thrown — with
    ``update-function-configuration``, without a rebuild or a redeploy of code.
    """

    enabled: bool = False
    #: Independent kill switch for the one paid action, so the deterministic demo can
    #: stay up while live invocation is off.
    agentcore_enabled: bool = True
    agentcore_runtime_arn: str = ""
    agentcore_qualifier: str = "DEFAULT"
    region: str = "us-east-1"
    #: Directory holding the built SPA (``index.html`` + ``assets/``).
    web_root: str = ""
    quota_table: str = ""
    max_actions_per_session: int = 40
    max_actions_per_day: int = 600
    max_live_per_session: int = 3
    max_live_per_day: int = 40
    #: Seeding a cold workspace writes ~100 rows, and any read endpoint will do it for
    #: a workspace it has never seen. Without a cap, a script cycling session ids is an
    #: unbounded write generator, so new sessions are rationed per day.
    max_new_sessions_per_day: int = 300

    @classmethod
    def from_env(cls) -> PublicDemoSettings:
        return cls(
            enabled=_bool_env("POOL_PUBLIC_DEMO", False),
            agentcore_enabled=_bool_env("PUBLIC_DEMO_AGENTCORE_ENABLED", True),
            agentcore_runtime_arn=os.environ.get("AGENTCORE_RUNTIME_ARN", ""),
            agentcore_qualifier=os.environ.get("AGENTCORE_QUALIFIER", "DEFAULT"),
            region=os.environ.get("AWS_REGION", "us-east-1"),
            web_root=os.environ.get("PUBLIC_DEMO_WEB_ROOT", ""),
            quota_table=os.environ.get("DYNAMODB_TABLE", ""),
            max_actions_per_session=_int_env("PUBLIC_DEMO_MAX_ACTIONS_PER_SESSION", 40),
            max_actions_per_day=_int_env("PUBLIC_DEMO_MAX_ACTIONS_PER_DAY", 600),
            max_live_per_session=_int_env("PUBLIC_DEMO_MAX_LIVE_PER_SESSION", 3),
            max_live_per_day=_int_env("PUBLIC_DEMO_MAX_LIVE_PER_DAY", 40),
            max_new_sessions_per_day=_int_env("PUBLIC_DEMO_MAX_NEW_SESSIONS_PER_DAY", 300),
        )

    @property
    def live_available(self) -> bool:
        return bool(self.enabled and self.agentcore_enabled and self.agentcore_runtime_arn)

    @property
    def runtime_label(self) -> str:
        """The agent's name, with the generated suffix and the account id removed.

        A judge wants to know *which* agent answered, not which AWS account hosts it.
        ``arn:aws:bedrock-agentcore:us-east-1:1234:runtime/Pool_PoolCoordinator-AbC123``
        becomes ``Pool_PoolCoordinator``.
        """
        if not self.agentcore_runtime_arn:
            return ""
        tail = self.agentcore_runtime_arn.rsplit("/", 1)[-1]
        return tail.rsplit("-", 1)[0] if "-" in tail else tail


# --------------------------------------------------------------------------- quotas


class QuotaStore(Protocol):
    def spend(self, key: str, limit: int, ttl_seconds: int) -> bool:
        """Consume one unit against ``key``. False means the limit is already reached."""
        ...


class InMemoryQuotaStore:
    """Per-process counters. Correct locally and in tests; adequate but not
    authoritative across Lambda containers — which is why the *day* caps use
    DynamoDB when a table is configured."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def spend(self, key: str, limit: int, ttl_seconds: int) -> bool:
        current = self._counts.get(key, 0)
        if current >= limit:
            return False
        self._counts[key] = current + 1
        return True


class DynamoDBQuotaStore:
    """Atomic counters in the demo's own table.

    ``ADD`` with a conditional expression is a single round trip that either
    increments or fails, so two Lambda containers racing on the last unit of a cap
    cannot both win. The row carries a TTL so spent windows delete themselves.
    """

    def __init__(self, table_name: str, region_name: str = "us-east-1", table: Any = None) -> None:
        self.table_name = table_name
        self.region_name = region_name
        self._table = table

    @property
    def table(self) -> Any:
        if self._table is None:
            import boto3

            self._table = boto3.resource("dynamodb", region_name=self.region_name).Table(
                self.table_name
            )
        return self._table

    def spend(self, key: str, limit: int, ttl_seconds: int) -> bool:
        bucket, _, window = key.partition("#")
        try:
            self.table.update_item(
                Key={"pk": f"{QUOTA_PK_PREFIX}#{bucket}", "sk": window or "default"},
                UpdateExpression="ADD #n :one SET #ttl = :ttl",
                ConditionExpression="attribute_not_exists(#n) OR #n < :limit",
                ExpressionAttributeNames={"#n": "n", "#ttl": "ttl"},
                ExpressionAttributeValues={
                    ":one": 1,
                    ":limit": limit,
                    ":ttl": int(time.time()) + ttl_seconds,
                },
            )
            return True
        except Exception as exc:  # noqa: BLE001 - the conditional failure is the signal
            if type(exc).__name__ == "ConditionalCheckFailedException":
                return False
            # A quota store that cannot be read must not become a way to bypass the
            # quota. Fail closed, loudly.
            logger.warning("quota store unavailable for %s: %s", key, type(exc).__name__)
            return False


def build_quota_store(settings: PublicDemoSettings) -> QuotaStore:
    if settings.quota_table:
        return DynamoDBQuotaStore(settings.quota_table, settings.region)
    return InMemoryQuotaStore()


#: Session caps expire with the demo workspace; day caps expire with the day.
_SESSION_TTL = 60 * 60 * 24
_DAY_TTL = 60 * 60 * 48


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


# --------------------------------------------------------------------------- guard


class PublicDemoGuard:
    """The single object the API asks before doing anything a public caller triggered.

    Every method is a no-op when public mode is off, so the local API, ``make demo``,
    and the test suite behave exactly as they did before.
    """

    def __init__(
        self,
        settings: PublicDemoSettings | None = None,
        quota: QuotaStore | None = None,
        bridge: AgentCoreBridge | None = None,
    ) -> None:
        self.settings = settings or PublicDemoSettings.from_env()
        self.quota = quota or build_quota_store(self.settings)
        self._bridge = bridge

    @property
    def enabled(self) -> bool:
        return self.settings.enabled

    # -- workspaces ------------------------------------------------------

    def check_workspace(self, ws: str) -> str:
        """Public sessions must look like a browser-generated session id.

        Anonymous isolation is by workspace: each visitor's dataset lives in its own
        DynamoDB partition with a 24 h TTL, so two judges cannot see or corrupt each
        other's demo, and nobody can address the long-lived ``primary`` workspace.
        """
        if not self.enabled:
            return ws
        if not PUBLIC_WORKSPACE_RE.match(ws):
            raise HTTPException(400, "invalid demo session")
        return ws

    # -- quotas ----------------------------------------------------------

    def spend_action(self, ws: str) -> None:
        """One deterministic, free-to-run action: a scan, a reset, or the scenario."""
        self._spend(
            "action",
            ws,
            self.settings.max_actions_per_session,
            self.settings.max_actions_per_day,
            "This demo session has run its allowance of actions. Press "
            "“Start a fresh session” to continue.",
        )

    def spend_new_session(self) -> None:
        """One cold workspace being seeded. Day-scoped only: there is no session to
        charge yet, which is precisely why this cap exists."""
        if not self.enabled:
            return
        if not self.quota.spend(
            f"newsession-day#{_today()}", self.settings.max_new_sessions_per_day, _DAY_TTL
        ):
            raise HTTPException(
                429,
                "Pool's public demo has opened as many sessions as it will today. "
                "The full experience runs locally with `make dev` — nothing there "
                "needs an AWS account.",
            )

    def spend_live(self, ws: str) -> None:
        """One live AgentCore invocation — the only action that spends model tokens."""
        self._spend(
            "live",
            ws,
            self.settings.max_live_per_session,
            self.settings.max_live_per_day,
            "The live agent allowance for this session is used up.",
        )

    def _spend(self, bucket: str, ws: str, per_session: int, per_day: int, message: str) -> None:
        """Session cap first, then the shared day cap. **The order is the point.**

        Spending the day counter first meant a request the *session* cap went on to
        refuse had already consumed a unit of everyone's daily budget — so one visitor
        could close the live agent button for every other judge with refused requests,
        without spending a cent at Bedrock. Observed on the deployed stack: `live-day`
        went 2 → 3 on a call that returned 429 and never reached AWS (#0024).

        Checking the narrower, cheaper cap first means a session can only ever exhaust
        its own allowance.
        """
        if not self.enabled:
            return
        if not self.quota.spend(f"{bucket}-session#{ws}", per_session, _SESSION_TTL):
            raise HTTPException(429, message)
        if not self.quota.spend(f"{bucket}-day#{_today()}", per_day, _DAY_TTL):
            raise HTTPException(
                429,
                "Pool's public demo has reached today's shared limit. The full "
                "experience runs locally with `make dev` — nothing here needs an "
                "AWS account.",
            )

    # -- the prompt surface ----------------------------------------------

    def resolve_run(self, trigger: str, instruction: str | None) -> tuple[str, str | None]:
        """Return the ``(trigger, instruction)`` a public run is allowed to use.

        Refusing a supplied ``instruction`` rather than dropping it is deliberate: a
        silently ignored field looks like it worked, and the first person to notice
        would be someone testing whether the agent can be steered.
        """
        if not self.enabled:
            return trigger, instruction
        if instruction is not None:
            raise HTTPException(400, "this demo does not accept custom agent instructions")
        if trigger not in PUBLIC_TRIGGERS:
            raise HTTPException(
                400, f"unknown action: {trigger}. Allowed: {sorted(PUBLIC_TRIGGERS)}"
            )
        return trigger, PUBLIC_TRIGGERS[trigger]

    # -- the live action -------------------------------------------------

    @property
    def bridge(self) -> AgentCoreBridge:
        if self._bridge is None:
            self._bridge = AgentCoreBridge(
                runtime_arn=self.settings.agentcore_runtime_arn,
                region=self.settings.region,
                qualifier=self.settings.agentcore_qualifier,
            )
        return self._bridge

    def config_view(self) -> dict[str, Any]:
        """What the UI needs in order to describe itself honestly."""
        return {
            "public_demo": self.enabled,
            "live_agent_available": self.settings.live_available,
            "live_agent_runtime": self.settings.runtime_label if self.settings.live_available else "",
            "region": self.settings.region if self.settings.live_available else "",
            "max_live_per_session": self.settings.max_live_per_session,
            "payments": "simulated",
            "purchase": "simulated",
        }


# --------------------------------------------------------------------------- bridge


def new_session_id() -> str:
    """A fresh AgentCore session id, 74 chars of server-generated randomness.

    AgentCore requires 33–100 characters. Generating it server-side per invocation is
    the isolation boundary: no client value reaches it, so one visitor cannot land in
    another visitor's runtime session, and no session is ever reused (#0023 showed a
    reused session id makes the second run see the first run's pools).
    """
    return f"pooldemo{uuid.uuid4().hex}{uuid.uuid4().hex}"


class AgentCoreBridge:
    """Invokes the deployed runtime with the Lambda's own execution identity.

    This exists because the runtime's inbound auth is ``AWS_IAM``. A browser cannot
    sign a SigV4 request without credentials, and giving a browser credentials is
    exactly what AGENTS.md §4 forbids — so the signing happens here, on a role whose
    only agent permission is ``InvokeAgentRuntime`` on this one runtime ARN.
    """

    def __init__(
        self,
        runtime_arn: str,
        region: str = "us-east-1",
        qualifier: str = "DEFAULT",
        client: Any = None,
    ) -> None:
        self.runtime_arn = runtime_arn
        self.region = region
        self.qualifier = qualifier
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            import boto3
            from botocore.config import Config

            self._client = boto3.client(
                "bedrock-agentcore",
                region_name=self.region,
                # One attempt. A retried invocation is a second billed agent run, and
                # the caller would never know it happened (AGENTS.md §3.1).
                config=Config(
                    connect_timeout=5,
                    read_timeout=90,
                    retries={"max_attempts": 1, "mode": "standard"},
                ),
            )
        return self._client

    def invoke(self) -> dict[str, Any]:
        """Run one live coordination cycle on AWS and project the result.

        The payload is built here, from constants. Nothing a caller sent reaches the
        runtime — not a prompt, not a workspace, not a community id.
        """
        session_id = new_session_id()
        payload = json.dumps(
            {"workspace": f"live{uuid.uuid4().hex[:12]}", "trigger": LIVE_TRIGGER}
        ).encode()

        started = time.perf_counter()
        response = self.client.invoke_agent_runtime(
            agentRuntimeArn=self.runtime_arn,
            qualifier=self.qualifier,
            runtimeSessionId=session_id,
            contentType="application/json",
            accept="application/json",
            payload=payload,
        )
        wall_ms = int((time.perf_counter() - started) * 1000)

        body = response.get("response")
        raw = body.read() if hasattr(body, "read") else body
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", "replace")
        result = json.loads(raw) if raw else {}
        if not isinstance(result, dict):
            raise ValueError("runtime returned a non-object response")
        if "error" in result:
            raise ValueError(str(result["error"])[:200])

        # Log the correlation handles; do not return them. A judge gains nothing from
        # an X-Ray trace id they cannot query, and it is an account-scoped identifier.
        logger.info(
            "live agentcore run run_id=%s outcome=%s tools=%d trace=%s",
            result.get("run_id"),
            result.get("outcome"),
            len(result.get("tool_calls") or []),
            response.get("traceId", ""),
        )
        return {"run": _project_live_run(result), "wall_ms": wall_ms}


#: Fields of the runtime's response that are safe and useful to show. Everything else
#: — including the runtime's own workspace name — is dropped rather than forwarded.
_LIVE_RUN_FIELDS = (
    "run_id",
    "outcome",
    "iterations",
    "termination_reason",
    "model_provider",
    "model_id",
    "duration_ms",
    "input_tokens",
    "output_tokens",
    "hitl_decisions_created",
)


def _project_live_run(result: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {field: result.get(field) for field in _LIVE_RUN_FIELDS}
    out["tool_calls"] = [
        {
            "name": str(call.get("name", ""))[:60],
            "ok": bool(call.get("ok")),
            "summary": str(call.get("summary", ""))[:180],
        }
        for call in (result.get("tool_calls") or [])
        if isinstance(call, dict)
    ]
    return out


# --------------------------------------------------------------------------- install


_STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".png": "image/png",
    ".webmanifest": "application/manifest+json",
}


def install(app: FastAPI, guard: PublicDemoGuard) -> None:
    """Attach the allowlist, the live action, and the built SPA to ``app``.

    Called once at import time from ``pool/api/app.py`` and only when public mode is
    on, so a local run is byte-for-byte the application it always was.
    """
    if not guard.enabled:
        return

    # AWS Lambda installs a log handler on the root logger but leaves the root *level*
    # at WARNING, so `logger.info` from application code is dropped before it reaches
    # CloudWatch. The deployed demo logged only START/REPORT and crashes until this was
    # added — which meant a judge's live agent invocation could not be correlated to
    # the AgentCore run it triggered (AGENTS.md §9). Scoped to the `pool` tree so it
    # cannot turn on third-party debug chatter, and only in public mode so a local run
    # keeps whatever logging the developer configured.
    logging.getLogger("pool").setLevel(logging.INFO)

    @app.middleware("http")
    async def allowlist(request: Request, call_next):  # type: ignore[no-untyped-def]
        path = request.url.path
        method = request.method.upper()
        if path.startswith("/api/"):
            if method == "GET":
                permitted = path in ALLOWED_GET or any(
                    p.match(path) for p in ALLOWED_GET_PATTERNS
                )
            elif method == "POST":
                permitted = path in ALLOWED_POST or any(
                    p.match(path) for p in ALLOWED_POST_PATTERNS
                )
            else:
                permitted = False
            if not permitted:
                # 404 rather than 405/403: a public demo owes a prober no map of what
                # exists behind it.
                return JSONResponse({"detail": "not found"}, status_code=404)
        response = await call_next(request)
        # No third party should be able to frame the demo or sniff its content type.
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/api/demo/config")
    def demo_config() -> dict[str, Any]:
        """What this deployment can actually do. The UI labels itself from this."""
        return guard.config_view()

    @app.post("/api/demo/agentcore")
    def demo_agentcore(workspace: str = "") -> dict[str, Any]:
        """Invoke the deployed AgentCore Runtime, for real, once.

        Returns ``ok: false`` with a reason rather than raising for the situations a
        judge can hit legitimately — the switch being off, or AWS refusing. It never
        returns a fabricated run: if this says a run happened, one happened
        (AGENTS.md §8).
        """
        # Read through the guard, never a captured copy: both kill switches and every
        # cap are environment variables so they can be changed on the deployed function
        # without a rebuild, and a handler holding a stale snapshot would ignore them.
        settings = guard.settings
        ws = guard.check_workspace(workspace)
        if not settings.live_available:
            return {
                "ok": False,
                "live": False,
                "reason": "The live agent action is switched off on this deployment.",
            }
        guard.spend_live(ws)
        try:
            result = guard.bridge.invoke()
        except Exception as exc:  # noqa: BLE001 - reported to the caller, not swallowed
            logger.warning("live agentcore invocation failed: %s", type(exc).__name__)
            return {
                "ok": False,
                "live": False,
                "reason": (
                    "The deployed agent did not answer this time "
                    f"({type(exc).__name__}). Nothing below is affected — it is "
                    "computed locally."
                ),
            }
        return {
            "ok": True,
            "live": True,
            "service": "Amazon Bedrock AgentCore Runtime",
            "runtime": settings.runtime_label,
            "region": settings.region,
            "wall_ms": result["wall_ms"],
            "run": result["run"],
            "note": (
                "This ran in its own AgentCore session on AWS, against its own "
                "synthetic Demo University seeded inside the runtime. It does not "
                "change the demo state on this page."
            ),
        }

    if guard.settings.web_root:
        _install_static(app, guard.settings.web_root)


def _install_static(app: FastAPI, web_root: str) -> None:
    """Serve the built SPA from the same origin as the API.

    One origin means no CORS at all, which is one fewer thing to get wrong, and it
    means the demo is a single deployable unit — no bucket, no distribution, no
    invalidation step (AGENTS.md §3.7).
    """
    root = os.path.abspath(web_root)

    def read(rel: str) -> Response | None:
        target = os.path.abspath(os.path.join(root, rel))
        # Path traversal: resolve first, then require the result to still be inside
        # the web root.
        if not target.startswith(root + os.sep) or not os.path.isfile(target):
            return None
        ext = os.path.splitext(target)[1].lower()
        with open(target, "rb") as handle:
            data = handle.read()
        headers = (
            {"cache-control": "public, max-age=31536000, immutable"}
            if rel.startswith("assets/")
            else {"cache-control": "no-cache"}
        )
        return Response(
            content=data,
            media_type=_STATIC_TYPES.get(ext, "application/octet-stream"),
            headers=headers,
        )

    @app.get("/assets/{name}")
    def asset(name: str) -> Response:
        found = read(f"assets/{name}")
        if found is None:
            raise HTTPException(404, "not found")
        return found

    @app.get("/")
    def index() -> Response:
        found = read("index.html")
        if found is None:
            raise HTTPException(404, "not found")
        return found

    # Registered last, so every route above wins. A single-page app has to answer for
    # paths it never declared.
    @app.get("/{path:path}")
    def spa(path: str) -> Response:
        found = read("index.html")
        if found is None:
            raise HTTPException(404, "not found")
        return found
