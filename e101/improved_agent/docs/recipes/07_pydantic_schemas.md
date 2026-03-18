# Recipe 07: Strict Output Enforcement with Pydantic

This recipe details how to force ADK agents to output data matching complex `pydantic` models without crashing during the framework's JSON schema validation envelope.

## Why It Matters
When passing `output_schema=MyModel` to an ADK `Agent`, the framework uses Gemini's underlying "Structured Output" (JSON Schema) generation capabilities. However, complex Pydantic models (especially those with nested lists or custom aliases) can confuse the model or the deserializer, leading to missed fields and validation crashes.

## Anti-Pattern: Pydantic Aliases

Do not use `Field(alias="...")` in ADK schemas if the alias contains characters the LLM struggles to parse as a raw dictionary key (like spaces or ampersands), or if it diverges too heavily from the python variable name. 

Gemini often outputs the JSON using the Python variable name, ignoring the alias constraint, causing the ADK Pydantic validator to crash because the `alias` expectation wasn't met.

```python
from pydantic import BaseModel, Field

# BAD: Gemini might output {"gemini_enterprise": {...}} instead of {"Gemini Enterprise": {...}}
# This causes the Pydantic parser to throw a "Field required" crash.
class CrossSellMatrixBad(BaseModel):
    gemini_enterprise: str = Field(alias="Gemini Enterprise", description="...")
    data_ai: str = Field(alias="Data & AI", description="...")

# GOOD: Use standard pythonic variable names. 
class CrossSellMatrixGood(BaseModel):
    gemini_enterprise: dict = Field(description="Gemini pitch...")
    data_ai: dict = Field(description="Data pitch...")
```

## The "Explicit Example" Pattern

Even with well-named Python variables, Gemini can sometimes hallucinate the schema's shape (for instance, dropping required keys in deeply nested arrays). 

To ensure 100% adherence to your Pydantic schema, provide an explicit dummy JSON example representing the *exact* shape directly inside the agent's `instructions`.

```python
INSTRUCTIONS = """
You are a research analyst. Analyze the data and return an OutreachEmailList.

OUTPUT STRUCTURE EXAMPLE:
```json
{
  "accounts": [
    {
      "account_name": "Company Name",
      "outreach": {
        "target_name": "Target Name",
        "hack": {
            "gemini_enterprise": { "name": "...", "solution": "..." },
            "security": { "name": "...", "solution": "..." }
        }
      }
    }
  ]
}
```
"""

my_agent = Agent(
    name="my_agent",
    instruction=INSTRUCTIONS,
    output_schema=OutreachEmailList
)
```

By merging the framework-level `output_schema` constraint with the explicit `OUTPUT STRUCTURE EXAMPLE` in the prompt, you dramatically cut down on Pydantic `ValidationError` tracebacks and framework crashes.
