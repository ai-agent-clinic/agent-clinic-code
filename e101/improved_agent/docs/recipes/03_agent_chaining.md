# Recipe 03: Agent Chaining Architectures

This recipe covers how to link multiple discrete `Agent` instances together using ADK's `SequentialAgent` structure to execute a deterministic, multi-step pipeline.

## Why It Matters
While monolithic agents (one massive prompt) are easy to write, they degrade as tasks become complex. Breaking tasks down into smaller, highly-focused agents (e.g., a "Researcher" followed by a "Drafter") drastically reduces hallucination and improves instruction adherence.

## Core Concepts

*   **`Agent`**: A single node in the graph, representing one LLM call with a specific system prompt, tools, and `output_key`.
*   **`SequentialAgent`**: A higher-order component that takes a `list` of `sub_agents`. It executes them in exact order.
*   **State Accumulation**: As the `SequentialAgent` steps through its `sub_agents`, any data emitted via an agent's `output_key` is appended to the session `state`. Subsequent agents in the chain can retrieve this data using Jinja templating (e.g., `{{ output_key_of_previous_agent }}`).

## Example: The Titanium Pro Pipeline

In the `titanium_pro` agent, we break the research and drafting process into 5 distinct agents executed sequentially.

```python
from google.adk.agents.llm_agent import Agent
from google.adk.agents.sequential_agent import SequentialAgent

# 1. Company Researcher
company_researcher = Agent(
    model=_ROBUST_FLASH_MODEL,
    name="company_researcher",
    instruction="Research the target bio and extract intel...",
    output_schema=CompanyResearch,
    output_key="company_research", # <-- Stored in state
)

# ... (Planner, Case Study Researcher, Case Study Selector) ...

# 5. Email Drafter
# We selectively inject the output of previous agents using Jinja template syntax.
EMAIL_DRAFTER_INSTRUCTIONS = """
TARGET BIO & RESEARCH: {{ company_research }}
RELEVANT CASE STUDIES: {{ selected_case_studies }}

Draft a PUNCHY, SIMPLE, 3-sentence outreach email...
"""

email_drafter = Agent(
    model=_ROBUST_PRO_MODEL, 
    name="email_drafter",
    instruction=EMAIL_DRAFTER_INSTRUCTIONS,
    output_schema=OutreachEmail,
    output_key="drafted_email",
)

# Orchestration
titanium_pro_agent = SequentialAgent(
    name="titanium_pro_pipeline",
    sub_agents=[
        company_researcher,
        planner_agent,
        case_study_researcher,
        selector_agent,
        email_drafter,
    ],
)
```

## Key Takeaways

1.  **Order Matters**: The `SequentialAgent` executes the list strictly from top to bottom.
2.  **Explicit Context Passing**: The `email_drafter` knows absolutely nothing about what the `company_researcher` did *unless* you explicitly inject its output using `{{ company_research }}` in the drafter's system prompt instructions. ADK does not magically pass context between chained agents.
3.  **Mixing Models**: Chaining is highly efficient for cost and speed. You can use cheaper/faster flash models (`gemini-3-flash-preview`) for early research/planning nodes, and reserve the slower/smarter pro models (`gemini-3-pro-preview`) for the final drafting and reasoning nodes.
