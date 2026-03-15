import functions_framework
import asyncio
from google import genai
from google.genai import types
import json, datetime, urllib.parse, os, re, logging
from dotenv import load_dotenv

load_dotenv()

# --- 🔐 SECURE CONFIGURATION ---
API_KEY = str(os.environ.get("GEMINI_API_KEY", "")).strip()
MODEL_ID = 'gemini-3.1-pro-preview' 
HEADER_IMAGE_URL = "https://storage.googleapis.com/titanium-assets-12345/Gemini_Generated_Image_r64uqkr64uqkr64u.png"


# --- 🎯 STRATEGIC ACCOUNTS ---
TARGET_COMPANIES = [
    {"name": "Johnson & Johnson", "domain": "jnj.com", "industry": "Healthcare"},
    {"name": "Procter & Gamble", "domain": "pg.com", "industry": "Consumer Goods"},
    {"name": "Exxon Mobil", "domain": "exxonmobil.com", "industry": "Energy"}
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TitaniumAgent")

def get_current_rotation_role():
    roles = ["CTO", "CFO", "CEO", "CIO", "VP of Engineering", "Head of Product"]
    return roles[datetime.date.today().isocalendar()[1] % len(roles)]

async def verify_intel(client, target, data):
    if "error" in data: return data
    
    prompt = f"""
    SYSTEM: Chief Intelligence Auditor & Fact Checker.
    TARGET: {target['name']} ({target['industry']})
    DATA TO AUDIT: {json.dumps(data)}
    
    OBJECTIVE:
    1. VERIFY IDENTITY: Use Google Search to confirm if "{data.get('target_name')}" is actually the executive at {target['name']}. If not, FIND THE REAL ONE.
    2. THE "RECEIPTS" RULE (ANTI-HALLUCINATION): You must use Google Search to aggressively fact-check the "outreach_body". 
       - If the draft claims a specific quote, roadmap initiative, or tech-stack detail about {target['name']}, VERIFY IT online. 
       - IF YOU CANNOT VERIFY IT, rewrite the email body to remove the hallucination and use a safe, universally true technical friction point instead.
    3. EMAIL TONE CHECK: 
       - Ensure the email body is PUNCHY and SIMPLE (3-4 sentences max). Focus strictly on thought leadership and technical upskilling. No sales fluff.
       - NO model numbers (e.g., "Gemini 1.5"). Use "Gemini" instead.
    
    OUTPUT: Return the CLEANED, VERIFIED, and FACTUAL JSON object.
    """
    try:
        response = await client.aio.models.generate_content(
            model=MODEL_ID, contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.0 
            )
        )
        
        safe_text = response.text if response.text else ""
        match = re.search(r'```json\s*(\{.*?\})\s*```', safe_text, re.DOTALL)
        if not match: match = re.search(r'(\{.*?\})', safe_text, re.DOTALL)
        
        if match: 
            return json.loads(match.group(1))
        else:
            return data
    except Exception as e:
        logger.warning(f"Auditor failed for {target['name']}: {e}")
        return data

async def generate_intel(client, target, role):
    current_year = datetime.date.today().year
    prompt = f"""
    SYSTEM: Senior Strategic Cloud Architect. High-Cognition Protocol. CURRENT YEAR: {current_year}.
    TARGET: {target['name']} ({target['industry']}) | WEBSITE: {target['domain']} | ROLE: {role}.
    VAULT: {CASE_STUDIES}

    OBJECTIVE:
    1. SCOUR: Analyze {target['name']}'s technical focus and identify the Name of the current {role}.
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

    CRITICAL FORMATTING: Return ONLY valid JSON. Start with ```json and end with ```.
    OUTPUT STRUCTURE:
    ```json
    {{ 
      "target_name": "Full Name of the Executive",
      "bio": "Strategic snapshot including the specific quote, tech stack, or roadmap finding...",
      "subject": "Professional subject line...",
      "outreach_body": "Hi [Name], [Body of email]...",
      "hack": {{ 
        "Gemini Enterprise": {{ "name": "Name", "persona": "Title", "solution": "Gemini Enterprise", "hook": "..." }}, 
        "Security": {{ "name": "Name", "persona": "Title", "solution": "Specific Product", "hook": "..." }}, 
        "Data & AI": {{ "name": "Name", "persona": "Title", "solution": "Specific Product", "hook": "..." }} 
      }}, 
      "sources": [{{ "title": "...", "url": "..." }}] 
    }}
    ```
    """
    last_exception = None
    for attempt in range(5): 
        try:
            response = await client.aio.models.generate_content(
                model=MODEL_ID, contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())], 
                    temperature=0.2
                )
            )
            
            safe_text = response.text if response.text else ""
            match = re.search(r'```json\s*(\{.*?\})\s*```', safe_text, re.DOTALL)
            if not match: match = re.search(r'(\{.*?\})', safe_text, re.DOTALL)
            
            if match: return json.loads(match.group(1))
            else:
                logger.warning(f"Attempt {attempt+1}: No JSON found or Empty Response. Retrying...")
                await asyncio.sleep(2)
        except Exception as e:
            last_exception = e
            error_str = str(e)
            wait_time = (2 ** attempt) * 5
            
            if "503" in error_str or "429" in error_str:
                logger.warning(f"Server Busy/Quota (Attempt {attempt+1}/5). Sleeping {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                logger.warning(f"Attempt {attempt+1} Error: {e}")
                await asyncio.sleep(2)
                
    return {"error": f"Failed after 5 attempts. Last error: {last_exception}"}

def build_card(name, industry, role, data):
    target_name = data.get("target_name", "Unknown Executive")
    bio = str(data.get("bio", "No bio available."))
    subject = str(data.get("subject", "No subject."))
    body = str(data.get("outreach_body", "No content."))
    hack = data.get("hack", {})
    
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

    src_html = "<br>".join([f'• <a href="{s["url"]}" style="color:#2563eb; font-weight:600; text-decoration:none;">{s["title"]}</a>' for s in data.get("sources", []) if isinstance(s, dict)])
    
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

async def process_single_account(client, target, role):
    logger.info(f"Analyzing {target['name']}...")
    data = await generate_intel(client, target, role)
    
    if data and "error" not in data:
        logger.info(f"🕵️ Verifying Intel for {target['name']}...")
        data = await verify_intel(client, target, data)
        
        if data and "error" not in data:
            card_html = build_card(target['name'], target['industry'], role, data)
            logger.info(f"✅ Success: {target['name']}")
            return True, card_html, None
        else:
            return False, "", data.get("error", "Verification Failed")
    elif data and "error" in data:
        return False, "", data["error"]
        
    return False, "", "Unknown Error"

async def orchestrate_all(client, role):
    cards_html = ""
    success_count = 0
    last_error = ""
    
    chunk_size = 3
    for i in range(0, len(TARGET_COMPANIES), chunk_size):
        batch = TARGET_COMPANIES[i:i + chunk_size]
        logger.info(f"🌊 Launching Wave {i//chunk_size + 1}...")
        
        tasks = [process_single_account(client, target, role) for target in batch]
        results = await asyncio.gather(*tasks)
        
        for success, html, err in results:
            if success:
                cards_html += html
                success_count += 1
            else:
                last_error = err
        
        if i + chunk_size < len(TARGET_COMPANIES):
            logger.info("⏳ Wave complete. Cooling down API for 60 seconds to bypass Quota Wall...")
            await asyncio.sleep(60)
            
    return success_count, cards_html, last_error

@functions_framework.http
def run_agent_logic(request):
    logger.info("Titanium 7.1 (UI Polish) Initiated...")
    if not API_KEY: 
        return "<h1>ERROR: API Key Missing.</h1>", 400
    
    client = genai.Client(api_key=API_KEY)
    role = get_current_rotation_role()
    total_targets = len(TARGET_COMPANIES)
    
    # Run the orchestrator
    success_count, cards_html, last_error = asyncio.run(orchestrate_all(client, role))
        
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
    return full_html, 200, {'Content-Type': 'text/html; charset=utf-8'}