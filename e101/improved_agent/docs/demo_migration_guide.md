# 🚀 Titanium Pro: The 1-Hour ADK Migration Masterclass

**Goal**: Transform a brittle, monolithic Python script into a resilient, multi-agent AI pipeline utilizing Google's Agent Development Kit (ADK) v1.23.0 in under 60 minutes.

**Theme**: From Prompt Engineering to Software Engineering.

**How to Use This Guide**: This is a prescriptive, click-by-click script. Paste the prompts exactly as written into your Gemini/Antigravity console during the live demo to advance through the milestones.

---

## ⏱️ Milestone 0: The Command Code (Minutes 0 - 5)

**The Problem**: AI coding assistants wander off-path when they don't have strict operating parameters for a new workspace.
**The Solution**: We will establish a powerful `AGENTS.md` context file at the root of our workspace to permanently enforce ADK best practices, routing patterns, and tooling rules for the rest of the demo.

### 🗣️ Presenter Script
1. Say: *"Before we write a single line of Python, we have to teach our AI agent how to behave in this specific enterprise sandbox. We do this by feeding it a root-level `AGENTS.md` file that codifies how we use ADK, how we use headless browsers, and how we handle local execution."*

### 🤖 Live Prompt to Copy/Paste
> "Create a file named `AGENTS.md` in the root of the workspace. This file must contain the following strict guidelines to govern all your future code generation in this project:
> 
> # Project Structure & Rules
> 
> ## Core Tooling & Management
> *   **Package Management**: `uv`
> *   **ADK Operations**: Always prefix ADK CLI commands with `uv run`.
> *   **Project Paths**: Code lives in `improved_agent/agents/[agent_name]/`.
> 
> ## Execution Modalities
> 1. **ADK UI**: Test agents visually via `uv run adk web improved_agent/agents/[agent_name]`.
> 2. **Headless Execution**: Use `uv run adk run improved_agent/agents/[agent_name]` for CLI mode.
> 3. **Python Standard**: For scripts running via generic python, execute as a module to handle relative imports: `uv run python -m improved_agent.agents.[agent_name].agent`
> 
> ## ADK Built-in Skills Catalog (v1.23.0)
> You must consult these built-in ADK Skills when uncertain:
> - `/adk-expert`: The primary master skill for writing ADK agents.
> - `/adk-cheatsheet`: Quick API references, parameter signatures, and component setup.
> - `/adk-dev-guide`: Core coding guidelines for the standard ADK lifecycle.
> 
> ## DeepWiki MCP Usage
> - We use the DeepWiki MCP server for fetching documentation on repositories. ALWAYS use `read_wiki_structure` first, followed by `read_wiki_contents`, before asking generic questions.
> 
> ## Playwright & Tooling Rules
> - **Playwright**: We use `playwright-cli` (`npm install -g @playwright/cli@latest`) wrapped in ADK tools for dynamic scraping. 
> - **Cleanup**: Ensure Playwright snapshot `.yml` files are deleted from the workspace immediately after they are read by tools.
> 
> ## Makefile Structure
> - Every major execution workflow must be wrapped in a root `Makefile` target (e.g., `make run-titanium-cli`, `make run-titanium-dashboard`, `make run-titanium-headless`).
> 
> Read and acknowledge this file."

### 🎯 The "Aha!" Demo Moment
1. Show the resulting `AGENTS.md` file in the IDE. Explain that by placing this in the workspace, we have effectively "jailbroken" the AI assistant to act as a senior ADK v1.23.0 architect for the rest of the hour.

---

## ⏱️ Milestone 1: The "Lift & Shift" (Minutes 5 - 20)

**The Problem**: Our legacy script `original_agent/main.py` uses raw genai clients, messy regex to extract JSON from unstructured text (the "Mega-Vault"), and it easily crashes when the LLM disobeys formatting.
**The Solution**: We are going to wrap this exact logic inside a single ADK `Agent` and replace the brittle regex parsing with strict Pydantic schemas. 

### 🗣️ Presenter Script
1. Open `original_agent/main.py` on the projector. Point out the regex block parsing `safe_text`.
2. Say: *"We've all written this ugly regex code. If the LLM misses a curly brace, the whole app crashes. Let's fix that by moving to ADK."*

### 🤖 Live Prompt to Copy/Paste
> "I want to migrate the core logic of `original_agent/main.py` into a single, cohesive ADK v1.23.0 Agent named `titanium_v1`. 
> 
> 1. Create a new folder: `improved_agent/agents/titanium_v1/`.
> 2. Look at the `OUTPUT STRUCTURE` expected in the `generate_intel` prompt inside `main.py`. I want you to create strict Pydantic models for this output in `improved_agent/agents/titanium_v1/tools.py`. Name the final model `OutreachEmail`.
> 3. Inside `improve_agent/agents/titanium_v1/agent.py`, define an `Agent` class named `titanium_v1`. Use the `output_key` parameter to bind your new `OutreachEmail` Pydantic schema to the agent's output.
> 4. Keep the original monolithic system prompt from `main.py` (the one with the Mega-Vault) and bind it to your new agent. Also, attach the default ADK `GoogleSearch` tool."

### 🎯 The "Aha!" Demo Moment
1. When the AI finishes, run `uv run adk web improved_agent/agents/titanium_v1` in the terminal.
2. Open the browser to port 8080.
3. Show the audience that just by wrapping the logic in an `Agent` class and using Pydantic, ADK automatically generated a chat interface, debugging sidebar, and handles the structured JSON coercion *for free*. You deleted 50 lines of regex logic.

---

## ⏱️ Milestone 2: The "Decomposition" Upgrade (Minutes 20 - 45)

**The Problem**: The monolithic agent hallucinates because we crammed too much context into it (scouring the web, reasoning over a static vault, and drafting an email).
**The Solution**: We will evolve the monolithic agent into a `SequentialAgent` composed of 5 specialized agents. We will eliminate the static Vault and add Playwright to intelligently scrape live Case Studies.

### 🗣️ Presenter Script
1. Say: *"A single prompt doing 5 things poorly is 'Prompt Engineering'. A pipeline of 5 specialized agents doing 1 thing perfectly is 'Software Engineering'. Let's decompose this monolith."*

### 🤖 Live Prompt to Copy/Paste
> "That monolithic agent is doing too much. I want to build a truly decomposed pipeline using the ADK `SequentialAgent`.
>
> 1. Please create a new folder: `improved_agent/agents/titanium_pro`.
> 2. Inside `improved_agent/agents/titanium_pro/tools.py`, create a Playwright wrapper tool named `run_browser_command` that executes the Playwright CLI to aggressively scrape target URLs. Also, define Pydantic schemas for the interim stages (e.g., `CompanyResearch`, `CaseStudyList`).
> 3. Inside `improved_agent/agents/titanium_pro/agent.py` define 5 distinct agents that share state using `output_key` and standard ADK string interpolation (e.g., `{var_name}` inside standard f-strings):
>    - `company_researcher`: Gathers target context (outputs `company_research`).
>    - `search_planner`: Determines query terms for case studies (outputs `search_plan`).
>    - `case_study_researcher`: Uses the Playwright tool to scrape the live Google Cloud Case Study directory (outputs `case_study_data`).
>    - `case_study_selector`: Down-selects the top 3 case studies (outputs `selected_case_studies`).
>    - `email_drafter`: Takes `{company_research}` + `{selected_case_studies}` to draft the final HTML email array.
> 4. End the file by assembling them all into a final `SequentialAgent` named `titanium_pro`."

### 🎯 The "Aha!" Demo Moment
1. Run `uv run adk web improved_agent/agents/titanium_pro`.
2. Enter a query like "Revolut Data Engineering".
3. Open the tracing sidebar. Show the audience the "thought process" flowing sequentially from agent to agent. Emphasize how `output_key` isolates state, making it infinitely easier to regression-test individual components.

---

## ⏱️ Milestone 3: Productization & Scale (Minutes 45 - 55)

**The Problem**: Sales reps need to run this on 50 accounts in parallel, not one by one in a chat UI.
**The Solution**: Build a custom Quart Web Application (`app.py`) for parallel batch processing and expose a headless Cloud Function endpoint.

### 🗣️ Presenter Script
1. Say: *"The ADK web console is incredible for debugging... but it's not a product. Let's embed this ADK logic into a fast, async web app that runs multiple agent instances concurrently to scale our workload."*

### 🤖 Live Prompt to Copy/Paste
> "Now I need a frontend to run this agent on multiple targets in parallel. 
> 
> Please create a fully-styled Quart web application.
> 1. Create `improved_agent/app.py`.
> 2. Create the `/` route to serve an aesthetic HTML dashboard (glassmorphism UI) where I can paste a CSV block of target companies.
> 3. Create a Server-Sent Events (SSE) `/stream` endpoint.
> 4. In this stream endpoint, use ADK's `InMemorySessionService.execute()` to launch the `titanium_pro` SequentialAgent. Crucially, use `asyncio.gather()` to launch multiple executions in parallel, streaming the live status updates ("Executing Web Search", "Drafting Email") down to the frontend.
> 5. Create the required HTML/JS frontend inside the `templates` and `static` directories to consume this SSE stream and dynamically render gorgeous result cards as they complete."

### 🎯 The "Aha!" Demo Moment
1. In the terminal, run `make run-titanium-dashboard` (referencing the Makefile convention we defined in milestone 0).
2. Open the custom dashboard. Paste a CSV of 3 famous S&P 500 companies.
3. Hit "Generate". Watch all 3 cards stream in concurrently with live tickers. Explain that moving from raw scripts to ADK components enables this exact parallel orchestration pattern easily.

---

## 🎤 Q&A & Wrap Up (Minutes 55 - 60)
- Review the journey: Hardcoded Regex Monolith -> Pydantic ADK Agent -> Decomposed Sequential Pipeline -> Scalable Async Web App.
- Open the floor for questions.
