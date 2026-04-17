# Titanium - AI Agent Clinic

Titanium is a highly optimized, production-ready sales research agent built using the **Google Agent Development Kit (ADK)**. 

Originally created as a monolithic script, Titanium was rebuilt during Episode 1 of the **AI Agent Clinic** series into a distributed, orchestrated, and resilient pipeline. Rather than relying on hardcoded case studies and brittle string parsing, it utilizes Pydantic for structured outputs, autonomous asynchronous crawlers (via Playwright) for RAG context building, and Vertex AI Vector Search to fetch accurate, hyper-relevant case studies.

## Architecture Highlights
*   **Orchestrated Sub-Agents:** Splits the monolithic task into an orchestrated pipeline of tools including a Company Researcher, Case Study Researcher, and Email Drafter.
*   **Dynamic RAG Pipeline:** Escapes hardcoded data by autonomously scraping customer success stories and injecting them into a Vertex AI Vector DB.
*   **Observability:** Full OpenTelemetry distributed tracing integrated natively via ADK.
*   **Structured Outputs:** Uses Pydantic objects to abstract API boilerplate and ensure rigid, schema-compliant JSON responses instead of brittle prompt parsing.

## Running the Application

Ensure you have your environment configured, specifically setting your `GEMINI_API_KEY`. The project leverages `uv` as the package manager and incorporates a web UI via Quart.

```bash
# Set your Gemini API key
export GEMINI_API_KEY="your-api-key-here"

# Run the application
uv run main.py
```

## Setup & Dependencies

To manage dependencies, ensure you have [uv](https://docs.astral.sh/uv/) installed on your machine.

```bash
# Command to add additional dependencies if needed
uv add <package_name>
```

You can learn more about ADK and view the documentation [here](https://google.github.io/agent-development-kit/).

## Contributing
We welcome contributions. Please review the `CONTRIBUTING.md` file for details on our code of conduct, and the process for submitting pull requests to us.
