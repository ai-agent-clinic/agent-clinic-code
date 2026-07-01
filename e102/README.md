# Playback IQ

An interactive football match replay with a built-in AI tactical analyst. Built on StatsBomb open data, it lets you scrub through a match minute-by-minute, watch player positions and ball movement animate on a live pitch canvas, and ask an AI agent to explain what happened at any key moment using real data from the match itself.

The demo match is the **2022 FIFA World Cup Quarter-Final: Morocco 1 – 0 Portugal**.

---

## What it looks like

- **Pitch canvas** — players rendered as coloured circles (green = Morocco, red = Portugal), the event actor highlighted with an amber ring, and the ball animated with physics-based arcs and a motion trail.
- **Timeline** — an intensity heatmap scrubber at the bottom showing match tempo across 96 minutes. Key event markers (goals ★, shots ●, cards ▪, key passes) sit above it and are clickable.
- **Cinematic overlays** — when playback crosses a shot or card event it pauses and plays a full-screen animation: bouncing ball + confetti for goals, a dimmed ball drifting wide for misses, a card flip for bookings.
- **AI analyst panel** — click any shot or card marker on the timeline to open a chat panel. Pick a suggested question or type your own; the agent calls real match data tools in real time and streams a tactical explanation.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12 · FastAPI · Uvicorn |
| AI | Google Gen AI Python SDK (`google-genai` 2.2.0) · Gemini 2.5 Flash |
| Data | StatsBomb open data (events, 360° frames, lineups) |
| Frontend | React 18 · Vite 5 (no component library) |
| Rendering | HTML5 Canvas (pitch + ball + players) |
| Styling | Plain CSS (no Tailwind or CSS-in-JS) |

---

## Project structure

```
playback-iq/
├── src/
│   ├── parser.py          # MatchData class — loads and queries StatsBomb JSON
│   └── server.py          # FastAPI app — all API endpoints + AI agent logic
│
├── frontend/
│   └── src/
│       ├── App.jsx                    # Root: playback state, event detection, layout
│       ├── App.css                    # All styles
│       └── components/
│           ├── Pitch.jsx              # Canvas renderer: pitch markings, players, ball
│           ├── Timeline.jsx           # Intensity heatmap, scrubber, key event markers
│           ├── EventOverlay.jsx       # Cinematic full-screen overlays (goal / shot / card)
│           └── AgentPanel.jsx         # Slide-in AI chat panel with step trace + streaming
│
├── data/
│   ├── events/3869486.json            # 3,381 match events (flat StatsBomb format)
│   ├── threesixty/3869486.json        # 360° freeze frames (player positions per event)
│   └── lineups/3869486.json           # Starting XIs with jersey numbers and positions
│
├── Data-Gathering/
│   ├── download_data.py               # Script that pulled data via statsbombpy
│   └── team_search.py                 # Helper for finding match IDs
│
├── pyproject.toml
├── uv.lock
├── .env.example
└── README.md
```

---

## Setup

### 1. Clone and install dependencies

```bash
git clone <repo-url>
cd playback-iq
uv sync
```

### 2. Data Setup (Compliance & Copyright)

Match data is not included in the repository for copyright and compliance reasons. You must fetch it from StatsBomb Open Data using the provided setup script:

```bash
python Data-Gathering/download_data.py
```

This will download the specific match data (Events, 360 Frames, and Lineups) required for the demo.

### 3. Add your Gemini API key

```bash
cp .env.example .env
# then edit .env and paste your key
```

```
GEMINI_API_KEY=your_key_here
```

Get a free key at [aistudio.google.com](https://aistudio.google.com).

### 4. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

---

## Running

### Development (hot-reload on both sides)

Open two terminals:

```bash
# Terminal 1 — backend
uvicorn src.server:app --port 8000 --reload

# Terminal 2 — frontend dev server
cd frontend
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The Vite dev server proxies `/api/*` to FastAPI on port 8000.

### Production (single server)

```bash
cd frontend && npm run build && cd ..
uvicorn src.server:app --port 8000
```

Open [http://localhost:8000](http://localhost:8000). FastAPI serves the built React app from `frontend/dist/` and handles all API routes.

---

## OpenTelemetry (OTEL) Telemetry (Traces & Metrics)

The application features full OpenTelemetry instrumentation to trace operations and measure token consumption across FastAPI, the manual Gemini agentic loop, and the voice synthesis (TTS) pipelines.

### Local Telemetry (Jaeger & Console Metrics)

1. **Start Jaeger**: Run the Jaeger container using the docker-compose setup:
   ```bash
   make jaeger
   ```
2. **Configure Environment**: Set the following variables in `.env`:
   ```env
   OTEL_ENABLED=true
   TRACE_EXPORTER=otlp # set to 'console' to print traces and metrics directly to terminal logs
   OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
   AUDIO_CACHE=true # set to false to force dynamic generation on every request
   ```
3. **View Traces & Metrics**:
   - Start the application with `make backend`. Trigger some analyst queries in the UI.
   - Traces appear in Jaeger at [http://localhost:16686](http://localhost:16686).
   - If `TRACE_EXPORTER=console` is set, custom token consumption metrics (like `gen_ai.client.token.usage`) are printed directly to standard output every 10 seconds.

### Cloud Telemetry (GCP Cloud Trace & Cloud Monitoring)

1. **Authenticate**: Authenticate with Google Cloud local ADC:
   ```bash
   gcloud auth application-default login
   ```
2. **Configure Environment**: Direct both trace spans and metric counters to GCP in `.env`:
   ```env
   OTEL_ENABLED=true
   TRACE_EXPORTER=gcp
   GOOGLE_CLOUD_PROJECT=<your-gcp-project-id>
   AUDIO_CACHE=false # disabled on Cloud Run to enforce dynamic audio synthesis
   ```
3. **View Data in GCP**:
   - **Traces**: Go to the **Google Cloud Trace** console under your project to inspect visual trace graphs.
   - **Metrics**: Go to the **Google Cloud Monitoring (Metrics Explorer)**. Query the metric `gen_ai.client.token.usage` to track, chart, and alert on real-time LLM input and output token consumption, grouped by `token_type` (input vs output) and `operation` (e.g. `agent_chat`, `audio_synthesis`).
   - **Token Analytics Dashboard**: Access **Monitoring > Dashboards** in the GCP Console and open the **Playback IQ Token Analytics** dashboard provisioned via Terraform to view real-time charts of token usage by operation and type.

---

## Infrastructure & Deployment (GCP)

We use **Terraform** and **Google Cloud Build** to provision, compile, and deploy Playback IQ natively to **Google Cloud Run**. The entire environment is fully isolated and disposable, creating a new GCP project using a dynamically generated pet name (`clinic-ep2-<pet-name>`).

### 1. Multi-Stage Dockerfile & Cloud Build
To run on Cloud Run, the application is containerized using a production-ready [Dockerfile](file:///Users/luissala/development/agent-clinic-episode-2/Dockerfile):
- **Stage 1 (Frontend)**: Compiles the React/Vite web application natively inside a Node environment.
- **Stage 2 (Runtime)**: Installs FastAPI and OpenTelemetry packages, copies backend/match data, pulls the built frontend assets, and launches Uvicorn on port `8080`.

Because building AMD64 containers locally on M-series Apple Silicon Macs can cause QEMU emulation bottlenecks and native `esbuild` panics, we leverage **Google Cloud Build** to compile the container natively on cloud servers using:
```bash
make gcp-build
```
This uploads the source code archive, builds it on high-performance AMD64 cloud infrastructure, and pushes it directly to the Google Artifact Registry repository.

### 2. IAM & Authentication Security
To enforce minimum privilege and security compliance:
- **FastAPI Runner Service Account**: A dedicated service account `playback-iq-runner` is provisioned for the Cloud Run instance, granted ONLY `roles/aiplatform.user` (Vertex AI access), `roles/cloudtrace.agent` (Tracing spans), and `roles/monitoring.metricWriter` (OTel metric reporting). No API keys are required; authentication is handled implicitly by the SDK via Application Default Credentials (ADC).
- **Domain Restricted Sharing Compatibility**: Corporate organizational policies typically enforce Domain Restricted Sharing (`constraints/iam.allowedPolicyMemberDomains`), blocking unauthenticated public access (`allUsers`). To satisfy this policy securely, the Cloud Run invoker binding (`roles/run.invoker`) is bound directly to your authenticated organizational email (`user:luis@luissala.altostrat.com`), keeping the endpoint protected and accessible only to you.

### 3. Workflow Targets

To make management easy, we've exposed several orchestration targets in the root [Makefile](file:///Users/luissala/development/agent-clinic-episode-2/Makefile):

- **Initialize Terraform**: Downloads providers and locks configurations.
  ```bash
  make tf-init
  ```
- **Deploy Cloud Run Environment**: provisions Artifact Registry, compiles the container via Cloud Build, pushes it, and deploys the Cloud Run service in a single automated step:
  ```bash
  make deploy-cloud-run
  ```
- **Tear Down**: Destroys all provisioned GCP services and the project cleanly:
  ```bash
  make tf-destroy
  ```

### 4. Domain Restricted Sharing Override
Corporate organizational policies typically enforce Domain Restricted Sharing (`constraints/iam.allowedPolicyMemberDomains`), blocking unauthenticated public access (`allUsers`). To make this disposable project fully functional and easy to browse:
- The Terraform configuration provisions a `google_project_organization_policy` override specifically for this project.
- It disables domain restrictions using a `list_policy` that sets `allow { all = true }`, which allows binding `allUsers` natively.
- As a result, the live Cloud Run URL is fully publicly accessible. You can browse the application directly in any browser tab without running any local proxy!

Before running deployment, configure your target credentials by copying the example vars file to `terraform.tfvars`:
```bash
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
# then edit terraform.tfvars and paste your billing account & folder/org ID
```

---

## How playback works

Playback is minute-based. The backend exposes `/api/events?minute_from=N&minute_to=N` and `/api/freeze-frame/<event_id>`.

Each time the minute advances, `Pitch.jsx` fetches the most significant event for that minute (prioritising goals → shots → key passes → fouls), then fetches the freeze frame — either a `shot_freeze_frame` (has player identities) or a 360° frame (has positions but no names). Players animate smoothly between frames using linear interpolation over 750ms.

The ball runs a two-phase animation per event:
- **Phase 1 (0–38% of animation):** ball glides from the previous event's end position to the current event's start position.
- **Phase 2 (38–100%):** ball travels from the actor's position to the end location with a parabolic arc (shot arc is steeper than pass arc), plus a motion trail of fading ghost circles.

---

## How the AI agent works

The agent uses **Gemini 2.5 Flash** via the Google Gen AI SDK with native function calling. It is **not** the Gemini ADK, the agentic loop is written manually using the SDK's multi-turn conversation API.

### Tools available to the agent

| Tool | What it fetches |
|---|---|
| `get_events_in_window(minute_from, minute_to)` | All significant events in a time window (noise-filtered) |
| `get_passing_sequence(minute_from, minute_to)` | Passes only, with length, outcome, and zone |
| `get_player_positions(event_id)` | Freeze frame positions translated to football zones |
| `get_pressure_events(minute_from, minute_to)` | Pressures, duels, tackles, interceptions |

All coordinate data is translated from raw StatsBomb numbers (x, y) into football language ("inside the penalty area, centrally", "on the right flank") before being handed to the model. The prompt explicitly instructs Gemini to never mention raw coordinates in its response.

### Agent loop (in `server.py`)

```
User question
    │
    ▼
POST /api/agent-chat
    │
    ├─ Build conversation: system context + match event info + history + question
    │
    └─ Loop (max 5 rounds):
           ├─ Call Gemini with tools attached
           ├─ If function_call parts returned:
           │      ├─ Execute tool (in-memory, instant)
           │      ├─ Stream [STEP] label | result detail to client
           │      └─ Append tool result to conversation, repeat
           └─ If no function_call: break
    │
    └─ Stream [DONE] then stream final Gemini text response
```

The frontend parses the stream line by line: `[STEP] ...` lines feed the live step trace, `[DONE]` switches to analysis mode, and everything after streams into the chat bubble character-by-character.

### Conversation history

`AgentPanel.jsx` sends the full conversation history with every request (`history: [{role, content}]`). The backend injects it as alternating `user`/`model` turns before the current question, giving Gemini context for follow-up answers.

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/match-info` | Match metadata and final score |
| `GET` | `/api/timeline` | 96-minute intensity heatmap data |
| `GET` | `/api/events` | Events, filterable by `minute_from`, `minute_to`, `event_types` |
| `GET` | `/api/freeze-frame/{event_id}` | Player positions for a specific event |
| `GET` | `/api/key-events` | Goals, shots, cards, key passes with descriptions |
| `GET` | `/api/lineups` | Both teams' starting XIs |
| `POST` | `/api/agent-chat` | Conversational AI analyst (streaming) |
| `POST` | `/api/explain-agent` | Single-shot AI explanation (streaming, legacy) |

---

## Data source

All match data comes from [StatsBomb open data](https://github.com/statsbomb/open-data) (free, no account needed). The `Data-Gathering/download_data.py` script fetched it via `statsbombpy`.

Match ID: **3869486** — Morocco vs Portugal, 2022 FIFA World Cup Quarter-Final, 10 December 2022.

StatsBomb pitch coordinates: x 0→120 (own goal → opponent goal), y 0→80 (bottom touchline → top touchline).

---

## Key design decisions

**Why minute-based playback instead of continuous streaming?**
StatsBomb 360° data covers ~2,880 of 3,381 events but doesn't include timestamps precise enough for smooth continuous interpolation at normal speed. Minute-based playback shows the most meaningful event per minute and animates the transition. It's a replay tool, not a simulation.