# Recipe 06: Context Management & Prompt Templating

This recipe details the difference between native ADK templating and Python f-strings, and how to pass variables successfully within an agent's `instructions`.

## F-Strings vs. ADK Jinja Templates

When defining an `Agent`'s instructions, you have two primary ways to inject dynamic data:

1.  **Python F-Strings (`f"{variable}"`)**: Evaluated exactly once, at the moment the Python file is parsed and the `Agent` object is instantiated.
2.  **ADK Jinja Templates (`{{ variable }}`)**: Evaluated dynamically by the ADK `Runner` right before the API call to Gemini is made, pulling data from the `SessionService` state.

## Rule of Thumb

*   **Use F-strings for Global, Static configurations.** Example: Injecting the current year, or loading a static text block from another file that does not change between pipeline runs.
*   **Use ADK Jinja templates for Pipeline Context.** Example: Passing the output of `Agent A` into the prompt of `Agent B` using `{{ output_key_from_agent_a }}`.

## Example: Combining Both

```python
import datetime
from google.adk.agents.llm_agent import Agent

# Note the f-string prefix 
COMPANY_RESEARCHER_INSTRUCTIONS = f"""
You are the Senior Strategic Cloud Architect. 
CURRENT YEAR: {datetime.date.today().year}.  <-- (1) F-String: Evaluated on load.

Analyze this data: 
{{ target_bio_result }}  <-- (2) Jinja Template: Evaluated at runtime by ADK.
"""

researcher = Agent(
    name="company_researcher",
    instruction=COMPANY_RESEARCHER_INSTRUCTIONS,
    output_key="research_findings"
)
```

## The Escaping Trap

If you use an f-string (e.g., to inject the current year) AND you want to include raw JSON examples in your prompt using literal curly braces `{}` (which you often do to guide formatting), Python will throw a `SyntaxError: f-string: expressions nested too deeply` or `KeyError` attempting to interpret your JSON braces as f-string variables.

**To fix this, you MUST double your curly braces `{{ }}` whenever you want literal braces inside an f-string:**

```python
# CORRECT WAY TO ESCAPE JSON IN AN F-STRING
INSTRUCTIONS_WITH_FSTRING_AND_JSON = f"""
CURRENT YEAR: {datetime.date.today().year}

RETURN FORMAT:
You MUST return data matching this JSON structure:
```json
{{
  "users": [
    {{
      "name": "John Doe",
      "role": "Admin"
    }}
  ]
}}
```
"""
```

**Warning:** Do not confuse doubled braces for f-string escaping `{{ "name": "val" }}` with the ADK Jinja template injection `{{ output_key }}`. 

If your prompt is NOT prefixed with an `f`, you do not need to escape curly braces for JSON. ADK's Jinja parser ignores standard single-brace JSON objects automatically.
