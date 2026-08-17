SHELL := /bin/bash
.DEFAULT_GOAL := help

AGENT   := services/agent
WEB     := apps/web
INFRA   := infra
PY      := $(AGENT)/.venv/bin/python
CDK_PY  := $(INFRA)/.venv/bin/python
export JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION := 1

# Everything below runs offline and free by default. Targets that can spend money are
# grouped under "cloud" and each says so.

.PHONY: help
help: ## Show this help
	@echo "Pool — autonomous collective-purchasing coordinator"
	@echo
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo
	@echo "Everything is free and offline unless the target says (COSTS MONEY)."

# ----------------------------------------------------------------- setup

.PHONY: install
install: ## Install all dependencies (Python agent, web, infra)
	cd $(AGENT) && uv venv --python 3.13 && uv pip install -e ".[dev]"
	cd $(WEB) && npm install
	cd $(INFRA) && uv venv --python 3.13 && uv pip install --python .venv/bin/python -r requirements.txt pytest

.PHONY: install-agentcore
install-agentcore: ## Install the AgentCore CLI, then build its generated CDK project
	npm install -g @aws/agentcore
	@$(MAKE) agentcore-cdk

.PHONY: agentcore-cdk
agentcore-cdk: ## Rebuild agentcore/cdk/ from the installed AgentCore CLI (generated, not committed)
	@bash scripts/agentcore_cdk_init.sh

# ----------------------------------------------------------------- run

.PHONY: api
api: ## Run the API locally on :8000
	cd $(AGENT) && .venv/bin/python -m uvicorn pool.api.app:app --reload --port 8000

.PHONY: web
web: ## Run the web app locally on :5173 (proxies /api to :8000)
	cd $(WEB) && npm run dev

.PHONY: dev
dev: ## Run API and web together
	@$(MAKE) -j2 api web

# ----------------------------------------------------------------- test

.PHONY: test
test: ## Run the full test suite (offline, no AWS, no model tokens)
	cd $(AGENT) && .venv/bin/python -m pytest tests/ -q
	cd $(INFRA) && .venv/bin/python -m pytest test_stack.py test_demo_stack.py -q

.PHONY: test-demo
test-demo: ## Prove the showcase scenario end to end
	cd $(AGENT) && .venv/bin/python -m pytest tests/test_demo_scenario.py -v

.PHONY: test-safety
test-safety: ## Run only the safety-critical suites (bounds, payments, policy, viability)
	cd $(AGENT) && .venv/bin/python -m pytest \
	  tests/test_agent_bounds.py tests/test_payments.py \
	  tests/test_policy.py tests/test_viability.py -q
	cd $(INFRA) && .venv/bin/python -m pytest test_stack.py test_demo_stack.py -q

.PHONY: demo
demo: ## Run the showcase scenario and print the transcript
	cd $(AGENT) && .venv/bin/python -m pool.scripts.demo

.PHONY: typecheck
typecheck: ## Typecheck the web app
	cd $(WEB) && npx tsc -b --noEmit

.PHONY: lint
lint: ## Lint Python
	cd $(AGENT) && .venv/bin/python -m ruff check pool tests agentcore_app.py

.PHONY: build
build: ## Build the web app for production
	cd $(WEB) && npm run build

.PHONY: secret-scan
secret-scan: ## Scan the repo for anything that looks like a credential
	@bash scripts/secret_scan.sh

.PHONY: secret-scan-selftest
secret-scan-selftest: ## Prove the secret scanner still detects planted secrets
	@bash scripts/secret_scan_selftest.sh

.PHONY: diagram
diagram: ## Re-render the architecture diagram from its Mermaid source
	npx -y @mermaid-js/mermaid-cli@11 -i docs/architecture.mmd -o docs/architecture.svg -b transparent
	@echo "→ docs/architecture.svg"

.PHONY: qa
qa: lint typecheck test build secret-scan ## Everything CI would run
	@echo "✅ all checks passed"

# ----------------------------------------------------------------- cloud

.PHONY: whoami
whoami: ## (cloud) Show which AWS principal is configured — run before anything else
	@bash scripts/aws_preflight.sh

.PHONY: verify-bedrock
verify-bedrock: ## (COSTS MONEY, a little) Prove Bedrock -> Strands -> Pool tools for real
	@bash scripts/aws_preflight.sh
	cd $(AGENT) && .venv/bin/python -m pool.scripts.verify_bedrock

.PHONY: verify-recovery
verify-recovery: ## (COSTS MONEY, a little) Prove the recovery branch against a real model
	@bash scripts/aws_preflight.sh
	cd $(AGENT) && .venv/bin/python -m pool.scripts.verify_recovery_bedrock

.PHONY: synth
synth: ## Synthesize the CloudFormation template (offline, no credentials needed)
	cd $(INFRA) && .venv/bin/python app.py && echo "→ infra/cdk.out/PoolStack.template.json"

.PHONY: deploy
deploy: ## (COSTS MONEY) Deploy the serverless stack
	@bash scripts/aws_preflight.sh
	cd $(INFRA) && npx aws-cdk@2 deploy --require-approval broadening

.PHONY: deploy-web
deploy-web: build ## (COSTS MONEY) Upload the built web app to S3 and invalidate CloudFront
	@bash scripts/deploy_web.sh

# ----------------------------------------------------------------- public demo
# The judge experience: one URL, no AWS account, no setup. A separate, tiny stack —
# NOT PoolStack. See infra/demo_app.py for why.

DEMO_STACK  := PoolDemoStack
DEMO_APP    := npx aws-cdk@2 --app "$(abspath $(INFRA)/.venv/bin/python) demo_app.py" \
               --output cdk.out.demo

.PHONY: demo-bundle
demo-bundle: build ## Build the public-demo Lambda bundle (web app + linux deps + pool)
	@bash scripts/build_demo_bundle.sh

.PHONY: demo-synth
demo-synth: ## Synthesize the public-demo stack (offline, no credentials, creates nothing)
	cd $(INFRA) && CDK_OUTDIR=cdk.out.demo .venv/bin/python demo_app.py \
	  && echo "→ infra/cdk.out.demo/$(DEMO_STACK).template.json"

.PHONY: demo-local
demo-local: demo-bundle ## Run the public demo exactly as deployed, on :8000 (free, offline)
	@echo "→ http://127.0.0.1:8000  (judge mode, in-memory store, live agent off)"
	cd $(AGENT) && POOL_PUBLIC_DEMO=true \
	  PUBLIC_DEMO_WEB_ROOT=$(abspath apps/web/dist) \
	  .venv/bin/python -m uvicorn pool.api.app:app --port 8000

.PHONY: deploy-demo
deploy-demo: demo-bundle ## (COSTS MONEY) Deploy the public judge demo
	@bash scripts/aws_preflight.sh
	cd $(INFRA) && $(DEMO_APP) deploy --require-approval broadening

.PHONY: demo-url
demo-url: ## (cloud) Print the deployed demo URL
	@aws cloudformation describe-stacks --stack-name $(DEMO_STACK) \
	  --query "Stacks[0].Outputs[?OutputKey=='DemoUrl'].OutputValue" --output text

.PHONY: demo-kill
demo-kill: ## (cloud) Stop the public demo answering, without deleting anything
	@FN=$$(aws cloudformation describe-stacks --stack-name $(DEMO_STACK) \
	  --query "Stacks[0].Outputs[?OutputKey=='FunctionName'].OutputValue" --output text) && \
	  aws lambda put-function-concurrency --function-name "$$FN" \
	    --reserved-concurrent-executions 0 >/dev/null && \
	  echo "✓ $$FN throttled to zero. Restore with: make demo-restore"

.PHONY: demo-restore
demo-restore: ## (cloud) Let the public demo answer again
	@FN=$$(aws cloudformation describe-stacks --stack-name $(DEMO_STACK) \
	  --query "Stacks[0].Outputs[?OutputKey=='FunctionName'].OutputValue" --output text) && \
	  aws lambda put-function-concurrency --function-name "$$FN" \
	    --reserved-concurrent-executions 5 >/dev/null && echo "✓ $$FN restored to 5"

.PHONY: destroy-demo
destroy-demo: ## (cloud) Destroy the public demo stack. Scoped to this stack only.
	@bash scripts/aws_preflight.sh
	cd $(INFRA) && $(DEMO_APP) destroy --force
	@echo "✓ $(DEMO_STACK) destroyed — function, URL, table, role and log group all go with it."

.PHONY: agent-validate
agent-validate: ## Validate the AgentCore project config (offline, free)
	agentcore validate

.PHONY: agent-dry-run
agent-dry-run: ## (cloud, read-only) Synthesize the AgentCore deployment without creating anything
	@bash scripts/aws_preflight.sh
	agentcore deploy --dry-run

.PHONY: deploy-agent
deploy-agent: ## (COSTS MONEY) Deploy the coordinator to Bedrock AgentCore Runtime
	@bash scripts/aws_preflight.sh
	agentcore deploy

.PHONY: smoke
smoke: ## (cloud) Smoke-test a deployed API — pass API_URL=https://…
	@bash scripts/smoke_test.sh

.PHONY: destroy
destroy: ## (cloud) Destroy the Pool stack. Scoped to this stack only.
	@bash scripts/aws_preflight.sh
	cd $(INFRA) && npx aws-cdk@2 destroy --force

.PHONY: destroy-agent
destroy-agent: ## (cloud) Delete the AgentCore stack. CLI 0.27.0 has no destroy command.
	@bash scripts/aws_preflight.sh
	aws cloudformation delete-stack --stack-name AgentCore-Pool-default
	aws cloudformation wait stack-delete-complete --stack-name AgentCore-Pool-default
	@echo "✓ AgentCore-Pool-default deleted."
	@echo "  NOT removed by this: the runtime log group, /aws/application-signals/data,"
	@echo "  aws/spans, the workload identity, or X-Ray Transaction Search."
	@echo "  See the resource ledger in BUILD_HISTORY.md for each one's own command."

.PHONY: schedule-off
schedule-off: ## (cloud) Disable the background scan schedule
	@bash scripts/schedule.sh disable

.PHONY: schedule-on
schedule-on: ## (COSTS MONEY) Enable the background scan schedule
	@bash scripts/schedule.sh enable

.PHONY: cost-check
cost-check: ## (cloud) List this project's AWS resources and flag anything recurring
	@bash scripts/cost_check.sh

.PHONY: clean
clean: ## Remove local build artifacts
	rm -rf $(WEB)/dist $(WEB)/node_modules/.vite $(INFRA)/cdk.out $(INFRA)/cdk.out.test
	rm -rf $(INFRA)/cdk.out.demo $(INFRA)/cdk.out.demotest build/
	rm -rf agentcore/.cache agentcore/cdk/cdk.out agentcore/cdk/dist
	find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
	find . -name .pytest_cache -type d -prune -exec rm -rf {} + 2>/dev/null || true
