# DESIGN_SPEC.md

## Overview
The `case_study_researcher` agent uses the Playwright CLI to automate searching for and downloading Google Cloud customer case studies from `https://cloud.google.com/customers`. The extracted text will be formatted as markdown and saved locally to the `improved_agent/knowledge_base/` folder. This is a foundational data-ingestion workflow pattern.

## Example Use Cases
- "Find a case study on retail customers using BigQuery."
- "Download a success story about Agentic AI."
- "Get a GCP customer case study involving ML training."

## Tools Required
- `run_browser_command(command: str)`
  - Requires `playwright-cli` to be installed globally on the system (`npm install -g @playwright/cli@latest`).
  - Strict validation ensures the command always starts with `playwright-cli`, preventing arbitrary code execution.
- `save_case_study(topic: str, company: str, markdown_content: str)`
  - A simple file IO tool to dump the ingested content to the local `knowledge_base` without dealing with bash string escaping.

## Constraints & Safety Rules
- The agent must NEVER execute raw bash commands outside of the `playwright-cli` binary.
- All web scraping is done via `playwright-cli` commands.
- The agent must not guess a customer name—it must search using `https://cloud.google.com/customers` and follow real links on the site.

## Success Criteria
- The agent successfully finds a target case study based on the provided topic.
- It clicks through to the full study page and extracts the text.
- The resulting text is saved as a cleanly formatted markdown file in `improved_agent/knowledge_base/<topic>_<company>.md`.

## Edge Cases to Handle
- No search results for the provided topic.
- `playwright-cli` timeouts or element not found errors.
- Unstructured HTML results that need to be parsed into markdown by passing them through the LLM.
