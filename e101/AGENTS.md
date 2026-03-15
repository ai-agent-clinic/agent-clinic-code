# Agent Work Instructions

This project uses Google Agent Development Kit (ADK) v1.23.0 to manage our agents.

## Core Tooling & Management
*   **Package Management**: `uv`
*   **ADK CLI Operations**: Always prefix commands with `uv run` to execute in the correct environment.
*   **Workspace Constraints**: Code logic lives in the `improved_agent/agents/` folder. The `original_agent` folder is read-only. Avoid modifying files outside `e101`.

## Essential Commands

### Booting the Web Interface
You can load an agent in a local test UI using the web server command:
```bash
# Start a specific agent by folder path
uv run adk web improved_agent/agents/<agent_name>

# Alternatively, pass the root agents folder
uv run adk web improved_agent/agents/
```
The application runs on `http://127.0.0.1:8080` by default.

### Running Headless (CLI mode)
For interactive terminal execution rather than a web UI:
```bash
uv run adk run improved_agent/agents/<agent_name>
```

### Script Execution (Standalone)
Scripts or agents can usually be run natively if they implement `if __name__ == "__main__":`. Use standard Python execution:
```bash
uv run python improved_agent/agents/<agent_name>/agent.py
```

### Useful SDK Flags
When using `adk web` or `adk run`, you might find these flags useful:
- `--reload` (Hot reloads for the server logic)
- `--reload_agents` (Hot reloads specifically for agent `.py` file changes)
- `--port <PORT>` (Override the port if 8080 is busy)
- `--log_level debug` (Enable verbose debug logging)

## Additional AI Directives
- **Checkpointing**: Checkpoint the code regularly (e.g., using git commits), particularly after any meaningful changes or refactors. This ensures we can easily compare with or revert to prior versions if development takes a wrong turn.
- **Model Usage**: Never silently upgrade or tweak the `model` param on agents unless the user asks for it. Defaults to `gemini-2.5-flash` for ADK v1.23.0 if omitted, but `gemini-3.1-flash-preview` and `gemini-3.0-pro-preview` may be present depending on context.
- **Reference Skills**: AI agents working on this should consult `adk-dev-guide` and `adk-cheatsheet` to ensure correct API usage for v1.23.0 code generation, tool usage (`verb_noun`), and evaluation practices. Evaluative loops (`make eval` or `adk eval`) are strongly preferred over simple test execution for agent grading.

## ADK Built-in Skills Catalog
The following skills are available natively to AI coding agents in this environment. When requested to perform a task, agents should consult the appropriate skill first:
- `/adk-expert`: The primary master skill for writing, debugging, and understanding ADK Python v1.23.0.
- `/adk-cheatsheet`: Quick API references. Excellent for fast lookup of agent types, parameter signatures, and component configuration.
- `/adk-dev-guide`: Core mandatory coding guidelines. Read this to understand the proper ADK development lifecycle, including spec-driven development and code preservation rules.
- `/adk-scaffold`: Guide for creating new ADK projects or major enhancements (like adding CI/CD or RAG data ingestion) using the `agent-starter-pack` CLI.
- `/adk-eval-guide`: Vital reference for running and debugging evaluations (`adk eval` / `make eval`), understanding metrics, and tweaking schemas.
- `/adk-deploy-guide`: Guide for deploying agents via Agent Engine, Cloud Run, or CI/CD pipelines.
## Tooling Dependencies

### Playwright CLI
This workspace relies on the `playwright-cli` tool for web scraping and browser automation tasks. 

**Installation Steps:**
Install the Playwright CLI globally on your system using npm. This makes the `playwright-cli` command available everywhere in your terminal.
```bash
npm install -g @playwright/cli@latest
```

*(Optional but Recommended)* Initialize your workspace to set up a configuration directory (`.playwright-cli/`) and potentially install a standalone browser if you don't have Chrome, Firefox, or WebKit installed.
```bash
cd your-project-folder
playwright-cli install
```
