# Titanium Pro: Bulk Case Study Crawler

To massively hydrate the Vector Search V2 caching collection beyond organic application interactions, this project includes standalone utilities capable of mining the entirety of Google Cloud case studies.

## Architecture

The system is designed with safety and thoroughness in mind and operates natively in two distinct CLI phases via `scripts/bulk_case_study_crawler.py`:

### Phase 1: Deterministic URL Discovery
Automates a headless Chromium browser instance using Playwright to evaluate and navigate `https://cloud.google.com/customers`. 
- Iteratively executes `Clear all` filters to unlock the entire unconstrained corpus.
- Automatically clicks `Show more` to exhaust all pagination permutations (discovering over 1,600 case studies).
- Isolates internal editorial studies matching `cloud.google.com/customers/.*` regex to inherently skip YouTube / Medium out-link redirects.
- Saves the results locally to `data/case_study_urls.txt`.

### Phase 2: AI-Assisted Pydantic Extraction
Consumes the URL catalog to scrape the dynamic HTML payload and map it programmatically. 
- Leverages Gemini (`gemini-2.5-flash`) to synthesize the editorial context into a highly-readable Markdown structure.
- Generates the exact `CaseStudy` Pydantic class format utilized by Titanium Pro originally.
- Provides a dual-layered backup: It dumps the parsed `.json` structures definitively onto the local disk (`data/extracted_case_studies/`) whilst continuously batching them natively into Google Cloud Vector Search.

## Execution

You can run these scripts directly via `uv`:

```bash
# Run URL Discovery
uv run --env-file .env python -m improved_agent.scripts.bulk_case_study_crawler --phase 1

# Run AI Extraction & Caching
uv run --env-file .env python -m improved_agent.scripts.bulk_case_study_crawler --phase 2
```

We also included convenience targets in the root `Makefile`:
```bash
make run-crawler-phase-1
make run-crawler-phase-2
make run-crawler-all
```

---

# Vector Search Export & Operations Tool

To safeguard API extraction costs and ensure zero data loss from the crawler, we supercharged the caching script (`scripts/manage_vector_search.py`) with an `export` capability. 

This command operates via an advanced `BatchSearchDataObjectsRequest` on Vector Search. It executes an open-ended generic text match alongside massive retrieval thresholds (`top_k=2000`) and explicit field scanning attributes (`data_field_names=["company", "content", "industry"]`). 

Running this utility guarantees all populated and embedded artifacts from the Cloud backend are safely extracted and serialized linearly.

## Commands

```bash
# Export the entire database to JSON Lines format (saved by default to data/exported_case_studies.jsonl)
uv run --env-file .env python -m improved_agent.scripts.manage_vector_search export

# Create / Init the Vector Search collection
uv run --env-file .env python -m improved_agent.scripts.manage_vector_search init

# Run a test hybrid-search query against the collection
uv run --env-file .env python -m improved_agent.scripts.manage_vector_search query --query "Kubernetes"

# Delete the target collection completely
uv run --env-file .env python -m improved_agent.scripts.manage_vector_search delete
```
