import argparse
import json
import os
import subprocess
import time
import urllib.request

from google import genai

from improved_agent.agents.titanium_pro.tools import CaseStudy
from improved_agent.agents.titanium_pro.vector_search import insert_case_study_into_cache

URLS_FILE = "data/case_study_urls.txt"
SESSION_ID = "crawler_session"


def run_pw(cmd: list):
    """Utility variable to execute playwright-cli commands."""
    return subprocess.run(["playwright-cli"] + cmd, capture_output=True, text=True)


def phase1_discover_urls():
    print("Starting Phase 1: URL Discovery...")
    os.makedirs("data", exist_ok=True)

    print("Cleaning up stale browser sessions...")
    run_pw(["-s=" + SESSION_ID, "close-all"])

    print("Opening browser to Google Cloud Customers portal...")
    run_pw(["-s=" + SESSION_ID, "open"])
    run_pw(["-s=" + SESSION_ID, "goto", "https://cloud.google.com/customers"])

    # Wait for initial data hydration
    time.sleep(3)

    print("Clearing any pre-selected filters (e.g., AI/ML)...")
    eval_clear_filters = """
    () => {
        const btns = Array.from(document.querySelectorAll('button'));
        const clearBtn = btns.find(b => b.innerText.trim() === 'Clear all' && b.offsetParent !== null && !b.disabled);
        if (clearBtn) {
            clearBtn.click();
            return 'cleared';
        }
        return 'no-filters';
    }
    """
    res = run_pw(["-s=" + SESSION_ID, "eval", eval_clear_filters])
    if "cleared" in res.stdout:
        print("Filters cleared successfully. Waiting for UI to refresh...")
        time.sleep(3)
    else:
        print("No active filters to clear.")

    print("Paginating through 'Show more' dynamically...")
    click_count = 0
    # Add a high limit to avoid true infinite loops but ensure we capture everything
    MAX_CLICKS = 300 
    
    while click_count < MAX_CLICKS:
        eval_check_and_click = """
        () => {
            let btns = Array.from(document.querySelectorAll('button'));
            let showMore = btns.find(b => b.innerText.includes('Show more') && b.offsetParent !== null && !b.disabled);
            if(showMore) {
                showMore.click();
                return 'clicked';
            }
            return 'no-more-buttons';
        }
        """
        res = run_pw(["-s=" + SESSION_ID, "eval", eval_check_and_click])
        if "clicked" in res.stdout:
            click_count += 1
            print(f"Clicked 'Show more' button (Iteration {click_count})...")
            time.sleep(2)
        else:
            print("No more visible 'Show more' buttons found. Pagination complete.")
            break

    print("Extracting canonical Case Study URLs...")
    eval_extract = """
    () => {
        const links = Array.from(document.querySelectorAll("a"));
        const urls = new Set();
        for (let link of links) {
            let href = link.href || "";
            if (href.includes("/customers/") && href.length > "https://cloud.google.com/customers/".length) {
                urls.add(href);
            }
        }
        return JSON.stringify(Array.from(urls));
    }
    """
    res = run_pw(["-s=" + SESSION_ID, "eval", eval_extract])
    
    import re
    # The output from playwright-cli is wrapped in markdown formatting ('### Result', '### Ran Playwright code', etc.).
    # We use a robust regex over the raw stdout to extract the URLs safely regardless of shell rendering.
    urls = list(set(re.findall(r'https://cloud\.google\.com[/a-zA-Z0-9_\-\.\?\=\&]*customers/[a-zA-Z0-9_\-\.\?\=\&]+', res.stdout)))

    if not urls:
        print("Warning: No URLs were extracted. Is the page layout correctly targeted?")

    valid_urls = sorted(set([u for u in urls if u.startswith("http")]))
    with open(URLS_FILE, "w") as f:
        for url in valid_urls:
            f.write(f"{url}\n")

    print(f"Phase 1 complete. Found {len(valid_urls)} unique case study URLs. Saved to {URLS_FILE}.")
    run_pw(["-s=" + SESSION_ID, "close-all"])


def fetch_html(url: str) -> str:
    """Fetch raw HTML natively using urllib to avoid heavy playwright sessions in Phase 2."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode("utf-8")
    except Exception as e:
        print(f"Error HTTP fetching {url}: {e}")
        return ""


def phase2_extract_and_cache():
    print("\nStarting Phase 2: AI-Assisted Content Extraction & Caching...")
    if not os.path.exists(URLS_FILE):
        print(f"Error: {URLS_FILE} not found. You must run Phase 1 first.")
        return

    with open(URLS_FILE, "r") as f:
        urls = [line.strip() for line in f if line.strip()]

    print(f"Loaded {len(urls)} URLs for processing.")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable is missing.")
        return

    client = genai.Client(api_key=api_key)
    # Using flash as it is the fastest, cheapest, and fully capable of standard markdown structured generation
    model_name = "gemini-2.5-flash"

    # Iterate over all discovered URLs
    for i, url in enumerate(urls):
        print(f"[{i+1}/{len(urls)}] Processing: {url}")
        
        try:
            html_content = fetch_html(url)
            if not html_content:
                continue

            # We truncate the HTML payload to 70k chars to maintain efficiency and stay under bounds
            prompt = f"""
            You are an expert data extractor. Extract the details of the customer case study from the following raw HTML payload.
            
            IMPORTANT RULES:
            - Focus exclusively on the main editorial content, article narrative, and the company overview.
            - Ignore global navigation HTML, footers, ad-banners, and generic boilerplate.
            - Translate the core HTML layout into high-quality, readable Markdown format for the 'extracted_contents' field.
            - Ensure 'products' captures the specific Google Cloud resources referenced.
            
            URL Context: {url}
            
            HTML Content:
            {html_content[:70000]}
            """

            # Note: We reuse the identical CaseStudy Pydantic model found in tools.py!
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=CaseStudy, 
                    temperature=0.1,
                ),
            )

            case_study_data = json.loads(response.text)

            # --- Local Disk Caching ---
            try:
                import os
                customer_name_clean = case_study_data.get("customer_name", "unknown_customer")
                # Sanitize filename
                customer_name_clean = "".join([c for c in customer_name_clean if c.isalpha() or c.isdigit() or c==' ']).rstrip().replace(" ", "_").lower()
                cache_dir = "data/extracted_case_studies"
                os.makedirs(cache_dir, exist_ok=True)
                cache_file = os.path.join(cache_dir, f"{customer_name_clean}.json")
                with open(cache_file, "w") as f:
                    json.dump(case_study_data, f, indent=2)
            except Exception as e:
                print(f"  -> Warning: Failed to save to local disk cache for {url}: {e}")

            # Route parsed Pydantic-compliant dictionary fields directly into the existing caching method
            insert_case_study_into_cache(
                source_url=case_study_data.get("source_url", url),
                company=case_study_data.get("customer_name", "Unknown Customer"),
                content=case_study_data.get("extracted_contents", ""),
                industry=case_study_data.get("industry", "Unknown"),
                products_used=", ".join(case_study_data.get("products", [])),
                metrics=case_study_data.get("summary", ""), # the Vector Search schema uses 'metrics' for summarization fields
            )
            print(f"  -> Successfully vectorized: {case_study_data.get('customer_name')}")

        except Exception as e:
            print(f"  -> Failed extraction/insertion for {url}: {e}")

    print("Phase 2 complete. The Vector Search Cache has been bulk hydrated!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Titanium Pro: Bulk Case Study Crawler")
    parser.add_argument("--phase", choices=["1", "2", "all"], default="all", help="Which execution phase to run.")
    args = parser.parse_args()

    if args.phase in ["1", "all"]:
        phase1_discover_urls()
    if args.phase in ["2", "all"]:
        phase2_extract_and_cache()
