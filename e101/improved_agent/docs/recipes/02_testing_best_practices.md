# Recipe 02: Testing Agents via ADK CLI

This recipe details the best practices for using the `adk run` command to test your Google ADK agents interactively from the terminal, avoiding the need to spin up the full web dashboard for rapid execution testing.

## Why It Matters
When developing agents and fine-tuning prompts (especially when generating complex Pydantic schemas), you need a tight feedback loop. The ADK CLI allows you to execute an agent in isolation and inspect the raw output.

## Execution Syntax

The baseline command to execute an agent from the root of an ADK application is:

```bash
uv run adk run <path/to/agent_directory>
```

For example, to run our `titanium_adk` adaptation:

```bash
uv run adk run agents/my_agent
```

This commands loads the `Agent` defined in `agents/my_agent/agent.py` or `__init__.py` and drops you into an interactive chat prompt.

## Supplying a Default Prompt (Bypassing Interactive Mode)

If your agent is designed to execute a monolithic pipeline based on an initial prompt or trigger (e.g., `"Begin"` or `"Run the workflow for XYZ"`) without requiring conversational back-and-forth, you can pass the prompt directly as arguments to the `adk run` command. 

This is incredibly useful for writing automated test scripts:

```bash
uv run adk run agents/my_agent "Run the workflow for XYZ"
```

## Reviewing Pydantic / JSON Schema Validation Errors

When an agent fails to output data matching the assigned `output_schema` precisely, the ADK standard runner will crash and dump the `ValidationError`.  Running via CLI is the fastest way to debug these tracebacks.

**Example Traceback (from missing dictionary keys due to LLM hallucination):**

```
Field required [type=missing, input_value={'security': {'hook': 'Se...rsona': 'Head of Data'}}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.12/v/missing
accounts.1.outreach.hack.Security
```

**Testing Tip**: When testing schema rigidity, always use the CLI. The Web UI (`uv run adk web`) often swallows strict parser tracebacks during streaming.

## Adding CLI Entrypoints Locally (Advanced)

If you are building complex logic that isn't cleanly handled by `adk run`, you can always add an `if __name__ == "__main__":` block to your `agent.py` file to test internal components (like the `Runner` programmatically). Just remember to execute it with the `-m` flag so relative imports resolve correctly:

```bash
uv run python -m agents/my_agent "Run the workflow for XYZ"
```
