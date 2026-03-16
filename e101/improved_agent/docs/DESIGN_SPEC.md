# Project Titanium Pro: Architectural Design Specification

## 1. Executive Summary
Titanium Pro is a high-cognitive, fully automated generative AI pipeline built on the **Google Agent Development Kit (ADK) v1.23.0**. It is designed to autonomously research Fortune 500 executives, identify deep strategic context, scrape live Google Cloud case studies, and draft hyper-personalized technical outreach emails. 

This spec outlines the migration from a monolithic scripting approach to a highly scalable, decomposed, concurrent agentic application.

## 2. Core Architecture: The `SequentialAgent` Pipeline
The core intelligence engine resides in `improved_agent/agents/titanium_pro/agent.py`. It implements the decomposition pattern, utilizing a `SequentialAgent` pipeline to break the complex research-and-draft workflow into 5 specialized micro-agents. 

State is passed cleanly between agents using the ADK `output_key` parameter and string interpolation (`{var_name}`).

### Pipeline Stages
1. **`company_researcher`**: 
   - **Role**: Information Gathering.
   - **Action**: Uses Google Search to extract the target executive's name and critical business context (e.g., recent quotes, likely tech stack, roadmap items).
   - **Output**: Writes to `output_key="company_research"` (validated via `CompanyResearch` Pydantic model).
2. **`search_planner`**: 
   - **Role**: Query Optimization.
   - **Action**: Synthesizes the company research to generate highly specific query strings targeting Google Cloud case studies.
   - **Output**: Writes to `output_key="search_plan"` (validated via `SearchPlan` Pydantic model).
3. **`case_study_researcher`**: 
   - **Role**: Data Extraction.
   - **Action**: Ingests `{search_plan}`. Utilizes the robust `playwright-cli` to search `https://cloud.google.com/customers` and recursively scrape the actual case study content.
   - **Output**: Writes to `output_key="case_study_data"` (validated via `CaseStudyList` Pydantic model).
4. **`case_study_selector`**: 
   - **Role**: Strategic Down-selection.
   - **Action**: Ingests `{case_study_data}` and evaluates which retrieved studies best align with the target's persona.
   - **Output**: Writes to `output_key="selected_case_studies"`.
5. **`email_drafter`**: 
   - **Role**: Content Generation.
   - **Action**: Ingests `{company_research}` and `{selected_case_studies}` to draft a 3-sentence, architect-to-architect HTML email and a strategic cross-sell matrix.
   - **Instructions**: Explicitly constrained via few-shot prompting to vary language and enforce a zero-sales-fluff tone.

## 3. Productization & Scale: The Orchestration Layer
To scale the pipeline for enterprise usage, the ADK agents are wrapped in a fast, asynchronous Python web server (`improved_agent/app.py`) built with **Quart**. 

The orchestrator supports two primary execution modalities:

### A. The Interactive Web Dashboard (UI Mode)
- **Frontend**: A custom HTML/JS interface utilizing dynamic glassmorphism aesthetics. Allows users to paste a CSV block of target accounts.
- **Backend Orchestration**: Uses `ADK`'s `InMemorySessionService.execute()` to trigger pipelines. 
- **Concurrency**: Bypasses sequential processing by wrapping executions in an `asyncio.gather()` array, allowing 10+ target accounts to be processed simultaneously.
- **Streaming**: Implements Server-Sent Events (SSE) via the `/stream` endpoint to stream live execution statuses ("Executing Web Search...", "Scraping Case Studies...") down to the browser context.

### B. The Headless API (Cloud Run Mode)
- **Endpoint**: Exposes a headless HTTP POST route (`/run_agent_logic`).
- **Input Flexibility**: Accepts both raw CSV strings or JSON arrays of target companies.
- **Execution**: Runs the same concurrent orchestration logic as the UI, returning structured JSON or a compiled HTML response. Designed specifically for integration into CRM workflows or automated CI/CD pipelines via Google Cloud Run/Functions.

## 4. Tooling & Security Constraints
- **Structured Outputs**: All critical data transitions use **Pydantic schemas** (`OutreachEmail`, `CompanyResearch`). The pipeline strictly avoids regex parsing.
- **Browser Automation Security**: The system uses a restricted wrapper (`run_browser_command`) around the `playwright-cli`. 
- **Workspace Hygiene**: The `playwright-cli` wrapper implements automatic cleanup procedures, deleting temporal snapshot `.yml` files immediately after they are read by the agent tools to prevent workspace clutter.
