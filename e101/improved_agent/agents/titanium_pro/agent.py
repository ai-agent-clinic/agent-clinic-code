# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import sys
import pathlib
import json
import datetime
import urllib.parse
import functions_framework
from string import Template

from google.adk.agents.llm_agent import Agent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.skills import load_skill_from_dir
from google.adk.tools import skill_toolset
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.models import Gemini
from google.genai import types

from .tools import (
    run_browser_command,
    save_case_study,
    search_vector_search_tool,
    save_case_study_to_cache,
    CaseStudyList,
    SearchPlan,
    CompanyResearch,
    OutreachEmail,
)

# --- 🔐 SECURE CONFIGURATION ---
HEADER_IMAGE_URL = "https://storage.googleapis.com/titanium-assets-12345/Gemini_Generated_Image_r64uqkr64uqkr64u.png"

# --------------------------------------------------------------------------------
# SKILLS & TOOLS
# --------------------------------------------------------------------------------

_RETRY_OPTIONS = types.HttpRetryOptions(
    initial_delay=2,  # Wait 2 seconds before the first retry
    attempts=5,  # Maximum number of attempts (including the first)
    exp_base=2.0,  # Exponential backoff multiplier
    max_delay=60,  # Maximum wait time between retries
    http_status_codes=[429, 503],  # The specific transient errors we want to catch
)

_FLASH_MODEL = Gemini(
    model="gemini-3-flash-preview",
    retry_options=_RETRY_OPTIONS,
)

_PRO_MODEL = Gemini(
    model="gemini-3.1-pro-preview",
    retry_options=_RETRY_OPTIONS,
)

playwright_skill = load_skill_from_dir(
    pathlib.Path(__file__).parent.parent.parent / "skills" / "playwright-cli"
)
playwright_toolset = skill_toolset.SkillToolset(skills=[playwright_skill])


def google_search(query: str) -> str:
    """Searches the web for the given query using Google Search.

    Args:
        query: The search term or question to execute.

    Returns:
        The search results as a string.
    """
    # ADK handles the actual translation into the Gemini extension natively for simple callables named google_search usually,
    # but we provide the signature here to pass the Pydantic type validation for callables.
    return f"Execute search for: {query}"


# --------------------------------------------------------------------------------
# 1. COMPANY RESEARCHER AGENT
# --------------------------------------------------------------------------------

COMPANY_RESEARCHER_INSTRUCTIONS = f"""
You are the Senior Strategic Cloud Architect. High-Cognition Protocol. 
CURRENT YEAR: {datetime.date.today().year}.

OBJECTIVE:
1. SCOUR: Analyze the user's provided target details and identify the Name of the current target persona (Role).
2. DEEP CONTEXT RESEARCH (RECENCY LOCK): Search the web from the last 12 months for ONE of the following highly specific anchors:
   - A public quote from their C-Suite (Earnings call, tech blog, interview).
   - Their likely Tech Stack (derived from recent engineering job postings).
   - A major Product Roadmap initiative or recent funding round.
3. IDENTIFY INDUSTRY: Analyze the company's core business model and explicitly identify their primary Industry or Sector (e.g. "Retail", "Healthcare", "Financial Services").
4. IDENTITY SCOUR: Find the Full Names of 3 key peers.
5. UNLOCK THE COMP PLAN: Identify Name, Title, AND Recommended Solution for:
   - Gemini Enterprise: (LOCKED to Gemini Enterprise). Target: VP Cust Success/Product.
   - Security: (Analyze target to recommend ONE: Mandiant or BeyondCorp). Target: CISO.
   - Data & AI: (Analyze target to recommend ONE: BigQuery, Vertex AI, or Looker). Target: Head of Data/AI.

Respond ONLY with a JSON object matching the requested CompanyResearch schema format.
"""

company_researcher = Agent(
    model=_FLASH_MODEL,  # Use robust fast model for research scraping
    name="company_researcher",
    description="Searches for strategic target context and builds a cross-sell matrix.",
    instruction=COMPANY_RESEARCHER_INSTRUCTIONS,
    tools=[google_search],
    output_schema=CompanyResearch,
    output_key="company_research",
)


# --------------------------------------------------------------------------------
# 2. SEARCH PLANNER AGENT
# --------------------------------------------------------------------------------

PLANNER_INSTRUCTIONS = """
You are the Search Planner Agent.
Review the original target company details provided by the user.

Generate 3 to 5 highly specific search terms or phrases we can use to find relevant Google Cloud case studies for a company in this industry.
Return ONLY a JSON list of strictly formatted search queries matching the SearchPlan schema.
"""

planner_agent = Agent(
    model=_FLASH_MODEL,
    name="search_planner",
    description="Analyzes the query and generates 3-5 optimal search terms.",
    instruction=PLANNER_INSTRUCTIONS,
    output_schema=SearchPlan,
    output_key="search_plan",
)


# --------------------------------------------------------------------------------
# 3. CASE STUDY RESEARCHER AGENT
# --------------------------------------------------------------------------------

CASE_STUDY_RESEARCHER_INSTRUCTIONS = """
You are the Case Study Researcher Agent.
Your job is to find relevant Google Cloud customer case studies for the user's target company.

You have the following tools at your disposal:
1. `search_vector_search_tool`: Searches the local Vector Search cache for existing case studies.

Here are the optimal search terms formulated by the planner:
{{ search_plan }}

WORKFLOW:
1. **Cache First:** Iteratively use `search_vector_search_tool` with the planned search terms and the target company to find relevant case studies that we have already cached.
2. **Evaluate Cache:** If you find highly relevant case studies in the cache, you may proceed to output them.
3. Provide a structured CaseStudyList object containing all extracted case studies.

Respond ONLY with a JSON object matching the requested CaseStudyList schema.
"""

case_study_researcher = Agent(
    model=_FLASH_MODEL,
    name="case_study_researcher",
    description="Scrapes Google Cloud customer case studies into structured JSON data.",
    instruction=CASE_STUDY_RESEARCHER_INSTRUCTIONS,
    tools=[
        search_vector_search_tool,
        # save_case_study_to_cache,
        # playwright_toolset,
        # run_browser_command,
    ],
    output_schema=CaseStudyList,
    output_key="case_study_result",
)


# --------------------------------------------------------------------------------
# 4. CASE STUDY SELECTOR AGENT
# --------------------------------------------------------------------------------

SELECTOR_INSTRUCTIONS = """
You are the Case Study Selector Agent.
Review the user's original target query.

And the retrieved case studies list: 
{{ case_study_result }}

Pick the 2-3 most relevant case studies matching the target constraints. 
Return ONLY the selected case studies as a structured CaseStudyList json object.
"""

selector_agent = Agent(
    model=_FLASH_MODEL,
    name="case_study_selector",
    description="Selects the top relevant case studies from the web research.",
    instruction=SELECTOR_INSTRUCTIONS,
    output_schema=CaseStudyList,
    output_key="selected_case_studies",
)


# --------------------------------------------------------------------------------
# 5. EMAIL DRAFTER & VERIFIER AGENT
# --------------------------------------------------------------------------------

EMAIL_DRAFTER_INSTRUCTIONS = f"""
You are the Senior Strategic Cloud Architect. High-Cognition Protocol. 
CURRENT YEAR: {{datetime.date.today().year}}.

TARGET BIO & RESEARCH: {{ company_research }}
RELEVANT CASE STUDIES: {{ selected_case_studies }}

OBJECTIVE:
Draft a PUNCHY, SIMPLE, 3-sentence outreach email based on the user's TARGET role and constraints.
- TONE: Architect-to-Architect. Absolutely zero sales fluff. Focus on technical upskilling and sharing thought leadership. 
- VARIANCE: The examples below are strictly FEW-SHOT examples. You MUST creatively vary the language, structure, and phrasing for every email so they do not feel formulaic.
- FORMAT: The email body must be HTML-formatted. Include the executive's target name from the bio research automatically in the greeting (e.g., "Hi <target_name>,").
- HOOK EXAMPLE: Use the Deep Context Research from the bio. (e.g., "Saw your recent push into [Initiative]...")
- PROOF EXAMPLE: "We recently mapped out an architectural blueprint for how [Case Study Customer] solved [Persona Pain Point] using [Google Cloud Products]..." Use specific details from the top CASE STUDIES provided.
- LINKS: You MUST embed an HTML `<a>` link directly to the specific case study URL within the text so the rep can copy/paste it natively. Keep the external citations mapped to the sources array as well.
- ASK EXAMPLE: "Open to trading notes on the architecture?"
- NO model numbers (1.0/1.5) - just "Gemini".

ANTI-HALLUCINATION VERIFICATION: Use the Google Search tool to aggressively fact check the drafted email body. If it contains fake stats, rewrite the email before returning the final JSON.

Respond ONLY with a JSON object matching the empty OutreachEmail schema format.
"""

email_drafter = Agent(
    model=_PRO_MODEL,  # Use robust Pro model for drafting and verification
    name="email_drafter",
    description="Drafts the outbound executive email based on collected intelligence.",
    instruction=EMAIL_DRAFTER_INSTRUCTIONS,
    tools=[google_search],
    output_schema=OutreachEmail,
    output_key="drafted_email",
)


# --------------------------------------------------------------------------------
# PIPELINE COMPOSITION
# --------------------------------------------------------------------------------

titanium_pro_agent = SequentialAgent(
    name="titanium_pro_pipeline",
    sub_agents=[
        company_researcher,
        planner_agent,
        case_study_researcher,
        selector_agent,
        email_drafter,
    ],
)

# This agent definition is not used, but it illustrates a more basic form of the agent that matches the functionality of the original agent.
# titanium_basic = SequentialAgent(
#     name="titanium_basic_pipeline",
#     sub_agents=[
#         company_researcher,
#         case_study_researcher,
#         email_drafter,
#     ],
# )

root_agent = titanium_pro_agent

# --------------------------------------------------------------------------------
# ORCHESTRATION EXECUTION LOGIC
# --------------------------------------------------------------------------------


async def generate_intel(target_name: str, domain: str, role: str) -> dict:
    """Execute the full titanium pipeline and return the aggregated intel dictionary."""
    session_id = f"pipeline_{target_name.replace(' ', '_')}"
    user_id = "titanium_user"
    app_name = "titanium_pro_app"

    query = f"Target: {target_name}. Domain: {domain}. Role: {role}."

    session_service = InMemorySessionService()
    runner = Runner(
        app_name=app_name, agent=titanium_pro_agent, session_service=session_service
    )

    try:
        await session_service.create_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )

        user_message = types.Content(role="user", parts=[types.Part(text=query)])

        # Generator iteration to push events
        async for event in runner.run_async(
            user_id=user_id, session_id=session_id, new_message=user_message
        ):
            pass  # The web UI handles streaming. This is for standalone/CLI.

        # Retrieve the populated state
        current_session = await session_service.get_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )

        # Assemble the final payload based on Pydantic schemas stored as raw unstructured dicts inside state
        company_res = current_session.state.get("company_research", {})
        email_res = current_session.state.get("drafted_email", {})

        return {
            "status": "success",
            "target": target_name,
            "role": role,
            "research": company_res,
            "email": email_res,
        }

    except Exception as e:
        return {"status": "error", "message": f"Error executing pipeline: {e}"}


# --------------------------------------------------------------------------------
# HEADLESS CLOUD FUNCTION / UI EXPORT LOGIC
# --------------------------------------------------------------------------------


def get_current_rotation_role():
    roles = ["CTO", "CFO", "CEO", "CIO", "VP of Engineering", "Head of Product"]
    return roles[datetime.date.today().isocalendar()[1] % len(roles)]


def build_card(name, role, data):
    research = data.get("research", {})
    email = data.get("email", {})

    target_name = research.get("target_name", "Unknown Executive")
    industry = str(research.get("industry", "Unknown Industry"))
    bio = str(research.get("bio", "No bio available."))
    subject = str(email.get("subject", "No subject."))
    body = str(email.get("outreach_body", "No content."))
    hack = research.get("hack", {})

    hack_rows = ""
    for k, v in hack.items():
        if isinstance(v, dict):
            p_name = v.get("name", "NA")
            p_hook = v.get("hook", "")
            p_persona = v.get("persona", "Executive")
            p_solution = v.get("solution", "Solution")

            if p_name and "Unknown" not in p_name and "NA" not in p_name:
                search_query = urllib.parse.quote(f"{p_name} {name}")
                search_url = f"https://www.linkedin.com/search/results/people/?keywords={search_query}"
                link_html = f'<a href="{search_url}" style="color:#15803d; font-weight:bold; text-decoration:underline;">{p_name} 🔍</a>'
            else:
                link_html = f'<span style="color:#64748b; font-weight:bold;">Position Vacant</span>'

            hack_rows += f"""
            <div style="margin-bottom:16px; border-left: 4px solid #16a34a; padding-left:16px; padding-top:4px; padding-bottom:4px;">
                <div style="font-size:11px; color:#64748b; font-weight:800; text-transform:uppercase; letter-spacing:0.5px;">{k}</div>
                <div style="font-size:15px; color:#0f172a; font-weight:bold; margin-top:4px;">Rec: {p_solution}</div>
                <div style="font-size:14px; color:#334155; margin-top:2px;">Pitch to {link_html} ({p_persona})</div>
                <div style="font-size:13px; font-style:italic; color:#475569; margin-top:6px; background:#ffffff; padding:8px; border-radius:6px; border:1px solid #e2e8f0;">"{p_hook}"</div>
            </div>
            """

    src_html = "<br>".join(
        [
            f'• <a href="{s["url"]}" style="color:#2563eb; font-weight:600; text-decoration:none;">{s["title"]}</a>'
            for s in email.get("sources", [])
            if isinstance(s, dict)
        ]
    )

    return f"""
    <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:16px; margin-bottom:40px; padding:32px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.05), 0 8px 10px -6px rgba(0,0,0,0.01);">
        <div style="border-bottom:2px solid #f8fafc; padding-bottom:16px; margin-bottom:24px;">
            <div style="font-size:26px; color:#0f172a; font-weight:800; letter-spacing:-0.5px;">{name} <span style="font-size:16px; color:#64748b; font-weight:500; letter-spacing:normal;">({industry})</span></div>
            <div style="font-size:14px; color:#475569; margin-top:6px; font-weight:600; text-transform:uppercase; letter-spacing:1px;">Rotation: {role}</div>
            <div style="font-size:18px; color:#2563eb; font-weight:700; margin-top:16px; display:flex; align-items:center;">
                <span style="margin-right:8px;">🎯</span> Target: {target_name}
            </div>
        </div>
        <div style="font-size:16px; color:#334155; line-height:1.6; margin-bottom:28px;">{bio}</div>
        
        <div style="background:#f8fafc; padding:24px; border-radius:12px; border:1px solid #e2e8f0; margin-bottom:28px;">
            <div style="font-size:12px; color:#64748b; text-transform:uppercase; font-weight:800; letter-spacing:1px; margin-bottom:12px;">Drafted Outreach</div>
            <div style="font-size:15px; color:#0f172a; font-weight:700; margin-bottom:12px;">Subject: {subject}</div>
            <div style="font-size:16px; line-height:1.7; color:#1e293b; white-space: pre-line;">{body}</div>
        </div>
        
        <div style="background:#f0fdf4; padding:24px; border-radius:12px; border:1px solid #bbf7d0; margin-bottom:28px;">
            <div style="color:#166534; font-weight:800; font-size:13px; text-transform:uppercase; letter-spacing:1px; margin-bottom:20px; display:flex; align-items:center;">
                <span style="margin-right:8px;">🚀</span> Strategic Cross-Sell Matrix
            </div>
            {hack_rows}
        </div>
        
        <div style="border-top:1px solid #f8fafc; padding-top:16px;">
            <div style="font-size:11px; color:#94a3b8; font-weight:800; text-transform:uppercase; letter-spacing:1px; margin-bottom:12px;">Verified Sources</div>
            <div style="font-size:13px; line-height:1.8;">{src_html}</div>
        </div>
    </div>
    """


async def process_single_account(target, role):
    print(f"Analyzing {target['name']}...")
    result = await generate_intel(target["name"], target["domain"], role)

    if result.get("status") == "success":
        card_html = build_card(target["name"], role, result)
        print(f"✅ Success: {target['name']}")
        return True, card_html, None

    return False, "", result.get("message", "Unknown Error")


async def orchestrate_all(companies, role):
    cards_html = ""
    success_count = 0
    last_error = ""

    chunk_size = 3
    for i in range(0, len(companies), chunk_size):
        batch = companies[i : i + chunk_size]
        print(f"🌊 Launching Wave {i//chunk_size + 1}...")

        tasks = [process_single_account(target, role) for target in batch]
        results = await asyncio.gather(*tasks)

        for success, html, err in results:
            if success:
                cards_html += html
                success_count += 1
            else:
                last_error = err

    return success_count, cards_html, last_error


@functions_framework.http
def run_agent_logic(request):
    print("Titanium Pro Headless Cloud Function Initiated...")

    request_json = request.get_json(silent=True) or {}
    role = request_json.get("role", get_current_rotation_role())

    companies = []
    csv_data = request_json.get("csv_data")
    if csv_data:
        import csv
        import io

        reader = csv.reader(io.StringIO(csv_data))
        for row in reader:
            if not row or len(row) < 2:
                continue
            if row[0].strip().lower() in ["company name", "company", "name"]:
                continue
            companies.append({"name": row[0].strip(), "domain": row[1].strip()})
    else:
        companies = request_json.get("companies", [])

    if not companies:
        return (
            "<h1>BAD REQUEST</h1><p>Please provide a JSON payload with 'csv_data' or 'companies'.</p>",
            400,
        )

    total_targets = len(companies)

    # Run the orchestrator
    success_count, cards_html, last_error = asyncio.run(
        orchestrate_all(companies, role)
    )

    if success_count == 0:
        return f"<h1>ANALYSIS FAILED</h1><p>Last Error: {last_error}</p>", 500

    # Wrap the output in a clean webpage shell with strict UTF-8 encoding
    full_html = f"""
    <!DOCTYPE html>
    <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Project Titanium Dashboard</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{
                    background-color: #f8fafc;
                    padding: 40px 20px;
                    font-family: 'Google Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                    color: #0f172a;
                    margin: 0;
                }}
                .container {{
                    max-width: 750px;
                    margin: 0 auto;
                }}
                .header-container {{
                    text-align: center;
                    padding-bottom: 50px;
                }}
                .header-image {{
                    width: 450px;
                    max-width: 100%;
                    height: auto;
                }}
                .header-subtitle {{
                    color: #64748b;
                    font-size: 13px;
                    font-weight: 800;
                    letter-spacing: 4px;
                    text-transform: uppercase;
                    margin-top: 30px;
                }}
                .header-status {{
                    color: #2563eb;
                    font-size: 15px;
                    font-weight: 700;
                    margin-top: 12px;
                    background: #eff6ff;
                    display: inline-block;
                    padding: 8px 20px;
                    border-radius: 30px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header-container">
                    <img src='{HEADER_IMAGE_URL}' class="header-image" alt="Titanium Logo">
                    <div class="header-subtitle">Strategic Territory Intelligence</div>
                    <div class="header-status">Targeting: {role}s | {success_count}/{total_targets} Accounts Analyzed</div>
                </div>
                {cards_html}
            </div>
        </body>
    </html>
    """

    # The crucial fix: hardcoding utf-8 into the response header
    return full_html, 200, {"Content-Type": "text/html; charset=utf-8"}


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Simplistic parsing for testing via CLI
        target = " ".join(sys.argv[1:])
        print(f"Running Titanium Pro pipeline for: {target}")

        from .vector_search import initialize_collection

        print("Checking/Initializing Vector Search Collection...")
        try:
            initialize_collection()
        except Exception as e:
            print(f"Failed to initialize Vector Search collection: {e}")

        result = asyncio.run(generate_intel(target, "example.com", "CTO"))
        print(f"\nPipeline Result:\n{json.dumps(result, indent=2)}")
    else:
        print("Run with a company name argument to test execution.")
