"""Public judge demo — infrastructure tests.

The demo stack is small enough to read, which is exactly why it is worth pinning: the
risk is not complexity, it is that something quietly grows. These assert the five
claims the stack is deployed on.

1. **Nothing always-on, nothing unbounded.** Per-request billing, capped retention,
   TTL'd data, and a hard concurrency ceiling.
2. **The browser gets no credential and no privilege.** The function's only privileged
   action is invoking one named AgentCore runtime.
3. **Payments and purchasing stay simulated,** pinned in the deployed environment
   rather than trusted to a default.
4. **The whole thing tears down** — every resource is DESTROY, and the log group is in
   the stack rather than created implicitly by Lambda and left behind (#0023).
5. **A judge can actually reach it.** The CDN added in #0065 exists because
   `*.lambda-url.*.on.aws` is a blocked category on filtered networks, and putting a
   cache in front of a stateful same-origin app has four silent failure modes that a
   successful deploy will not reveal. `TestCdn` covers each one.

Runs offline: synthesis needs no AWS credentials.
"""

from __future__ import annotations

import ast
import json
import pathlib

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template

from demo_app import TABLE_NAME, PoolDemoStack

ARN = "arn:aws:bedrock-agentcore:us-east-1:111111111111:runtime/Pool_PoolCoordinator-Abc123"

ROOT = pathlib.Path(__file__).resolve().parent.parent


def agentcore_runtime() -> dict:
    """The coordinator's deployed configuration, with its env vars as a plain dict.

    Read from the file the AgentCore CLI deploys from, not from a copy — the whole
    reason these tests exist is that this stack and that one are deployed by different
    tools and have to agree about a table.
    """
    spec = json.loads((ROOT / "agentcore" / "agentcore.json").read_text())
    runtime = next(r for r in spec["runtimes"] if r["name"] == "PoolCoordinator")
    return {**runtime, "envVars": {v["name"]: v["value"] for v in runtime["envVars"]}}


def agentcore_target() -> dict:
    """The deployment target the AgentCore CLI uses — the source of the pinned region."""
    targets = json.loads((ROOT / "agentcore" / "aws-targets.json").read_text())
    return next(t for t in targets if t["name"] == "default")


def _actions(statement: dict) -> list[str]:
    """A statement's actions, whether CDK emitted one string or a list."""
    actions = statement["Action"]
    return actions if isinstance(actions, list) else [actions]


def runtime_dynamodb_policy() -> dict:
    """The inline IAM policy `agentcore.json` attaches to the runtime's execution role."""
    entry = agentcore_runtime()["additionalPolicies"][0]
    return json.loads((ROOT / "services" / "agent" / entry).read_text())


def public_demo_constant(name: str):
    """One module-level constant from ``pool/api/public_demo.py``, read without importing.

    The agent package is not installed in this virtualenv — infra depends on CDK and
    nothing else — and adding FastAPI here to read one number would be a worse trade
    than parsing the assignment. `ast` rather than a regex so a moved or renamed
    constant is a clean failure instead of a silent no-match.
    """
    source = (ROOT / "services" / "agent" / "pool" / "api" / "public_demo.py").read_text()
    for node in ast.parse(source).body:
        # Both forms, because a constant gaining a type annotation turns `Assign` into
        # `AnnAssign` and would otherwise read as "the constant was renamed".
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return ast.literal_eval(node.value)
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
            and node.value is not None
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} is not a module-level constant of public_demo.py")

#: Resource types whose presence would mean this stack bills while nobody is looking.
#:
#: ``AWS::CloudFront::Distribution`` **was** in this list and was removed in #0065, when a
#: distribution was deliberately added to make the demo reachable from filtered networks.
#: The removal is a correction, not an exemption: CloudFront has no hourly or idle charge,
#: so it never belonged beside EC2, RDS, a NAT gateway or a load balancer, all of which bill
#: by the hour with zero traffic. It bills per request and per GB, both inside a perpetual
#: free tier. The properties that *could* make a distribution cost money while idle —
#: access logging into a bucket, real-time logs, Origin Shield — are asserted absent by
#: ``TestCdn`` instead, which is a tighter check than this list could express anyway.
ALWAYS_ON = [
    "AWS::EC2::Instance",
    "AWS::RDS::DBInstance",
    "AWS::EC2::NatGateway",
    "AWS::ElasticLoadBalancingV2::LoadBalancer",
    "AWS::OpenSearchService::Domain",
    "AWS::ECS::Service",
    "AWS::ElastiCache::CacheCluster",
    "AWS::Redshift::Cluster",
    "AWS::ApiGatewayV2::Api",
    "AWS::Events::Rule",
]

#: The managed policies the CDN is pinned to, by the id CloudFront publishes for them.
#: Asserting the id rather than the shape is deliberate: these are AWS-managed and the
#: template only ever carries the reference, so the id *is* the contract.
CACHING_DISABLED = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
CACHING_OPTIMIZED = "658327ea-f89d-4fab-a63d-7e88639e58f6"
ALL_VIEWER_EXCEPT_HOST_HEADER = "b689b0a8-53d0-40ab-baf2-68738e2966ac"


@pytest.fixture(scope="module")
def bundle(tmp_path_factory) -> str:
    """A stand-in for build/demo-lambda. The real bundle's contents are checked by
    scripts/build_demo_bundle.sh; what matters here is the stack's shape."""
    root = tmp_path_factory.mktemp("bundle")
    (root / "pool").mkdir()
    (root / "pool" / "__init__.py").write_text("")
    (root / "web").mkdir()
    (root / "web" / "index.html").write_text("<!doctype html>")
    return str(root)


@pytest.fixture(scope="module")
def template(bundle) -> Template:
    app = cdk.App(outdir="cdk.out.demotest")
    stack = PoolDemoStack(
        app,
        "TestDemoStack",
        bundle_path=bundle,
        agentcore_runtime_arn=ARN,
        env=cdk.Environment(account="111111111111", region="us-east-1"),
    )
    return Template.from_stack(stack)


@pytest.fixture(scope="module")
def function_env(template: Template) -> dict:
    fns = template.find_resources("AWS::Lambda::Function")
    assert len(fns) == 1, "the demo is one function; a second one is a design change"
    return next(iter(fns.values()))["Properties"]["Environment"]["Variables"]


@pytest.fixture(scope="module")
def cdn(template: Template) -> dict:
    """The distribution's config — one, in front of the one function."""
    dists = template.find_resources("AWS::CloudFront::Distribution")
    assert len(dists) == 1, "one distribution in front of one origin"
    return next(iter(dists.values()))["Properties"]["DistributionConfig"]


def behavior(cdn: dict, path: str) -> dict:
    """The cache behaviour that serves ``path``, or the default one for ``*``."""
    if path == "*":
        return cdn["DefaultCacheBehavior"]
    matches = [b for b in cdn.get("CacheBehaviors", []) if b["PathPattern"] == path]
    patterns = [b["PathPattern"] for b in cdn.get("CacheBehaviors", [])]
    assert matches, f"no behaviour for {path}; the stack has {patterns}"
    return matches[0]


class TestCostSafety:
    @pytest.mark.parametrize("resource_type", ALWAYS_ON)
    def test_nothing_bills_while_nobody_is_looking(self, template: Template, resource_type):
        assert template.find_resources(resource_type) == {}, resource_type

    def test_the_table_is_on_demand(self, template: Template):
        template.has_resource_properties(
            "AWS::DynamoDB::Table", {"BillingMode": "PAY_PER_REQUEST"}
        )

    def test_demo_sessions_expire_by_themselves(self, template: Template):
        template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {"TimeToLiveSpecification": {"AttributeName": "ttl", "Enabled": True}},
        )

    def test_log_retention_is_capped_and_the_group_belongs_to_the_stack(
        self, template: Template
    ):
        """An implicit Lambda log group retains forever and survives `cdk destroy`."""
        template.has_resource_properties("AWS::Logs::LogGroup", {"RetentionInDays": 14})
        fns = template.find_resources("AWS::Lambda::Function")
        props = next(iter(fns.values()))["Properties"]
        assert "LoggingConfig" in props, "the function must log to the stack's own group"

    def test_the_default_stack_reserves_no_concurrency(self, template: Template):
        """Because AWS will not let it.

        `account_limit - sum(reserved) >= 10` is enforced by Lambda, and a new account's
        limit *is* 10 — so any nonzero reservation is rejected and the deploy rolls back
        (it did, once). The ceiling still exists: with no other function in the account,
        the account limit caps this function. The property is opt-in for accounts whose
        limit has been raised.
        """
        fns = template.find_resources("AWS::Lambda::Function")
        props = next(iter(fns.values()))["Properties"]
        assert "ReservedConcurrentExecutions" not in props

    def test_a_configured_reservation_still_reaches_the_template(self, bundle, monkeypatch):
        """The control is dormant, not deleted."""
        import demo_app

        monkeypatch.setattr(demo_app, "RESERVED_CONCURRENCY", 5)
        app = cdk.App(outdir="cdk.out.demotest")
        stack = demo_app.PoolDemoStack(
            app,
            "ReservedStack",
            bundle_path=bundle,
            agentcore_runtime_arn=ARN,
            env=cdk.Environment(account="111111111111", region="us-east-1"),
        )
        fns = Template.from_stack(stack).find_resources("AWS::Lambda::Function")
        assert next(iter(fns.values()))["Properties"]["ReservedConcurrentExecutions"] == 5

    def test_a_wedged_request_cannot_run_for_minutes(self, template: Template):
        """Long enough for a live agent invocation, short enough to be a real ceiling.

        It was 30 s, which is ample for everything the function does by itself and not
        for waiting on the deployed agent: the function would have been killed
        mid-invocation while the runtime carried on writing to the visitor's workspace,
        which is the single failure mode where the browser is told nothing happened and
        something did. The bound is now the outermost of three (see
        ``test_the_deadlines_nest_innermost_first``) and still caps a stuck request at
        roughly a tenth of a cent.
        """
        fns = template.find_resources("AWS::Lambda::Function")
        assert next(iter(fns.values()))["Properties"]["Timeout"] <= 120

    def test_the_deadlines_nest_innermost_first(self, template: Template):
        """Agent wall clock < bridge read timeout < function timeout.

        Whichever deadline fires, the caller gets a structured answer rather than a
        dropped connection: the agent's own bound ends the run as a recorded loop fault
        and still returns it, and the bridge's read timeout becomes a reported failure
        here. Invert any pair and the outer layer starts killing the inner one
        mid-write, which is exactly the case that leaves shared state changed and the
        browser uninformed. The three numbers live in three files, which is why this is
        worth asserting rather than commenting.
        """
        fns = template.find_resources("AWS::Lambda::Function")
        function_timeout = next(iter(fns.values()))["Properties"]["Timeout"]
        agent_bound = int(agentcore_runtime()["envVars"]["WORKFLOW_TIMEOUT_SECONDS"])
        bridge_read = public_demo_constant("LIVE_READ_TIMEOUT_SECONDS")

        assert agent_bound < bridge_read < function_timeout, (
            agent_bound,
            bridge_read,
            function_timeout,
        )

    def test_everything_is_destroyable(self, template: Template):
        for logical_id, resource in template.to_json()["Resources"].items():
            policy = resource.get("DeletionPolicy", "Delete")
            assert policy == "Delete", f"{logical_id} would survive teardown ({policy})"

    def test_the_stack_creates_nothing_recurring(self, template: Template):
        for kind in ("AWS::Events::Rule", "AWS::Scheduler::Schedule", "AWS::Lambda::EventSourceMapping"):
            assert template.find_resources(kind) == {}, kind


class TestPublicSafety:
    def test_the_demo_runs_in_judge_mode(self, function_env):
        """Without this the deployed function would expose all 40 endpoints and an
        arbitrary agent prompt."""
        assert function_env["POOL_PUBLIC_DEMO"] == "true"

    def test_the_public_surface_never_invokes_bedrock_directly(self, function_env):
        """Every action a judge can spam runs the deterministic offline planner. The
        only model tokens this demo can spend go through the capped live action."""
        assert function_env["MODEL_PROVIDER"] == "offline"

    def test_payments_and_purchasing_are_pinned_to_simulated(self, function_env):
        assert function_env["PAYMENT_PROVIDER"] == "simulated"
        assert function_env["PURCHASE_EXECUTOR"] == "simulated"

    def test_schedules_are_off(self, function_env):
        assert function_env["SCHEDULES_ENABLED"] == "false"

    def test_the_abuse_caps_are_present_and_finite(self, function_env):
        for key in (
            "PUBLIC_DEMO_MAX_ACTIONS_PER_SESSION",
            "PUBLIC_DEMO_MAX_ACTIONS_PER_DAY",
            "PUBLIC_DEMO_MAX_LIVE_PER_SESSION",
            "PUBLIC_DEMO_MAX_LIVE_PER_DAY",
            "PUBLIC_DEMO_MAX_NEW_SESSIONS_PER_DAY",
        ):
            assert int(function_env[key]) > 0, key

    def test_the_agent_bounds_travel_with_the_deployment(self, function_env):
        assert int(function_env["MAX_AGENT_ITERATIONS"]) == 8
        assert int(function_env["MAX_TOOL_CALLS_PER_RUN"]) == 25
        assert int(function_env["WORKFLOW_TIMEOUT_SECONDS"]) == 45

    def test_no_bound_is_configured_that_nothing_enforces(self, function_env):
        """Every bound shipped here has to correspond to code that reads it.

        `MAX_TOOL_RETRIES=3` travelled with both stacks and with the runtime, was listed
        in the cost notes as "bounded with backoff", and was read by nothing: Pool has no
        generic tool-retry mechanism. A configured limit for behaviour that does not
        exist is worse than no limit, because it reads as a guarantee (#audit P1-1).
        """
        runtime_env = agentcore_runtime()["envVars"]
        for env, where in ((function_env, "the function"), (runtime_env, "the runtime")):
            offenders = [
                k for k in env if k.startswith("MAX_") and k.endswith(("_RETRIES", "_ATTEMPTS"))
            ]
            assert offenders == [], f"{offenders} configured on {where}, enforced nowhere"

    def test_every_published_bound_is_one_a_run_can_actually_hit(
        self, template: Template, function_env
    ):
        """`/api/health` publishes these, and the Live-on-AWS view prints them as the
        limits every run is held to. So each one has to be reachable, and the wall clock
        has to mean the same thing in both places a run can execute.

        It did not. The function shipped `WORKFLOW_TIMEOUT_SECONDS=120` against its own
        90 s Lambda timeout, so that bound could never fire — Lambda killed the request
        first — while the runtime's identical-named bound was 45. The page printed 120
        beside a deployed run held to 45 (#0030). An unreachable limit is worse than a
        loose one: it reads as a guarantee and enforces nothing.
        """
        fns = template.find_resources("AWS::Lambda::Function")
        function_timeout = next(iter(fns.values()))["Properties"]["Timeout"]
        local_bound = int(function_env["WORKFLOW_TIMEOUT_SECONDS"])
        remote_bound = int(agentcore_runtime()["envVars"]["WORKFLOW_TIMEOUT_SECONDS"])

        assert local_bound == remote_bound, (
            "one number is published for both execution paths; they must agree or the "
            f"page is lying about one of them ({local_bound} here, {remote_bound} on "
            "the runtime)"
        )
        assert local_bound < function_timeout, (
            f"a {local_bound}s agent bound inside a {function_timeout}s function can "
            "never fire"
        )

        # The other three bounds are environment-independent, so the page may state them
        # flatly. Pin that they are, since the wall clock stopped being so once.
        for key in ("MAX_AGENT_ITERATIONS", "MAX_TOOL_CALLS_PER_RUN", "MAX_DUPLICATE_TOOL_CALLS"):
            assert function_env[key] == agentcore_runtime()["envVars"][key], key

    def test_the_live_action_has_its_own_kill_switch(self, function_env):
        """Turning off the paid path must not require taking the demo down."""
        assert function_env["PUBLIC_DEMO_AGENTCORE_ENABLED"] in {"true", "false"}

    def test_no_credential_is_baked_into_the_template(self, template: Template):
        body = json.dumps(template.to_json())
        for marker in ("sk_test_", "sk_live_", "whsec_", "AKIA", "aws_secret_access_key"):
            assert marker not in body, marker

    def test_no_stripe_configuration_reaches_the_deployed_function(self, function_env):
        assert "STRIPE_API_KEY" not in function_env
        assert "STRIPE_WEBHOOK_SECRET" not in function_env


class TestLeastPrivilege:
    def test_the_only_privileged_action_is_invoking_one_named_runtime(
        self, template: Template
    ):
        """This role is what stands between an anonymous URL and the account. It may
        read and write one table, and invoke one agent runtime. Nothing else."""
        policies = template.find_resources("AWS::IAM::Policy")
        statements = [
            s
            for p in policies.values()
            for s in p["Properties"]["PolicyDocument"]["Statement"]
        ]
        agent = [s for s in statements if "bedrock-agentcore" in json.dumps(s["Action"])]
        assert len(agent) == 1
        assert agent[0]["Action"] == "bedrock-agentcore:InvokeAgentRuntime"
        for resource in agent[0]["Resource"]:
            assert resource.startswith(ARN), resource

    def test_the_function_gets_only_the_dynamodb_actions_it_issues(
        self, template: Template
    ):
        """`grant_read_write_data` is a convenience, not a policy.

        It also hands out Scan, DescribeTable, BatchGetItem, ConditionCheckItem,
        DeleteItem and the stream read actions, none of which appear anywhere in
        `pool/`. Scan is the one that matters: it is what turns a single-table,
        per-workspace design into a whole-table read (#audit P1-6).
        """
        statements = [
            statement
            for policy in template.find_resources("AWS::IAM::Policy").values()
            for statement in policy["Properties"]["PolicyDocument"]["Statement"]
        ]
        dynamo = {
            action
            for statement in statements
            for action in _actions(statement)
            if action.startswith("dynamodb:")
        }

        assert dynamo == {
            "dynamodb:GetItem",
            "dynamodb:PutItem",
            "dynamodb:Query",
            "dynamodb:UpdateItem",
            "dynamodb:BatchWriteItem",
        }, dynamo
        assert "dynamodb:Scan" not in dynamo
        assert "dynamodb:DeleteItem" not in dynamo

    def test_no_dynamodb_grant_reaches_beyond_this_stacks_table(self, template: Template):
        """A wildcard table ARN would make the workspace isolation decorative."""
        for policy in template.find_resources("AWS::IAM::Policy").values():
            for statement in policy["Properties"]["PolicyDocument"]["Statement"]:
                if not any(a.startswith("dynamodb:") for a in _actions(statement)):
                    continue
                resources = statement["Resource"]
                resources = resources if isinstance(resources, list) else [resources]
                for resource in resources:
                    assert resource != "*", statement
                    assert isinstance(resource, dict), resource  # a Fn::GetAtt, not a string

    def test_no_statement_grants_a_wildcard_action(self, template: Template):
        policies = template.find_resources("AWS::IAM::Policy")
        for policy in policies.values():
            for statement in policy["Properties"]["PolicyDocument"]["Statement"]:
                actions = statement["Action"]
                actions = actions if isinstance(actions, list) else [actions]
                for action in actions:
                    assert action != "*", statement
                    assert not action.endswith(":*"), statement

    def test_the_function_cannot_reach_bedrock_models_directly(self, template: Template):
        """Model access belongs to the AgentCore runtime's own execution role. A second
        path to Bedrock here would be a second thing that can spend tokens."""
        body = json.dumps(template.to_json())
        assert "bedrock:InvokeModel" not in body

    def test_the_role_holds_no_administrator_policy(self, template: Template):
        template.has_resource_properties(
            "AWS::IAM::Role",
            {
                "ManagedPolicyArns": Match.array_with(
                    [
                        {
                            "Fn::Join": [
                                "",
                                [
                                    "arn:",
                                    {"Ref": "AWS::Partition"},
                                    ":iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
                                ],
                            ]
                        }
                    ]
                )
            },
        )
        assert "AdministratorAccess" not in json.dumps(template.to_json())


class TestSharedWorkspaceContract:
    """The agreement between this stack and the AgentCore one.

    The public demo's Lambda and the deployed coordinator now read and write the same
    DynamoDB table, and they are deployed by two different tools from two different
    directories — this CDK app, and the AgentCore CLI reading ``agentcore/``. Nothing in
    either tool can express the dependency, and neither can be deployed second without
    breaking the other if the two disagree. So the contract is a constant in three
    places, and this class is what keeps the three the same.

    A failure here is not a style problem: a table name that has drifted means the
    deployed agent writes to a table nobody reads, and the demo silently goes back to
    being two disconnected halves.
    """

    def test_the_table_has_an_explicit_name_the_other_stack_can_reference(
        self, template: Template
    ):
        template.has_resource_properties("AWS::DynamoDB::Table", {"TableName": TABLE_NAME})

    def test_the_runtime_is_pointed_at_that_exact_table(self):
        env = agentcore_runtime()["envVars"]
        assert env["DYNAMODB_TABLE"] == TABLE_NAME
        assert env["POOL_REPOSITORY"] == "dynamodb", (
            "an in-memory runtime cannot mutate the workspace the browser is reading"
        )

    def test_the_runtimes_iam_grant_names_that_exact_table(self):
        statements = runtime_dynamodb_policy()["Statement"]
        assert len(statements) == 1
        assert statements[0]["Resource"].endswith(f"table/{TABLE_NAME}")

    def test_the_runtime_may_read_and_write_but_never_delete(self):
        """The asymmetry the whole design rests on. The API owns workspaces — it seeds
        them, resets them, and rations how many exist; the runtime is a participant
        inside one that already exists. ``DeleteItem`` and ``BatchWriteItem`` are what
        ``Repository.reset()`` needs to empty a partition, so withholding them means the
        most destructive operation in the codebase is unavailable to the agent by
        construction rather than by care."""
        actions = set(runtime_dynamodb_policy()["Statement"][0]["Action"])
        assert actions == {"dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query"}

    def test_the_runtime_grant_is_scoped_to_one_table_in_one_region(self):
        """The table segment must not be a prefix, and the region must not be a wildcard.

        The region *was* one, which granted the runtime access to a same-named table in
        every region for no reason — the deployment target is pinned to us-east-1 in
        `agentcore/aws-targets.json`, so there was nothing the wildcard bought (#audit
        P1-6).

        The account stays a wildcard deliberately. This policy is attached to a role that
        can only ever act in its own account, so pinning it narrows nothing real, and it
        would make a fork edit two files to deploy instead of one.
        """
        resource = runtime_dynamodb_policy()["Statement"][0]["Resource"]
        region = agentcore_target()["region"]

        assert isinstance(resource, str)
        assert not resource.endswith("*"), resource
        assert resource == f"arn:aws:dynamodb:{region}:*:table/{TABLE_NAME}", resource
        assert resource.count("*") == 1, resource

    def test_both_halves_read_their_own_writes(self, function_env):
        """Two compute environments writing one partition inside a single user action.
        An eventually consistent read can be served by a replica that has not seen the
        other's writes yet, which would show a visitor the world as it was before the
        agent ran — on the one page whose entire claim is the opposite."""
        assert function_env["DYNAMODB_CONSISTENT_READS"] == "true"
        assert agentcore_runtime()["envVars"]["DYNAMODB_CONSISTENT_READS"] == "true"

    def test_every_live_trigger_is_one_the_runtime_accepts(self):
        """The bridge sends a trigger name; the entrypoint validates it against a fixed
        set. A mismatch is a refusal at the far end, visible only in production.

        Every value, not just the default: the live action now offers two questions — the
        member's own declarations and the community-wide scan — and the one a judge
        reaches least often is exactly the one whose mismatch would survive a rehearsal.
        """
        source = (ROOT / "services" / "agent" / "agentcore_app.py").read_text()
        allowed = next(
            ast.literal_eval(node.value)
            for node in ast.parse(source).body
            if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "ALLOWED_TRIGGERS" for t in node.targets)
        )
        triggers = public_demo_constant("LIVE_TRIGGERS")
        assert triggers, "the live action must name at least one trigger"
        for action, trigger in triggers.items():
            assert trigger in allowed, f"{action} sends {trigger!r}, which the runtime refuses"


class TestShape:
    def test_the_origin_is_a_function_url(self, template: Template):
        """API Gateway would be a second resource, a second stage, and a second place
        for CORS to be wrong.

        The *public entry point* is now the CDN — see ``TestCdn`` — but what sits behind
        it is still one Function URL and not a gateway. The URL is also still `NONE`
        auth and still directly reachable: the CDN was added for a hostname filtered
        networks resolve, not to hide the origin, and keeping the origin public leaves a
        fallback for the one path where the CDN's 60 s ceiling can fire first (#0065).
        """
        template.has_resource_properties("AWS::Lambda::Url", {"AuthType": "NONE"})
        assert template.find_resources("AWS::ApiGateway::RestApi") == {}
        assert template.find_resources("AWS::ApiGatewayV2::Api") == {}

    def test_the_web_app_ships_inside_the_function(self, function_env, template: Template):
        """No bucket, no invalidation step — and no cross-origin request to secure,
        because the app and the API still share an origin.

        A CDN in front of the function does not change any of that: it caches
        `/assets/*`, whose filenames Vite content-hashes, so a redeploy publishes new
        URLs rather than needing a purge. What was rejected was S3 as the *origin*.
        """
        assert function_env["PUBLIC_DEMO_WEB_ROOT"] == "/var/task/web"
        assert template.find_resources("AWS::S3::Bucket") == {}

    def test_the_runtime_matches_what_the_bundle_is_built_for(self, template: Template):
        """scripts/build_demo_bundle.sh resolves manylinux wheels for this exact
        version. A mismatch is a cold-start ImportError, not a build failure."""
        template.has_resource_properties("AWS::Lambda::Function", {"Runtime": "python3.13"})

    def test_state_is_durable_so_a_cold_container_does_not_lose_a_judges_demo(
        self, function_env
    ):
        assert function_env["POOL_REPOSITORY"] == "dynamodb"

    def test_the_stack_is_tagged_for_cleanup(self, template: Template):
        fns = template.find_resources("AWS::Lambda::Function")
        tags = {t["Key"]: t["Value"] for t in next(iter(fns.values()))["Properties"]["Tags"]}
        assert tags["Project"] == "Pool"
        assert tags["Hackathon"] == "AgentsForHumans"
        assert tags["Component"] == "PublicDemo"

    def test_the_stack_stays_small(self, template: Template):
        """A guard against drift, not a rule about the number nine. If this stack
        grows, that should be a decision someone made, not a diff nobody read.

        It was eight against a ceiling of ten. The CloudFront distribution added in
        #0065 is the ninth, and the ceiling moved with it so the headroom is what it
        was — moving the ceiling is the decision being recorded, which is the point.
        """
        resources = template.to_json()["Resources"]
        assert len(resources) <= 11, sorted(resources)

    def test_the_live_action_can_be_deployed_switched_off(self, bundle):
        """A deployment with no runtime ARN must still be a valid, safe stack — and
        must grant no agent permission at all."""
        app = cdk.App(outdir="cdk.out.demotest")
        stack = PoolDemoStack(
            app,
            "NoAgentStack",
            bundle_path=bundle,
            agentcore_runtime_arn="",
            env=cdk.Environment(account="111111111111", region="us-east-1"),
        )
        body = json.dumps(Template.from_stack(stack).to_json())
        assert "bedrock-agentcore:InvokeAgentRuntime" not in body


class TestCdn:
    """The distribution added in #0065, and the four ways it could have broken the demo.

    It exists for one reason: `*.lambda-url.*.on.aws` is a blocked category on filtered
    resolvers (Cisco Umbrella on this university's network answers the demo's hostname
    with a block-page address and an untrusted certificate), so a judge on such a network
    sees `ERR_CERT_AUTHORITY_INVALID` and reads it as a broken demo. `*.cloudfront.net`
    is not in that category.

    Putting a CDN in front of a stateful, mutating, same-origin app has four specific
    failure modes, and every one of them is silent — the deploy succeeds and the demo
    misbehaves. Each has a test here.
    """

    def test_the_host_header_never_reaches_the_origin(self, cdn):
        """The one misconfiguration that breaks everything.

        A Function URL authorises against its own hostname. Forward the viewer's `Host`
        — which `ALL_VIEWER`, the obvious-looking policy, does — and every request is
        rejected at the origin. `ALL_VIEWER_EXCEPT_HOST_HEADER` exists for exactly this
        pairing, and it must be the policy on the dynamic path.
        """
        assert (
            behavior(cdn, "*")["OriginRequestPolicyId"] == ALL_VIEWER_EXCEPT_HOST_HEADER
        )

    def test_one_workspace_can_never_be_served_anothers_state(self, cdn):
        """Why the dynamic path is uncached rather than briefly cached.

        The demo identifies a visitor's workspace with a **query parameter**, not a
        cookie. Any cache policy that dropped the query string from the key would hand
        one visitor another's pool — a correctness failure wearing a performance
        feature's clothes. `CachingDisabled` cannot make that mistake at any TTL.
        """
        assert behavior(cdn, "*")["CachePolicyId"] == CACHING_DISABLED

    def test_every_mutation_survives_the_cdn(self, cdn):
        """CloudFront's default is GET/HEAD, which would 403 every action in the product.

        Onboarding, declaring a need, advancing a pool, the live agent run — all POST.
        A distribution that allows only reads turns a working demo into a read-only one.
        """
        allowed = set(behavior(cdn, "*")["AllowedMethods"])
        assert {"POST", "PUT", "PATCH", "DELETE", "OPTIONS"} <= allowed

    def test_the_cdn_does_not_become_the_shortest_deadline(self, cdn, function_env):
        """The #0030 inversion, one layer further out.

        CloudFront's default origin timeout is 30 s. The agent's own wall-clock bound is
        45 s, so the default would have shown a judge a CDN 504 while the function was
        still working and the runtime was still writing — the exact failure where shared
        state changes and the browser is told nothing happened. The CDN's ceiling has to
        sit outside the agent's bound.
        """
        agent_bound = int(function_env["WORKFLOW_TIMEOUT_SECONDS"])
        cdn_timeout = cdn["Origins"][0]["CustomOriginConfig"]["OriginReadTimeout"]
        assert cdn_timeout > agent_bound, (
            f"CDN would cut the agent off: {cdn_timeout}s vs the agent's {agent_bound}s"
        )

    def test_a_cleared_error_is_not_served_for_ten_more_seconds(self, cdn):
        """CloudFront applies a 10 s error-caching TTL regardless of the cache policy.

        On a stateful demo that means a quota refusal or a validation error keeps being
        served after the condition clears, and the retry that should have worked looks
        like a broken app. Every code CloudFront will cache is pinned to zero.
        """
        ttls = {e["ErrorCode"]: e["ErrorCachingMinTTL"] for e in cdn["CustomErrorResponses"]}
        assert ttls, "no error caching configured; CloudFront's 10 s default would apply"
        assert set(ttls.values()) == {0}, ttls

    def test_static_assets_are_cached_because_their_names_are_hashed(self, cdn):
        """The one safe thing to cache, and the reason no invalidation step is needed.

        Vite content-hashes everything under `/assets/`, so a cached object cannot go
        stale — a rebuilt asset is a different URL. `index.html`, which names those URLs,
        is served by the uncached default behaviour.
        """
        assets = behavior(cdn, "/assets/*")
        assert assets["CachePolicyId"] == CACHING_OPTIMIZED
        assert set(assets["AllowedMethods"]) == {"GET", "HEAD"}
        assert "OriginRequestPolicyId" not in assets or not assets["OriginRequestPolicyId"], (
            "assets need no viewer forwarding, and forwarding Host would break the origin"
        )

    def test_the_distribution_bills_nothing_while_idle(self, cdn, template: Template):
        """Why CloudFront was removed from ALWAYS_ON rather than exempted from it.

        A distribution has no hourly charge; it bills per request and per GB, inside a
        perpetual free tier. What *could* cost money with no visitors is the optional
        machinery — access logs need a bucket (and a bucket that outlives `cdk destroy`
        is the orphan shape of #0023), real-time logs bill per record, Origin Shield adds
        a surcharge and a second region. None of it is here.
        """
        assert "Logging" not in cdn, "access logging would need a bucket this stack lacks"
        assert template.find_resources("AWS::S3::Bucket") == {}
        assert template.find_resources("AWS::CloudFront::RealtimeLogConfig") == {}
        origin = cdn["Origins"][0]
        assert "OriginShield" not in origin
        assert cdn["PriceClass"] == "PriceClass_100", "cheapest edge footprint"

    def test_the_judge_facing_url_is_the_reachable_one(self, template: Template):
        """`DemoUrl` is what `make demo-url` prints and what gets handed out, so it has
        to be the CDN's name — the Function URL is published separately as the origin
        and the fallback, not as the address to share."""
        outputs = template.to_json()["Outputs"]
        demo_url = json.dumps(outputs["DemoUrl"]["Value"])
        assert "DemoCdn" in demo_url, f"DemoUrl does not point at the distribution: {demo_url}"
        assert "FunctionUrl" in outputs, "the origin should still be published, separately"

    def test_the_default_deployment_needs_no_domain_and_no_certificate(self, cdn):
        """What is actually deployed: the `*.cloudfront.net` name.

        A custom domain is supported and unset. Requesting an ACM certificate from CDK
        would need DNS validation, which would need a Route 53 hosted zone, which is
        $0.50 a month whether or not anyone visits (AGENTS.md §3.5).
        """
        assert "Aliases" not in cdn
        assert "ViewerCertificate" not in cdn or not cdn.get("ViewerCertificate")

    def test_a_custom_domain_is_wired_when_both_halves_are_given(self, bundle):
        """The optional path is real, not aspirational."""
        app = cdk.App(outdir="cdk.out.demotest")
        stack = PoolDemoStack(
            app,
            "DomainStack",
            bundle_path=bundle,
            agentcore_runtime_arn=ARN,
            domain_name="pool.example.com",
            certificate_arn="arn:aws:acm:us-east-1:111111111111:certificate/abc-123",
            env=cdk.Environment(account="111111111111", region="us-east-1"),
        )
        rendered = Template.from_stack(stack).to_json()
        config = [
            r["Properties"]["DistributionConfig"]
            for r in rendered["Resources"].values()
            if r["Type"] == "AWS::CloudFront::Distribution"
        ][0]
        assert config["Aliases"] == ["pool.example.com"]
        assert config["ViewerCertificate"]["MinimumProtocolVersion"] == "TLSv1.2_2021"
        assert rendered["Outputs"]["DemoUrl"]["Value"] == "https://pool.example.com"
        # An imported certificate is a reference, not a resource: the stack stays nine.
        assert len(rendered["Resources"]) == 9, sorted(rendered["Resources"])

    @pytest.mark.parametrize(
        "domain,cert",
        [
            ("pool.example.com", ""),
            ("", "arn:aws:acm:us-east-1:111111111111:certificate/abc-123"),
        ],
    )
    def test_half_a_custom_domain_fails_at_synthesis_not_at_deploy(self, bundle, domain, cert):
        """A domain with no certificate is a distribution CloudFront refuses to create.
        Failing here costs a second; failing in CloudFormation costs a rollback."""
        app = cdk.App(outdir="cdk.out.demotest")
        with pytest.raises(ValueError, match="must be set together"):
            PoolDemoStack(
                app,
                "HalfDomainStack",
                bundle_path=bundle,
                agentcore_runtime_arn=ARN,
                domain_name=domain,
                certificate_arn=cert,
                env=cdk.Environment(account="111111111111", region="us-east-1"),
            )
