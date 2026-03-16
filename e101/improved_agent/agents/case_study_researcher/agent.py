import asyncio
import sys
import pathlib
from google.adk.agents.llm_agent import Agent
from google.adk.skills import load_skill_from_dir
from google.adk.tools import skill_toolset
from google.adk.runners import InMemoryRunner
from google.genai.types import Content, Part
from .tools import run_browser_command, save_case_study, CaseStudy
import json

playwright_skill = load_skill_from_dir(
    pathlib.Path(__file__).parent.parent.parent / "skills" / "playwright-cli"
)

playwright_toolset = skill_toolset.SkillToolset(
    skills=[playwright_skill]
)

PLANNER_INSTRUCTIONS = """
You are the Search Planner Agent.
Review the user's query and generate 3 to 5 highly specific search terms or phrases we can use to find relevant Google Cloud case studies.
Return ONLY a JSON list of strictly formatted search queries matching the SearchPlan schema.
"""

RESEARCHER_INSTRUCTIONS = """
You are the Case Study Researcher Agent.
Your job is to search for and extract Google Cloud customer case studies from 'https://cloud.google.com/customers' on behalf of the user.

You have the `playwright-cli` skill. Use this skill to learn how to interact with the browser and extract content. Use `run_browser_command` to run playwright-cli commands.

Here are the optimal search terms formulated by the planner:
{{ search_plan }}

When browsing:
1. Initialize the browser by navigating to the Google Cloud customers page.
2. Search for the requested topics using the planned search terms.
3. Extract the clean text of the case study. Remove navigation bars, footers, and HTML clutter.
4. Format the extracted text as a clean Markdown document.
5. Once you have all the information, provide a structured CaseStudy object containing the source URL, customer name, extracted contents, summary, industry, location, and products used.

Respond ONLY with a JSON object matching the requested CaseStudy schema as your final response.

CRITICAL: When the user asks you to "respond with exactly this: '[some phrase]'", you MUST output ONLY that exact phrase in your final response. Do not add conversational padding, do not say "Here is the response", and do not include the markdown content in the chat. Just the exact phrase or the JSON object.
"""

from google.adk.agents.sequential_agent import SequentialAgent
from .tools import SearchPlan

planner_agent = Agent(
    model='gemini-3-flash-preview',
    name='search_planner',
    description='Analyzes the query and generates 3-5 optimal search terms.',
    instruction=PLANNER_INSTRUCTIONS,
    output_schema=SearchPlan,
    output_key="search_plan"
)

researcher_agent = Agent(
    model='gemini-3-flash-preview',
    name='case_study_researcher',
    description='An agent that scrapes Google Cloud customer case studies and extracts them into structured JSON data.',
    instruction=RESEARCHER_INSTRUCTIONS,
    tools=[playwright_toolset, run_browser_command],
    output_schema=CaseStudy,
    output_key="case_study_result"
)

root_agent = SequentialAgent(
    name='case_study_pipeline',
    sub_agents=[planner_agent, researcher_agent]
)

from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
import json

async def case_study_research(query: str) -> dict:
    """Execute the sequential pipeline (planner -> researcher) to extract structured case study intel."""
    session_id = "pipeline_session"
    user_id = "pipeline_user"
    app_name = "case_study_app"

    session_service = InMemorySessionService()
    runner = Runner(
        app_name=app_name,
        agent=root_agent,
        session_service=session_service
    )
    
    try:
        await session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
        
        user_message = types.Content(role="user", parts=[types.Part(text=query)])
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=user_message):
            # Print minimal event progress to stdout just for tracking
            agent_name = getattr(event, 'agent_name', getattr(event, 'source', 'Unknown'))
            if event.is_final_response():
                print(f"Pipeline executed step for {agent_name}...")
        
        current_session = await session_service.get_session(app_name=app_name, user_id=user_id, session_id=session_id)
        raw_json = current_session.state.get("case_study_result")
        
        if raw_json:
            try:
                case_study_data = CaseStudy.model_validate_json(raw_json)
                result = save_case_study(query, case_study_data)
                return {"status": "success", "data": case_study_data.model_dump(), "filepath": result.get("filepath", "")}
            except Exception as e:
                return {"status": "error", "message": f"Failed to parse case study JSON: {e}", "raw": raw_json}
        else:
             return {"status": "error", "message": "No 'case_study_result' found in session state."}
             
    except Exception as e:
        return {"status": "error", "message": f"Error executing pipeline: {e}"}

if __name__ == "__main__":
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        print(f"Running agent with query: {query}")
        result = asyncio.run(case_study_research(query))
        print(f"\\nPipeline Result:\\n{json.dumps(result, indent=2)}")
    else:
        print("Starting interactive mode... please use the ADK CLI to run interactively:")
        print("uv run adk run improved_agent/agents/case_study_researcher")
