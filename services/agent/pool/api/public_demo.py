"""Public judge mode — the narrow surface Pool exposes to an anonymous browser.

The local API (``pool/api/app.py``) is a full four-surface application: 45 endpoints
covering buyer, host, operator, and demo flows, plus a payment webhook. That is the
right shape for development and for the test suite. It is **not** the right shape to
put on the open internet with no authentication, so this module reduces it.

Turned on with ``POOL_PUBLIC_DEMO=true``. What it changes, and why each one matters:

1. **Route allowlist.** Twenty-nine of those forty-five endpoints are reachable; everything
   else 404s before it reaches a handler. Supplier-offer mutation, the operator pickup
   override, the payment webhook, direct ``lock``/``purchase`` calls, and the private
   message threads are all outside it. The lifecycle still reaches those code paths —
   the scenario runs them server-side — but no anonymous request can drive them
   directly. Both counts are method-and-path pairs, and
   ``test_the_published_endpoint_counts_are_the_real_ones`` pins them, because these
   are the numbers the README quotes and they had already drifted once.

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

Workspace binding
-----------------

The live action runs the deployed agent **against the visitor's own workspace**, so the
pool that appears afterwards was formed by that execution rather than replayed from its
answer. Four things make that safe to expose anonymously:

* **The workspace is a server value on every hop.** The client sends a session id as a
  query parameter and it is checked against :data:`PUBLIC_WORKSPACE_RE` before anything
  reads it; the payload the bridge signs is then *built here* from that checked value.
  No client string is forwarded, and there is no field a caller can add to name a
  different one.
* **It grants nothing the caller did not already have.** A public session id is a bearer
  capability — whoever holds it can already read and drive that workspace through this
  same API. Binding the agent to it widens no boundary; addressing someone else's
  workspace requires guessing their id, and that is the property that was already
  protecting `/api/state`.
* **The model never sees it.** No tool takes a workspace argument, and the workspace
  string appears in neither the system prompt nor the run instruction. The model chooses
  *what to do*; it cannot choose *whose data to do it to* (AGENTS.md §4, §5).
* **One invocation per workspace at a time** (:class:`LeaseStore`). Two runs racing on
  one partition would both read "no pool exists" and both write one, and a reset landing
  mid-run would delete rows the run is still writing.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Protocol

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

#: Session workspaces the public client is allowed to ask for. Deliberately narrower
#: than the API's own ``WORKSPACE_RE``: the public client generates exactly this shape,
#: so anything else is either a mistake or someone probing.
#: The canonical scripted showcase runs in its own partition, derived from the visitor's
#: session by :func:`showcase_workspace`. Two properties matter and both come from the
#: hyphen: a browser-generated session id can never contain one, so a visitor's *own*
#: workspace and their showcase workspace can never be the same partition; and reaching
#: somebody else's showcase still means guessing their session id, which is the property
#: that already protects ``/api/state``.
SHOWCASE_SUFFIX = "-showcase"

PUBLIC_WORKSPACE_RE = re.compile(rf"^w[a-z0-9]{{8,32}}({re.escape(SHOWCASE_SUFFIX)})?$")


def showcase_workspace(ws: str) -> str:
    """The partition the scripted showcase runs in, for a given visitor session.

    Idempotent, so a surface already reading the showcase can pass its own workspace
    without accumulating suffixes.
    """
    return ws if ws.endswith(SHOWCASE_SUFFIX) else f"{ws}{SHOWCASE_SUFFIX}"


def is_showcase_workspace(ws: str) -> bool:
    return ws.endswith(SHOWCASE_SUFFIX)

#: Never reachable as a workspace prefix — ``WORKSPACE_RE`` requires a leading
#: ``[a-z0-9]`` — so quota and lease rows cannot collide with a session's data.
QUOTA_PK_PREFIX = "_quota"

#: One row per workspace, holding the mutation lease described in
#: :meth:`PublicDemoGuard.workspace_mutation`. The stored value still says ``agentcore``
#: because that is the partition the row has always lived in and renaming it would mean
#: a deploy in which old and new containers took *different* locks — precisely the
#: overlap the lease exists to prevent. It protects every mutating coordinator now, not
#: only the live one.
WORKSPACE_LEASE_PK = "_lease#agentcore"
LEASE_PK = WORKSPACE_LEASE_PK  # historical alias

#: A content security policy the bundle can actually satisfy, verified against the built
#: SPA rather than copied from a template. Every directive here is one the deployed page
#: already complies with, which is why it can be strict:
#:
#: * ``script-src 'self'`` — no ``unsafe-inline``, no ``unsafe-eval``. Vite emits a
#:   single same-origin module script and `index.html` carries no inline script, so the
#:   one directive that actually stops XSS is the one that costs nothing here.
#: * ``style-src`` keeps ``'unsafe-inline'`` because the views use React ``style={{…}}``
#:   attributes, which CSP treats as inline styles. Stating that plainly beats a policy
#:   that looks stricter and has to be relaxed the first time anyone tests it.
#: * ``img-src`` allows ``data:`` for exactly one thing: the inline SVG favicon, which is
#:   embedded precisely so the tab icon reaches no external host.
#: * ``connect-src 'self'`` — the API is same-origin, and the browser holds no AWS
#:   credential, so there is nothing it should ever call cross-origin. A page that starts
#:   talking to another host is a page that has been compromised.
#: * ``font-src 'self'`` — Instrument Serif is bundled, not fetched from a CDN.
#: * ``frame-ancestors``/``base-uri``/``form-action``/``object-src`` are all ``'none'``:
#:   nothing frames this, nothing rewrites its base URL, and it submits no forms in the
#:   HTML sense — the need form posts through `fetch`, which `connect-src` governs.
CONTENT_SECURITY_POLICY = "; ".join(
    (
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "frame-ancestors 'none'",
        "base-uri 'none'",
        "form-action 'none'",
        "object-src 'none'",
    )
)

#: Sent on every public response. The first three were already here; the rest close the
#: gaps an external review found (#audit P2).
#:
#: ``Strict-Transport-Security`` carries no ``preload`` and no ``includeSubDomains``
#: beyond this host: the demo is served from an AWS-owned Function URL domain, and
#: asserting a policy over a domain this project does not control would be overreach with
#: a two-year memory. Browsers ignore the header entirely over plain HTTP, so a local run
#: is unaffected.
#:
#: ``Permissions-Policy`` denies the capability set outright. Pool asks for none of it —
#: the map is a synthetic coarse-grid rendering and never requests a real position — so
#: the honest policy is an empty allowlist rather than a considered subset.
SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "Strict-Transport-Security": "max-age=31536000",
    "Permissions-Policy": (
        "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), "
        "microphone=(), payment=(), usb=(), interest-cohort=()"
    ),
}

#: What a caller is told when another coordinator holds this workspace. Deliberately
#: does not name which one: from the losing request's side, a live run, a reset, the
#: scenario and a second tab's coordinator run are the same event, and guessing wrong
#: in the message would be worse than not guessing.
WORKSPACE_BUSY = (
    "Something else is already working on this session. Give it a moment and try again."
)

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
        # Resolving what somebody typed into products they might mean. The first half of
        # the product's primary action, so it has to be reachable for the same reason
        # `/api/needs` is. Cheap to expose: it reads a bundled snapshot with a pure
        # function, spends no model tokens, touches no workspace state, and takes no
        # client string that reaches an agent prompt.
        "/api/products/search",
        # A member's own account view: their Smart Join rules, their community
        # verification, whether a payment method exists. It already refuses to emit a
        # contact detail or a payment reference, which is what makes it safe to expose.
        "/api/hosting/opportunities",
    }
)

ALLOWED_GET_PATTERNS = tuple(
    re.compile(p)
    for p in (
        rf"^/api/pools/{_ID}$",
        rf"^/api/pools/{_ID}/checklist$",
        rf"^/api/pools/{_ID}/allocations$",
        rf"^/api/runs/{_ID}$",
        # What one run did about this member's own declarations. A pure read over
        # records that run already wrote: it creates nothing, spends no model tokens,
        # and refuses to describe a run that was not this member's.
        rf"^/api/runs/{_ID}/report$",
        rf"^/api/members/{_ID}$",
    )
)

ALLOWED_POST = frozenset(
    {
        "/api/agent/run",
        "/api/demo/reset",
        "/api/demo/scenario",
        "/api/demo/agentcore",
        # Declaring a standing need. The product's primary user action, and the one a
        # judge has to be able to *perform* rather than read about — the whole thesis is
        # that this is all anybody does and the agent finds the overlap. It creates no
        # group, commits no money, and the service refuses to write a declaration for a
        # household other than the one the request names.
        "/api/needs",
        # Recording an item the catalogue does not have. Writes one product row into the
        # caller's own session workspace with no substitute group and no offer, so it can
        # be declared against and can never combine with anybody else's demand. Bounded
        # by the same session quota as every other mutation here.
        "/api/products/custom",
        # Finishing account setup: the name Pool should use, and how much authority it
        # has. Both are this member's own facts about themselves, both are validated
        # server-side, and neither touches another household or any money.
        "/api/onboarding",
        # Saving a simulated payment method for the caller's own account. The household
        # is a server constant here; there is no field to point it at anyone else.
        "/api/onboarding/payment-method",
    }
)

#: Participant actions. Each one is something a *person* does in the real product —
#: answering a question, offering to host, replying to an offer, opening the pickup
#: window, leaving a pool — performed here against synthetic members inside the caller's
#: own isolated session.
#:
#: What is deliberately still absent, and why:
#:
#: * ``lock`` and ``purchase`` — consequential decisions the *agent* makes. The judge
#:   reaches them by running the agent, which is both the honest path and the one the
#:   viability engine gates. A button that locks a pool directly would undercut the
#:   entire claim that the model decides what to do.
#: * ``override`` — the audited bypass of the pickup credential. Exposing it anonymously
#:   would make the single-use guarantee decorative.
#: * ``operator/offers`` — supplier price mutation. A stranger could poison the
#:   economics every other number on the site is derived from.
#: * ``webhooks/payments`` — a client-submitted "payment succeeded" is never trusted.
#: * ``threads``, ``issues``, ``close-pickup`` — no product surface in the demo needs
#:   them, and an endpoint nobody calls is an endpoint nobody has to reason about.
#:
#: ``members/{id}/payment-method`` stays off it too, and setup does not need it: it takes
#: a household id, and the only one setup ever wants is the caller's own. Exposing the
#: general form would also let somebody hand a working card to the synthetic household
#: whose card is seeded to decline — silently removing the payment-failure branch the
#: recovery story is built on. ``/api/onboarding/payment-method`` does the same job with
#: the household as a server constant, and that is what is allowlisted instead.
#: * ``host-response`` — the host's own accept/decline route. Real, and reachable on the
#:   full API, but the product answers host offers through the decision inbox like every
#:   other question Pool asks, so exposing a second path here would widen the surface
#:   without adding a capability.
ALLOWED_POST_PATTERNS = tuple(
    re.compile(p)
    for p in (
        # Amending one's own standing need. The ownership check lives in the service, so
        # this pattern being open does not let a caller rewrite another member's rules.
        rf"^/api/needs/{_ID}$",
        rf"^/api/decisions/{_ID}/respond$",
        rf"^/api/pools/{_ID}/pickup-credential/{_ID}$",
        rf"^/api/pools/{_ID}/redeem$",
        rf"^/api/pools/{_ID}/host-offer/{_ID}$",
        rf"^/api/pools/{_ID}/open-distribution$",
        rf"^/api/pools/{_ID}/withdraw/{_ID}$",
    )
)

#: Trigger name → the run prompt the *server* supplies for it. ``None`` means the
#: coordinator's own default discovery prompt.
#:
#: This map is the entire public prompt surface — a public caller selects a key, never a
#: value — and it is also what makes a local run and a deployed run the same run. It used
#: to be consulted only in public mode, so ``manual_advance`` against the local API fell
#: through to the *discovery* prompt and the agent went looking for new pools instead of
#: advancing the one in front of it. Same button, same name, different behaviour depending
#: on an environment variable, which is exactly the kind of difference that survives until
#: someone demonstrates it live.
TRIGGER_PROMPTS: dict[str, str | None] = {
    # The consumer's own **Run Pool now**. ``None`` because the server does not have a
    # fixed sentence for it: the coordinator derives the instruction from the member's
    # authoritative standing declarations (``agent/objective.py``), which is the whole
    # point of the trigger. A client selects the key and never the objective.
    "member_scan": None,
    "manual_scan": None,
    "manual_advance": (
        "Advance every pool that is blocked: recruit a host, refresh the supplier "
        "quote, issue final offers, recover lost demand, and lock anything that is "
        "fully funded and viable."
    ),
}

#: Triggers the live AgentCore action may send, keyed by the action the *server*
#: classifies the request as. Both must be in the runtime entrypoint's own
#: ``ALLOWED_TRIGGERS`` (``services/agent/agentcore_app.py``).
#:
#: The default is the member's own question, because the live button on the product is
#: the consumer's. The community scan stays reachable — it is what the scheduled
#: pool-day invocation means, and the technical surface exists to demonstrate it — but a
#: caller selects a key from this map and never an objective.
LIVE_TRIGGERS: dict[str, str] = {
    "member": "member_scan",
    "community": "scheduled_scan",
}
LIVE_TRIGGER = LIVE_TRIGGERS["member"]

#: Server-owned classification of the live action. The browser may use
#: ``allow_local_fallback`` to choose a safe path, but it must never infer safety from
#: an exception string or an HTTP transport failure.
LIVE_CLASS_SUCCESS = "success"
LIVE_CLASS_SAFE_REFUSAL = "safe_refusal"
LIVE_CLASS_SAFE_PRE_EXECUTION = "safe_pre_execution_failure"
LIVE_CLASS_AMBIGUOUS = "ambiguous_remote_execution"
LIVE_CLASS_WORKSPACE_BUSY = "workspace_busy"

#: How long the bridge waits for the runtime. The middle rung of three nested deadlines
#: — the agent's own wall-clock bound (``agentcore/agentcore.json``), then this, then the
#: Lambda's timeout (``infra/demo_app.py``) — so the innermost one fires first and the
#: caller gets a structured answer instead of a dropped connection. The ordering spans
#: three files and is asserted in ``infra/test_demo_stack.py``.
LIVE_READ_TIMEOUT_SECONDS = 60
LIVE_CONNECT_TIMEOUT_SECONDS = 5


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
    #: Raised from 40 when the demo stopped being a single scripted button and became a
    #: product a judge drives themselves. One complete hands-on run — scan, advance,
    #: answer two decisions, accept the host job, open pickup, then issue and redeem ten
    #: credentials — is around thirty actions, so 40 was a cap a genuine visitor could
    #: hit halfway through. These are free, deterministic, server-side operations; the
    #: cap exists to stop a script, not a judge. The paid action keeps its own far
    #: tighter budget (3/session, 40/day) and is untouched by this.
    max_actions_per_session: int = 100
    max_actions_per_day: int = 1200
    max_live_per_session: int = 3
    max_live_per_day: int = 40
    #: Seeding a cold workspace writes ~100 rows, and any read endpoint will do it for
    #: a workspace it has never seen. Without a cap, a script cycling session ids is an
    #: unbounded write generator, so new sessions are rationed per day.
    max_new_sessions_per_day: int = 300
    #: How long one workspace stays locked to a single live invocation. Must outlast the
    #: slowest thing that can still be writing — the runtime's own 45 s wall-clock bound
    #: plus cold start and network — because the lease is released on a clean return and
    #: otherwise left to expire. A failed invocation is indistinguishable, from here,
    #: from one still in flight, and holding is the safe direction to be wrong in.
    live_lease_seconds: int = 120
    #: How long a workspace stays locked to a single *local* mutating action — seeding,
    #: reset, the scenario, a local coordinator run. Sized to outlive the slowest holder
    #: that could die without releasing, which is this Lambda's own 90 s timeout
    #: (``infra/demo_app.py``). Shorter than the live lease because nothing here can
    #: still be writing from another compute environment once the request is gone.
    mutation_lease_seconds: int = 90
    #: A cold workspace is seeded by whichever request gets the lease; the others wait
    #: for it rather than seeding a second time over the top. Bounded, because a request
    #: that waits forever is worse than one that renders an empty community.
    seed_wait_seconds: float = 6.0

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
            live_lease_seconds=_int_env("PUBLIC_DEMO_LIVE_LEASE_SECONDS", 120),
            mutation_lease_seconds=_int_env("PUBLIC_DEMO_MUTATION_LEASE_SECONDS", 90),
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


# --------------------------------------------------------------------------- leases


class LeaseStore(Protocol):
    def acquire(self, key: str, seconds: int) -> bool:
        """Take an exclusive lease on ``key``. False means somebody else holds it."""
        ...

    def release(self, key: str) -> None:
        """Give the lease back early. Safe to call when it is not held."""
        ...


class InMemoryLeaseStore:
    """Per-process leases. Correct for a local run and for tests; adequate but not
    authoritative across Lambda containers, which is why the deployed demo uses the
    DynamoDB one."""

    def __init__(self) -> None:
        self._held: dict[str, float] = {}

    def acquire(self, key: str, seconds: int) -> bool:
        now = time.time()
        if self._held.get(key, 0.0) > now:
            return False
        self._held[key] = now + seconds
        return True

    def release(self, key: str) -> None:
        self._held.pop(key, None)


class DynamoDBLeaseStore:
    """One row per workspace, taken with a conditional write.

    The condition — no row, or a row whose lease has already expired — makes acquiring
    a single atomic operation, so two containers racing to start a run on one workspace
    cannot both win. **An expiry is required, not optional:** the holder is a Lambda
    that can be killed mid-flight, and a lease that outlives its holder would wedge a
    visitor's session until the TTL swept it. The row also carries ``ttl`` so DynamoDB
    eventually removes it, but correctness rests on ``until``, which is evaluated on
    every acquire — TTL deletion is best-effort and can lag by hours.
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

    def acquire(self, key: str, seconds: int) -> bool:
        now = int(time.time())
        try:
            self.table.update_item(
                Key={"pk": LEASE_PK, "sk": key},
                UpdateExpression="SET #until = :until, #ttl = :ttl",
                # `<=`, not `<`, so a hold is reclaimable the moment its time is up
                # rather than a second later — the same boundary
                # :class:`InMemoryLeaseStore` uses, so a local run and the deployed one
                # cannot disagree about when a lease has ended. Two containers arriving
                # on that exact second is still settled by the write being conditional:
                # the loser's condition is false against the winner's new value.
                ConditionExpression="attribute_not_exists(#until) OR #until <= :now",
                ExpressionAttributeNames={"#until": "until", "#ttl": "ttl"},
                ExpressionAttributeValues={
                    ":until": now + seconds,
                    ":now": now,
                    ":ttl": now + _DAY_TTL,
                },
            )
            return True
        except Exception as exc:  # noqa: BLE001 - the conditional failure is the signal
            if type(exc).__name__ == "ConditionalCheckFailedException":
                return False
            # A lease that cannot be taken must not become a way to run anyway. Fail
            # closed: refusing costs a visitor one retry, and the alternative is two
            # agents writing one partition.
            logger.warning("lease store unavailable for %s: %s", key, type(exc).__name__)
            return False

    def release(self, key: str) -> None:
        try:
            self.table.update_item(
                Key={"pk": LEASE_PK, "sk": key},
                UpdateExpression="SET #until = :zero",
                ExpressionAttributeNames={"#until": "until"},
                ExpressionAttributeValues={":zero": 0},
            )
        except Exception as exc:  # noqa: BLE001 - the lease expires on its own anyway
            logger.warning("lease release failed for %s: %s", key, type(exc).__name__)


def build_lease_store(settings: PublicDemoSettings) -> LeaseStore:
    if settings.quota_table:
        return DynamoDBLeaseStore(settings.quota_table, settings.region)
    return InMemoryLeaseStore()


# --------------------------------------------------------------------------- guard


class PublicDemoGuard:
    """The single object the API asks before doing anything a public caller triggered.

    The route allowlist, the prompt substitution, and the spend quotas are all no-ops
    when public mode is off, so the local API, ``make demo``, and the test suite behave
    exactly as they did before.

    The **workspace mutation lease is not**. It is correctness rather than rationing:
    two tabs pointed at one workspace can interleave a reset with a coordinator run on a
    laptop exactly as they can on Lambda, and a protection that only exists in
    production is one nothing ever tests.
    """

    def __init__(
        self,
        settings: PublicDemoSettings | None = None,
        quota: QuotaStore | None = None,
        bridge: AgentCoreBridge | None = None,
        lease: LeaseStore | None = None,
    ) -> None:
        self.settings = settings or PublicDemoSettings.from_env()
        self.quota = quota or build_quota_store(self.settings)
        self.lease = lease or build_lease_store(self.settings)
        self._bridge = bridge
        #: Re-entrancy depth per workspace, per request thread. See `hold_workspace`.
        self._local = threading.local()

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

    # -- exclusive access to one workspace -------------------------------
    #
    # One lease per workspace, taken by *every* coordinator that mutates it: seeding,
    # reset, the scenario, a local coordinator run, and the live AgentCore invocation.
    # They are mutually exclusive because they are all writing the same partition, and
    # which two happen to overlap is an accident of what a visitor clicked.
    #
    # It has to be one lock rather than one per action. Reset deletes every row while
    # the scenario is halfway through writing them; a local run and a live run both
    # create the pool the other is about to look for. Anything narrower would only move
    # the race.
    #
    # Unrelated workspaces never contend: the lease key *is* the workspace, so two
    # judges in two sessions are on two different rows.

    def hold_workspace(self, ws: str, seconds: int | None = None) -> bool:
        """Take this workspace's mutation lease, or return False.

        Two coordinators on one partition is not a theoretical race. Pool formation is
        idempotent on ``community:product:site:day``, but that idempotency is a read
        followed by a write: two runs that both find no matching pool will both create
        one, and the visitor ends up with a duplicate nobody asked for. The cost caps do
        not prevent it — three live invocations per session is three that can be in
        flight at once, from two tabs or a script.

        Re-entrant *within one request*. Handlers compose — a coordinator run seeds a
        cold workspace before it runs — and an inner acquisition that blocked on the
        lease its own caller is holding would deadlock a request against itself. The
        depth counter is thread-local because a sync FastAPI handler runs start to
        finish on one worker thread, so the count belongs to the request that opened it
        and never leaks into a concurrent one.

        Held regardless of ``enabled``. Two browser tabs are two browser tabs whether
        the process is a public Lambda or a laptop running ``make dev``, and the tests
        that prove this exercise the real lease rather than a bypass.
        """
        depth = self._depth()
        if depth.get(ws, 0) > 0:
            depth[ws] += 1
            return True
        window = self.settings.mutation_lease_seconds if seconds is None else seconds
        if not self.lease.acquire(ws, window):
            return False
        depth[ws] = 1
        return True

    def release_workspace(self, ws: str) -> None:
        """Give the lease back. Only the outermost holder actually releases it."""
        depth = self._depth()
        held = depth.get(ws, 0)
        if held > 1:
            depth[ws] = held - 1
            return
        depth.pop(ws, None)
        self.lease.release(ws)

    def abandon_workspace(self, ws: str) -> None:
        """Stop tracking the lease without releasing it, so it expires on its own.

        For the one case where releasing would be wrong: a live invocation that failed
        ambiguously may still be writing from another compute environment, and the lease
        is the only thing keeping a second coordinator out of that partition.
        """
        self._depth().pop(ws, None)

    def _depth(self) -> dict[str, int]:
        held = getattr(self._local, "held", None)
        if held is None:
            held = {}
            self._local.held = held
        return held

    @contextmanager
    def workspace_mutation(
        self, ws: str, message: str, seconds: int | None = None
    ) -> Iterator[None]:
        """Hold the mutation lease for the duration of one mutating action.

        Refuses with 409 rather than queueing: the caller is a browser, and a request
        that waits for a 45-second agent run has already failed. The lease is released
        on the way out however the body ends, including on an exception — a handler that
        raised has stopped writing, so continuing to hold would only wedge the visitor's
        own next click.
        """
        if not self.hold_workspace(ws, seconds):
            raise HTTPException(409, message)
        try:
            yield
        finally:
            self.release_workspace(ws)

    def require_workspace_idle(self, ws: str, message: str) -> None:
        """Acquire the workspace lease for an action that must not overlap another.

        Used by reset, which starts by deleting every row in the partition. The caller
        must release the lease in a ``finally`` block *after* the destructive operation
        completes. A check followed by an early release leaves a gap in which another
        coordinator can start while reset is deleting and reseeding the same partition.
        """
        if not self.hold_workspace(ws):
            raise HTTPException(409, message)

    # -- the prompt surface ----------------------------------------------

    def resolve_run(self, trigger: str, instruction: str | None) -> tuple[str, str | None]:
        """Return the ``(trigger, instruction)`` this run is allowed to use.

        Refusing a supplied ``instruction`` in public mode rather than dropping it is
        deliberate: a silently ignored field looks like it worked, and the first person to
        notice would be someone testing whether the agent can be steered.

        Outside public mode the full API is a development surface and a caller may write
        the prompt — but a caller who supplies *none* gets the same server-owned prompt the
        deployed demo would use, so the two behave identically for the triggers the product
        actually sends.
        """
        if not self.enabled:
            if instruction is None:
                return trigger, TRIGGER_PROMPTS.get(trigger)
            return trigger, instruction
        if instruction is not None:
            raise HTTPException(400, "this demo does not accept custom agent instructions")
        if trigger not in TRIGGER_PROMPTS:
            raise HTTPException(
                400, f"unknown action: {trigger}. Allowed: {sorted(TRIGGER_PROMPTS)}"
            )
        return trigger, TRIGGER_PROMPTS[trigger]

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


class RuntimeRefusal(RuntimeError):
    """The runtime answered, and its answer was a refusal.

    Worth its own type because it is the one failure where we know something the generic
    path does not: the entrypoint validates the payload *before* it builds a run, so a
    structured error means nothing was executed and nothing was written. Collapsing it
    into "the agent did not answer" would tell a visitor the call might still have
    finished — which is untrue — and would hold their workspace for the lease's full
    duration to protect writes that cannot exist.
    """


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
                # One attempt. A retried invocation is a second billed agent run against
                # shared state, and the caller would never know it happened
                # (AGENTS.md §3.1).
                #
                # ``total_max_attempts``, not ``max_attempts``. They are not synonyms:
                # botocore treats ``max_attempts`` as the legacy shorthand and resolves
                # it to ``total_max_attempts = max_attempts + 1``, so the obvious-looking
                # ``{"max_attempts": 1}`` asks for one *retry* — two invocations. That is
                # not a style point. Observed on the deployed stack (#0030): one live
                # action whose read timed out started two agent runs 17 ms apart, both
                # coordinating the same workspace, because the retry is issued inside
                # botocore and never passes the workspace lease that serialises callers.
                # One paid run became two, and the second was invisible from every side.
                config=Config(
                    connect_timeout=LIVE_CONNECT_TIMEOUT_SECONDS,
                    read_timeout=LIVE_READ_TIMEOUT_SECONDS,
                    retries={"total_max_attempts": 1, "mode": "standard"},
                ),
            )
        return self._client

    def invoke(self, workspace: str, trigger: str = LIVE_TRIGGER) -> dict[str, Any]:
        """Run one live coordination cycle on AWS, in ``workspace``, and project it.

        ``workspace`` is the caller's own session, already checked against
        :data:`PUBLIC_WORKSPACE_RE` by :meth:`PublicDemoGuard.check_workspace`. It is the
        only caller-derived value in the payload, and it is the payload's *whole*
        purpose: the runtime coordinates inside that partition, so the pool a visitor
        sees afterwards is the one this run created rather than a copy of its answer.

        ``trigger`` names which of two questions the run answers — the member's own
        declarations, or a community-wide scan — and is a key from :data:`LIVE_TRIGGERS`
        chosen by the server, never a value from the browser. Nothing about *whose*
        declarations travels: the runtime resolves the member from the workspace itself,
        so the payload carries no household id, no name and no contact detail.

        Everything else is still built here from constants — no prompt, no community id,
        no instruction. The runtime rejects a trigger outside its own allowlist, so even
        this value cannot be steered into a different behaviour.
        """
        session_id = new_session_id()
        if trigger not in set(LIVE_TRIGGERS.values()):
            raise ValueError(f"trigger not permitted on the live action: {trigger!r}")
        payload = json.dumps({"workspace": workspace, "trigger": trigger}).encode()

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
            raise RuntimeRefusal(str(result["error"])[:200])

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


def _live_note(observed: dict[str, Any]) -> str:
    """One sentence about where the state on the page came from.

    Both branches are read-backs, not claims about the model's answer. The second is
    written as an anomaly on purpose: the runtime reported a run id, and that run's own
    record is not in the workspace it says it wrote — which would mean the two halves
    are not looking at the same table, and is worth seeing rather than smoothing over.
    """
    if observed.get("run_pool_links_verified"):
        created = ", ".join(observed.get("created_pool_ids") or [])
        return (
            "This ran on Amazon Bedrock AgentCore against this demo session's data. "
            f"The database readback contains its run record and resulting pool {created}; "
            "the pool's stored created_by_run is this exact run id."
        )
    if observed.get("run_recorded"):
        return (
            "This ran on Amazon Bedrock AgentCore in a session generated here and used "
            "once, against this demo session's own data. Everything on the page below "
            "is read back from that data — including the agent's own run record."
        )
    return (
        "The deployed agent reported a completed run, but its run record is not "
        "readable in this session's data. Nothing on the page below has been changed to "
        "match the agent's answer; it is whatever the database actually holds."
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
    # The build emits a .woff alongside every .woff2 as a fallback. Serving it as
    # application/octet-stream mostly works and occasionally does not, which is the worst
    # kind of bug to ship on a demo URL.
    ".woff": "font/woff",
    ".png": "image/png",
    ".webmanifest": "application/manifest+json",
}


#: Reads authoritative state back after a live run: ``(workspace, run_id) -> facts``.
#: Supplied by ``pool/api/app.py``, which owns the repository. The bridge deliberately
#: cannot do this itself — it would then be able to *describe* state, and the one thing
#: this endpoint must never do is source its answer from anywhere but the store.
ObserveRun = Any


def install(app: FastAPI, guard: PublicDemoGuard, observe: Any = None) -> None:
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
        for name, value in SECURITY_HEADERS.items():
            response.headers[name] = value
        return response

    @app.post("/api/demo/agentcore")
    def demo_agentcore(workspace: str = "", action: str = "member") -> dict[str, Any]:
        """Invoke the deployed AgentCore Runtime, for real, once, on this session.

        Returns ``ok: false`` with a reason rather than raising for the situations a
        judge can hit legitimately — the switch being off, or AWS refusing. It never
        returns a fabricated run: if this says a run happened, one happened
        (AGENTS.md §8).

        It also never *reports* state. Whatever the run created is in DynamoDB, and the
        client re-reads ``/api/state`` for it. The ``observed`` block below is a
        read-back of that same store, not a description of the model's answer — which is
        the difference between proving the agent changed the world and taking its word.
        """
        # Read through the guard, never a captured copy: both kill switches and every
        # cap are environment variables so they can be changed on the deployed function
        # without a rebuild, and a handler holding a stale snapshot would ignore them.
        settings = guard.settings
        ws = guard.check_workspace(workspace)
        # A key, never a value. ``member`` is the consumer's own button; ``community``
        # is the scan the scheduled pool-day invocation performs. Anything else is a
        # caller inventing an objective, which is exactly what this refuses.
        trigger = LIVE_TRIGGERS.get(action, "")
        if not trigger:
            raise HTTPException(
                400, f"unknown action: {action}. Allowed: {sorted(LIVE_TRIGGERS)}"
            )
        if not settings.live_available:
            return {
                "ok": False,
                "live": False,
                "classification": LIVE_CLASS_SAFE_PRE_EXECUTION,
                "remote_may_still_write": False,
                "allow_local_fallback": True,
                "refresh_state": False,
                "reason": "The live agent action is switched off on this deployment.",
            }

        # The lease before the quota, deliberately. A double-click, two tabs, or a script
        # can put three permitted invocations in flight at once, and the loser of that
        # race must not also lose one of its three paid runs — so the free, per-workspace
        # check goes first and is handed straight back if the paid one refuses. (The same
        # reasoning as the session-before-day cap order in `_spend`, one level out.)
        if not guard.hold_workspace(ws, settings.live_lease_seconds):
            return {
                "ok": False,
                "live": False,
                "classification": LIVE_CLASS_WORKSPACE_BUSY,
                "remote_may_still_write": True,
                "allow_local_fallback": False,
                "refresh_state": True,
                "reason": (
                    "Something is already working on this session. "
                    "Wait for it to finish before starting another run."
                ),
            }
        try:
            guard.spend_live(ws)
        except HTTPException:
            guard.release_workspace(ws)
            raise

        try:
            result = guard.bridge.invoke(ws, trigger)
        except RuntimeRefusal as refusal:
            # A refusal is an answer. The runtime validated the payload and declined
            # before running anything, so the workspace goes straight back and the client
            # is told plainly rather than being warned about work that never started.
            guard.release_workspace(ws)
            logger.info("live agentcore invocation refused: %s", refusal)
            return {
                "ok": False,
                "live": False,
                "classification": LIVE_CLASS_SAFE_REFUSAL,
                "remote_may_still_write": False,
                "allow_local_fallback": True,
                "refresh_state": False,
                "reason": f"The deployed agent refused this request ({refusal}). "
                "Nothing in this session was changed.",
            }
        except Exception as exc:  # noqa: BLE001 - reported to the caller, not swallowed
            # The lease is *not* released here. From this side a timeout and a crash look
            # identical, and in the timeout case the runtime is very likely still writing
            # to this partition — so the workspace stays held until the lease expires on
            # its own. Refusing the next run for a minute is cheap; letting a second
            # agent into a partition a first one is still mutating is not.
            #
            # `abandon` rather than `release`: the request stops tracking the lease so a
            # later action on this same thread does not decrement a hold it no longer
            # owns, while the row itself is left to expire. This is the one path where
            # the reply is *also* what keeps the local coordinator out — the client is
            # told `allow_local_fallback: false`, and any local run it tried anyway would
            # now find the workspace held.
            guard.abandon_workspace(ws)
            logger.warning("live agentcore invocation failed: %s", type(exc).__name__)
            return {
                "ok": False,
                "live": False,
                "classification": LIVE_CLASS_AMBIGUOUS,
                "remote_may_still_write": True,
                "allow_local_fallback": False,
                "refresh_state": True,
                "reason": (
                    "The deployed agent did not answer this time "
                    f"({type(exc).__name__}). It may still have finished on AWS — the "
                    "state on this page is read back from the database either way, so "
                    "it shows whatever actually happened. The session remains protected "
                    "until it is safe to retry."
                ),
            }
        guard.release_workspace(ws)

        observed = observe(ws, result["run"].get("run_id") or "") if observe else {}
        return {
            "ok": True,
            "live": True,
            "classification": LIVE_CLASS_SUCCESS,
            "remote_may_still_write": False,
            "allow_local_fallback": False,
            "service": "Amazon Bedrock AgentCore Runtime",
            "runtime": settings.runtime_label,
            "region": settings.region,
            "wall_ms": result["wall_ms"],
            "run": result["run"],
            "observed": observed,
            "refresh_state": True,
            "note": _live_note(observed),
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
