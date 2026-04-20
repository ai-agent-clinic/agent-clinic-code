# AI Agent Clinic

Welcome to the **AI Agent Clinic** repository! This project contains the code developed across various episodes of the AI Agent Clinic YouTube program.

Our mission is to help AI developers transition from fragile, monolithic prototypes into robust, production-ready agentic systems. We take "brittle" AI agents—those prone to hallucination, silent failures, rate limits, and infinite loops—and rebuild them live. The code in this repository demonstrates how to implement best practices such as separating monolithic scripts into orchestrated sub-agents, enforcing structured outputs, constructing dynamic RAG (Retrieval-Augmented Generation) pipelines, and adding rigorous observability.

---

## Episodes

### [Episode 101: Rebuilding "Titanium"](./e101)
In our premiere episode, we perform a complete teardown of "Titanium", a promising but fragile sales research agent. Originally, Titanium ran as a massive monolithic Python script trying to execute a multi-step prompt with a tiny hardcoded list of case studies.

**What we cover in this episode:**
- **Orchestrated Sub-Agents:** Splitting a monolithic script into a distributed framework using the Google Agent Development Kit (ADK) `SequentialAgent` pipeline with specialized nodes (Planner, Researcher, Selector, Drafter).
- **Structured Outputs via Pydantic:** Moving away from fragile textual JSON instructions by injecting native Pydantic schemas, relying on Vertex AI to guarantee structural integrity.
- **Dynamic RAG Pipelines:** Replacing hardcoded context with an autonomous Playwright crawler that pushes data to a Google Cloud Vector Search database, and implementing hybrid search for semantic and exact-keyword precision.
- **Observability:** Leveraging ADK's OpenTelemetry integration to emit distributed traces for execution flows, preventing the dreaded "black-box" failures.
- **Cost Optimization:** Installing standard circuit-breakers via native framework settings (exponential backoffs, timeout boundaries) to prevent runaway cloud bills from agent errors.

Check out the [e101 directory](./e101) to explore the original fragile agent and our improved, production-ready implementation!
