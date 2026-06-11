# Project Guidelines & Collaboration Best Practices

This document records project-specific preferences and core architecture configurations for the **Playback IQ** workspace to ensure absolute consistency and precision across future coding sessions.

---

## 1. Git Workflow & Branching Strategy

To prevent premature integration and preserve testing boundaries:
* **Feature Branches First**: All active development, testing, and cloud infrastructure modifications must be executed and validated strictly on dedicated feature branches (e.g., `gcloud-integration`).
* **Zero Automatic Merges**: Merging into the `main` branch is **strictly forbidden** unless explicitly and unambiguously requested by Luis. 
* **Commit Frequency**: Code checkpoints should be made as logical, atomic micro-commits, grouped by distinct solutions (e.g., infrastructure variables, core application code, documentation).
* **Commit Message Conventions**: Standard semantic commit prefixes are used:
  * `feat:` for new capabilities or infrastructure updates
  * `docs:` for readme or internal markdown modifications
  * `chore:` for temporary scripts, workspace cleanup, or boilerplate

---

## 2. Infrastructure & Telemetry Design Patterns

### OpenTelemetry (OTel) Configuration
* **Async Spans via `BatchSpanProcessor`**: To prevent blocking or deadlocking Python's asynchronous `asyncio` event loop (FastAPI/Uvicorn), the `BatchSpanProcessor` must be used for all trace exports. Synchronous processors like `SimpleSpanProcessor` block the request context thread and can deadlock under async I/O.
* **Metric Conventions**: Prompt and output tokens are monitored, structured under the OTel metric `gen_ai.client.token.usage` and exported to Google Cloud Monitoring using `ALIGN_DELTA` and `REDUCE_SUM` aggregators.
* **GCP Cloud Trace & Monitoring Integration**: Telemetry export is enabled when `OTEL_ENABLED="true"` and `TRACE_EXPORTER="gcp"`.

### Domain Restricted Sharing (DRS) Policy Overrides
* For disposable project setups, the corporate domain restricted sharing policy (`constraints/iam.allowedPolicyMemberDomains`) is disabled at the project level via a `google_project_organization_policy` override. This enables binding `roles/run.invoker` cleanly to `allUsers` for public internet browser testing without OIDC proxies.

---

## 3. Application Execution Standards

### Vertex AI & Client Lifespans
* **Zero-Argument Initialization**: The Google Gen AI SDK client is initialized inside `src/server.py` with zero arguments:
  ```python
  _ai = genai.Client()
  ```
* The SDK auto-resolves either `GEMINI_API_KEY` (local/AI Studio mode) or `GOOGLE_GENAI_USE_VERTEXAI` (Vertex AI mode on Cloud Run using implicit Application Default Credentials, `GOOGLE_CLOUD_PROJECT`, and `GOOGLE_CLOUD_LOCATION`).

### Dynamic Audio Caching
* **`AUDIO_CACHE` Toggle**: Set to `true` locally to reuse audio assets, but **must** be set to `false` inside the Cloud Run container environment variables to enforce production-grade dynamic text-to-speech synthesis on every request.
