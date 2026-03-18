# Recipe 08: The Writer-Critic Loop

This recipe details how to implement the Writer-Critic loop pattern in ADK, which is one of the most effective ways to improve output quality. The core idea is simple: Agent A generates a draft, and Agent B critiques it against a rubric. The loop continues until the critic is satisfied.

## Setup: Writer and Critic Agents

First, define the two agents. The crucial parts are:
1. The Writer uses `output_key="draft"`.
2. The Critic's instructions inject the draft using the Jinja template `{{ draft }}`.
3. The Critic uses Pydantic to enforce a structured response (`is_approved`, `feedback`).

```python
from google.adk.agents.llm_agent import Agent
from pydantic import BaseModel, Field

class CriticFeedback(BaseModel):
    is_approved: bool = Field(description="True if the draft meets all requirements.")
    feedback: str = Field(description="Specific feedback on what needs to be changed.")

# 1. The Writer
writer = Agent(
    name="writer",
    instruction="Write a technical blog post based on the user's prompt. Take into account any previous feedback.",
    output_key="draft"
)

# 2. The Critic
critic = Agent(
    name="critic",
    instruction=\"\"\"
    Review the following draft against the technical style guide.
    Be strict. Output feedback and whether it is approved.
    
    DRAFT:
    {{ draft }}
    \"\"\",
    output_schema=CriticFeedback
)
```

## Creating the Feedback Loop

Once you have the two agents, you can orchestrate the loop in the runner. While ADK supports various graph structures, a simple `while` loop around isolated `Agent.run()` invocations (or using ADK's `SessionService`) is often the most explicit and easiest to debug.

```python
from google.adk.runners import DefaultRunner

def run_writer_critic_loop(prompt: str, max_iterations: int = 3):
    runner = DefaultRunner()
    
    # Initial state
    current_prompt = prompt
    
    for i in range(max_iterations):
        print(f"--- Iteration {i+1} ---")
        
        # 1. Writer generates draft
        writer_response = runner.run(agent=writer, prompt=current_prompt)
        draft = runner.state.get("draft")
        print(f"Draft Generated ({len(draft)} chars)")
        
        # 2. Critic reviews the draft
        # The critic agent will automatically unpack {{ draft }} from the state
        critic_response = runner.run(agent=critic, prompt="Review the draft.")
        
        is_approved = critic_response.data.is_approved
        feedback = critic_response.data.feedback
        
        if is_approved:
            print("Draft Approved!")
            return draft
            
        print(f"Critic Feedback: {feedback}")
        
        # Update the prompt for the next iteration to include the feedback
        current_prompt = f"Previous attempt was rejected. Address this feedback:\n{feedback}\n\nOriginal Request: {prompt}"
        
    print("Max iterations reached. Returning best effort.")
    return draft
```

## Key Takeaways
1. **Explicit Data Flow:** Use `output_key` on the Writer so the framework automatically binds the result to the session state. Use `{{ output_key }}` on the Critic so it reads it on the next turn.
2. **Structured Criticism:** Forcing the Critic to output a Pydantic schema (with a boolean `is_approved` flag) is the only reliable way for a parent script or framework graph to know if it should break the loop. 
3. **Pass Feedback Back:** Make sure the Writer's prompt in the next iteration explicitly contains the Critic's feedback, or it will just generate the exact same draft again.
