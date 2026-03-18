# ADK Development Recipes

This directory contains a progressive set of "recipes" and best practices for developing, testing, and scaling agents using the Google Agent Development Kit (ADK) v1.23.0.

These guides move from basic foundational concepts (handling state and testing) up through complex architectural patterns (hierarchies, Writer-Critic loops).

## Table of Contents

1. **[Runner & Session Management](./01_runner_and_sessions.md)**: Handling local runs, managing `SessionService`, and tracking conversation state.
2. **[Testing Best Practices](./02_testing_best_practices.md)**: Leveraging the `adk run` CLI vs. automated testing suites.
3. **[Agent Chaining Architectures](./03_agent_chaining.md)**: Passing output dynamically from one agent to the next.
4. **[RAG with Vector Search](./04_rag_vector_search.md)**: Using external vector databases as tools.
5. **[Custom Tools & System Skills](./05_custom_tools.md)**: Defining strict `verb_noun` Python functions and loading external binary skills.
6. **[Context Management & Prompt Templating](./06_context_and_prompts.md)**: Understanding when to use Python f-strings vs. ADK Jinja templates, and how to escape JSON schemas.
7. **[Strict Output Enforcement with Pydantic](./07_pydantic_schemas.md)**: Preventing `ValidationError` crashes by matching explicit prompt JSON to schema classes.
8. **[The Writer-Critic Loop](./08_writer_critic.md)**: Using feedback loops to guarantee higher quality LLM output.
9. **[Hierarchical Multi-Agent Structures](./09_hierarchical_agents.md)**: Implementing a structured "Russian Doll" Manager-Worker decomposition approach.

## How to use this documentation
Read them sequentially to learn ADK, or jump directly into the architecture recipes if you are designing a specific pipeline. Always refer back to the [ADK documentation tools](../../AGENTS.md) if syntax behavior changes over time.
