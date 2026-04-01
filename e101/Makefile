.PHONY: help run-original

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

run-original: ## Run the app using functions-framework locally
	uv run --env-file .env functions-framework --source original_agent/main.py --target run_agent_logic --debug

run-improved: ## Run the improved app using functions-framework locally
	PYTHONPATH=. uv run --env-file .env functions-framework --source improved_agent/main.py --target run_agent_logic --debug --port 8081

eval: ## Run the evaluation for the improved case study researcher
	uv run --env-file .env adk eval --config_file_path improved_agent/evalsets/eval_config.json improved_agent/agents/case_study_researcher improved_agent/evalsets/research_evals.json

run-web: ## Run the ADK web interface for the improved case study researcher
	uv run --env-file .env adk web improved_agent/agents/case_study_researcher


run: ## Run the case study researcher interactively or with a query (e.g. make run query="Find retail case studies")
	@if [ "$(query)" = "" ]; then \
		uv run --env-file .env python -m improved_agent.agents.case_study_researcher.agent; \
	else \
		uv run --env-file .env python -m improved_agent.agents.case_study_researcher.agent "$(query)"; \
	fi

run-titanium-cli: ## Run the Titanium Pro pipeline via CLI (e.g. make run-titanium-cli target="Home Depot")
	@if [ "$(target)" = "" ]; then \
		echo "Please provide a target company (e.g., make run-titanium-cli target=\"Home Depot\")"; \
	else \
		uv run --env-file .env python -m improved_agent.agents.titanium_pro.agent "$(target)"; \
	fi

run-titanium-dashboard: ## Run the interactive Quart Web Dashboard for Titanium Pro on port 8080
	PYTHONPATH=. uv run --env-file .env hypercorn improved_agent.app:app --bind 0.0.0.0:8080

run-titanium-headless: ## Run the Titanium Pro headless cloud function on port 8081
	PYTHONPATH=. uv run --env-file .env functions-framework --source improved_agent/agents/titanium_pro/agent.py --target run_agent_logic --debug --port 8081

run-crawler-phase-1: ## Run the bulk crawler phase 1 to extract case study URLs
	uv run --env-file .env python -m improved_agent.scripts.bulk_case_study_crawler --phase 1

run-crawler-phase-2: ## Run the bulk crawler phase 2 to fetch contents and insert into Vector Search
	uv run --env-file .env python -m improved_agent.scripts.bulk_case_study_crawler --phase 2

run-crawler-all: ## Run both phases of the bulk crawler
	uv run --env-file .env python -m improved_agent.scripts.bulk_case_study_crawler --phase all
