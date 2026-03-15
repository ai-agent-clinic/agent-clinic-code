import asyncio
import pathlib
from google.adk.agents.llm_agent import Agent
from google.adk.skills import load_skill_from_dir
from google.adk.tools import skill_toolset
from .tools import run_browser_command, save_case_study

playwright_skill = load_skill_from_dir(
    pathlib.Path(__file__).parent.parent.parent / "skills" / "playwright-cli"
)

playwright_toolset = skill_toolset.SkillToolset(
    skills=[playwright_skill]
)

INSTRUCTIONS = """
You are the Case Study Researcher Agent.
Your job is to search for and extract Google Cloud customer case studies from 'https://cloud.google.com/customers' on behalf of the user.

You have access to a custom tool, `run_browser_command`, to control the Playwright CLI.
You have the `playwright-cli` skill. Use this skill to learn how to interact with the browser and extract content using the `run_browser_command` tool.

When browsing:
1. Initialize the browser by navigating to the Google Cloud customers page.
2. Search for the requested topics.
3. Extract the clean text of the case study. Remove navigation bars, footers, and HTML clutter.
4. Format the extracted text as a clean Markdown document.
5. Use the `save_case_study` tool to save your work. Provide the original topic, the company name from the case study, and the formatted markdown string.
"""


root_agent = Agent(
    model='gemini-2.5-flash',
    name='case_study_researcher',
    description='An agent that scrapes Google Cloud customer case studies and saves them to a local knowledge base.',
    instruction=INSTRUCTIONS,
    tools=[playwright_toolset, run_browser_command, save_case_study]
)

if __name__ == "__main__":
    from google.adk.cli.cli import run_interactively
    asyncio.run(run_interactively(root_agent))
