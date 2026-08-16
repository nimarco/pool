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
	cd $(AGENT) && uv venv --python 3.13 && uv pip install -e ".[dev]" bedrock-agentcore
	cd $(WEB) && npm install
	cd $(INFRA) && uv venv --python 3.13 && uv pip install --python .venv/bin/python -r requirements.txt pytest

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
	cd $(INFRA) && .venv/bin/python -m pytest test_stack.py -q

.PHONY: test-demo
test-demo: ## Prove the showcase scenario end to end
	cd $(AGENT) && .venv/bin/python -m pytest tests/test_demo_scenario.py -v

.PHONY: test-safety
test-safety: ## Run only the safety-critical suites (bounds, payments, policy, viability)
	cd $(AGENT) && .venv/bin/python -m pytest \
	  tests/test_agent_bounds.py tests/test_payments.py \
	  tests/test_policy.py tests/test_viability.py -q
	cd $(INFRA) && .venv/bin/python -m pytest test_stack.py -q

.PHONY: demo
demo: ## Run the showcase scenario and print the transcript
	cd $(AGENT) && .venv/bin/python -m pool.scripts.demo

.PHONY: typecheck
typecheck: ## Typecheck the web app
	cd $(WEB) && npx tsc -b --noEmit

.PHONY: lint
lint: ## Lint Python
	cd $(AGENT) && .venv/bin/python -m ruff check pool tests

.PHONY: build
build: ## Build the web app for production
	cd $(WEB) && npm run build

.PHONY: secret-scan
secret-scan: ## Scan the repo for anything that looks like a credential
	@bash scripts/secret_scan.sh

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

.PHONY: deploy-agent
deploy-agent: ## (COSTS MONEY) Deploy the coordinator to Bedrock AgentCore Runtime
	@bash scripts/aws_preflight.sh
	cd $(AGENT) && agentcore configure --entrypoint agentcore_app.py && agentcore launch

.PHONY: smoke
smoke: ## (cloud) Smoke-test a deployed API — pass API_URL=https://…
	@bash scripts/smoke_test.sh

.PHONY: destroy
destroy: ## (cloud) Destroy the Pool stack. Scoped to this stack only.
	@bash scripts/aws_preflight.sh
	cd $(INFRA) && npx aws-cdk@2 destroy --force

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
	find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
	find . -name .pytest_cache -type d -prune -exec rm -rf {} + 2>/dev/null || true
