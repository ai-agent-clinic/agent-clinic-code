Building an AI agent that works beautifully on your local machine is easy. Building one that survives contact with reality—handling rate limits, avoiding infinite loops, and scaling beyond hardcoded data—is a completely different beast.

In the premiere episode of the AI Agent Clinic, Luis Sala sat down with Jacob Badish to pop the hood on "Titanium"—a promising but brittle sales research agent. Titanium's original job was to research a target company and draft a personalized outreach email. While the prototype ran, it was slow, relied on a monolithic Python script, and was limited to a hardcoded list of just 12 case studies.

Over the course of an hour, the team tore down and rebuilt the agent for production. Here are the core breakdowns, the fixes, and the engineering lessons from Episode 1.

1. Ditch the Monolith for Orchestrated Sub-Agents
The Breakdown: The original agent was running on a massive, linear for loop—a monolithic "engine block." If one spark plug misfired (an API timeout or hallucination), the entire engine stalled out and failed silently.
The Fix: We ripped out the monolith and installed a distributed framework using Google’s Agent Development Kit (ADK). We created a SequentialAgent pipeline, splitting the workload into specialized "cylinders": a Company Researcher, Search Planner, Case Study Researcher, Selector, and an Email Drafter.
The Lesson: Separation of concerns. Specialized agents with narrow tasks run more reliably than a single LLM trying to execute a massive, multi-step prompt.

Architecture: The Engine Swap
Plaintext
[BEFORE: The Monolith]
User Prompt 
   │
   ▼
[ Single, Massive Python Script ]
 ├─> Search Web 
 ├─> Analyze Data  --> IF ERROR: Entire script crashes
 └─> Draft Email 

====================================================================

[AFTER: Orchestrated Pipeline (ADK)]
User Prompt
   │
   ▼
[ Company Researcher Agent ] --> Initial client reconnaissance
   │
   ▼
[ Search Planner Agent ] --> Maps the research strategy
   │
   ▼
[ Case Study Researcher Agent ] --> Executes strategy, pulls raw data
   │
   ▼
[ Selector Agent ] --> Filters data, picks best 1-2 case studies
   │
   ▼
[ Drafter Agent ] --> Synthesizes context into final email


2. Decouple JSON Requirements (Pydantic is standard)
The Breakdown: Originally, Titanium forced JSON outputs out of the model via extensive hard-coding straight inside the prompt string. It resulted in dirty code, fragile parsing, and wasted tokens describing the exact structure over and over again.
The Fix: When swapping to ADK, we eradicated schema formatting instructions out of the prompt. Instead, we injected native Pydantic objects directly as explicit schema definitions. 

```python
# BEFORE: Prompt String Bloat
prompt = """
Give me the answer in this JSON format:
{
   "company": "Company Name",
   "pain_points": ["point1", "point2"]
}
"""

# AFTER: Pydantic Schema Injection in ADK
class CompanyIntel(BaseModel):
    company: str
    pain_points: list[str]

# ADK gracefully forces adherence behind the scenes.
```


3. Replace Hardcoded State with a Dynamic RAG Pipeline
The Breakdown: Titanium’s fuel tank was artificially tiny. It only knew about 12 hardcoded case studies written directly into the Python file. It couldn't scale or learn without a developer manually updating the code.
The Fix: We built a dynamic data intake system. An out-of-band headless web crawler (Playwright) was scripted to autonomously scrape Google Cloud's customer success website and batch them to Google Cloud Vector Search. Back in the pipeline, the Case Study Researcher runs a true Hybrid Search (combining Semantic & Exact Text searches via Reciprocal Rank Fusion) on the indexed corpus to fetch ideal case studies.
The Lesson: Hardcoding is fine for a prototype, but a production vehicle needs to refuel itself. True agentic value comes from giving agents the tools to autonomously fetch, scale, and query via Vector Search. Stop hardcoding your context limits.

Architecture: The RAG Pipeline Intake
Plaintext
 🌐 Live Web (Customer Success Site)
        │
        ▼
 🕷️ Playwright Crawler (Async, out-of-band dataset generation)
        │
        ▼
 🗄️ Google Cloud Vector DB (Hybrid Semantic/Text Search)
        │
        ▼ 
 🤖 Case Study Researcher (RRF Querying against Vector DB)


4. Observability is Non-Negotiable
The Breakdown: When an LLM gets confused in a standard script, it’s a "black box." You hear a clanking noise under the hood, but you have no idea which component is failing.
The Fix: We tapped into ADK’s first-class support for OpenTelemetry. Out of the box, ADK emits distributed traces for full execution flows, capturing model requests, tokens, and tool executions. We paired this OpenTelemetry backend with a tailored Server-Sent Events (SSE) streaming app, effectively designing a sleek live-telemetry dashboard for the user.
The Lesson: You cannot put an agent into production without "On-Board Diagnostics" (telemetry). You need OpenTelemetry traces to resolve ground-truth disputes and debug individual component latencies.


5. Taming the Token Burn (Cost Optimization)
The Breakdown: Agentic loops are gas guzzlers. If an agent hits an error and continually retries a prompt without a circuit breaker, it will burn through your token budget in minutes.
The Fix: By standardizing heavily on ADK's native orchestration, we inherited strict governor limits automatically. The framework natively encompasses exponential backoffs, timeout boundaries, and configurable retry loops without writing custom loop breaks into our native Python.
The Lesson: Always install circuit breakers. Let ADK or your orchestration framework handle graceful failures rather than writing complex try-catch retry loops natively.


Want to see the code in action? There is no substitute for watching the engine rebuild happen live. Watch the full Episode 1 of the AI Agent Clinic here to see exactly how Titanium was refactored. Here’s the repo.

Is your agent broken, buggy, or stuck in prototype purgatory? We want to help. Submit your agent and its architecture to agent-clinic@google.com for a chance to have it diagnosed and refactored live on the next episode!
