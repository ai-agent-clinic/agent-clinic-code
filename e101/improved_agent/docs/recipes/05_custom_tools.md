# Recipe 05: Custom Tools & System Skills

This recipe details how to extend an ADK agent's capabilities beyond simple API calls by defining robust Python functions (`verb_noun` pattern) and loading external system scripts via ADK Skills.

## The Explicit Docstring (Verb-Noun Pattern)

ADK agents rely heavily on Google Gemini's function calling architecture. When you pass a Python function to an `Agent(tools=[...])` array, ADK parses the function name, arguments, and docstring into a JSON schema that the LLM understands.

To optimize this process, adhere to strict styling:

```python
# GOOD: Verb_Noun naming convention. Clear description. Documented args.
def generate_pdf_report(title: str, content: str) -> str:
    """Generates a PDF report and saves it to the local filesystem.

    Args:
        title: The title of the report.
        content: The HTML or markdown body of the report.

    Returns:
        The absolute file path to the saved PDF.
    """
    # Implementation...
    return f"/tmp/{title}.pdf"

# BAD: Vague naming. Missing docstrings. No type hints.
def do_pdf(t, c):
    # Implementation...
    return "done"
```

If your function lacks type hints or a docstring, the LLM will hallucinate arguments or misuse the tool entirely.

## System Skills & Execution Delegation

Sometimes you need an agent to run raw system binaries or Node.js scripts (like `playwright-cli` for browser automation). Instead of writing complex wrapper logic, you can define an isolated ADK "Skill" directory and load it.

### Step 1: Define the Skill
Create a directory (e.g., `skills/playwright-cli/`) containing:
1. `SKILL.yaml` (Defining the skill name and entrypoint).
2. The implementation script (e.g., `run.sh` or `index.js`).

### Step 2: Load the Skill in ADK

```python
import pathlib
from google.adk.skills import load_skill_from_dir
from google.adk.tools import skill_toolset

# Load the external binary/script logic into an ADK Skill object
playwright_skill = load_skill_from_dir(
    pathlib.Path(__file__).parent.parent.parent / "skills" / "playwright-cli"
)

# Wrap it in a Toolset (ADK's interface for managing multiple skills)
playwright_toolset = skill_toolset.SkillToolset(skills=[playwright_skill])
```

### Step 3: Provide a Shim Tool for the Agent

While the `playwright_toolset` exposes the underlying mechanic, it is often best to provide a "shim" Python function that acts as the cleanly documented interface for the LLM to call, which then hooks into the underlying binary execution:

```python
import subprocess

def run_browser_command(url: str, extract_selector: str) -> str:
    """Navigates a headless browser to the URL and extracts text matching the CSS selector.
    
    Args:
        url: The website to scrape.
        extract_selector: The CSS selector to target (e.g., "article", "p.bio").
    """
    # Use the underlying system tool via standard subprocess or the ADK Toolset execution methods
    result = subprocess.run(
        ["playwright-cli", "extract", url, extract_selector], 
        capture_output=True, text=True
    )
    return result.stdout
```

Then attach `run_browser_command` to your `Agent(tools=[run_browser_command])`.

## Key Takeaways
1. **The LLM is Blind:** The LLM cannot read your Python code. It only sees the function name, arguments, type hints, and docstring. 
2. **Error Handling in Tools:** If your custom tool hits a 404 or an internal error, **return the error message as a string** rather than throwing a Python Exception. Returning the error string allows the LLM to read the failure and try a different approach natively without crashing the entire ADK Runner pipeline.
