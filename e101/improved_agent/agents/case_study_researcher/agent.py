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

INSTRUCTIONS = """
You are the Case Study Researcher Agent.
Your job is to search for and extract Google Cloud customer case studies from 'https://cloud.google.com/customers' on behalf of the user.

You have the `playwright-cli` skill. Use this skill to learn how to interact with the browser and extract content. Use `run_browser_command` to run playwright-cli commands.

When browsing:
1. Initialize the browser by navigating to the Google Cloud customers page.
2. Search for the requested topics.
3. Extract the clean text of the case study. Remove navigation bars, footers, and HTML clutter.
4. Format the extracted text as a clean Markdown document.
5. Once you have all the information, provide a structured CaseStudy object containing the source URL, customer name, extracted contents, summary, industry, location, and products used.

Respond ONLY with a JSON object matching the requested CaseStudy schema as your final response.

CRITICAL: When the user asks you to "respond with exactly this: '[some phrase]'", you MUST output ONLY that exact phrase in your final response. Do not add conversational padding, do not say "Here is the response", and do not include the markdown content in the chat. Just the exact phrase or the JSON object.
"""


root_agent = Agent(
    model='gemini-3-flash-preview',
    name='case_study_researcher',
    description='An agent that scrapes Google Cloud customer case studies and extracts them into structured JSON data.',
    instruction=INSTRUCTIONS,
    tools=[playwright_toolset, run_browser_command],
    output_schema=CaseStudy,
    output_key="case_study_result"
)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        print(f"Running agent with query: {query}")
        
        # Use InMemoryRunner to execute the agent directly
        runner = InMemoryRunner(agent=root_agent)
        try:
            # run_debug blockingly executes the agent loop and prints to console
            # It returns the stream of events
            events = asyncio.run(runner.run_debug(
                query,
                user_id="cli_user",
                session_id="cli_session",
                verbose=True
            ))
            
            # Save output to file from the final response event
            for event in reversed(events):
                if event.is_final_response():
                    raw_json = event.content.parts[0].text
                    try:
                        case_study_data = CaseStudy.model_validate_json(raw_json)
                        result = save_case_study(query, case_study_data)
                        print(f"\\nCase study saved successfully: {result}")
                    except Exception as e:
                        print(f"\\nFailed to parse or save case study JSON: {e}")
                        print(f"Raw output:\\n{raw_json}")
                    break
                    
        except Exception as e:
            print(f"Error executing agent: {e}")
    else:
        print("Starting interactive mode...")
        from google.adk.cli.cli import run_interactively
        asyncio.run(run_interactively(root_agent))
