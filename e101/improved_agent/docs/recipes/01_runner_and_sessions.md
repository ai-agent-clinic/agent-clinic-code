# Recipe 01: Runner & Session Management

This recipe covers how to programmatically execute an ADK agent using the `Runner` component and manage state across turns using `InMemorySessionService`.

## Why It Matters
While the CLI (`uv run adk run`) is great for testing interactively, deploying an agent behind an API or a custom UI requires programmatic execution. The `Runner` orchestrates the flow of messages, and the `SessionService` persists the conversational and functional state (`output_key` results).

## Core Concepts

1.  **`InMemorySessionService`**: A lightweight, non-persistent storage mechanism for holding chat history and agent state during a run. In production, this would be swapped for a database-backed service.
2.  **`Runner`**: The execution engine that binds an `Agent` to a `SessionService` and processes incoming messages.
3.  **`runner.run_async()`**: An asynchronous generator that yields execution events (e.g., tool calls, agent responses) as they happen.

## Example: Executing a Pipeline Programmatically

This snippet demonstrates how to set up a session, run a `SequentialAgent` pipeline, and retrieve the final state once execution completes. 

```python
import asyncio
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Assuming you have an imported agent
from improved_agent.agents.titanium_pro.agent import titanium_pro_agent

async def run_pipeline(target_name: str, domain: str, role: str):
    # 1. Define Unique Identifiers
    session_id = f"pipeline_{target_name.replace(' ', '_')}"
    user_id = "titanium_user"
    app_name = "titanium_pro_app"

    # 2. Formulate the initial prompt
    query = f"Target: {target_name}. Domain: {domain}. Role: {role}."

    # 3. Initialize Services
    session_service = InMemorySessionService()
    runner = Runner(
        app_name=app_name, 
        agent=titanium_pro_agent, 
        session_service=session_service
    )

    try:
        # 4. Create the session explicitly
        await session_service.create_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )

        # 5. Format the message
        user_message = types.Content(role="user", parts=[types.Part(text=query)])

        # 6. Execute the runner
        # run_async is a generator yielding internal ADK events.
        # If running purely headless without UI streaming, you can just exhaust the iterator.
        async for _event in runner.run_async(
            user_id=user_id, session_id=session_id, new_message=user_message
        ):
            pass 

        # 7. Retrieve the populated state AFTER execution completes
        current_session = await session_service.get_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )

        # 8. Extract specific pieces of state based on the agent's output_key configurations
        company_res = current_session.state.get("company_research", {})
        email_res = current_session.state.get("drafted_email", {})

        return {
            "status": "success",
            "research": company_res,
            "email": email_res
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

# Execute
# result = asyncio.run(run_pipeline("Google", "google.com", "CTO"))
```

## Key Takeaways

*   **State Extraction**: The `current_session.state` dictionary automatically accumulates outputs from any agent in the pipeline that defines an `output_key`.
*   **Generators**: `run_async` yields highly granular events. In web endpoints (like Quart/FastAPI), you can yield these events directly to a Server-Sent Events (SSE) stream to provide real-time UI feedback to the user while the pipeline runs in the background.
