# Recipe 09: Hierarchical Multi-Agent Structures (Manager-Worker Pattern)

This recipe explores how to build hierarchical "Russian Doll" agent architectures in ADK. In this pattern, a "Manager" agent interprets a broad prompt, breaks it down into a list of specific sub-tasks, and delegates those tasks to "Worker" agents.

## Understanding the Architecture

Instead of one monolithic agent with 20 tools, it is more reliable to have:
1. **The Manager:** An agent focusing purely on planning, decomposition, and routing. It outputs a structured list of tasks.
2. **The Workers:** Narrowly scoped agents, each equipped with specific tools (e.g., a "Code Writer", a "Code Reviewer", a "Web Searcher").

## The Manager Schema and Agent

First, force the Manager to output an executable plan using Pydantic.

```python
from pydantic import BaseModel, Field
from typing import List
from google.adk.agents.llm_agent import Agent

class SubTask(BaseModel):
    worker_type: str = Field(description="Must be 'researcher' or 'writer'")
    instructions: str = Field(description="Detailed instructions for the worker")

class ExecutionPlan(BaseModel):
    tasks: List[SubTask] = Field(description="The ordered list of tasks to execute")

manager_agent = Agent(
    name="manager",
    instruction="""
    You are the Project Manager. Break the user's request down into a step-by-step ExecutionPlan.
    You can delegate tasks to either a 'researcher' or a 'writer'. 
    Be highly specific in your instructions for each task.
    """,
    output_schema=ExecutionPlan
)
```

## The Worker Agents

Define the localized worker agents. They do not need to know about the broader architectural plan.

```python
researcher_agent = Agent(
    name="researcher",
    instruction="You are a Web Researcher. Find answers to the queries assigned to you.",
    tools=[search_web_tool]  # Assumes you defined this tool elsewhere
)

writer_agent = Agent(
    name="writer",
    instruction="You are a Technical Writer. Produce content based on the provided research context."
)

WORKER_REGISTRY = {
    "researcher": researcher_agent,
    "writer": writer_agent
}
```

## Orchestrating the Hierarchy

The runtime script acts as the "glue", invoking the Manager, parsing the array of tasks, and iterating through them to invoke the appropriate Workers.

```python
from google.adk.runners import DefaultRunner

def execute_hierarchical_plan(user_prompt: str):
    runner = DefaultRunner()
    
    # 1. The Manager creates the plan
    print("Manager is planning...")
    manager_result = runner.run(agent=manager_agent, prompt=user_prompt)
    plan = manager_result.data.tasks
    
    # 2. Iterate through the delegated tasks
    aggregated_context = []
    
    for task in plan:
        worker_agent = WORKER_REGISTRY.get(task.worker_type)
        if not worker_agent:
            print(f"Error: Unknown worker type {task.worker_type}")
            continue
            
        print(f"Delegating to {task.worker_type}: {task.instructions}")
        
        # Provide the worker with its specific instructions AND the context generated so far
        worker_prompt = f"""
        TASK INSTRUCTIONS:
        {task.instructions}
        
        PREVIOUS CONTEXT:
        {aggregated_context}
        """
        
        worker_result = runner.run(agent=worker_agent, prompt=worker_prompt)
        
        # Append the worker's output to the running state
        aggregated_context.append(f"Output from {task.worker_type}: {worker_result.text}")
        
    print("\n--- FINAL EXECUTION COMPLETE ---")
    return aggregated_context[-1] # Return the final worker's output
```

## Key Takeaways
1. **Reduce Context Overload:** The hierarchical pattern is the best way to prevent the LLM from getting "confused" by a massive system prompt with dozens of tools.
2. **Dynamic DAGs:** By letting the Manager output a list of `SubTask` items, the LLM is effectively writing its own Directed Acyclic Graph (DAG) for execution at runtime, rather than you hardcoding the sequence of steps.
3. **State Management:** When orchestrating sub-agents, manually passing the `aggregated_context` into the next worker's prompt is crucial; otherwise, they operate blind to what the previous worker discovered.
