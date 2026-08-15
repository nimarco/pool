#!/usr/bin/env bash
# List this project's resources and flag anything that bills while nobody is working.
# Read-only: it never deletes and never touches a resource outside the Pool stack.
set -uo pipefail
STACK="${POOL_STACK_NAME:-PoolStack}"

echo "→ Resources in stack '$STACK'"
aws cloudformation list-stack-resources --stack-name "$STACK" \
  --query 'StackResourceSummaries[].{Type:ResourceType,Id:PhysicalResourceId}' \
  --output table 2>/dev/null || echo "  (stack not deployed)"

echo
echo "→ Scheduled rules (anything ENABLED here costs money unattended)"
aws events list-rules --query 'Rules[?contains(Name, `Pool`) || contains(Name, `BackgroundScan`)].{Name:Name,State:State,Schedule:ScheduleExpression}' \
  --output table 2>/dev/null || true

echo
echo "→ Bedrock AgentCore runtimes (these are the easiest thing to forget)"
aws bedrock-agentcore-control list-agent-runtimes \
  --query 'agentRuntimes[].{Name:agentRuntimeName,Status:status}' --output table 2>/dev/null \
  || echo "  (none, or the control API is unavailable in this region)"

echo
echo "→ Resources tagged Project=Pool"
aws resourcegroupstaggingapi get-resources --tag-filters Key=Project,Values=Pool \
  --query 'ResourceTagMappingList[].ResourceARN' --output table 2>/dev/null || true

echo
echo "Reminder: 'make schedule-off' stops recurring runs; 'make destroy' removes the stack."
