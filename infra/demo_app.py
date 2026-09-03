#!/usr/bin/env python3
"""Pool public judge demo — a deliberately tiny AWS CDK app.

This is **not** ``PoolStack``. That stack is the shape a pilot would want: API Gateway,
CloudFront, S3, an EventBridge scan. A public hackathon demo needs none of it, and
AGENTS.md §3.7 says to build the smallest architecture the current milestone needs —
so this is a separate stack, deployed and destroyed on its own.

It synthesizes to **nine CloudFormation resources**: a DynamoDB table, a log group, an
execution role and its policy, the function, its URL, the two Lambda permissions a public
Function URL requires, and a CloudFront distribution. Four of those are things CDK adds
for the others.

What a judge gets: a URL. No AWS account, no CLI, no credentials, no configuration.

    browser ──HTTPS──▶ CloudFront ──▶ Lambda Function URL ──▶ one Lambda
                        │                                      ├─ serves the built SPA
                        │                                      │  (same origin)
                        │                                      ├─ serves the 24
                        │                                      │  allowlisted API paths
                        │                                      ├─ DynamoDB: this session's
                        │                                      │  demo state
                        │                                      └─ InvokeAgentRuntime,
                        │                                         bound to this session's
                        │                                         workspace
                        │                                              │
                        └─ caches /assets/* only    AgentCore Runtime ◀─┘
                           (content-hashed names)     └─ the same DynamoDB table,
                                                         the same partition

**Why a Function URL and not API Gateway.** The gateway would add a resource, a stage,
and a second place for CORS to be wrong, and buys nothing here: there is one function,
one route, no authorizer, no usage plan we would use. A Function URL is HTTPS, is free,
and is deleted with the function.

**Why one Lambda serves the web app too.** S3 + CloudFront would add a bucket, an
origin access control, a bucket policy, a distribution, and a cache invalidation step
on every deploy. The built app is 196 KB. Serving it from the function means one
deployable unit, one origin, and therefore no cross-origin request to secure at all.

**Why there is a CloudFront distribution anyway, and why that is not the same decision.**
The paragraph above rejected S3 as an *origin*. This adds a CDN in *front* of the origin
the function already is, and buys one thing: a hostname filtered networks will resolve.
`*.lambda-url.*.on.aws` is a blocked category on Cisco Umbrella and its peers — this
university's own resolvers answer the demo's hostname with a block-page address and a
certificate no browser trusts, which reaches a visitor as `ERR_CERT_AUTHORITY_INVALID`
and reads as "their demo is broken" (#0065). Everything the S3 paragraph was protecting
survives: no bucket, no invalidation step, one origin, one browser origin. Only
`/assets/*` is cached, and Vite content-hashes those filenames, so a rebuilt asset is a
new URL rather than a purge someone has to remember.

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

**A distribution does not change that shape.** CloudFront has no hourly charge — an idle
distribution bills nothing, unlike every resource in `test_demo_stack.py`'s `ALWAYS_ON`
list, which is why it was removed from it rather than left there and worked around. It
bills per request and per GB egressed, both inside a perpetual free tier (1 TB out and
10 M HTTPS requests per month) that a hackathon demo cannot plausibly exhaust; the
`/assets/*` cache makes it *cheaper* than before by not waking the function for static
bytes. Access logging is off, so it creates no bucket and no log ingestion. It is
deleted by `cdk destroy` along with everything else — slowly, because CloudFront
disables a distribution before removing it, but with no charge while that happens.
"""

from __future__ import annotations

import os

import aws_cdk as cdk
from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_certificatemanager as acm,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
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

#: Optional vanity hostname for the CDN, and the ACM certificate that proves it.
#:
#: Both or neither. A domain without a certificate is a distribution CloudFront will
#: refuse to create, and a certificate without a domain is a no-op — so a half-configured
#: deploy is a synthesis-time error here rather than a rollback ten minutes in.
#:
#: The certificate must already exist **in us-east-1**, which is the only region
#: CloudFront reads viewer certificates from. It is deliberately referenced by ARN rather
#: than requested here: an ACM certificate issued by CDK needs DNS validation, DNS
#: validation from CDK needs a Route 53 hosted zone, and a hosted zone is $0.50 a month
#: whether or not anyone visits (AGENTS.md §3.5 — "explicitly call out anything that can
#: keep accruing cost while nobody is developing"). Pointing an existing name at the
#: distribution with one CNAME at whatever registrar already holds it costs nothing.
#:
#: Unset — the default, and what is deployed — the distribution answers on its own
#: ``*.cloudfront.net`` name, which needs no domain, no certificate and no DNS record.
DEMO_DOMAIN = os.environ.get("POOL_DEMO_DOMAIN", "")
DEMO_CERT_ARN = os.environ.get("POOL_DEMO_CERT_ARN", "")

#: How long CloudFront waits for this function to answer.
#:
#: This number has to be read together with the three deadlines on the function below,
#: because the CDN is now the *outermost* layer and its default would have been the
#: shortest: 30 s, against a live agent action whose own wall-clock bound is 45 s. A
#: judge pressing the live button would have been shown a CloudFront 504 while the
#: function was still working and the runtime was still writing — the same inverted
#: nesting as #0030, one layer further out.
#:
#: 60 s is the ceiling CloudFront allows without a service-quota increase, so it is what
#: is set, and it is honestly not enough to cover the *worst* case: if the AgentCore
#: runtime wedges, the function's own bridge read timeout also fires at 60 s, and which
#: of the two lands first is a race. That path surfaces as a 504 from the CDN instead of
#: the structured loop-fault the function would have returned. The ordinary path — the
#: agent finishing, or hitting its own 45 s bound — is comfortably inside this and comes
#: back through the CDN unchanged. The raw Function URL stays public, so a judge who hits
#: the race has a route that does not involve CloudFront at all.
CDN_ORIGIN_TIMEOUT = Duration.seconds(int(os.environ.get("POOL_DEMO_CDN_TIMEOUT", "60")))

#: Error status codes CloudFront will cache on its own initiative, pinned to zero.
#:
#: CloudFront applies a 10 s "error caching minimum TTL" to these regardless of the cache
#: policy, so ``CACHING_DISABLED`` alone does not stop it. For a stateful demo that is a
#: real trap: a judge who trips a validation error or a quota refusal would keep being
#: served that refusal for ten seconds after the condition cleared, and the retry that
#: should have worked would look like a broken app. Naming each code with a zero TTL
#: leaves the origin's own body and status untouched and only removes the caching.
#:
#: 429 is deliberately absent because CloudFront never caches it, and asserting a policy
#: over a code that has none would be a claim the template cannot keep.
CDN_UNCACHED_ERRORS = (400, 403, 404, 405, 500, 502, 503, 504)


class PoolDemoStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        bundle_path: str | None = None,
        agentcore_runtime_arn: str | None = None,
        domain_name: str | None = None,
        certificate_arn: str | None = None,
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
        domain = DEMO_DOMAIN if domain_name is None else domain_name
        cert_arn = DEMO_CERT_ARN if certificate_arn is None else certificate_arn
        if bool(domain) != bool(cert_arn):
            raise ValueError(
                "POOL_DEMO_DOMAIN and POOL_DEMO_CERT_ARN must be set together: a custom "
                "domain needs a us-east-1 ACM certificate that covers it, and a "
                "certificate with no domain changes nothing. Set both, or neither and "
                "take the *.cloudfront.net name."
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
            # every action a visitor can reach — discovery, advancing a pool, the scripted
            # showcase — so all of them are repeatable and unaffected by model variance.
            # With the kill switch below off, this is the only planner the public demo
            # runs, which is what makes the judge path a zero-token path.
            "MODEL_PROVIDER": "offline",
            "ROUTING_PROVIDER": "deterministic",
            "PAYMENT_PROVIDER": "simulated",
            "PURCHASE_EXECUTOR": "simulated",
            "SCHEDULES_ENABLED": "false",
            # Kill switch for the only paid path, independent of the demo itself.
            #
            # Off for the public judge demo, deliberately. With it on, the product's own
            # "Ask Pool to check now" routes to AgentCore/Nova before any local fallback,
            # so a judge pressing the primary button spends model tokens — and, if that
            # invocation fails, gets an error, no pool, and a lease-length lockout rather
            # than a result. Off, the same button runs the same bounded Strands loop with
            # the deterministic planner, and the API refuses the paid route before taking
            # a lease, spending a quota unit, or reaching AWS. The runtime stays deployed;
            # set this back to "true" to re-arm it on a deployment of your own.
            "PUBLIC_DEMO_AGENTCORE_ENABLED": "false",
            "AGENTCORE_RUNTIME_ARN": runtime_arn,
            "AGENTCORE_QUALIFIER": "DEFAULT",
            # Abuse and cost bounds. Environment variables so they can be tightened on
            # the deployed function in seconds, without a rebuild (AGENTS.md §3.1).
            # 40 was a cap a genuine visitor could hit halfway through: one hands-on run
            # — scan, advance, answer two decisions, accept the host job, open pickup,
            # then issue and redeem ten credentials — is around thirty actions. These are
            # free, deterministic, server-side operations; the cap exists to stop a
            # script, not a judge. Matches the dataclass default in `public_demo.py`.
            "PUBLIC_DEMO_MAX_ACTIONS_PER_SESSION": "100",
            "PUBLIC_DEMO_MAX_ACTIONS_PER_DAY": "1200",
            "PUBLIC_DEMO_MAX_LIVE_PER_SESSION": "3",
            "PUBLIC_DEMO_MAX_LIVE_PER_DAY": "40",
            "PUBLIC_DEMO_MAX_NEW_SESSIONS_PER_DAY": "300",
            # Agent bounds, same defaults as everywhere else.
            "MAX_AGENT_ITERATIONS": "8",
            "MAX_TOOL_CALLS_PER_RUN": "25",
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
        fn.add_to_role_policy(
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

        # ------------------------------------------------------------- cdn
        # **Why a CDN was added to a stack whose whole point is being small.**
        #
        # Not for latency, and not for cost. For *reachability*. `*.lambda-url.*.on.aws`
        # is a category block on filtered networks — Cisco Umbrella on this university's
        # own resolvers returns its block-page address for the demo's hostname and serves
        # a certificate signed by a CA no browser trusts, so the demo presents as
        # `NET::ERR_CERT_AUTHORITY_INVALID`. Not a Pool bug and not an AWS outage: the
        # name never resolved to AWS. Attacker use of Function URLs for phishing and C2
        # is why the category exists, and no amount of correctness on our side removes a
        # demo URL from it.
        #
        # `*.cloudfront.net` is not in that category. The distribution is bought for the
        # hostname; the caching below is a side benefit.
        #
        # This does not walk back the "one Lambda serves the web app too" decision above.
        # That decision was about not *replacing* the function's static serving with S3 —
        # a bucket, an origin access control, a bucket policy and an invalidation step on
        # every deploy. None of that is here. There is still one origin, one deployable
        # unit, and one browser origin, so there is still no cross-origin request to
        # secure; the app and the API arrive from the same CloudFront hostname exactly as
        # they arrived from the same Function URL hostname.
        origin = origins.FunctionUrlOrigin(url, read_timeout=CDN_ORIGIN_TIMEOUT)

        # The Host header must **not** reach the origin. A Function URL authorises against
        # its own hostname, so forwarding the viewer's `Host` (the CloudFront name) gets
        # the request rejected at the origin — `ALL_VIEWER` is the wrong policy here and
        # `ALL_VIEWER_EXCEPT_HOST_HEADER` is the whole reason it exists. Everything else a
        # request carries does travel, which matters because the demo identifies a visitor's
        # workspace with a **query parameter**, not a cookie.
        dynamic = cloudfront.BehaviorOptions(
            origin=origin,
            viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            # The default is GET/HEAD, which would turn every mutation in the demo into a
            # 403 from the CDN. Every lifecycle action in this product is a POST.
            allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
            # Nothing dynamic is cached, at all. The alternative is worse than slow: two
            # workspaces share a path and differ only in a query parameter, so any cache
            # policy that dropped the query string from the key would serve one visitor's
            # pool to another. `CACHING_DISABLED` cannot make that mistake.
            cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
            origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
            compress=True,
        )

        distribution = cloudfront.Distribution(
            self,
            "DemoCdn",
            comment="Pool public demo — reachable hostname in front of the Function URL",
            default_behavior=dynamic,
            additional_behaviors={
                # The only cacheable surface. Vite content-hashes every filename under
                # `/assets/`, so a cached object can never be stale — a rebuilt asset is a
                # different URL — and `index.html`, which is what names those URLs, is
                # served by the uncached default behaviour above. That is what keeps the
                # "no invalidation step on every deploy" property true with a CDN in
                # front: correctness here comes from the filenames, not from remembering
                # to purge. It is also most of the bytes (a ~200 KB bundle plus the
                # product imagery), which now leave the edge instead of waking the
                # function.
                "/assets/*": cloudfront.BehaviorOptions(
                    origin=origin,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD,
                    cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                    compress=True,
                ),
            },
            # Cheapest edge footprint, same choice as `PoolStack` makes.
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
            # No access logs. They would need an S3 bucket this stack does not have, and
            # a bucket that survives `cdk destroy` is exactly the orphan shape of #0023.
            # CloudWatch on the function already records every request that reaches it.
            enable_logging=False,
            error_responses=[
                cloudfront.ErrorResponse(http_status=code, ttl=Duration.seconds(0))
                for code in CDN_UNCACHED_ERRORS
            ],
            # Absent unless both are configured — see the constants. With neither, this is
            # the `*.cloudfront.net` name and the default CloudFront certificate.
            domain_names=[domain] if domain else None,
            certificate=(
                acm.Certificate.from_certificate_arn(self, "DemoCert", cert_arn)
                if cert_arn
                else None
            ),
            # Only meaningful alongside a custom certificate; CloudFront's own shared
            # certificate does not take a floor.
            minimum_protocol_version=(
                cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021 if cert_arn else None
            ),
        )

        # ------------------------------------------------------------- outputs
        # `DemoUrl` is the URL a judge is given, and it is now the CDN's — that is the
        # point of the change, and `make demo-url` reads this key. The Function URL is
        # still public and still works; it is published separately, below, because it is
        # the fallback and the thing to curl when the question is "is the CDN the
        # problem?", not the address to hand out.
        CfnOutput(
            self,
            "DemoUrl",
            value=f"https://{domain}" if domain else f"https://{distribution.domain_name}",
        )
        CfnOutput(self, "FunctionUrl", value=url.url)
        CfnOutput(self, "CdnDistributionId", value=distribution.distribution_id)
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
