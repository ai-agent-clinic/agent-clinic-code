import datetime
import json
import urllib.parse
from string import Template

from google.adk.agents.llm_agent import Agent
from google.adk.models import Gemini
from google.genai import types

from .tools import OutreachEmailList, google_search

# --- 🔐 SECURE CONFIGURATION ---
HEADER_IMAGE_URL = "https://storage.googleapis.com/titanium-assets-12345/Gemini_Generated_Image_r64uqkr64uqkr64u.png"

# --- 🎯 STRATEGIC ACCOUNTS ---
TARGET_COMPANIES = [
    {"name": "Ford", "domain": "ford.com", "industry": "Automotive"},
    # {"name": "Johnson & Johnson", "domain": "jnj.com", "industry": "Healthcare"},
    # {"name": "Procter & Gamble", "domain": "pg.com", "industry": "Consumer Goods"},
    # {"name": "Exxon Mobil", "domain": "exxonmobil.com", "industry": "Energy"}
]

# --- 🏆 THE MEGA-VAULT 6.0 (Expanded & Deep) ---
CASE_STUDIES = """
[PRODUCTIVITY - GEMINI ENTERPRISE]
- "Kärcher: 90% reduction in drafting time for 13k users via Gemini Agents."
- "Mercari: 500% ROI and 20% workload reduction for support reps via Gemini support agents."
- "Rivian: Accelerates technical research by 40% via Gemini + NotebookLM."
- "Bayer: 700+ custom Gemini agents deployed to 100k employees, saving 30% time on complex querying."
- "Bristol Myers Squibb: Accelerated clinical trial documentation by 60% using Gemini for Workspace."
[GEN AI & INFRASTRUCTURE]
- "Character.ai: Trained foundational LLMs 30% faster on TPU v5p vs AWS for 20M+ users."
- "AssemblyAI: Achieved 4.2x price-performance for LLM inference on TPU v5p."
- "Cohere: 50% better cost-efficiency than H100s for inference via AI Hypercomputer."
- "Hugging Face: 2x faster training times on Cloud TPU v5e for open models."
- "Midjourney: Scaling to 10M+ users on Google Cloud GPUs with zero downtime events."
[DATA & SCALE]
- "Snap Inc: 20% unit economic win on GKE for 5B daily multimodal snaps."
- "Spotify: Processes 10PB of data daily; eliminated 15 hours of manual ops weekly."
- "The Home Depot: Unified 17 silos on BigQuery; reduced query times from 4 days to 4 minutes."
- "Walmart: Optimized inventory for 10,000 stores using BigQuery + Vertex AI Forecasting."
- "Twitter/X: Migrated 300PB Hadoop clusters to GCS/BigQuery for real-time analytics."
[SECURITY]
- "Mandiant/SCC: Blocked 100% of major DDoS bursts via global Threat Intelligence."
- "Yahoo: Zero Trust (BeyondCorp) for 10k employees; zero legacy VPN dependency."
- "Broadcom: Reduced security incident response time by 50% using Chronicle Security Operations."
"""


def get_current_rotation_role():
    roles = ["CTO", "CFO", "CEO", "CIO", "VP of Engineering", "Head of Product"]
    return roles[datetime.date.today().isocalendar()[1] % len(roles)]


_ROBUST_PRO_MODEL = Gemini(
    model="gemini-3.1-pro-preview",
    retry_options=types.HttpRetryOptions(
        initial_delay=2,
        attempts=5,
        exp_base=2.0,
        max_delay=60,
        http_status_codes=[429, 503],
    ),
)


MONOLITHIC_INSTRUCTIONS = f"""
SYSTEM: Senior Strategic Cloud Architect. High-Cognition Protocol. CURRENT YEAR: {datetime.date.today().year}.
VAULT: {CASE_STUDIES}

We are targeting the following companies today:
{json.dumps(TARGET_COMPANIES, indent=2)}

We are targeting the following rotation role for ALL of them:
{get_current_rotation_role()}

OBJECTIVE:
For EACH of the target companies, you must:
1. SCOUR: Analyze the target's technical focus and identify the Name of the current {get_current_rotation_role()}.
2. DEEP CONTEXT RESEARCH (RECENCY LOCK): Search the web from the last 12 months for ONE of the following highly specific anchors:
   - A public quote from their C-Suite (Earnings call, tech blog, interview).
   - Their likely Tech Stack (derived from recent engineering job postings).
   - A major Product Roadmap initiative or recent funding round.
3. IDENTITY SCOUR: Find the Full Names of 3 key peers.
4. UNLOCK THE COMP PLAN: Identify Name, Title, AND Recommended Solution for:
   - Gemini Enterprise: (LOCKED to Gemini Enterprise). Target: VP Cust Success/Product.
   - Security: (Analyze target to recommend ONE: Mandiant or BeyondCorp). Target: CISO.
   - Data & AI: (Analyze target to recommend ONE: BigQuery, Vertex AI, or Looker). Target: Head of Data/AI.
5. OUTREACH (THOUGHT LEADERSHIP): Draft a PUNCHY, SIMPLE, 3-sentence email.
   - TONE: Architect-to-Architect. Absolutely zero sales fluff. Focus on technical upskilling and sharing thought leadership. 
   - HOOK: Use the Deep Context Research. (e.g., "Saw your recent push into [Initiative]..." or "Read [CEO]'s note on scaling your data infra...")
   - PROOF: "We recently mapped out an architectural blueprint for how [Vault Case] solved [Persona Pain Point]..."
   - ASK: "Open to trading notes on the architecture?"
   - NO "I hope this finds you well". NO model numbers (1.0/1.5).

6. THE "RECEIPTS" RULE (ANTI-HALLUCINATION): You must use the `google_search` tool to aggressively fact-check the outreach body. 
   - If the draft claims a specific quote, roadmap initiative, or tech-stack detail about the company, VERIFY IT online. 
   - IF YOU CANNOT VERIFY IT, rewrite the email body to remove the hallucination and use a safe, universally true technical friction point instead.
7. EMAIL TONE CHECK: 
   - Ensure the email body is PUNCHY and SIMPLE (3-4 sentences max).

RETURN FORMAT:
Provide the final output exclusively as a structured list of accounts and their mapped intel matching the provided Pydantic schema OutreachEmailList.

OUTPUT STRUCTURE EXAMPLE:
```json
{{
  "accounts": [
    {{
      "account_name": "Company Name",
      "outreach": {{
        "target_name": "Full Name of the Executive",
        "bio": "Strategic snapshot finding...",
        "subject": "Professional subject line...",
        "outreach_body": "Hi [Name], [Body]...",
        "hack": {{
            "gemini_enterprise": {{ "name": "Name", "persona": "Role", "solution": "Gemini Enterprise", "hook": "..." }},
            "security": {{ "name": "Name", "persona": "Role", "solution": "Mandiant", "hook": "..." }},
            "data_ai": {{ "name": "Name", "persona": "Role", "solution": "BigQuery", "hook": "..." }}
        }},
        "sources": [ {{ "title": "...", "url": "..." }} ]
      }}
    }}
  ]
}}
```
"""


titanium_v1_agent = Agent(
    model=_ROBUST_PRO_MODEL,
    name="titanium_v1",
    description="Analyzes multiple strategic accounts and drafts outbound outreach, all inside a single structured prompt.",
    instruction=MONOLITHIC_INSTRUCTIONS,
    tools=[google_search],
    output_schema=OutreachEmailList,
    output_key="company_outreaches",
)

root_agent = titanium_v1_agent

# UI Export logic to render ADK dashboard


def build_card(name, industry, role, email_data):
    target_name = email_data.target_name
    bio = email_data.bio
    subject = email_data.subject
    body = email_data.outreach_body
    hack = email_data.hack

    hack_rows = ""
    hack_map = {
        {
            "Gemini Enterprise": hack.gemini_enterprise,
            "Security": hack.security,
            "Data & AI": hack.data_ai,
        }
    }

    for k, v in hack_map.items():
        if v:
            p_name = v.name
            p_hook = v.hook
            p_persona = v.persona
            p_solution = v.solution

            if p_name and "Unknown" not in p_name and "NA" not in p_name:
                search_query = urllib.parse.quote(f"{{p_name}} {{name}}")
                search_url = f"https://www.linkedin.com/search/results/people/?keywords={{search_query}}"
                link_html = f'<a href="{{search_url}}" style="color:#15803d; font-weight:bold; text-decoration:underline;">{{p_name}} 🔍</a>'
            else:
                link_html = f'<span style="color:#64748b; font-weight:bold;">Position Vacant</span>'

            hack_rows += f"""
            <div style="margin-bottom:16px; border-left: 4px solid #16a34a; padding-left:16px; padding-top:4px; padding-bottom:4px;">
                <div style="font-size:11px; color:#64748b; font-weight:800; text-transform:uppercase; letter-spacing:0.5px;">{{k}}</div>
                <div style="font-size:15px; color:#0f172a; font-weight:bold; margin-top:4px;">Rec: {{p_solution}}</div>
                <div style="font-size:14px; color:#334155; margin-top:2px;">Pitch to {{link_html}} ({{p_persona}})</div>
                <div style="font-size:13px; font-style:italic; color:#475569; margin-top:6px; background:#ffffff; padding:8px; border-radius:6px; border:1px solid #e2e8f0;">"{{p_hook}}"</div>
            </div>
            """

    src_html = "<br>".join(
        [
            f'• <a href="{{s.url}}" style="color:#2563eb; font-weight:600; text-decoration:none;">{{s.title}}</a>'
            for s in email_data.sources
        ]
    )

    return f"""
    <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:16px; margin-bottom:40px; padding:32px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.05), 0 8px 10px -6px rgba(0,0,0,0.01);">
        <div style="border-bottom:2px solid #f8fafc; padding-bottom:16px; margin-bottom:24px;">
            <div style="font-size:26px; color:#0f172a; font-weight:800; letter-spacing:-0.5px;">{{name}} <span style="font-size:16px; color:#64748b; font-weight:500; letter-spacing:normal;">({{industry}})</span></div>
            <div style="font-size:14px; color:#475569; margin-top:6px; font-weight:600; text-transform:uppercase; letter-spacing:1px;">Rotation: {{role}}</div>
            <div style="font-size:18px; color:#2563eb; font-weight:700; margin-top:16px; display:flex; align-items:center;">
                <span style="margin-right:8px;">🎯</span> Target: {{target_name}}
            </div>
        </div>
        <div style="font-size:16px; color:#334155; line-height:1.6; margin-bottom:28px;">{{bio}}</div>
        
        <div style="background:#f8fafc; padding:24px; border-radius:12px; border:1px solid #e2e8f0; margin-bottom:28px;">
            <div style="font-size:12px; color:#64748b; text-transform:uppercase; font-weight:800; letter-spacing:1px; margin-bottom:12px;">Drafted Outreach</div>
            <div style="font-size:15px; color:#0f172a; font-weight:700; margin-bottom:12px;">Subject: {{subject}}</div>
            <div style="font-size:16px; line-height:1.7; color:#1e293b; white-space: pre-line;">{{body}}</div>
        </div>
        
        <div style="background:#f0fdf4; padding:24px; border-radius:12px; border:1px solid #bbf7d0; margin-bottom:28px;">
            <div style="color:#166534; font-weight:800; font-size:13px; text-transform:uppercase; letter-spacing:1px; margin-bottom:20px; display:flex; align-items:center;">
                <span style="margin-right:8px;">🚀</span> Strategic Cross-Sell Matrix
            </div>
            {{hack_rows}}
        </div>
        
        <div style="border-top:1px solid #f8fafc; padding-top:16px;">
            <div style="font-size:11px; color:#94a3b8; font-weight:800; text-transform:uppercase; letter-spacing:1px; margin-bottom:12px;">Verified Sources</div>
            <div style="font-size:13px; line-height:1.8;">{{src_html}}</div>
        </div>
    </div>
    """


def render_html_dashboard(outreaches_list, role):
    cards_html = ""
    company_map = {{c["name"]: c for c in TARGET_COMPANIES}}

    for account_data in outreaches_list.accounts:
        target_name = account_data.account_name
        email_info = account_data.outreach
        industry = company_map.get(target_name, {{}}).get("industry", "Unknown")
        cards_html += build_card(target_name, industry, role, email_info)

    total_targets = len(TARGET_COMPANIES)
    success_count = len(outreaches_list.accounts)

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
                    <img src='{{HEADER_IMAGE_URL}}' class="header-image" alt="Titanium Logo">
                    <div class="header-subtitle">Strategic Territory Intelligence</div>
                    <div class="header-status">Targeting: {{role}}s | {{success_count}}/{{total_targets}} Accounts Analyzed</div>
                </div>
                {{cards_html}}
            </div>
        </body>
    </html>
    """

    return full_html
