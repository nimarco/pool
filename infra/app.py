#!/usr/bin/env python3
"""Pool infrastructure — AWS CDK.

Everything here is serverless and pay-per-use. Nothing is always-on: no EC2, no RDS,
no NAT gateway, no load balancer, no provisioned capacity (AGENTS.md §3.5, §3.7).

Deliberately *not* in this stack:

* **AgentCore Runtime** — deployed with its own official tooling
  (``agentcore configure`` / ``agentcore launch``), which owns its container build and
  IAM. Duplicating that in CDK would be the fragile custom path the brief warns against.
* **A route calculator resource** — the Amazon Location ``geo-routes`` API is called
  directly and needs no provisioned calculator, so there is nothing to create or forget.

Cost-relevant choices, all deliberate:

* DynamoDB on-demand billing with a TTL attribute, so idle demo workspaces cost nothing
  and clean themselves up.
* CloudWatch log retention capped at two weeks everywhere.
* The EventBridge schedule is created **disabled** and at a slow cadence. Enabling it is
  an explicit, reversible act.
* ``RemovalPolicy.DESTROY`` throughout so ``cdk destroy`` genuinely removes everything.
"""

from __future__ import annotations

import os

import aws_cdk as cdk
from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
    aws_apigatewayv2 as apigw,
    aws_apigatewayv2_integrations as integrations,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_dynamodb as dynamodb,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_s3 as s3,
)
from constructs import Construct

PROJECT_TAGS = {
    "Project": "Pool",
    "Hackathon": "AgentsForHumans",
    "Environment": os.environ.get("POOL_ENV", "dev"),
}

# Slow on purpose. Recurring demand changes on the scale of days and a Community's
# Pool Day comes round once a week, so scanning more often would buy nothing and cost
# model invocations (AGENTS.md §3.2).
SCAN_SCHEDULE = events.Schedule.rate(Duration.hours(6))


class PoolStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Tag inside the stack, not at the app level: a leftover resource is only
        # findable later if the tags applied no matter how the stack was constructed
        # (AGENTS.md §3.8).
        for key, value in PROJECT_TAGS.items():
            cdk.Tags.of(self).add(key, value)

        # ------------------------------------------------------------- state
        table = dynamodb.Table(
            self,
            "PoolState",
            partition_key=dynamodb.Attribute(name="pk", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="sk", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="ttl",
            # Synthetic demo data — point-in-time recovery would add storage cost for
            # nothing worth recovering.
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=False
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Explicit log group so retention is capped and the group is destroyed with the
        # stack. Left implicit, Lambda creates a log group that survives `cdk destroy`
        # and quietly retains logs forever.
        api_log_group = logs.LogGroup(
            self,
            "PoolApiLogs",
            retention=logs.RetentionDays.TWO_WEEKS,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ------------------------------------------------------------- api
        api_env = {
            "DYNAMODB_TABLE": table.table_name,
            "POOL_REPOSITORY": "dynamodb",
            "ROUTING_PROVIDER": os.environ.get("ROUTING_PROVIDER", "deterministic"),
            "MODEL_PROVIDER": os.environ.get("MODEL_PROVIDER", "offline"),
            "BEDROCK_MODEL_ID": os.environ.get("BEDROCK_MODEL_ID", ""),
            # Payments default to the free simulated provider. Switching to Stripe is a
            # deliberate act, and the application refuses to construct the Stripe
            # provider with anything but a `sk_test_` key regardless of what is set here.
            "PAYMENT_PROVIDER": os.environ.get("PAYMENT_PROVIDER", "simulated"),
            # Only the clearly-labelled simulated executor exists in this build: no
            # supplier is contacted and no money moves.
            "PURCHASE_EXECUTOR": "simulated",
            #
            # STRIPE_API_KEY and STRIPE_WEBHOOK_SECRET are deliberately NOT set here.
            # A secret placed in a CDK stack ends up in the synthesized template, in
            # cdk.out, and potentially in version control (AGENTS.md §4). Set them on the
            # deployed function out of band instead:
            #
            #   aws lambda update-function-configuration --function-name <name> \
            #     --environment "Variables={...,STRIPE_API_KEY=sk_test_...}"
            #
            # A pilot should move them to Secrets Manager and read them at cold start.
            "SCHEDULES_ENABLED": "false",
            # Bounds travel as configuration so they can be tightened without a deploy.
            "MAX_AGENT_ITERATIONS": "8",
            "MAX_TOOL_CALLS_PER_RUN": "25",
            "MAX_DUPLICATE_TOOL_CALLS": "2",
            "WORKFLOW_TIMEOUT_SECONDS": "120",
            "MAX_ROUTE_MATRIX_CELLS": "100",
        }

        api_fn = lambda_.Function(
            self,
            "PoolApi",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="pool.api.app.lambda_handler",
            code=lambda_.Code.from_asset("../services/agent"),
            timeout=Duration.seconds(60),
            memory_size=1024,
            environment=api_env,
            log_group=api_log_group,
        )
        # Exactly the five DynamoDB actions this function issues, rather than
        # `grant_read_write_data`, which also hands it Scan, DescribeTable, BatchGetItem,
        # ConditionCheckItem, DeleteItem and the stream read actions. None of those
        # appear anywhere in `pool/`:
        #
        #   GetItem / PutItem / Query   the repository's three primitives
        #   UpdateItem                  the quota counters and the workspace lease, both
        #                               of which are conditional writes
        #   BatchWriteItem              `reset()` deletes a workspace through a batch
        #                               writer, so the delete travels as a batch
        #
        # Scan is the one worth naming: it is the action that turns a per-workspace grant
        # into a whole-table read, and the single-table design has no reason to issue one.
        api_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:Query",
                    "dynamodb:UpdateItem",
                    "dynamodb:BatchWriteItem",
                ],
                resources=[table.table_arn],
            )
        )

        # Least privilege: only the two Location Routes actions Pool actually calls, and
        # only the specific Bedrock model it is configured to use.
        api_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["geo-routes:CalculateRouteMatrix", "geo-routes:CalculateRoutes"],
                resources=["*"],  # geo-routes has no resource-level ARNs
            )
        )
        model_id = os.environ.get("BEDROCK_MODEL_ID", "")
        if model_id:
            api_fn.add_to_role_policy(
                iam.PolicyStatement(
                    actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                    resources=[
                        f"arn:aws:bedrock:{self.region}::foundation-model/*",
                        f"arn:aws:bedrock:{self.region}:{self.account}:inference-profile/{model_id}",
                    ],
                )
            )

        http_api = apigw.HttpApi(
            self,
            "PoolHttpApi",
            default_integration=integrations.HttpLambdaIntegration("ApiIntegration", api_fn),
            cors_preflight=apigw.CorsPreflightOptions(
                allow_origins=["*"],
                allow_methods=[apigw.CorsHttpMethod.GET, apigw.CorsHttpMethod.POST,
                               apigw.CorsHttpMethod.OPTIONS],
                allow_headers=["content-type"],
            ),
        )

        # ------------------------------------------------------------- background
        # Created DISABLED. Enabling a recurring model-invoking job must be a conscious
        # act, not something a deploy switches on (AGENTS.md §3.2).
        scan_rule = events.Rule(
            self,
            "BackgroundScan",
            schedule=SCAN_SCHEDULE,
            enabled=False,
            description=(
                "Pool background coordination scan. DISABLED BY DEFAULT — enabling this "
                "starts recurring model invocations. Disable again with: "
                "aws events disable-rule --name <name>"
            ),
        )
        scan_rule.add_target(
            targets.LambdaFunction(
                api_fn,
                event=events.RuleTargetInput.from_object(
                    {
                        "rawPath": "/api/agent/run",
                        "requestContext": {"http": {"method": "POST", "path": "/api/agent/run"}},
                        "queryStringParameters": {"workspace": "primary"},
                        "body": '{"trigger": "scheduled_scan"}',
                        "isBase64Encoded": False,
                    }
                ),
            )
        )

        # ------------------------------------------------------------- web
        site_bucket = s3.Bucket(
            self,
            "PoolWeb",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
        )

        distribution = cloudfront.Distribution(
            self,
            "PoolCdn",
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(site_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
            ),
            error_responses=[
                # Single-page app: unknown paths resolve to the shell.
                cloudfront.ErrorResponse(
                    http_status=403, response_http_status=200, response_page_path="/index.html"
                ),
                cloudfront.ErrorResponse(
                    http_status=404, response_http_status=200, response_page_path="/index.html"
                ),
            ],
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,  # cheapest edge footprint
            comment="Pool demo web app",
        )

        # ------------------------------------------------------------- outputs
        cdk.CfnOutput(self, "ApiUrl", value=http_api.url or "")
        cdk.CfnOutput(self, "WebBucket", value=site_bucket.bucket_name)
        cdk.CfnOutput(self, "WebUrl", value=f"https://{distribution.distribution_domain_name}")
        cdk.CfnOutput(self, "TableName", value=table.table_name)
        cdk.CfnOutput(self, "ScanRuleName", value=scan_rule.rule_name)
        cdk.CfnOutput(
            self,
            "ScanRuleState",
            value="DISABLED — enable deliberately, and disable again when done",
        )


# The CDK CLI sets CDK_OUTDIR; defaulting it lets `python app.py` be run directly to
# check that the stack synthesizes without needing the CLI or AWS credentials.
app = cdk.App(outdir=os.environ.get("CDK_OUTDIR", "cdk.out"))
stack = PoolStack(
    app,
    os.environ.get("POOL_STACK_NAME", "PoolStack"),
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1"),
    ),
    description="Pool — autonomous collective-purchasing coordinator (hackathon demo)",
)

app.synth()
