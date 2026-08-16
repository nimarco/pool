"""Central configuration for Pool.

Every cost-relevant bound lives here with a safe default (AGENTS.md §3.1, §3.2).
Nothing in this module reads AWS or performs I/O — importing it is free.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# The Bedrock model id is deliberately NOT hardcoded into agent code.
#
# Strands talks to Bedrock through the boto3 `bedrock-runtime` Converse API, whose
# model identifiers are inference-profile-scoped and vary by account and region.
# This default has NOT been verified against a live account (no AWS credentials were
# available when it was written). Before any real invocation, list what the account
# actually has and set BEDROCK_MODEL_ID accordingly:
#
#     aws bedrock list-inference-profiles --region "$AWS_REGION" \
#       --query 'inferenceProfileSummaries[?contains(inferenceProfileId, `anthropic`)].inferenceProfileId'
#
# A cost-efficient model with solid tool-use behaviour is the right default for this
# project (AGENTS.md §3.3): the coordinator's job is tool selection and escalation
# judgement, not deep reasoning.
DEFAULT_BEDROCK_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"


@dataclass(frozen=True)
class AgentBounds:
    """Hard limits on a single agent run. See AGENTS.md §3.1.

    A run that hits any of these terminates loudly with a recorded loop-fault
    outcome — never a silent truncation that looks like a normal result.
    """

    max_iterations: int = 8
    max_tool_calls: int = 25
    max_tool_retries: int = 3
    max_duplicate_tool_calls: int = 2
    workflow_timeout_seconds: int = 120

    @classmethod
    def from_env(cls) -> AgentBounds:
        return cls(
            max_iterations=_int_env("MAX_AGENT_ITERATIONS", 8),
            max_tool_calls=_int_env("MAX_TOOL_CALLS_PER_RUN", 25),
            max_tool_retries=_int_env("MAX_TOOL_RETRIES", 3),
            max_duplicate_tool_calls=_int_env("MAX_DUPLICATE_TOOL_CALLS", 2),
            workflow_timeout_seconds=_int_env("WORKFLOW_TIMEOUT_SECONDS", 120),
        )


@dataclass(frozen=True)
class Settings:
    aws_region: str = "us-east-1"
    bedrock_model_id: str = DEFAULT_BEDROCK_MODEL_ID
    model_max_tokens: int = 2048

    # Cost safety
    schedules_enabled: bool = False
    bounds: AgentBounds = field(default_factory=AgentBounds)

    # Adapters. "deterministic" keeps every test and local run free of paid calls.
    routing_provider: str = "deterministic"  # deterministic | aws_location
    repository: str = "memory"  # memory | dynamodb
    # "offline" runs the real agent loop with a deterministic planner in place of the
    # LLM — zero token cost. "bedrock" is the real model. See pool/agent/offline_model.py.
    model_provider: str = "offline"  # offline | bedrock

    # Payments. "simulated" is free, offline, and deterministic; "stripe" is TEST mode
    # only and refuses to construct with a non-test key (brief §12, §54).
    payment_provider: str = "simulated"  # simulated | stripe
    stripe_api_key: str = ""
    stripe_webhook_secret: str = ""
    # Purchase execution. Only the clearly-labelled simulated executor exists (§63).
    purchase_executor: str = "simulated"

    # AWS resource names (only read when the corresponding adapter is active)
    dynamodb_table: str = "pool-state"
    location_route_calculator: str = ""

    # Routing bound: a route matrix is origins x destinations, so cap it (AGENTS.md §3.4).
    max_route_matrix_cells: int = 100

    @property
    def stripe_configured(self) -> bool:
        """True only for a usable TEST-mode key. A live key is never usable here."""
        return self.stripe_api_key.startswith("sk_test_")

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            aws_region=os.environ.get("AWS_REGION", "us-east-1"),
            bedrock_model_id=os.environ.get("BEDROCK_MODEL_ID", DEFAULT_BEDROCK_MODEL_ID),
            model_max_tokens=_int_env("MODEL_MAX_TOKENS", 2048),
            schedules_enabled=_bool_env("SCHEDULES_ENABLED", False),
            bounds=AgentBounds.from_env(),
            routing_provider=os.environ.get("ROUTING_PROVIDER", "deterministic"),
            repository=os.environ.get("POOL_REPOSITORY", "memory"),
            model_provider=os.environ.get("MODEL_PROVIDER", "offline"),
            payment_provider=os.environ.get("PAYMENT_PROVIDER", "simulated"),
            stripe_api_key=os.environ.get("STRIPE_API_KEY", ""),
            stripe_webhook_secret=os.environ.get("STRIPE_WEBHOOK_SECRET", ""),
            purchase_executor=os.environ.get("PURCHASE_EXECUTOR", "simulated"),
            dynamodb_table=os.environ.get("DYNAMODB_TABLE", "pool-state"),
            location_route_calculator=os.environ.get("LOCATION_ROUTE_CALCULATOR", ""),
            max_route_matrix_cells=_int_env("MAX_ROUTE_MATRIX_CELLS", 100),
        )


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings


def reset_settings() -> None:
    """Test hook — forces the next get_settings() to re-read the environment."""
    global _settings
    _settings = None
