.PHONY: help run-original

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

run-original: ## Run the app using functions-framework locally
	uv run functions-framework --source original_agent/main.py --target run_agent_logic --debug
