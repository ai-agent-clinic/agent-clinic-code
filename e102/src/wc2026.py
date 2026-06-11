"""World Cup 2026 — data loading and AI match-preview generation.

Architecture mirrors the pre-game podcast: ONE script with [SCENE:id] markers
is generated, split, and synthesised as individual TTS clips. Exact scene
start/end times are stored in metadata so the frontend can sync visual
scene cards to the audio without any guesswork.
"""

import csv
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from google import genai
from google.genai import types as gtypes
from pydantic import BaseModel, Field

_DATA_DIR = Path(__file__).parent.parent / "data" / "worldcup_2026"
_PREVIEW_CACHE = Path(__file__).parent.parent / ".wc2026_cache"
_PREVIEW_CACHE.mkdir(exist_ok=True)

from opentelemetry import trace as _otel_trace
from src.telemetry import record_tokens

_tracer = _otel_trace.get_tracer(__name__)

SCENE_IDS = ["opener", "venue", "group", "home", "away", "kickoff"]
SCENE_LABELS = {
    "opener": "Opening",
    "venue": "The Venue",
    "group": "Group Stakes",
    "home": "Home Team",
    "away": "Away Team",
    "kickoff": "Kickoff",
}


# ── Data loading ──────────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _teams() -> dict[str, dict]:
    with open(_DATA_DIR / "teams.csv", encoding="utf-8") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


@lru_cache(maxsize=1)
def _stadiums() -> dict[str, dict]:
    with open(_DATA_DIR / "stadiums.csv", encoding="utf-8") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def _team_obj(t: dict) -> dict:
    return {
        "id": t.get("id", ""),
        "name": t.get("name_en", "TBD"),
        "flag": t.get("flag", ""),
        "fifa_code": t.get("fifa_code", "TBD"),
        "iso2": (t.get("iso2") or "").lower(),
        "group": t.get("groups", ""),
    }


def _safe_float(val) -> float | None:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _stadium_obj(s: dict) -> dict:
    raw_cap = s.get("capacity", "")
    try:
        cap_fmt = f"{int(raw_cap):,}"
    except (ValueError, TypeError):
        cap_fmt = raw_cap
    return {
        "id": s.get("id", ""),
        "name": s.get("name_en", ""),
        "city": s.get("city_en", ""),
        "country": s.get("country_en", ""),
        "capacity": cap_fmt,
        "lat": _safe_float(s.get("lat")),
        "lng": _safe_float(s.get("lng")),
    }


@lru_cache(maxsize=1)
def get_matches() -> tuple[dict, ...]:
    """Return all 72 group-stage matches with joined team/stadium data (cached)."""
    teams = _teams()
    stadiums = _stadiums()
    with open(_DATA_DIR / "games.csv", encoding="utf-8") as f:
        games = list(csv.DictReader(f))

    result = []
    for g in games:
        result.append(
            {
                "id": int(g["id"]),
                "group": g["group"],
                "matchday": int(g["matchday"]),
                "local_date": g.get("local_date", ""),
                "date": g.get("date", ""),
                "home_team": _team_obj(teams.get(g["home_team_id"], {})),
                "away_team": _team_obj(teams.get(g["away_team_id"], {})),
                "stadium": _stadium_obj(stadiums.get(g["stadium_id"], {})),
            }
        )
    return tuple(result)


def get_match(match_id: int) -> dict | None:
    return next((m for m in get_matches() if m["id"] == match_id), None)


# ── Cache paths ───────────────────────────────────────────────────────────────


def preview_wav_path(match_id: int) -> Path:
    return _PREVIEW_CACHE / f"match_{match_id}.wav"


def preview_meta_path(match_id: int) -> Path:
    return _PREVIEW_CACHE / f"match_{match_id}_meta.json"


def pregame_wav_path(match_id: int) -> Path:
    return _PREVIEW_CACHE / f"match_{match_id}_pregame.wav"


def pregame_meta_path(match_id: int) -> Path:
    return _PREVIEW_CACHE / f"match_{match_id}_pregame_meta.json"


def pregame_data_path(match_id: int) -> Path:
    return _PREVIEW_CACHE / f"match_{match_id}_pregame_data.json"


# ── Prompt builder ────────────────────────────────────────────────────────────


def _fmt_date(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%B %d, %Y")
    except Exception:
        return iso


def _group_others(group: str, exclude_ids: set[str]) -> str:
    others = [
        t["name_en"]
        for t in _teams().values()
        if t.get("groups") == group and t["id"] not in exclude_ids
    ]
    return " and ".join(others) if others else ""


def build_preview_prompt(match: dict) -> str:
    home = match["home_team"]
    away = match["away_team"]
    stadium = match["stadium"]
    group = match["group"]
    date_s = _fmt_date(match["date"])
    others = _group_others(group, {home["id"], away["id"]})
    grp_ctx = f"The other teams in Group {group} are {others}." if others else ""
    today_s = datetime.now().strftime("%B %d, %Y")

    return (
        "You are a seasoned, authoritative, and evocative English football commentator and "
        "master storyteller—blending the poetic gravitas of Peter Drury with the "
        "traditional cadence of classic British broadcasting. You are delivering a live "
        "pre-match monologue for the 2026 FIFA World Cup — hosted across Canada, Mexico, "
        "and the United States, treating the beautiful game like a grand theater production.\n\n"
        f"TODAY'S DATE: {today_s} (Use this to anchor your Google Search grounding for real-world qualification runs, warm-ups, squad selections, and player form leading up to the tournament).\n\n"
        f"MATCH: {home['name']} vs {away['name']}\n"
        f"GROUP: Group {group}  ·  Matchday {match['matchday']}\n"
        f"DATE: {date_s}\n"
        f"VENUE: {stadium['name']}, {stadium['city']}, {stadium['country']} "
        f"({stadium['capacity']} capacity)\n"
        f"{grp_ctx}\n\n"
        "Write roughly 240 words of ONE continuous, organic, and evocative narration that builds "
        "to a crescendo. Deliver with the authentic passion of a seasoned broadcaster overlooking "
        "a packed, roaring stadium. Seamlessly use traditional British football terminology "
        "(e.g., 'pitch', 'gantry', 'absolute cracker', 'the terraces', 'breezed past'). "
        "Flow naturally through these sections, placing the EXACT marker at the start "
        "of each (markers are invisible to the listener — purely technical dividers):\n\n"
        f"[SCENE:opener] — Fire-up: announce this match with immense theatrical gravitas, its World Cup magnitude, and why tonight matters.\n"
        f"[SCENE:venue] — The stadium: {stadium['name']} in {stadium['city']}. Set the scene overlooking the roaring pitch, the host-nation atmosphere, the scale of this arena under the floodlights.\n"
        f"[SCENE:group] — Group {group} stakes: outline the sweeping narrative stakes of what both teams need, weaving in the group context and the other sides.\n"
        f"[SCENE:home] — {home['name']}: Use search to ground their narrative. "
        f"Weave their recent qualification or warmup game results leading up to today ({today_s}) into a story of momentum. "
        f"Identify their key star player to watch for this upcoming game and explain "
        f"exactly why their specific strengths are the tactical key to unlocking the opponent.\n"
        f"[SCENE:away] — {away['name']}: Use search to ground their narrative. "
        f"Weave their recent qualification or warmup game results leading up to today ({today_s}) into a story of momentum. "
        f"Identify their key star player to watch for this upcoming game and explain "
        f"exactly why their specific strengths are the tactical key to unlocking the opponent.\n"
        f"[SCENE:kickoff] — Final electric buildup: build the tension to a high-pitched crescendo as kickoff approaches—the global audience, the anticipation, the beautiful game—land it with dramatic finality.\n\n"
        "Critical: ONE unbroken monologue — no stilted transitions, no 'moving on to...', no list-reading. "
        "Maintain absolute consistency and a strong narrative through-line across the entire script. "
        "Write with flawless articulation and rich, resonant phrasing. "
        "No stage directions, no parenthetical hints, no brackets other than the "
        "[SCENE:x] markers themselves. Pure spoken English, present tense."
    )


# ── Preview generation stream ─────────────────────────────────────────────────


async def generate_preview_stream(client: genai.Client, match: dict):
    """Yield SSE progress strings then a final ('audio', wav_bytes, meta) tuple.

    Mirrors the pre-game podcast architecture:
      1. Generate ONE script with [SCENE:id] markers.
      2. Split → per-scene text → synthesise each to natural PCM completion.
      3. Assemble with 700 ms gaps; emit exact scene timestamps as metadata.
    """
    import re as _re
    from src.commentary import _synth, _to_wav, _clip_clean, SAMPLE_RATE, SAMPLE_WIDTH

    _GAP_SAMPS = round(0.70 * SAMPLE_RATE)

    home = match["home_team"]["name"]
    away = match["away_team"]["name"]

    yield f"data: Writing preview script for {home} vs {away}…\n\n"

    with _tracer.start_as_current_span("wc2026.generate_preview_script") as span:
        span.set_attribute("llm.model", "gemini-3.5-flash")
        resp = await client.aio.models.generate_content(
            model="gemini-3.5-flash",
            contents=build_preview_prompt(match),
            config=gtypes.GenerateContentConfig(
                thinking_config=gtypes.ThinkingConfig(thinking_budget=0),
                max_output_tokens=1200,
                tools=[gtypes.Tool(google_search=gtypes.GoogleSearch())],
                response_mime_type="application/json",
                response_schema=CohesivePregameScript,
            ),
        )
        if resp.usage_metadata:
            span.set_attribute("llm.prompt_tokens", resp.usage_metadata.prompt_token_count or 0)
            span.set_attribute("llm.output_tokens", resp.usage_metadata.candidates_token_count or 0)
            span.set_attribute("llm.total_tokens",  resp.usage_metadata.total_token_count or 0)
            record_tokens(resp.usage_metadata.prompt_token_count or 0, "input", "gemini-3.5-flash", "wc2026_preview_script_generation")
            record_tokens(resp.usage_metadata.candidates_token_count or 0, "output", "gemini-3.5-flash", "wc2026_preview_script_generation")

    full_text = ""
    if resp.parsed:
        full_text = resp.parsed.full_script.strip()
    if not full_text:
        yield "data: ERROR: script generation failed\n\n"
        return

    # Split at [SCENE:id] markers
    ids = SCENE_IDS
    pattern = r"\[SCENE:(" + "|".join(_re.escape(s) for s in ids) + r")\]"
    parts = _re.split(pattern, full_text)
    sections: dict[str, str] = {}
    i = 1
    while i + 1 < len(parts):
        sid, body = parts[i].strip(), parts[i + 1].strip()
        if sid in ids and body:
            sections[sid] = body
        i += 2

    missing = [s for s in ids if s not in sections]
    if missing:
        yield f"data: WARNING: missing sections {missing} — generating anyway\n\n"

    n = len(ids)
    clips: list[bytes] = []
    clip_meta: list[dict] = []
    cursor = 0  # running samples

    for idx, sid in enumerate(ids):
        text = sections.get(sid, "")
        label = SCENE_LABELS[sid]
        if not text:
            yield f"data: Skipping {label} (no text)…\n\n"
            continue

        yield f"data: Synthesising {idx + 1}/{n}: {label}…\n\n"
        pcm = await _synth(client, text, label=f"preview-{sid}")
        if not pcm:
            continue
        pcm = _clip_clean(pcm)
        pcm = pcm[: (len(pcm) // SAMPLE_WIDTH) * SAMPLE_WIDTH]

        clip_samps = len(pcm) // SAMPLE_WIDTH
        audio_start = cursor / SAMPLE_RATE
        audio_end = (cursor + clip_samps) / SAMPLE_RATE
        clip_meta.append(
            {
                "scene": sid,
                "label": label,
                "audio_start": round(audio_start, 3),
                "audio_end": round(audio_end, 3),
            }
        )
        clips.append(pcm)
        cursor += clip_samps

        if idx < n - 1:
            clips.append(b"\x00" * (_GAP_SAMPS * SAMPLE_WIDTH))
            cursor += _GAP_SAMPS

    if not clips:
        yield "data: ERROR: all TTS calls failed\n\n"
        return

    total_secs = cursor / SAMPLE_RATE
    wav = _to_wav(clips)
    meta = {"total_duration": round(total_secs, 3), "clips": clip_meta}
    yield f"data: Done — {len(wav) // 1024} KB · {total_secs:.1f}s\n\n"
    yield ("audio", wav, meta)


# ── Pre-game show (cinematic, upcoming matches) ───────────────────────────────


def _group_team_list(group: str) -> list[dict]:
    """Return all teams in a group, sorted so known teams come first."""
    return [_team_obj(t) for t in _teams().values() if t.get("groups") == group]


def build_pregame_prompt(match: dict) -> str:
    """6-scene script for the upcoming-match cinematic pre-game show.

    KEY DIFFERENCE from build_preview_prompt: the kickoff scene must NOT say
    "the whistle is minutes away" — the match is days in the future.
    """
    home = match["home_team"]
    away = match["away_team"]
    stadium = match["stadium"]
    group = match["group"]
    date_s = _fmt_date(match["date"])
    others = _group_others(group, {home["id"], away["id"]})
    grp_ctx = f"The other teams in Group {group} are {others}." if others else ""
    today_s = datetime.now().strftime("%B %d, %Y")

    return (
        "You are a seasoned, authoritative, and evocative English football commentator and "
        "master storyteller—blending the poetic gravitas of Peter Drury with the "
        "traditional cadence of classic British broadcasting. You are delivering a "
        "cinematic pre-match show for the 2026 FIFA World Cup — hosted across "
        "Canada, Mexico, and the United States, treating the beautiful game like a grand theater production.\n\n"
        f"TODAY'S DATE: {today_s} (Use this to anchor your Google Search grounding for real-world qualification runs, warm-ups, squad selections, and player form leading up to the tournament).\n\n"
        f"MATCH: {home['name']} vs {away['name']}\n"
        f"GROUP: Group {group}  ·  Matchday {match['matchday']}\n"
        f"DATE: {date_s}  — this match has NOT happened yet. It is upcoming.\n"
        f"VENUE: {stadium['name']}, {stadium['city']}, {stadium['country']} "
        f"({stadium['capacity']} capacity)\n"
        f"{grp_ctx}\n\n"
        "Write roughly 240 words of ONE continuous, organic, and evocative narration that builds "
        "to a crescendo. Deliver with the authentic passion of a seasoned broadcaster overlooking "
        "a packed, roaring stadium. Seamlessly use traditional British football terminology "
        "(e.g., 'pitch', 'gantry', 'absolute cracker', 'the terraces', 'breezed past'). "
        "Flow naturally through these sections, placing the EXACT marker at the start "
        "of each (markers are invisible to the listener — purely technical):\n\n"
        f"[SCENE:opener] — Fire-up: announce this clash with immense theatrical gravitas and its World Cup magnitude.\n"
        f"[SCENE:venue] — The stadium: {stadium['name']} in {stadium['city']}. Set the scene overlooking the roaring pitch, the host-nation energy, the scale of this arena under the floodlights.\n"
        f"[SCENE:group] — Group {group} stakes: outline the sweeping narrative stakes of what both teams need, weaving in the group context and the other sides.\n"
        f"[SCENE:home] — {home['name']}: Use search to ground their narrative. "
        f"Weave their recent qualification or warmup game results leading up to today ({today_s}) into a story of momentum. "
        f"Identify their key star player to watch for this upcoming game and explain "
        f"exactly why their specific strengths are the tactical key to unlocking the opponent.\n"
        f"[SCENE:away] — {away['name']}: Use search to ground their narrative. "
        f"Weave their recent qualification or warmup game results leading up to today ({today_s}) into a story of momentum. "
        f"Identify their key star player to watch for this upcoming game and explain "
        f"exactly why their specific strengths are the tactical key to unlocking the opponent.\n"
        f"[SCENE:kickoff] — The anticipation: build excitement and tension to a grand crescendo for what's to come "
        f"when these sides meet on {date_s}. Use future-tense — "
        f'"when they step out", "mark your calendars", "the world will be watching". '
        f"Do NOT say the whistle is about to blow or is minutes away.\n\n"
        "Critical: ONE unbroken monologue — no stilted transitions, no 'moving on to...', no list-reading. "
        "Maintain absolute consistency and a strong narrative through-line across the entire script. "
        "Write with flawless articulation and rich, resonant phrasing. "
        "No stage directions, no parenthetical hints, no brackets other than the "
        "[SCENE:x] markers themselves. Pure spoken English."
    )


class TeamFact(BaseModel):
    headline: str = Field(description="3-5 word catchy headline")
    fact: str = Field(description="2 sentences about their footballing identity, style, and strengths")


class TeamFacts(BaseModel):
    home: TeamFact
    away: TeamFact


class SpotlightPlayer(BaseModel):
    name: str = Field(description="Actual Star Player name")
    team: str = Field(description="Team name")
    position: str = Field(description="Player position")
    jersey: int = Field(description="Jersey number")
    highlight: str = Field(description="3-4 word badge describing the player highlight")
    fact: str = Field(description="1 sentence on why they matter or key details about them")


class MatchPregameInsight(BaseModel):
    team_facts: TeamFacts
    spotlights: list[SpotlightPlayer]


class CohesivePregameScript(BaseModel):
    full_script: str = Field(
        description="The complete, unbroken monologue narration script containing all requested [SCENE:id] markers in order. "
                    "Ensure absolute consistency and a strong narrative through-line across the entire script."
    )


async def generate_pregame_data(
    client: genai.Client, match: dict, use_cache: bool = True
) -> dict:
    """Generate + cache AI team facts for the pregame show visual scenes.

    Returns dict with: team_facts, group_teams.
    Caches to pregame_data_path so repeated calls are instant.
    """
    import json as _json

    cached = pregame_data_path(match["id"])
    if use_cache and cached.exists():
        try:
            return _json.loads(cached.read_text(encoding="utf-8"))
        except Exception:
            pass  # corrupted cache — regenerate

    home = match["home_team"]
    away = match["away_team"]
    group = match["group"]
    today_s = datetime.now().strftime("%B %d, %Y")

    prompt = (
        f"Generate pre-match insight data for this upcoming 2026 FIFA World Cup match: "
        f"{home['name']} vs {away['name']}, Group {group}.\n\n"
        f"Use Google Search grounded as of today ({today_s}) to fetch the most accurate "
        f"real-world roster, actual star players, their correct current positions, jersey numbers, "
        f"and key tactical details for both teams leading into the tournament."
    )

    data: dict = {"team_facts": {}, "spotlights": []}
    try:
        with _tracer.start_as_current_span("wc2026.generate_pregame_data") as span:
            span.set_attribute("llm.model", "gemini-3.5-flash")
            resp = await client.aio.models.generate_content(
                model="gemini-3.5-flash",
                contents=prompt,
                config=gtypes.GenerateContentConfig(
                    thinking_config=gtypes.ThinkingConfig(thinking_budget=0),
                    max_output_tokens=800,
                    tools=[gtypes.Tool(google_search=gtypes.GoogleSearch())],
                    response_mime_type="application/json",
                    response_schema=MatchPregameInsight,
                ),
            )
            if resp.usage_metadata:
                span.set_attribute("llm.prompt_tokens", resp.usage_metadata.prompt_token_count or 0)
                span.set_attribute("llm.output_tokens", resp.usage_metadata.candidates_token_count or 0)
                span.set_attribute("llm.total_tokens",  resp.usage_metadata.total_token_count or 0)
                record_tokens(resp.usage_metadata.prompt_token_count or 0, "input", "gemini-3.5-flash", "wc2026_pregame_data_generation")
                record_tokens(resp.usage_metadata.candidates_token_count or 0, "output", "gemini-3.5-flash", "wc2026_pregame_data_generation")

        if resp.parsed:
            data = resp.parsed.model_dump()
    except Exception:
        pass  # fall back to empty facts; front-end handles gracefully

    data["group_teams"] = _group_team_list(group)
    cached.write_text(_json.dumps(data), encoding="utf-8")
    return data


async def generate_pregame_stream(client: genai.Client, match: dict):
    """Like generate_preview_stream but uses build_pregame_prompt (future-tense kickoff).

    Caches to pregame_wav_path / pregame_meta_path, not the preview paths.
    """
    import re as _re
    from src.commentary import _synth, _to_wav, _clip_clean, SAMPLE_RATE, SAMPLE_WIDTH

    _GAP_SAMPS = round(0.70 * SAMPLE_RATE)

    home = match["home_team"]["name"]
    away = match["away_team"]["name"]

    yield f"data: Writing pre-match script for {home} vs {away}…\n\n"

    with _tracer.start_as_current_span("wc2026.generate_pregame_script") as span:
        span.set_attribute("llm.model", "gemini-3.5-flash")
        resp = await client.aio.models.generate_content(
            model="gemini-3.5-flash",
            contents=build_pregame_prompt(match),
            config=gtypes.GenerateContentConfig(
                thinking_config=gtypes.ThinkingConfig(thinking_budget=0),
                max_output_tokens=1200,
                tools=[gtypes.Tool(google_search=gtypes.GoogleSearch())],
                response_mime_type="application/json",
                response_schema=CohesivePregameScript,
            ),
        )
        if resp.usage_metadata:
            span.set_attribute("llm.prompt_tokens", resp.usage_metadata.prompt_token_count or 0)
            span.set_attribute("llm.output_tokens", resp.usage_metadata.candidates_token_count or 0)
            span.set_attribute("llm.total_tokens",  resp.usage_metadata.total_token_count or 0)
            record_tokens(resp.usage_metadata.prompt_token_count or 0, "input", "gemini-3.5-flash", "wc2026_pregame_script_generation")
            record_tokens(resp.usage_metadata.candidates_token_count or 0, "output", "gemini-3.5-flash", "wc2026_pregame_script_generation")

    full_text = ""
    if resp.parsed:
        full_text = resp.parsed.full_script.strip()
    if not full_text:
        yield "data: ERROR: script generation failed\n\n"
        return

    ids = SCENE_IDS
    pattern = r"\[SCENE:(" + "|".join(_re.escape(s) for s in ids) + r")\]"
    parts = _re.split(pattern, full_text)
    sections: dict[str, str] = {}
    i = 1
    while i + 1 < len(parts):
        sid, body = parts[i].strip(), parts[i + 1].strip()
        if sid in ids and body:
            sections[sid] = body
        i += 2

    missing = [s for s in ids if s not in sections]
    if missing:
        yield f"data: WARNING: missing sections {missing} — generating anyway\n\n"

    n = len(ids)
    clips: list[bytes] = []
    clip_meta: list[dict] = []
    cursor = 0

    for idx, sid in enumerate(ids):
        text = sections.get(sid, "")
        label = SCENE_LABELS[sid]
        if not text:
            yield f"data: Skipping {label} (no text)…\n\n"
            continue

        yield f"data: Synthesising {idx + 1}/{n}: {label}…\n\n"
        pcm = await _synth(client, text, label=f"pregame-{sid}")
        if not pcm:
            continue
        pcm = _clip_clean(pcm)
        pcm = pcm[: (len(pcm) // SAMPLE_WIDTH) * SAMPLE_WIDTH]

        clip_samps = len(pcm) // SAMPLE_WIDTH
        audio_start = cursor / SAMPLE_RATE
        audio_end = (cursor + clip_samps) / SAMPLE_RATE
        clip_meta.append(
            {
                "scene": sid,
                "label": label,
                "audio_start": round(audio_start, 3),
                "audio_end": round(audio_end, 3),
            }
        )
        clips.append(pcm)
        cursor += clip_samps

        if idx < n - 1:
            clips.append(b"\x00" * (_GAP_SAMPS * SAMPLE_WIDTH))
            cursor += _GAP_SAMPS

    if not clips:
        yield "data: ERROR: all TTS calls failed\n\n"
        return

    total_secs = cursor / SAMPLE_RATE
    wav = _to_wav(clips)
    meta = {"total_duration": round(total_secs, 3), "clips": clip_meta}
    yield f"data: Done — {len(wav) // 1024} KB · {total_secs:.1f}s\n\n"
    yield ("audio", wav, meta)
