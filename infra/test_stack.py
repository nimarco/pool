"""Infrastructure tests.

These assert the *cost-safety* properties of the stack, not its shape. Every claim
AGENTS.md §3 makes about the deployed system is checked here so it cannot quietly stop
being true — a schedule flipped to enabled or a log group left unbounded would fail the
build rather than surface on a bill.

Runs offline: ``cdk synth`` needs no AWS credentials.
"""

from __future__ import annotations

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template

from app import PoolStack

ALWAYS_ON = [
    "AWS::EC2::Instance",
    "AWS::RDS::DBInstance",
    "AWS::EC2::NatGateway",
    "AWS::ElasticLoadBalancingV2::LoadBalancer",
    "AWS::OpenSearchService::Domain",
    "AWS::ECS::Service",
    "AWS::ElastiCache::CacheCluster",
    "AWS::Redshift::Cluster",
]


@pytest.fixture(scope="module")
def template() -> Template:
    app = cdk.App(outdir="cdk.out.test")
    stack = PoolStack(app, "TestStack", env=cdk.Environment(account="111111111111", region="us-east-1"))
    return Template.from_stack(stack)


class TestCostSafety:
    def test_the_background_schedule_ships_disabled(self, template: Template):
        """Enabling recurring model invocations must be a deliberate act."""
        template.has_resource_properties("AWS::Events::Rule", {"State": "DISABLED"})

    def test_the_schedule_is_not_high_frequency(self, template: Template):
        rules = template.find_resources("AWS::Events::Rule")
        for rule in rules.values():
            expr = rule["Properties"].get("ScheduleExpression", "")
            assert "minute" not in expr, f"minute-level polling is not permitted: {expr}"

    def test_dynamodb_is_on_demand(self, template: Template):
        """Provisioned capacity bills whether or not anyone is using the demo."""
        template.has_resource_properties(
            "AWS::DynamoDB::Table", {"BillingMode": "PAY_PER_REQUEST"}
        )

    def test_dynamodb_has_ttl_so_demo_data_expires(self, template: Template):
        template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {"TimeToLiveSpecification": {"AttributeName": "ttl", "Enabled": True}},
        )

    def test_log_retention_is_bounded(self, template: Template):
        groups = template.find_resources("AWS::Logs::LogGroup")
        assert groups, "an explicit log group is required; the implicit one never expires"
        for group in groups.values():
            days = group["Properties"].get("RetentionInDays")
            assert days is not None and days <= 30, f"log retention unbounded or too long: {days}"

    @pytest.mark.parametrize("resource_type", ALWAYS_ON)
    def test_no_always_on_infrastructure(self, template: Template, resource_type: str):
        assert template.find_resources(resource_type) == {}, (
            f"{resource_type} bills continuously and must not appear in this stack"
        )

    def test_everything_is_destroyable(self, template: Template):
        """`cdk destroy` must genuinely remove everything — no orphaned billable leftovers."""
        for logical_id, resource in template.to_json()["Resources"].items():
            policy = resource.get("DeletionPolicy")
            if policy is None:
                continue
            assert policy == "Delete", f"{logical_id} would survive cdk destroy ({policy})"


class TestSecurity:
    def test_the_web_bucket_blocks_public_access(self, template: Template):
        template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "PublicAccessBlockConfiguration": {
                    "BlockPublicAcls": True,
                    "BlockPublicPolicy": True,
                    "IgnorePublicAcls": True,
                    "RestrictPublicBuckets": True,
                }
            },
        )

    def test_cloudfront_forces_https(self, template: Template):
        template.has_resource_properties(
            "AWS::CloudFront::Distribution",
            {
                "DistributionConfig": Match.object_like(
                    {"DefaultCacheBehavior": Match.object_like(
                        {"ViewerProtocolPolicy": "redirect-to-https"}
                    )}
                )
            },
        )

    def test_no_hardcoded_secrets_in_lambda_environment(self, template: Template):
        """Configuration travels as environment variables; credentials never do."""
        banned = ("SECRET", "PASSWORD", "TOKEN", "ACCESS_KEY", "PRIVATE_KEY")
        for fn in template.find_resources("AWS::Lambda::Function").values():
            env = fn["Properties"].get("Environment", {}).get("Variables", {})
            for key, value in env.items():
                assert not any(b in key.upper() for b in banned), f"suspicious env var {key}"
                if isinstance(value, str):
                    assert not value.startswith("AKIA"), "an AWS access key id is present"

    def test_iam_grants_are_scoped_not_wildcard_admin(self, template: Template):
        for policy in template.find_resources("AWS::IAM::Policy").values():
            for statement in policy["Properties"]["PolicyDocument"]["Statement"]:
                actions = statement.get("Action", [])
                actions = [actions] if isinstance(actions, str) else actions
                assert "*" not in actions, "a wildcard-action policy grants far too much"


class TestShape:
    def test_the_expected_services_are_present(self, template: Template):
        template.resource_count_is("AWS::DynamoDB::Table", 1)
        template.resource_count_is("AWS::ApiGatewayV2::Api", 1)
        template.resource_count_is("AWS::CloudFront::Distribution", 1)
        template.resource_count_is("AWS::Events::Rule", 1)

    def test_no_route_calculator_resource_is_provisioned(self, template: Template):
        """geo-routes needs none — one less billable thing to create and forget."""
        assert template.find_resources("AWS::Location::RouteCalculator") == {}

    def test_stack_is_tagged_for_cleanup(self, template: Template):
        """Consistent tags are what make an accidental leftover findable later."""
        tables = template.find_resources("AWS::DynamoDB::Table")
        tags = list(tables.values())[0]["Properties"].get("Tags", [])
        keys = {t["Key"] for t in tags}
        assert {"Project", "Hackathon"} <= keys, f"missing project tags, got {keys}"
