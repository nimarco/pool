#!/usr/bin/env python3
"""Pool public judge demo — a deliberately tiny AWS CDK app.

This is **not** ``PoolStack``. That stack is the shape a pilot would want: API Gateway,
CloudFront, S3, an EventBridge scan. A public hackathon demo needs none of it, and
AGENTS.md §3.7 says to build the smallest architecture the current milestone needs —
so this is a separate stack, deployed and destroyed on its own.

It synthesizes to **eight CloudFormation resources**: a DynamoDB table, a log group, an
execution role and its policy, the function, its URL, and the two Lambda permissions a
public Function URL requires. Four of those are things CDK adds for the other four.

What a judge gets: a URL. No AWS account, no CLI, no credentials, no configuration.

    browser ──HTTPS──▶ Lambda Function URL ──▶ one Lambda
                                                 ├─ serves the built SPA (same origin)
                                                 ├─ serves the 23 allowlisted API paths
                                                 ├─ DynamoDB: this session's demo state
                                                 └─ InvokeAgentRuntime, bound to this
                                                    session's workspace
                                                          │
                                    AgentCore Runtime ◀───┘
                                      └─ the same DynamoDB table, the same partition

**Why a Function URL and not API Gateway.** The gateway would add a resource, a stage,
and a second place for CORS to be wrong, and buys nothing here: there is one function,
one route, no authorizer, no usage plan we would use. A Function URL is HTTPS, is free,
and is deleted with the function.

**Why one Lambda serves the web app too.** S3 + CloudFront would add a bucket, an
origin access control, a bucket policy, a distribution, and a cache invalidation step
on every deploy. The built app is 196 KB. Serving it from the function means one
deployable unit, one origin, and therefore no cross-origin request to secure at all.

**Why DynamoDB is here and the AgentCore runtime's in-memory store is not enough.**
The runtime holds state in the microVM, which is right for a one-shot agent invocation
and wrong for a judge who clicks through a lifecycle: a cold Lambda would lose their
pool mid-demo, and two judges on two containers would see different worlds. One
on-demand table with a 24 h TTL per session costs approximately nothing idle and makes
the demo deterministic across containers.

**Why the runtime shares that table rather than keeping its own copy.** It used to keep
its own: the live action ran the deployed agent against a throwaway workspace inside the
runtime, which proved the agent was real and could not be the product, because the pool
it formed was invisible to the person who pressed the button. Pointing it at this table
makes the deployed agent the thing that actually forms the visitor's pool. The sharing
is one-directional in authority — the API owns workspaces (it seeds them, resets them,
and rations how many exist), and the runtime is only ever a participant inside one that
already exists. That asymmetry is what the runtime's IAM grant encodes: read and write,
no delete (`services/agent/iam/agentcore-dynamodb.json`).

Cost shape, in full: **no always-on compute, no idle charge.** Lambda and DynamoDB are
per-request; the table is PAY_PER_REQUEST; the log group is capped at 14 days. Reserved
concurrency caps how much of any of it can happen at once. The only path that spends
model tokens is the live action, which is capped per session and per day in application
code and can be switched off with one environment variable.
"""

from __future__ import annotations

import os

import aws_cdk as cdk
from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_logs as logs,
)
from constructs import Construct

PROJECT_TAGS = {
    "Project": "Pool",
    "Hackathon": "AgentsForHumans",
    "Environment": os.environ.get("POOL_ENV", "dev"),
    "Component": "PublicDemo",
}

#: Built by scripts/build_demo_bundle.sh. Deploying without it is a hard error rather
#: than a function that fails at cold start with an ImportError nobody sees.
BUNDLE = os.environ.get("POOL_DEMO_BUNDLE", "../build/demo-lambda")

#: The deployed AgentCore runtime this demo is allowed to invoke — and only this one.
#: Empty means the live action ships switched off, which is a valid deployment.
AGENTCORE_RUNTIME_ARN = os.environ.get("AGENTCORE_RUNTIME_ARN", "")

#: Explicit physical table name, not CDK's generated one.
#:
#: The AgentCore runtime is deployed by a *different* stack (the AgentCore CLI's
#: `AgentCore-Pool-default`) and now reads and writes this same table, so it needs both
#: the name (`DYNAMODB_TABLE` in `agentcore/agentcore.json`) and an IAM statement naming
#: the ARN (`services/agent/iam/agentcore-dynamodb.json`). Neither of those is a
#: CloudFormation reference that could resolve a generated name, and wiring an export
#: between two stacks that are deployed by two different tools — in either order — is a
#: dependency neither tool can express. A fixed name makes the contract a constant that
#: both halves can state and a test can compare.
TABLE_NAME = os.environ.get("POOL_DEMO_TABLE", "pool-demo-state")

#: Hard ceiling on parallel executions — the cost control that does not depend on any
#: application code being correct.
#:
#: **Zero means "do not set the property", and zero is the default.** AWS enforces
#: `account_concurrency_limit - sum(reserved) >= 10`, and this account's limit *is* 10
#: (the default for a new account, raised by AWS after sustained usage). So any nonzero
#: reservation is rejected outright — the first deploy failed on exactly this and rolled
#: back. The ceiling still exists, it is just enforced one level up: with no other
#: function in the account, the account's own limit of 10 caps this function at 10
#: concurrent executions. Set POOL_DEMO_CONCURRENCY on an account whose limit has been
#: raised.
#:
#: The kill switch is unaffected: reserving *0* subtracts nothing from the unreserved
#: pool, so `put-function-concurrency --reserved-concurrent-executions 0` is permitted
#: and throttles the function to nothing.
RESERVED_CONCURRENCY = int(os.environ.get("POOL_DEMO_CONCURRENCY", "0"))


class PoolDemoStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        bundle_path: str | None = None,
        agentcore_runtime_arn: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Constructor arguments rather than module globals so the infrastructure tests
        # can synthesize against a fixture bundle. Defaults come from the environment,
        # which is how the CDK CLI invokes this.
        bundle_path = BUNDLE if bundle_path is None else bundle_path
        runtime_arn = (
            AGENTCORE_RUNTIME_ARN if agentcore_runtime_arn is None else agentcore_runtime_arn
        )

        for key, value in PROJECT_TAGS.items():
            cdk.Tags.of(self).add(key, value)

        # ------------------------------------------------------------- state
        # One item per entity, partitioned by demo session. Anonymous isolation is a
        # partition-key property, not a filter someone has to remember to apply.
        table = dynamodb.Table(
            self,
            "DemoState",
            table_name=TABLE_NAME,
            partition_key=dynamodb.Attribute(name="pk", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="sk", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            # Every session's data — and every quota counter — carries a TTL, so the
            # table empties itself and an abandoned demo costs nothing next week.
            time_to_live_attribute="ttl",
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=False
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Explicit, so retention is capped and the group dies with the stack. Left
        # implicit, Lambda creates a log group that retains forever and survives
        # `cdk destroy` — which is how orphaned log groups happen (#0023).
        log_group = logs.LogGroup(
            self,
            "DemoLogs",
            retention=logs.RetentionDays.TWO_WEEKS,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ------------------------------------------------------------- function
        env = {
            "POOL_PUBLIC_DEMO": "true",
            "PUBLIC_DEMO_WEB_ROOT": "/var/task/web",
            "POOL_REPOSITORY": "dynamodb",
            "DYNAMODB_TABLE": table.table_name,
            # The AgentCore runtime writes this same partition inside a single user
            # action, so the refresh that follows one has to be a read-your-writes read
            # or the browser can be shown the world as it was before the agent ran.
            "DYNAMODB_CONSISTENT_READS": "true",
            # The API Lambda never calls Bedrock. The deterministic offline planner backs
            # the free lifecycle actions — advancing a pool, the scripted showcase — so
            # those are repeatable and unaffected by model variance. The product's
            # discovery action goes to AgentCore, which has its own model configuration.
            "MODEL_PROVIDER": "offline",
            "ROUTING_PROVIDER": "deterministic",
            "PAYMENT_PROVIDER": "simulated",
            "PURCHASE_EXECUTOR": "simulated",
            "SCHEDULES_ENABLED": "false",
            # Kill switch for the only paid path, independent of the demo itself.
            "PUBLIC_DEMO_AGENTCORE_ENABLED": "true",
            "AGENTCORE_RUNTIME_ARN": runtime_arn,
            "AGENTCORE_QUALIFIER": "DEFAULT",
            # Abuse and cost bounds. Environment variables so they can be tightened on
            # the deployed function in seconds, without a rebuild (AGENTS.md §3.1).
            "PUBLIC_DEMO_MAX_ACTIONS_PER_SESSION": "40",
            "PUBLIC_DEMO_MAX_ACTIONS_PER_DAY": "600",
            "PUBLIC_DEMO_MAX_LIVE_PER_SESSION": "3",
            "PUBLIC_DEMO_MAX_LIVE_PER_DAY": "40",
            "PUBLIC_DEMO_MAX_NEW_SESSIONS_PER_DAY": "300",
            # Agent bounds, same defaults as everywhere else.
            "MAX_AGENT_ITERATIONS": "8",
            "MAX_TOOL_CALLS_PER_RUN": "25",
            "MAX_TOOL_RETRIES": "3",
            "MAX_DUPLICATE_TOOL_CALLS": "2",
            # 45, matching `agentcore/agentcore.json`, and it has to be *below* this
            # function's own timeout to mean anything. It was 120 — larger than the 90 s
            # timeout below — so a wedged run here would have been killed by Lambda at 90 s
            # and this bound could never have fired. A limit that cannot be reached is not
            # a limit, and worse, it is the number `/api/health` publishes and the
            # Live-on-AWS view prints as the wall clock every run is held to. A judge read
            # "120s" beside a run whose real bound was 45 (#0030).
            #
            # Both environments now state the same figure, so the one number that page
            # shows is true of every run it lists, wherever that run executed.
            # `infra/test_demo_stack.py` pins it to the runtime's value and to the
            # ordering below.
            "WORKFLOW_TIMEOUT_SECONDS": "45",
            "MAX_ROUTE_MATRIX_CELLS": "100",
            #
            # No STRIPE_API_KEY, no STRIPE_WEBHOOK_SECRET, and no credential of any
            # kind. A secret set here is a secret in the synthesized template, in
            # cdk.out, and possibly in git (AGENTS.md §4). An infra test asserts this.
        }

        fn = lambda_.Function(
            self,
            "DemoApi",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="pool.api.app.lambda_handler",
            code=lambda_.Code.from_asset(bundle_path),
            # Three nested deadlines, innermost first, so whichever one fires produces a
            # structured answer rather than a dropped connection:
            #
            #   45 s  the agent's own wall-clock bound — WORKFLOW_TIMEOUT_SECONDS, and the
            #         same 45 in both places it can run: inside the AgentCore runtime
            #         (agentcore/agentcore.json) and inside this function (the env above).
            #         Hitting it ends the run loudly as a recorded loop fault, and that
            #         record is still returned;
            #   60 s  this function's read timeout on invoke_agent_runtime, so a runtime
            #         that never answers becomes a reported failure here;
            #   90 s  this timeout, the outermost net.
            #
            # The innermost rung has to be genuinely innermost in *both* directions. It
            # was 45 remotely and 120 locally, and 120 sits outside this 90 — so on the
            # local path the nesting was inverted and the agent's own bound was dead
            # config (#0030).
            #
            # It was 30 s, which was ample for the showcase (~800 DynamoDB round trips)
            # and is not for a live agent invocation: the Lambda would have been killed
            # mid-flight while the runtime carried on writing, which is the one failure
            # mode where the browser is told nothing happened and something did. The
            # worst case a wedged request can now bill is 90 s of one 1 GB execution,
            # about a tenth of a cent.
            timeout=Duration.seconds(90),
            memory_size=1024,
            environment=env,
            log_group=log_group,
        )
        table.grant_read_write_data(fn)

        # The single privileged thing this function can do, scoped to one runtime ARN.
        # This is why the browser needs no AWS credential and the runtime can keep
        # AWS_IAM inbound auth: the signing happens here.
        if runtime_arn:
            fn.add_to_role_policy(
                iam.PolicyStatement(
                    actions=["bedrock-agentcore:InvokeAgentRuntime"],
                    resources=[
                        runtime_arn,
                        # The endpoint is a child resource of the runtime and is the
                        # ARN the data plane authorises against for a qualifier.
                        f"{runtime_arn}/runtime-endpoint/*",
                    ],
                )
            )

        # Only when the account can actually accept a reservation — see the constant.
        # Omitted, the account's own concurrency limit is the ceiling instead.
        if RESERVED_CONCURRENCY > 0:
            fn.node.default_child.add_property_override(
                "ReservedConcurrentExecutions", RESERVED_CONCURRENCY
            )

        url = fn.add_function_url(
            auth_type=lambda_.FunctionUrlAuthType.NONE,
            # No CORS block: the app is served from this same origin, so there is no
            # cross-origin request to allow. Anything that needs one is not this demo.
        )

        # ------------------------------------------------------------- outputs
        CfnOutput(self, "DemoUrl", value=url.url)
        CfnOutput(self, "FunctionName", value=fn.function_name)
        CfnOutput(self, "TableName", value=table.table_name)
        CfnOutput(
            self,
            "LiveAgentAction",
            value=runtime_arn or "disabled — no AGENTCORE_RUNTIME_ARN set",
        )
        CfnOutput(
            self,
            "KillSwitch",
            value=(
                f"aws lambda put-function-concurrency --function-name {fn.function_name} "
                "--reserved-concurrent-executions 0"
            ),
        )


def build() -> cdk.App:
    app = cdk.App(outdir=os.environ.get("CDK_OUTDIR", "cdk.out.demo"))
    PoolDemoStack(
        app,
        os.environ.get("POOL_DEMO_STACK_NAME", "PoolDemoStack"),
        env=cdk.Environment(
            account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
            region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1"),
        ),
        description="Pool — public judge demo (hackathon). One Lambda, one table, one URL.",
    )
    return app


# Guarded so the test module can import the stack class without synthesizing — and,
# more usefully, without needing the Lambda bundle to exist on disk.
if __name__ == "__main__":
    build().synth()
