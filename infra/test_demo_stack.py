"""Public judge demo — infrastructure tests.

The demo stack is small enough to read, which is exactly why it is worth pinning: the
risk is not complexity, it is that something quietly grows. These assert the four
claims the stack is deployed on.

1. **Nothing always-on, nothing unbounded.** Per-request billing, capped retention,
   TTL'd data, and a hard concurrency ceiling.
2. **The browser gets no credential and no privilege.** The function's only privileged
   action is invoking one named AgentCore runtime.
3. **Payments and purchasing stay simulated,** pinned in the deployed environment
   rather than trusted to a default.
4. **The whole thing tears down** — every resource is DESTROY, and the log group is in
   the stack rather than created implicitly by Lambda and left behind (#0023).

Runs offline: synthesis needs no AWS credentials.
"""

from __future__ import annotations

import json

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template

from demo_app import PoolDemoStack

ARN = "arn:aws:bedrock-agentcore:us-east-1:111111111111:runtime/Pool_PoolCoordinator-Abc123"

ALWAYS_ON = [
    "AWS::EC2::Instance",
    "AWS::RDS::DBInstance",
    "AWS::EC2::NatGateway",
    "AWS::ElasticLoadBalancingV2::LoadBalancer",
    "AWS::OpenSearchService::Domain",
    "AWS::ECS::Service",
    "AWS::ElastiCache::CacheCluster",
    "AWS::Redshift::Cluster",
    "AWS::CloudFront::Distribution",
    "AWS::ApiGatewayV2::Api",
    "AWS::Events::Rule",
]


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

    def test_concurrency_is_capped_so_an_anonymous_url_cannot_run_away(
        self, template: Template
    ):
        """The one cost control that does not depend on application code being right."""
        fns = template.find_resources("AWS::Lambda::Function")
        reserved = next(iter(fns.values()))["Properties"]["ReservedConcurrentExecutions"]
        assert 0 < reserved <= 10, reserved

    def test_a_wedged_request_cannot_run_for_minutes(self, template: Template):
        fns = template.find_resources("AWS::Lambda::Function")
        assert next(iter(fns.values()))["Properties"]["Timeout"] <= 60

    def test_everything_is_destroyable(self, template: Template):
        for logical_id, resource in template.to_json()["Resources"].items():
            policy = resource.get("DeletionPolicy", "Delete")
            assert policy == "Delete", f"{logical_id} would survive teardown ({policy})"

    def test_the_stack_creates_nothing_recurring(self, template: Template):
        for kind in ("AWS::Events::Rule", "AWS::Scheduler::Schedule", "AWS::Lambda::EventSourceMapping"):
            assert template.find_resources(kind) == {}, kind


class TestPublicSafety:
    def test_the_demo_runs_in_judge_mode(self, function_env):
        """Without this the deployed function would expose all 45 endpoints and an
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
        assert int(function_env["WORKFLOW_TIMEOUT_SECONDS"]) == 120

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


class TestShape:
    def test_the_public_entry_point_is_a_function_url(self, template: Template):
        """API Gateway would be a second resource, a second stage, and a second place
        for CORS to be wrong."""
        template.has_resource_properties("AWS::Lambda::Url", {"AuthType": "NONE"})
        assert template.find_resources("AWS::ApiGateway::RestApi") == {}
        assert template.find_resources("AWS::ApiGatewayV2::Api") == {}

    def test_the_web_app_ships_inside_the_function(self, function_env, template: Template):
        """No bucket, no distribution, no invalidation step — and no cross-origin
        request to secure, because the app and the API share an origin."""
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
        """A guard against drift, not a rule about the number eight. If this stack
        grows, that should be a decision someone made, not a diff nobody read."""
        resources = template.to_json()["Resources"]
        assert len(resources) <= 10, sorted(resources)

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
