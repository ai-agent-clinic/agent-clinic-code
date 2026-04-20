# Titanium - AI Agent Clinic

[![Can we fix this AI agent in 60 minutes?](https://img.youtube.com/vi/md2VFN6SojQ/maxresdefault.jpg)](https://www.youtube.com/live/md2VFN6SojQ)
*📺 Watch the live teardown and rebuild on YouTube: [Can we fix this AI agent in 60 minutes?](https://www.youtube.com/live/md2VFN6SojQ)*

**Titanium** is a highly optimized, production-ready sales research agent built using the **Google Agent Development Kit (ADK)**. 

Have you ever "vibe-coded" an AI prototype that works perfectly on the first try, but fails silently in production? That was Titanium. Originally created as a brittle, monolithic script, Titanium was brought to the **AI Agent Clinic** to be torn down and rebuilt live in under 60 minutes. 

It was transformed into a distributed, orchestrated, and resilient pipeline. Rather than relying on hardcoded case studies and brittle string parsing, it utilizes Pydantic for rigid structured outputs, autonomous asynchronous crawlers (via Playwright) for RAG context building, and Vertex AI Vector Search to fetch accurate, hyper-relevant case studies.

## Architecture Highlights
*   **Orchestrated Sub-Agents:** Splits the monolithic task into an orchestrated pipeline of tools including a Company Researcher, Case Study Researcher, and Email Drafter.
*   **Dynamic RAG Pipeline:** Escapes hardcoded data by autonomously scraping customer success stories and injecting them into a Vertex AI Vector DB.
*   **Observability:** Full OpenTelemetry distributed tracing integrated natively via ADK.
*   **Structured Outputs:** Uses Pydantic objects to abstract API boilerplate and ensure rigid, schema-compliant JSON responses instead of brittle prompt parsing.

## Running the Application

Before running the agents, you must configure your environment variables. We have provided a sample template you can duplicate:
```bash
cp .env.sample .env
```
Update the new `.env` file with your specific `GEMINI_API_KEY`, your GCP `PROJECT_ID`, and adjust the Vector Search cache configuration if necessary. The project leverages `uv` as the package manager and incorporates a web UI via Quart.

You can use the provided `Makefile` to easily run different versions of the agent.

### 1. Running the Original Agent
To run the original, monolithic version of the agent locally via the Google Cloud Functions Framework:
```bash
make run-original
```

### 2. Running Titanium Pro via the Web Dashboard
To run the new, orchestrated pipeline (Titanium Pro) through the interactive web user interface:
```bash
make run-titanium-dashboard
```
This will start a local Quart web server. Open `http://0.0.0.0:8080` in your browser to access the dashboard.

## Setup & Dependencies

To manage dependencies, ensure you have [uv](https://docs.astral.sh/uv/) installed on your machine.

```bash
# Command to add additional dependencies if needed
uv add <package_name>
```

You can learn more about ADK and view the documentation [here](https://google.github.io/agent-development-kit/).

## Contributing
We welcome contributions. Please review the `CONTRIBUTING.md` file for details on our code of conduct, and the process for submitting pull requests to us.
