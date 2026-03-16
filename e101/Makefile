.PHONY: help run-original

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

run-original: ## Run the app using functions-framework locally
	uv run functions-framework --source original_agent/main.py --target run_agent_logic --debug

eval: ## Run the evaluation for the improved case study researcher
	uv run adk eval --config_file_path improved_agent/evalsets/eval_config.json improved_agent/agents/case_study_researcher improved_agent/evalsets/research_evals.json

run: ## Run the case study researcher interactively or with a query (e.g. make run query="Find retail case studies")
	@if [ "$(query)" = "" ]; then \
		uv run python -m improved_agent.agents.case_study_researcher.agent; \
	else \
		uv run python -m improved_agent.agents.case_study_researcher.agent "$(query)"; \
	fi
