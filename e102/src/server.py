"""FastAPI backend — match data API and Gemini-powered tactical analyst."""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import truststore
truststore.inject_into_ssl()  # use the OS certificate store (fixes SSL on Windows)

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from google import genai
from google.genai import types
from opentelemetry import trace
from pydantic import BaseModel, Field

from src.commentary import generate_commentary_stream, cache_path, cache_meta_path
from src.wc2026 import (
    get_matches as wc_get_matches, get_match as wc_get_match,
    generate_preview_stream, preview_wav_path, preview_meta_path,
    generate_pregame_data, generate_pregame_stream,
    pregame_wav_path, pregame_meta_path, pregame_data_path,
)

load_dotenv()

_AUDIO_CACHE = os.getenv("AUDIO_CACHE", "true").lower() == "true"

from src.parser import MatchData
from src.telemetry import setup_telemetry, record_tokens



# ─── Constants ────────────────────────────────────────────────────────────────

MODEL = "gemini-3.5-flash"
_DIST = Path(__file__).parent.parent / "frontend" / "dist"

# StatsBomb event types that carry no tactical information (ball receipt, carry, etc.)
_NOISE = {"Ball Receipt*", "Carry", "Starting XI", "Half Start", "Half End"}


# ─── App lifecycle ────────────────────────────────────────────────────────────

_md: MatchData | None = None
_ai: genai.Client | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _md, _ai

    _md = MatchData()
    _md.load()

    try:
        _ai = genai.Client()
        print("Gemini GenAI client initialized successfully.")
    except Exception as e:
        print(f"WARNING: Failed to initialize Gemini GenAI client: {e}. AI endpoints will return 500.")

    print("Playback IQ ready.")
    yield


app = FastAPI(title="Playback IQ", lifespan=lifespan)
if os.getenv("OTEL_ENABLED", "false").lower() == "true":
    setup_telemetry(app)

_tracer = trace.get_tracer(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Match data endpoints ──────────────────────────────────────────────────────

@app.get("/api/match-info")
def match_info():
    events = _md.get_events()
    max_minute = max((e["minute"] or 0 for e in events), default=90)
    return {**_md.get_match_info(), "total_duration_minutes": max_minute}


@app.get("/api/timeline")
def timeline():
    return _md.get_timeline_data()


@app.get("/api/events")
def events(
    minute_from: int | None = Query(None),
    minute_to: int | None = Query(None),
    event_types: str | None = Query(None, description="Comma-separated event types"),
):
    result = _md.get_events()
    if minute_from is not None:
        result = [e for e in result if (e["minute"] or 0) >= minute_from]
    if minute_to is not None:
        result = [e for e in result if (e["minute"] or 0) <= minute_to]
    if event_types:
        wanted = {t.strip() for t in event_types.split(",")}
        result = [e for e in result if e["type"] in wanted]
    return result


@app.get("/api/freeze-frame/{event_id}")
def freeze_frame(event_id: str):
    players = _md.get_freeze_frame(event_id)
    if not players:
        raise HTTPException(status_code=404, detail="No freeze frame for this event")
    return players


@app.get("/api/lineups")
def lineups():
    return _md.get_lineups()


# ─── Key events ───────────────────────────────────────────────────────────────

def _describe(e: dict) -> str:
    """Build a human-readable description of a key match event."""
    player = e.get("player") or "Unknown"
    team = e.get("team") or ""
    t = f"{e.get('minute', 0)}'"
    etype = e.get("type", "")

    if etype == "Shot":
        outcome = e.get("shot_outcome") or ""
        technique = e.get("shot_technique") or ""
        if outcome == "Goal":
            suffix = f" ({technique.lower()})" if technique and technique != "Normal" else ""
            return f"{player}{suffix} goal, {t}"
        label = {"Saved": "Shot saved", "Blocked": "Shot blocked", "Post": "Post!"}.get(
            outcome, "Shot off target"
        )
        return f"{label} — {player} ({team}), {t}"

    if etype == "Foul Committed":
        card = e.get("foul_committed_card") or ""
        return f"{card} — {player} ({team}), {t}" if card else f"Foul — {player} ({team}), {t}"

    if etype == "Substitution":
        on = e.get("substitution_replacement") or "?"
        return f"Sub: {on} on for {player} ({team}), {t}"

    if etype == "Pass":
        suffix = " (goal assist)" if e.get("is_goal_assist") else ""
        return f"Key pass{suffix} — {player} ({team}), {t}"

    return f"{etype} — {player} ({team}), {t}"


@app.get("/api/key-events")
def key_events():
    result = []
    for e in _md.get_events():
        etype = e.get("type", "")
        is_key = (
            etype == "Shot"
            or etype == "Substitution"
            or (etype == "Foul Committed" and e.get("foul_committed_card"))
            or (etype == "Pass" and e.get("is_key_pass"))
        )
        if not is_key:
            continue
        result.append({
            "event_id": e["event_id"],
            "minute": e["minute"],
            "second": e["second"],
            "period": e["period"],
            "type": etype,
            "team": e["team"],
            "player": e["player"],
            "shot_outcome": e.get("shot_outcome"),
            "shot_xg": e.get("shot_xg"),
            "foul_committed_card": e.get("foul_committed_card"),
            "description": _describe(e),
        })
    return result


# ─── Match stats (real-time, per-minute cumulative) ───────────────────────────

@app.get("/api/match-stats")
def match_stats():
    """Return cumulative per-minute stats for both teams (indices 0–95).

    Possession is approximated from ball touches (passes + carries + receipts),
    which closely tracks real broadcast possession figures.
    """
    events = _md.get_events()
    N = 96

    per_min = {
        t: [{"shots": 0, "on_target": 0, "passes": 0, "touches": 0, "fouls": 0}
            for _ in range(N)]
        for t in ("Morocco", "Portugal")
    }

    for e in events:
        team = e.get("team")
        if team not in per_min:
            continue
        minute = min(e.get("minute") or 0, 95)
        etype  = e.get("type", "")

        if etype == "Shot":
            per_min[team][minute]["shots"] += 1
            if e.get("shot_outcome") in ("Goal", "Saved", "Saved To Post"):
                per_min[team][minute]["on_target"] += 1
        elif etype == "Pass":
            per_min[team][minute]["passes"]  += 1
            per_min[team][minute]["touches"] += 1
        elif etype in ("Ball Receipt*", "Carry"):
            per_min[team][minute]["touches"] += 1
        elif etype == "Foul Committed":
            per_min[team][minute]["fouls"] += 1

    # Build cumulative arrays
    result: dict[str, list[dict]] = {"Morocco": [], "Portugal": []}
    for team in ("Morocco", "Portugal"):
        cum = {"shots": 0, "on_target": 0, "passes": 0, "touches": 0, "fouls": 0}
        for m in range(N):
            p = per_min[team][m]
            for k in cum:
                cum[k] += p[k]
            result[team].append(dict(cum))

    # Possession % derived from cumulative touches
    for m in range(N):
        total = result["Morocco"][m]["touches"] + result["Portugal"][m]["touches"]
        for team in ("Morocco", "Portugal"):
            t = result[team][m]["touches"]
            result[team][m]["possession"] = round(t / total * 100) if total else 50

    return result


# ─── AI helpers ───────────────────────────────────────────────────────────────

def _require_ai() -> genai.Client:
    if _ai is None:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not set — add it to .env")
    return _ai


def _zone_name(x: float | None, y: float | None) -> str:
    """Translate StatsBomb (x, y) coordinates to a readable football pitch zone.

    StatsBomb pitch: x 0→120 (own goal → opponent goal), y 0→80 (right → left touchline).
    """
    if x is None or y is None:
        return "an unknown position"

    if x < 18:      h = "inside his own penalty area"
    elif x < 40:    h = "in the defensive third"
    elif x < 60:    h = "in his own half"
    elif x < 80:    h = "in the attacking half"
    elif x < 102:   h = "in the attacking third"
    elif x < 112:   h = "inside the penalty area"
    else:           h = "at the six-yard box"

    if y < 18:      v = "on the right flank"
    elif y < 30:    v = "in the right channel"
    elif y < 38:    v = "right of centre"
    elif y <= 42:   v = "centrally"
    elif y < 50:    v = "left of centre"
    elif y < 62:    v = "in the left channel"
    else:           v = "on the left flank"

    return f"{h}, {v}"


def _score_at(all_events: list[dict], before_minute: int) -> str:
    """Return 'Morocco N – N Portugal' counting only goals scored before `before_minute`."""
    goals = {
        team: sum(
            1 for e in all_events
            if e["type"] == "Shot"
            and e.get("shot_outcome") == "Goal"
            and e["team"] == team
            and (e["minute"] or 0) < before_minute
        )
        for team in ("Morocco", "Portugal")
    }
    return f"Morocco {goals['Morocco']} – {goals['Portugal']} Portugal"


# ─── Agent tools (plain functions — SDK auto-generates declarations) ──────────

def get_events_in_window(minute_from: int, minute_to: int) -> dict:
    """Get all significant match events between two minutes to understand build-up or aftermath.

    Args:
        minute_from: Start minute (inclusive).
        minute_to: End minute (inclusive).

    Returns:
        dict with 'events' list showing type, player, team, location zone, and outcome.
    """
    evs = [
        e for e in _md.get_events()
        if minute_from <= (e["minute"] or 0) <= minute_to and e["type"] not in _NOISE
    ]
    return {"events": [
        {
            "event_id": e["event_id"],
            "minute": e["minute"],
            "second": e["second"],
            "type": e["type"],
            "player": e["player"],
            "team": e["team"],
            "location": _zone_name(e.get("location_x"), e.get("location_y")),
            "outcome": e.get("shot_outcome") or e.get("pass_outcome") or "",
        }
        for e in evs[:30]
    ]}


def get_passing_sequence(minute_from: int, minute_to: int) -> dict:
    """Get the sequence of passes in a time window to trace ball circulation and build-up patterns.

    Args:
        minute_from: Start minute (inclusive).
        minute_to: End minute (inclusive).

    Returns:
        dict with 'passes' list showing player, team, from_zone, length, and outcome.
    """
    passes = [
        e for e in _md.get_events()
        if e["type"] == "Pass" and minute_from <= (e["minute"] or 0) <= minute_to
    ]
    return {"passes": [
        {
            "minute": e["minute"],
            "second": e["second"],
            "player": e["player"],
            "team": e["team"],
            "from_zone": _zone_name(e.get("location_x"), e.get("location_y")),
            "length_m": round(e.get("pass_length") or 0, 1),
            "outcome": e.get("pass_outcome") or "Complete",
            "is_key_pass": bool(e.get("is_key_pass")),
        }
        for e in passes[:25]
    ]}


def get_player_positions(event_id: str) -> dict:
    """Get player positions from the freeze frame at the moment of a specific event.

    Args:
        event_id: The UUID of the event to fetch the freeze frame for.

    Returns:
        dict with 'players' list showing name, team, zone on the pitch, and whether they are the actor.
    """
    ff = _md.get_freeze_frame(event_id)
    return {"players": [
        {
            "name": p["player_name"] or "unnamed player",
            "team": p["team"],
            "zone": _zone_name(p["location_x"], p["location_y"]),
            "is_actor": p["is_actor"],
        }
        for p in ff if p["location_x"] is not None
    ][:22]}


def get_pressure_events(minute_from: int, minute_to: int) -> dict:
    """Get pressure, duel, and tackle events in a time window to reveal defensive intensity.

    Args:
        minute_from: Start minute (inclusive).
        minute_to: End minute (inclusive).

    Returns:
        dict with 'events' list showing type, player, team, and zone.
    """
    evs = [
        e for e in _md.get_events()
        if e["type"] in ("Pressure", "Duel", "Tackle", "Interception")
        and minute_from <= (e["minute"] or 0) <= minute_to
    ]
    return {"events": [
        {
            "minute": e["minute"],
            "type": e["type"],
            "player": e["player"],
            "team": e["team"],
            "zone": _zone_name(e.get("location_x"), e.get("location_y")),
        }
        for e in evs[:20]
    ]}


_AGENT_TOOLS = [get_events_in_window, get_passing_sequence, get_player_positions, get_pressure_events]
_TOOL_DISPATCH = {fn.__name__: fn for fn in _AGENT_TOOLS}

_STEP_LABELS = {
    "get_events_in_window": "Scanning event timeline",
    "get_passing_sequence": "Tracing passing sequence",
    "get_player_positions": "Reading player positions",
    "get_pressure_events":  "Analysing defensive pressure",
}


def _step_str(name: str, args: dict, result: dict) -> str:
    """Format '[STEP] label | N records · context' for the streaming step trace."""
    label = _STEP_LABELS.get(name, name.replace("_", " ").title())

    if name == "get_events_in_window":
        n = len(result.get("events", []))
        detail = f"{n} events · min {args.get('minute_from')}–{args.get('minute_to')}"
    elif name == "get_passing_sequence":
        n = len(result.get("passes", []))
        detail = f"{n} passes · min {args.get('minute_from')}–{args.get('minute_to')}"
    elif name == "get_player_positions":
        n = len(result.get("players", []))
        detail = f"{n} players mapped on pitch"
    elif name == "get_pressure_events":
        n = len(result.get("events", []))
        detail = f"{n} defensive actions · min {args.get('minute_from')}–{args.get('minute_to')}"
    else:
        detail = ""

    return f"{label} | {detail}" if detail else label


async def _run_tool_loop(
    contents: list,
    config: types.GenerateContentConfig,
) -> AsyncGenerator[str, None]:
    """Run the agentic tool-calling loop, yielding a '[STEP]' line per tool call.

    Mutates `contents` in place so the caller can continue with the updated
    conversation history for the final text generation pass.
    """
    client = _require_ai()

    with _tracer.start_as_current_span("agent.tool_loop") as loop_span:
        for round_num in range(5):
            with _tracer.start_as_current_span("gemini.generate_content") as llm_span:
                llm_span.set_attribute("llm.round", round_num)
                llm_span.set_attribute("llm.model", MODEL)
                resp = await client.aio.models.generate_content(
                    model=MODEL,
                    contents=contents,
                    config=config,
                )
                if resp.usage_metadata:
                    llm_span.set_attribute("llm.prompt_tokens",  resp.usage_metadata.prompt_token_count or 0)
                    llm_span.set_attribute("llm.output_tokens",  resp.usage_metadata.candidates_token_count or 0)
                    llm_span.set_attribute("llm.total_tokens",   resp.usage_metadata.total_token_count or 0)
                    record_tokens(resp.usage_metadata.prompt_token_count or 0, "input", MODEL, "agent_tool_loop")
                    record_tokens(resp.usage_metadata.candidates_token_count or 0, "output", MODEL, "agent_tool_loop")


            calls = resp.function_calls
            if not calls:
                loop_span.set_attribute("agent.rounds_used", round_num + 1)
                break

            contents.append(resp.candidates[0].content)

            tool_results = []
            for call in calls:
                args = dict(call.args)
                with _tracer.start_as_current_span(f"tool.{call.name}") as tool_span:
                    result = _TOOL_DISPATCH[call.name](**args)
                    tool_span.set_attribute("tool.name", call.name)
                    count = len(
                        result.get("events") or result.get("passes") or result.get("players") or []
                    )
                    tool_span.set_attribute("tool.result_count", count)
                yield f"[STEP] {_step_str(call.name, args, result)}\n"
                tool_results.append(
                    types.Part(
                        function_response=types.FunctionResponse(name=call.name, response=result)
                    )
                )

            contents.append(types.Content(role="user", parts=tool_results))


# ─── AI explain (simple, single-shot) ─────────────────────────────────────────

class ExplainBody(BaseModel):
    event_id: str
    context_minutes: int = 2


@app.post("/api/explain")
async def explain(body: ExplainBody):
    client = _require_ai()

    all_events = _md.get_events()
    event = next((e for e in all_events if e["event_id"] == body.event_id), None)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    minute = event["minute"] or 0

    ctx = [
        e for e in all_events
        if abs((e["minute"] or 0) - minute) <= body.context_minutes
        and e["type"] not in _NOISE
    ][:25]

    ff = _md.get_freeze_frame(body.event_id)
    lineups = _md.get_lineups()

    ctx_block = "\n".join(
        f"  {e['minute']}:{str(e['second'] or 0).zfill(2)} | {e['type']:<22} | "
        f"{(e['player'] or '—'):<35} | {e['team']}"
        for e in ctx
    )
    ff_block = "\n".join(
        f"  {(p['player_name'] or 'Unknown'):<35} | "
        f"{'teammate' if p['is_teammate'] else 'opponent'} | "
        f"({p['location_x']:.1f}, {p['location_y']:.1f})"
        for p in ff if p["location_x"] is not None
    )[:15]
    morocco_shape = " · ".join(p["position"] for p in lineups.get("Morocco", []))
    portugal_shape = " · ".join(p["position"] for p in lineups.get("Portugal", []))

    prompt = f"""You are a tactical football analyst providing a retrospective review of the 2022 Football Championship quarter-final: Morocco vs Portugal.

MATCH STATE at {minute}' (period {event.get('period', '?')}):
Score: {_score_at(all_events, minute)}

FOCAL EVENT:
  Type        : {event['type']}
  Player      : {event['player']} ({event['team']})
  Zone        : {_zone_name(event.get('location_x'), event.get('location_y'))}
  Outcome     : {event.get('shot_outcome') or 'N/A'}
  xG          : {event.get('shot_xg') or 'N/A'}
  Technique   : {event.get('shot_technique') or 'N/A'}
  Play pattern: {event.get('play_pattern') or 'N/A'}

EVENTS ±{body.context_minutes} min (noise filtered):
{ctx_block or '  (none)'}

FREEZE FRAME — player positions at this moment:
{ff_block or '  (no positional data)'}

FORMATIONS:
  Morocco : {morocco_shape}
  Portugal: {portugal_shape}

Write a concise tactical analysis in 3–4 sentences in the past tense. Focus strictly on tactical dynamics (such as positioning, defensive structure, and shape) rather than play-by-play description of the action. Reference player names and pitch zones. Never mention raw x/y coordinates or xG values."""

    async def stream():
        response = await client.aio.models.generate_content_stream(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                max_output_tokens=500,
            ),
        )
        async for chunk in response:
            if chunk.text:
                yield chunk.text

    return StreamingResponse(stream(), media_type="text/plain")


# ─── AI explain (agentic, with tool calls) ────────────────────────────────────

@app.post("/api/explain-agent")
async def explain_agent(body: ExplainBody):
    all_events = _md.get_events()
    event = next((e for e in all_events if e["event_id"] == body.event_id), None)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    minute = event["minute"] or 0
    span = trace.get_current_span()
    span.set_attribute("event.id",     body.event_id)
    span.set_attribute("event.minute", minute)
    span.set_attribute("event.type",   event.get("type", ""))

    system_prompt = f"""You are a tactical football analyst providing a retrospective review of the 2022 Football Championship quarter-final: Morocco vs Portugal.

MATCH STATE at {minute}' (period {event.get('period', '?')}):
Score: {_score_at(all_events, minute)}

FOCAL EVENT:
  Type          : {event['type']}
  Outcome       : {event.get('shot_outcome') or 'N/A'}
  Player        : {event['player']} ({event['team']})
  Zone          : {_zone_name(event.get('location_x'), event.get('location_y'))}
  xG            : {event.get('shot_xg') or 'N/A'}
  Technique     : {event.get('shot_technique') or 'N/A'}
  Body part     : {event.get('shot_body_part') or 'N/A'}
  Under pressure: {event.get('under_pressure') or False}
  Play pattern  : {event.get('play_pattern') or 'N/A'}

Use the tools to investigate this moment:
1. get_events_in_window — see the build-up (e.g. minutes {minute - 3}–{minute})
2. get_player_positions — freeze frame positioning
3. get_passing_sequence — trace how the attack developed
4. get_pressure_events  — defensive battle details (optional)

Then write a concise 3–4 sentence tactical analysis in the past tense. Focus strictly on tactical concepts (such as team shape, defensive organization, and build-up patterns) rather than standard play-by-play live action commentary. Name players, reference pitch zones, cite data from the tools."""

    config_tools = types.GenerateContentConfig(
        tools=_AGENT_TOOLS,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )
    config_final = types.GenerateContentConfig(
        tools=_AGENT_TOOLS,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        max_output_tokens=600,
    )

    async def stream():
        contents = [types.Content(role="user", parts=[types.Part.from_text(text=system_prompt)])]

        async for step_line in _run_tool_loop(contents, config_tools):
            yield step_line

        yield "[DONE]\n"

        client = _require_ai()
        with _tracer.start_as_current_span("gemini.generate_content_stream") as stream_span:
            stream_span.set_attribute("llm.model", MODEL)
            response = await client.aio.models.generate_content_stream(
                model=MODEL,
                contents=contents,
                config=config_final,
            )
            recorded_tokens = False
            async for chunk in response:
                if chunk.usage_metadata:
                    stream_span.set_attribute("llm.prompt_tokens", chunk.usage_metadata.prompt_token_count or 0)
                    stream_span.set_attribute("llm.output_tokens", chunk.usage_metadata.candidates_token_count or 0)
                    stream_span.set_attribute("llm.total_tokens",  chunk.usage_metadata.total_token_count or 0)
                    if not recorded_tokens:
                        record_tokens(chunk.usage_metadata.prompt_token_count or 0, "input", MODEL, "explain_agent")
                        record_tokens(chunk.usage_metadata.candidates_token_count or 0, "output", MODEL, "explain_agent")
                        recorded_tokens = True

                if chunk.text:
                    yield chunk.text

    return StreamingResponse(stream(), media_type="text/plain")


# ─── AI agent chat (conversational) ───────────────────────────────────────────

class ChatBody(BaseModel):
    event_id: str | None = None  # set for specific-event mode (marker click)
    minute: int | None = None    # set for overview mode (FAB click)
    question: str
    history: list[dict] = []     # [{"role": "user" | "assistant", "content": str}]


@app.post("/api/agent-chat")
async def agent_chat(body: ChatBody):
    span = trace.get_current_span()
    span.set_attribute("chat.event_id",   body.event_id or "")
    span.set_attribute("chat.minute",     body.minute or 0)
    span.set_attribute("chat.history_len", len(body.history))
    span.set_attribute("chat.mode",       "overview" if body.minute is not None else "event")

    all_events = _md.get_events()

    # ── Resolve the anchor event ──────────────────────────────────────────────
    if body.event_id:
        # Specific event — the user clicked a timeline marker
        event = next((e for e in all_events if e["event_id"] == body.event_id), None)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        is_overview = False

    elif body.minute is not None:
        # Overview mode — find the nearest interesting event for tool context
        _priority = {"Shot": 0, "Foul Committed": 1, "Pass": 2, "Duel": 3}
        candidates = [
            e for e in all_events
            if abs((e["minute"] or 0) - body.minute) <= 3 and e["type"] not in _NOISE
        ]
        event = min(
            candidates,
            key=lambda e: (_priority.get(e["type"], 99), abs((e["minute"] or 0) - body.minute)),
            default=None,
        )
        if event is None:
            raise HTTPException(status_code=422, detail="No events found near this minute")
        is_overview = True

    else:
        raise HTTPException(status_code=422, detail="Either event_id or minute is required")

    # ── Build system context ──────────────────────────────────────────────────
    minute = body.minute if is_overview else (event["minute"] or 0)
    score = _score_at(all_events, minute)

    if is_overview:
        system_context = f"""You are a tactical football analyst providing a retrospective review of the 2022 Football Championship quarter-final: Morocco vs Portugal.

The user is watching the match at minute {minute} and wants to discuss the tactical situation — not a specific event.

MATCH STATE at {minute}':
Score: {score}

RULES — follow these exactly:
• Discuss all events, tactics, and player actions in the past tense.
• Focus on deep tactical analysis (such as team shape, spacing, defensive organization, and build-up structures) rather than play-by-play live action commentary.
• Never mention raw x/y coordinates or xG values. Use football language only.
• Describe positions as "in the penalty area", "on the right flank", "at the edge of the box", etc.
• Reference actual player names when available.
• Write for a football fan — clear, engaging, and tactically specific, prioritizing analysis over commentary. 3–5 sentences."""

        if not body.history:
            system_context += f"""

Use the tools to build context for minute {minute}:
1. get_events_in_window — scan the last 4–5 minutes (each event includes an event_id you can pass to get_player_positions)
2. get_passing_sequence — which team is controlling the ball and how
3. get_pressure_events — pressing and defensive intensity
4. get_player_positions(event_id) — optional, use an event_id from the window to inspect player shape"""
        else:
            system_context += """

The conversation already has tool data. Answer follow-ups from that context.
Only call tools again if the question requires data not already fetched."""

    else:
        actor_team = event["team"]
        opponent_team = "Portugal" if actor_team == "Morocco" else "Morocco"

        system_context = f"""You are a tactical football analyst providing a retrospective review of the 2022 Football Championship quarter-final: Morocco vs Portugal.

MATCH STATE at {minute}' (period {event.get('period', '?')}):
Score: {score}

EVENT:
  Type        : {event['type']}
  Outcome     : {event.get('shot_outcome') or event.get('foul_committed_card') or 'N/A'}
  Player      : {event['player']} ({actor_team})
  Zone        : {_zone_name(event.get('location_x'), event.get('location_y'))}
  Technique   : {event.get('shot_technique') or 'N/A'}
  Body part   : {event.get('shot_body_part') or 'N/A'}
  Play pattern: {event.get('play_pattern') or 'N/A'}

RULES — follow these exactly:
• Discuss all events and tactics in the past tense.
• Focus on deep tactical analysis (such as team shape, spacing, defensive organization, and build-up structures) rather than play-by-play live action commentary.
• Never mention raw numbers, x/y coordinates, or xG values. Use football language only.
• Describe positions as "in the penalty area", "on the right flank", "at the edge of the box", etc.
• Explain the tactical reasons behind what {actor_team} did well and what {opponent_team} got wrong in the past tense.
• Reference actual player names from the data.
• Write for a football fan — clear, engaging, and tactically analytical. 3–5 sentences."""

        if not body.history:
            system_context += f"""

For this first question, use the tools to investigate:
1. get_events_in_window — build-up around minute {minute}
2. get_player_positions — positioning at this moment
3. get_passing_sequence — how the attack developed
4. get_pressure_events  — defensive battle details (optional)"""
        else:
            system_context += """

The conversation already has tool data. Answer follow-ups directly from that context.
Only call tools again if the question requires data you don't already have."""

    config_tools = types.GenerateContentConfig(
        tools=_AGENT_TOOLS,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )
    config_final = types.GenerateContentConfig(
        tools=_AGENT_TOOLS,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        max_output_tokens=700,
    )

    async def stream():
        # Combine system context and question if history is empty to avoid two consecutive user messages
        if not body.history:
            combined_text = f"{system_context}\n\nQuestion: {body.question}"
            contents = [types.Content(role="user", parts=[types.Part.from_text(text=combined_text)])]
        else:
            contents = [types.Content(role="user", parts=[types.Part.from_text(text=system_context)])]
            for msg in body.history:
                role = "model" if msg["role"] == "assistant" else "user"
                contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])]))
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=body.question)]))

        async for step_line in _run_tool_loop(contents, config_tools):
            yield step_line

        yield "[DONE]\n"

        client = _require_ai()
        with _tracer.start_as_current_span("gemini.generate_content_stream") as stream_span:
            stream_span.set_attribute("llm.model", MODEL)
            response = await client.aio.models.generate_content_stream(
                model=MODEL,
                contents=contents,
                config=config_final,
            )
            recorded_tokens = False
            async for chunk in response:
                if chunk.usage_metadata:
                    stream_span.set_attribute("llm.prompt_tokens", chunk.usage_metadata.prompt_token_count or 0)
                    stream_span.set_attribute("llm.output_tokens", chunk.usage_metadata.candidates_token_count or 0)
                    stream_span.set_attribute("llm.total_tokens",  chunk.usage_metadata.total_token_count or 0)
                    if not recorded_tokens:
                        record_tokens(chunk.usage_metadata.prompt_token_count or 0, "input", MODEL, "agent_chat")
                        record_tokens(chunk.usage_metadata.candidates_token_count or 0, "output", MODEL, "agent_chat")
                        recorded_tokens = True

                if chunk.text:
                    yield chunk.text

    return StreamingResponse(stream(), media_type="text/plain")


# ─── Dynamic Suggestions Endpoint ─────────────────────────────────────────────

class SuggestBody(BaseModel):
    event_id: str | None = None
    minute: int | None = None


class SuggestedQuestions(BaseModel):
    questions: list[str] = Field(description="List of exactly 3 analytical, interesting, and specific questions under 15 words each")


@app.post("/api/suggest-questions")
async def suggest_questions(body: SuggestBody):
    client = _require_ai()
    all_events = _md.get_events()

    # Resolve event context
    event = None
    minute = 0
    if body.event_id:
        event = next((e for e in all_events if e["event_id"] == body.event_id), None)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        minute = event["minute"] or 0
    elif body.minute is not None:
        minute = body.minute
        # Find the nearest interesting event to anchor the suggestions
        _priority = {"Shot": 0, "Foul Committed": 1, "Pass": 2, "Duel": 3}
        candidates = [
            e for e in all_events
            if abs((e["minute"] or 0) - body.minute) <= 3 and e["type"] not in _NOISE
        ]
        event = min(
            candidates,
            key=lambda e: (_priority.get(e["type"], 99), abs((e["minute"] or 0) - body.minute)),
            default=None,
        )
    else:
        raise HTTPException(status_code=422, detail="Either event_id or minute is required")

    score = _score_at(all_events, minute)
    context_details = f"MATCH SCORE AT MINUTE {minute}': {score}\n\n"

    if event:
        player = event.get("player") or "a player"
        team = event.get("team") or "unknown team"
        etype = event.get("type") or "unknown event"
        outcome = event.get("shot_outcome") or event.get("foul_committed_card") or "N/A"
        zone = _zone_name(event.get("location_x"), event.get("location_y"))
        context_details += (
            f"FOCAL EVENT DETAILS:\n"
            f"- Type of event: {etype}\n"
            f"- Actor/Player: {player} ({team})\n"
            f"- Location zone: {zone}\n"
            f"- Outcome/Result: {outcome}\n"
        )
    else:
        context_details += f"OVERVIEW CONTEXT:\n- The match is running at minute {minute}.\n"

    # Surrounding events sequence
    surround = [
        e for e in all_events
        if abs((e["minute"] or 0) - minute) <= 4 and e["type"] not in _NOISE
    ][:10]
    if surround:
        events_str = "\n".join(
            f"  {e['minute']}:{str(e['second'] or 0).zfill(2)}' | {e['type']} by {e.get('player')} ({e.get('team')})"
            for e in surround
        )
        context_details += f"\nSURROUNDING MATCH EVENT SEQUENCE:\n{events_str}"

    system_prompt = f"""You are a world-class football tactical analyst providing a retrospective breakdown of a classic match, generating three suggested questions for a user in an interactive match viewer.
The current match is Morocco vs Portugal (2022 Football Championship Quarter-Final). Morocco won 1–0.

CONTEXT DETAILED DATA:
{context_details}

TASK:
Based on the detailed match data provided, generate exactly three (3) highly analytical, interesting, and specific questions a user might want to ask an AI football analyst about this moment.
The questions should focus on tactics, team shapes, player positioning, passing chains, defensive structure, or tactical decisions. They must be concise (under 15 words each).

RULES:
- Phrase all questions in the past tense (e.g., "Why did..." instead of "Why does...").
- Do not mention raw x/y coordinates."""

    try:
        with _tracer.start_as_current_span("agent.suggest_questions") as span:
            span.set_attribute("llm.model", MODEL)
            resp = await client.aio.models.generate_content(
                model=MODEL,
                contents=system_prompt,
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                    max_output_tokens=300,
                    response_mime_type="application/json",
                    response_schema=SuggestedQuestions,
                ),
            )
            if resp.usage_metadata:
                span.set_attribute("llm.prompt_tokens", resp.usage_metadata.prompt_token_count or 0)
                span.set_attribute("llm.output_tokens", resp.usage_metadata.candidates_token_count or 0)
                span.set_attribute("llm.total_tokens",  resp.usage_metadata.total_token_count or 0)
                record_tokens(resp.usage_metadata.prompt_token_count or 0, "input", MODEL, "suggest_questions")
                record_tokens(resp.usage_metadata.candidates_token_count or 0, "output", MODEL, "suggest_questions")

            if resp.parsed:
                questions = resp.parsed.questions
                if isinstance(questions, list) and len(questions) == 3:
                    return {"suggestions": questions}
    except Exception as e:
        print(f"Failed to generate custom suggestions: {e}")

    # Fallback to empty list so frontend can gracefully handle it
    return {"suggestions": []}


# ─── Commentary endpoints ─────────────────────────────────────────────────────

class CommentaryBody(BaseModel):
    mode: str = "full"  # "quick" | "full"


def _valid_mode(mode: str) -> str:
    return mode if mode in ("quick", "full") else "full"


@app.post("/api/commentary/generate")
async def commentary_generate(body: CommentaryBody):
    """SSE stream: progress lines, then saves WAV + meta to disk."""
    client = _require_ai()
    mode = _valid_mode(body.mode)

    if _AUDIO_CACHE and cache_path(mode).exists() and cache_meta_path(mode).exists():
        async def _cached():
            yield "data: DONE\n\n"
        return StreamingResponse(_cached(), media_type="text/event-stream")

    async def stream():
        import json as _json
        with _tracer.start_as_current_span("commentary.generate") as span:
            span.set_attribute("commentary.mode", mode)
            wav_bytes  = None
            meta_dict  = None
            clip_count = 0

            async for item in generate_commentary_stream(client, _md.get_events(), mode):
                if isinstance(item, tuple) and item[0] == "audio":
                    _, wav_bytes, meta_dict = item
                else:
                    if "Synthesising" in item:
                        clip_count += 1
                    yield item  # SSE progress line

            if wav_bytes:
                cache_path(mode).parent.mkdir(parents=True, exist_ok=True)
                cache_path(mode).write_bytes(wav_bytes)
                if meta_dict:
                    cache_meta_path(mode).write_text(_json.dumps(meta_dict), encoding="utf-8")
                span.set_attribute("commentary.clip_count",  clip_count)
                span.set_attribute("commentary.wav_size_kb", len(wav_bytes) // 1024)
                yield "data: DONE\n\n"
            else:
                span.set_attribute("commentary.failed", True)
                yield "data: ERROR: synthesis failed\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/api/commentary/audio")
def commentary_audio(mode: str = Query("full")):
    """Return the cached WAV for the requested brief mode."""
    mode = _valid_mode(mode)
    path = cache_path(mode)
    if not path.exists():
        raise HTTPException(status_code=404, detail="No brief audio cached for this mode. Generate it first.")
    return FileResponse(
        path,
        media_type="audio/wav",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/commentary/audio-meta")
def commentary_audio_meta(mode: str = Query("full")):
    """Return the clip timing metadata JSON for the cached brief audio."""
    mode = _valid_mode(mode)
    path = cache_meta_path(mode)
    if not path.exists():
        raise HTTPException(status_code=404, detail="No metadata cached. Generate the brief first.")
    return Response(
        content=path.read_bytes(),
        media_type="application/json",
        headers={"Cache-Control": "no-store"},
    )


# ─── Pre-game show ────────────────────────────────────────────────────────────

_PREGAME_CACHE_DIR  = Path(__file__).parent.parent / ".pregame_cache"
_PREGAME_CACHE_DIR.mkdir(exist_ok=True)
_PREGAME_CACHE_WAV  = _PREGAME_CACHE_DIR / "pregame_podcast.wav"
_PREGAME_CACHE_META = _PREGAME_CACHE_DIR / "pregame_podcast.json"

_PREGAME_SCENE_IDS = ["title", "road", "venue", "weather", "spotlights", "lineups"]
_PREGAME_SCENE_LABELS = {
    "title": "Opening", "road": "The Journey", "venue": "The Venue",
    "weather": "Conditions", "spotlights": "Key Players", "lineups": "Lineups",
}


@app.get("/api/pregame/data")
def pregame_data():
    """Return pre-game show data: lineups, stadium coords, player spotlights."""
    lineups = _md.get_lineups()
    return {
        "audio_cache_enabled": _AUDIO_CACHE,
        "match": {
            "date": "December 10, 2022",
            "competition": "2022 Football Championship Quarter-Final",
            "venue": "Al Thumama Stadium, Doha, Qatar",
            "kickoff": "22:00 AST (19:00 UTC)",
            "lat": 25.2350,
            "lng": 51.5187,
        },
        "lineups": lineups,
        "spotlights": [
            {
                "name": "Sofyan Amrabat",
                "team": "Morocco",
                "position": "Defensive Midfielder",
                "jersey": 4,
                "highlight": "Morocco's Engine",
                "fact": "The Fiorentina midfielder has been unplayable in this tournament — his engine, range, and ferocity in midfield will be the key battle tonight.",
            },
            {
                "name": "Hakim Ziyech",
                "team": "Morocco",
                "position": "Winger",
                "jersey": 7,
                "highlight": "Morocco's Maestro",
                "fact": "The Chelsea winger carries Morocco's creative burden — his ability to unlock defensive blocks could be decisive in a tight quarter-final.",
            },
            {
                "name": "Cristiano Ronaldo",
                "team": "Portugal",
                "position": "Forward",
                "jersey": 7,
                "highlight": "Starting from the bench",
                "fact": "Controversially dropped to the bench by Fernando Santos — the first time CR7 has started a tournament knockout game on the bench in his legendary career.",
            },
            {
                "name": "Bruno Fernandes",
                "team": "Portugal",
                "position": "Attacking Midfielder",
                "jersey": 8,
                "highlight": "Portugal's creative spark",
                "fact": "Portugal's most technically gifted player must find pockets of space against Morocco's suffocating press — a near-impossible task tonight.",
            },
        ],
    }


class ClassicPregameScript(BaseModel):
    full_script: str = Field(
        description="The complete, unbroken monologue narration script containing all requested [SCENE:id] markers in order. "
                    "Ensure absolute consistency and a strong narrative through-line across the entire script."
    )


@app.post("/api/pregame/generate")
async def pregame_generate():
    """SSE: write ONE cohesive script, split at [SCENE:id] markers, synthesise each
    section as a separate TTS clip (no forced duration), concatenate, and save both the
    WAV and a JSON metadata file with the exact scene start timestamps so the frontend
    can synchronise scenes to the actual audio rather than hardcoded fractions."""
    client  = _require_ai()
    lineups = _md.get_lineups()
    mor_xi  = ", ".join(p["player_name"] for p in lineups.get("Morocco",  [])[:11])
    por_xi  = ", ".join(p["player_name"] for p in lineups.get("Portugal", [])[:11])

    script_prompt = f"""You are a passionate, spontaneous football podcast host delivering a retrospective pre-match monologue. Write ONE continuous, organic, breathless narration reflecting back on the legendary 2022 Football Championship Quarter-Final: MOROCCO vs PORTUGAL.

Venue: Al Thumama Stadium, Doha, Qatar · December 10, 2022 · Kickoff 22:00
Morocco starting XI: {mor_xi}
Portugal starting XI: {por_xi}

Write roughly 280 words of genuine, excited spoken word — the kind that makes you feel like you're reflecting back on that historic night. Flow naturally through these topics in order in the past tense, inserting the exact marker shown at the start of each topic shift (the markers are invisible to the listener — they are just section dividers for technical reasons):

[SCENE:title] — Fire-up opening: announce the match, its historic magnitude, and why that night mattered.
[SCENE:road] — Both journeys converging: Morocco's grind (Croatia, Belgium, Canada, Spain); Portugal's path (Ghana, Uruguay, South Korea, Switzerland). Recreate the drama.
[SCENE:venue] — Paint the stadium: Al Thumama, the gahfiya dome, 40,000 electric fans, the Doha night as it was.
[SCENE:weather] — The atmosphere and conditions: the warm clear night, 26 degrees, the weight of a continent that was watching.
[SCENE:spotlights] — The key men who were spotlighted: Amrabat the unstoppable engine; Ziyech the Moroccan maestro; Ronaldo controversially starting on the bench; Fernandes carrying Portugal's burden. Discuss their roles prior to kickoff. Do NOT predict or reveal any match outcomes, goals, or scorers yet.
[SCENE:lineups] — Call both XIs with mounting excitement. Morocco: {mor_xi}. Portugal: {por_xi}. Land the final line like a knockout punch.

Critical: this must sound like ONE unbroken monologue delivered in the past tense — no stilted transitions, no "moving on to...", no list-reading. Just pure, authentic football passion that builds and builds. Maintain absolute consistency and a strong narrative through-line across the entire script. No stage directions, no brackets other than the [SCENE:x] markers themselves. The listener should feel the hairs stand up on the back of their neck. Do NOT include the words 'FIFA' or 'World Cup' anywhere in the generated script under any circumstances."""

    if _AUDIO_CACHE and _PREGAME_CACHE_WAV.exists() and _PREGAME_CACHE_META.exists():
        async def _cached():
            yield "data: DONE\n\n"
        return StreamingResponse(_cached(), media_type="text/event-stream")

    async def stream():
        import json as _json
        from src.commentary import _synth as _tts, _to_wav, _clip_clean, SAMPLE_RATE, SAMPLE_WIDTH

        yield "data: Generating script…\n\n"
        with _tracer.start_as_current_span("pregame.generate_script") as span:
            span.set_attribute("llm.model", MODEL)
            resp = await client.aio.models.generate_content(
                model=MODEL,
                contents=script_prompt,
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                    max_output_tokens=1000,
                    response_mime_type="application/json",
                    response_schema=ClassicPregameScript,
                ),
            )
            if resp.usage_metadata:
                span.set_attribute("llm.prompt_tokens", resp.usage_metadata.prompt_token_count or 0)
                span.set_attribute("llm.output_tokens", resp.usage_metadata.candidates_token_count or 0)
                span.set_attribute("llm.total_tokens",  resp.usage_metadata.total_token_count or 0)
                record_tokens(resp.usage_metadata.prompt_token_count or 0, "input", MODEL, "pregame_script_generation")
                record_tokens(resp.usage_metadata.candidates_token_count or 0, "output", MODEL, "pregame_script_generation")
        full_text = ""
        if resp.parsed:
            full_text = resp.parsed.full_script.strip()
        if not full_text:
            yield "data: ERROR: script generation failed\n\n"
            return

        import re as _re
        pattern = r"\[SCENE:(" + "|".join(_re.escape(s) for s in _PREGAME_SCENE_IDS) + r")\]"
        parts = _re.split(pattern, full_text)
        sections = {}
        i = 1
        while i + 1 < len(parts):
            sid, body = parts[i].strip(), parts[i + 1].strip()
            if sid in _PREGAME_SCENE_IDS and body:
                sections[sid] = body
            i += 2
        missing  = [sid for sid in _PREGAME_SCENE_IDS if sid not in sections]
        if missing:
            yield f"data: ERROR: script missing sections: {missing}\n\n"
            return

        n = len(_PREGAME_SCENE_IDS)
        clips:      list[bytes] = []
        boundaries: list[dict]  = []
        cursor_secs = 0.0

        import asyncio as _asyncio

        yield f"data: Synthesising {n} scenes in parallel…\n\n"

        async def synth_one(idx, sid, text):
            try:
                pcm = await _tts(client, text, label=f"pregame-{sid}")
                return idx, sid, pcm
            except Exception:
                return idx, sid, b""

        tasks = {
            _asyncio.create_task(synth_one(idx, sid, sections[sid])): (idx, sid)
            for idx, sid in enumerate(_PREGAME_SCENE_IDS)
        }

        pcm_results = [b""] * n
        for fut in _asyncio.as_completed(tasks.keys()):
            idx, sid, pcm = await fut
            label = _PREGAME_SCENE_LABELS[sid]
            if not pcm:
                yield f"data: ⚠ {label} — synthesis failed or returned no audio\n\n"
            else:
                yield f"data: Synthesised {label} ({len(pcm) // 1024} KB)\n\n"
            pcm_results[idx] = pcm

        for idx, sid in enumerate(_PREGAME_SCENE_IDS):
            label = _PREGAME_SCENE_LABELS[sid]
            pcm = pcm_results[idx]

            if not pcm:
                # Record zero-duration section so the remaining scenes still have entries
                boundaries.append({"id": sid, "start": cursor_secs, "frac": None})
                continue

            pcm = _clip_clean(pcm)
            pcm = pcm[: (len(pcm) // SAMPLE_WIDTH) * SAMPLE_WIDTH]  # sample-align

            boundaries.append({"id": sid, "start": cursor_secs, "frac": None})
            cursor_secs += len(pcm) / (SAMPLE_RATE * SAMPLE_WIDTH)
            clips.append(pcm)

        if not clips:
            yield "data: ERROR: all TTS calls failed\n\n"
            return

        total_secs = cursor_secs
        for b in boundaries:
            b["frac"] = b["start"] / total_secs if total_secs > 0 else 0.0

        wav = _to_wav(clips)
        _PREGAME_CACHE_WAV.parent.mkdir(parents=True, exist_ok=True)
        _PREGAME_CACHE_WAV.write_bytes(wav)
        _PREGAME_CACHE_META.write_bytes(
            _json.dumps({"total_duration": total_secs, "scenes": boundaries}).encode()
        )
        yield f"data: Done — {len(wav) // 1024} KB · {total_secs:.0f}s\n\n"
        yield "data: DONE\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/api/pregame/audio")
def pregame_audio():
    """Serve the cached pre-game podcast WAV via FileResponse (range-request capable)."""
    if not _PREGAME_CACHE_WAV.exists():
        raise HTTPException(status_code=404, detail="No pre-game audio cached. Call /api/pregame/generate first.")
    return FileResponse(
        _PREGAME_CACHE_WAV,
        media_type="audio/wav",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/pregame/audio-meta")
def pregame_audio_meta():
    """Scene boundary metadata produced during generation: [{id, start, frac}, ...]."""
    if not _PREGAME_CACHE_META.exists():
        raise HTTPException(status_code=404, detail="No metadata yet. Regenerate the pre-game audio.")
    from fastapi.responses import Response as _Resp
    return _Resp(
        content=_PREGAME_CACHE_META.read_bytes(),
        media_type="application/json",
        headers={"Cache-Control": "no-store"},
    )


# ─── World Cup 2026 ───────────────────────────────────────────────────────────

@app.get("/api/wc2026/matches")
def wc2026_matches():
    """Return all 72 group-stage matches with joined team and stadium data."""
    return list(wc_get_matches())


@app.post("/api/wc2026/preview/generate")
async def wc2026_preview_generate(match_id: int = Query(...)):
    """SSE: generate and cache an AI narrated pre-match preview for a WC 2026 match."""
    client = _require_ai()
    match  = wc_get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail=f"Match {match_id} not found")

    if _AUDIO_CACHE and preview_wav_path(match_id).exists() and preview_meta_path(match_id).exists():
        async def _cached():
            yield "data: DONE\n\n"
        return StreamingResponse(_cached(), media_type="text/event-stream")

    async def stream():
        import json as _json
        wav_bytes = None
        meta_dict = None

        async for item in generate_preview_stream(client, match):
            if isinstance(item, tuple) and item[0] == "audio":
                _, wav_bytes, meta_dict = item
            else:
                yield item

        if wav_bytes:
            preview_wav_path(match_id).parent.mkdir(parents=True, exist_ok=True)
            preview_wav_path(match_id).write_bytes(wav_bytes)
            if meta_dict:
                preview_meta_path(match_id).write_text(_json.dumps(meta_dict), encoding="utf-8")
            yield "data: DONE\n\n"
        else:
            yield "data: ERROR: synthesis failed\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/api/wc2026/preview/audio")
def wc2026_preview_audio(match_id: int = Query(...)):
    path = preview_wav_path(match_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="No preview audio cached. Generate it first.")
    return FileResponse(path, media_type="audio/wav", headers={"Cache-Control": "no-store"})


@app.get("/api/wc2026/preview/audio-meta")
def wc2026_preview_audio_meta(match_id: int = Query(...)):
    path = preview_meta_path(match_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="No metadata cached. Generate the preview first.")
    return Response(content=path.read_bytes(), media_type="application/json",
                    headers={"Cache-Control": "no-store"})


# ─── World Cup 2026 — Pregame show ───────────────────────────────────────────

@app.get("/api/wc2026/pregame/data")
async def wc2026_pregame_data(match_id: int = Query(...)):
    """Return match info + AI-generated team facts + group teams for the pregame show.

    The AI call is cached after the first request so subsequent loads are instant.
    """
    client = _require_ai()
    match  = wc_get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail=f"Match {match_id} not found")
    data = await generate_pregame_data(client, match, use_cache=True)
    return {"match": match, "audio_cache_enabled": _AUDIO_CACHE, **data}


@app.post("/api/wc2026/pregame/generate")
async def wc2026_pregame_generate(match_id: int = Query(...)):
    """SSE: generate and cache a cinematic pregame audio show for a WC 2026 match."""
    client = _require_ai()
    match  = wc_get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail=f"Match {match_id} not found")

    if _AUDIO_CACHE and pregame_wav_path(match_id).exists() and pregame_meta_path(match_id).exists():
        async def _cached():
            yield "data: DONE\n\n"
        return StreamingResponse(_cached(), media_type="text/event-stream")

    async def stream():
        import json as _json
        wav_bytes = None
        meta_dict = None

        async for item in generate_pregame_stream(client, match):
            if isinstance(item, tuple) and item[0] == "audio":
                _, wav_bytes, meta_dict = item
            else:
                yield item

        if wav_bytes:
            pregame_wav_path(match_id).parent.mkdir(parents=True, exist_ok=True)
            pregame_wav_path(match_id).write_bytes(wav_bytes)
            if meta_dict:
                pregame_meta_path(match_id).write_text(_json.dumps(meta_dict), encoding="utf-8")
            yield "data: DONE\n\n"
        else:
            yield "data: ERROR: synthesis failed\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/api/wc2026/pregame/audio")
def wc2026_pregame_audio(match_id: int = Query(...)):
    path = pregame_wav_path(match_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="No pregame audio cached. Generate it first.")
    return FileResponse(path, media_type="audio/wav", headers={"Cache-Control": "no-store"})


@app.get("/api/wc2026/pregame/audio-meta")
def wc2026_pregame_audio_meta(match_id: int = Query(...)):
    path = pregame_meta_path(match_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="No metadata cached. Generate the pregame first.")
    return Response(content=path.read_bytes(), media_type="application/json",
                    headers={"Cache-Control": "no-store"})


# ─── Frontend (serves the built React app in production) ──────────────────────

@app.get("/")
def index():
    return FileResponse(_DIST / "index.html")


@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    candidate = _DIST / full_path
    if candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(_DIST / "index.html")
