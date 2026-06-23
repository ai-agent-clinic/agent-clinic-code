"""AI voice commentary — event-anchored synthesis with exact timestamp alignment.

Architecture
------------
One TTS clip is generated per key match moment. Each clip is placed at exactly

    audio_second = (moment_minute / 90) * total_audio_seconds

via PCM silence padding. This is the ONLY way to guarantee sync: a range-based
approach lets the AI decide where within a segment to mention an event, which
is always wrong. Here, each clip is ABOUT a specific moment and STARTS at that
moment's exact timestamp — mathematical accuracy is structural, not prompt-based.

Assembly
--------
  [silence → clip₀ → silence → clip₁ → ... → silence → clipₙ → silence (tail)]

Silence between clips = natural atmosphere/crowd noise gap.
"""

import asyncio
import io
import wave
from pathlib import Path

from google import genai
from google.genai import types as gtypes
from opentelemetry import trace as _otel_trace
from src.telemetry import record_tokens
from pydantic import BaseModel, Field


class MatchCommentaryScript(BaseModel):
    full_script: str = Field(
        description="The complete, unbroken live football commentary script containing all requested [MOMENT:kind@minute] markers in order. "
                    "Ensure absolute consistency and a strong narrative through-line across the entire match timeline."
    )



_tracer = _otel_trace.get_tracer(__name__)

MODEL = "gemini-3.5-flash"

TTS_MODEL = "gemini-3.1-flash-tts-preview"
TTS_VOICE = "Charon"
SAMPLE_RATE = 24000
SAMPLE_WIDTH = 2  # 16-bit PCM mono

# Fraction of available gap used for speech. 1.0 would fill every second;
# 0.65 leaves 35 % as natural silence before the next moment begins.
FILL_FACTOR = 0.65

# No two moments closer than this many match minutes (prevents overlapping clips)
MIN_MATCH_GAP = 3.0

_CACHE_DIR = Path(__file__).parent.parent / ".commentary_cache"
_CACHE_DIR.mkdir(exist_ok=True)

# Event types that carry no tactical information — excluded from build-up context
_CTX_NOISE = {
    "Ball Receipt*",
    "Starting XI",
    "Half Start",
    "Half End",
    "Referee Ball-Drop",
    "Camera On",
    "50/50",
}


# ── Tactical context helpers ──────────────────────────────────────────────────


def _zone(x, y) -> str:
    """Convert StatsBomb pitch coords (x 0–120, y 0–80) to readable zone string."""
    if x is None:
        return "midfield"
    if x > 102 and y is not None and 24 < y < 56:
        return "in the six-yard box"
    if x > 88 and y is not None and 18 < y < 62:
        return "inside the penalty area"
    if x > 80:
        lat = (
            "left channel"
            if (y or 40) < 30
            else ("right channel" if (y or 40) > 50 else "central")
        )
        return f"in the final third, {lat}"
    if x > 60:
        lat = "left" if (y or 40) < 30 else ("right" if (y or 40) > 50 else "central")
        return f"in midfield, {lat}"
    if x > 40:
        return "in their own half"
    return "deep in their own half"


def _fmt_ctx_events(events: list[dict]) -> str:
    """Render a list of events as a numbered tactical build-up log."""
    lines = []
    for e in events:
        if e.get("type") in _CTX_NOISE:
            continue
        typ = e.get("type", "")
        player = e.get("player") or "?"
        team = e.get("team") or ""
        x, y = e.get("location_x"), e.get("location_y")
        zone = _zone(x, y)

        if typ == "Pass":
            recip = e.get("pass_recipient") or ""
            if isinstance(recip, dict):
                recip = recip.get("name") or ""
            outcome = e.get("pass_outcome") or ""
            bad = f" ({outcome})" if outcome and outcome not in ("Complete", "") else ""
            length = e.get("pass_length")
            lstr = f", {int(length)}y" if length else ""
            to_str = f" → {recip}" if recip else ""
            lines.append(f"{player} ({team}): Pass{to_str}{lstr} {zone}{bad}")
        elif typ == "Carry":
            ex = e.get("end_location_x") or e.get("carry_end_location_x")
            ey = e.get("end_location_y") or e.get("carry_end_location_y")
            ez = _zone(ex, ey)
            lines.append(f"{player} ({team}): Drives with ball {zone} → {ez}")
        elif typ == "Shot":
            xg = e.get("shot_xg") or 0
            out = e.get("shot_outcome") or ""
            tech = e.get("shot_technique") or ""
            lines.append(f"{player} ({team}): {tech} shot {zone} → {out} (xG {xg:.2f})")
        elif typ in (
            "Dribble",
            "Interception",
            "Ball Recovery",
            "Pressure",
            "Clearance",
            "Block",
            "Error",
        ):
            lines.append(f"{player} ({team}): {typ} {zone}")
        elif typ == "Foul Committed":
            card = e.get("foul_committed_card") or ""
            cstr = f" [{card}]" if card else ""
            lines.append(f"{player} ({team}): Foul{cstr} {zone}")
        elif typ == "Goalkeeper":
            action = e.get("goalkeeper_type") or "action"
            lines.append(f"{player} ({team}): GK {action} {zone}")
        else:
            lines.append(f"{player} ({team}): {typ} {zone}")

    return "\n".join(f"  {l}" for l in lines)


# ── PCM helpers ───────────────────────────────────────────────────────────────


def _silence(secs: float) -> bytes:
    # round() then * SAMPLE_WIDTH guarantees even byte count (sample-aligned).
    return b"\x00" * (max(0, round(secs * SAMPLE_RATE)) * SAMPLE_WIDTH)


def _trim(pcm: bytes, max_secs: float) -> bytes:
    # Round down to a sample boundary so we never truncate mid-sample.
    n_samples = int(max_secs * SAMPLE_RATE)
    return pcm[: n_samples * SAMPLE_WIDTH]


def _dur(pcm: bytes) -> float:
    return len(pcm) / (SAMPLE_RATE * SAMPLE_WIDTH)


def _to_wav(chunks: list[bytes]) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(b"".join(chunks))
    return buf.getvalue()


# ── Moment selection ──────────────────────────────────────────────────────────

_SHOT_PRIORITY = {
    "Goal": 0,
    "Saved": 1,
    "Saved To Post": 1,
    "Post": 2,
    "Blocked": 3,
}


def _select_moments(match_events: list[dict], mode: str = "full") -> list[dict]:
    """Return a list of key moments sorted by minute.

    Fixed anchors (intro, halftime, fulltime) are always included.
    Dynamic events (goals, on-target shots, cards) are added when they fit
    the MIN_MATCH_GAP constraint.

    mode="quick"  — top 2 dynamic events only (~5 clips total, ~3–4 min audio)
    mode="full"   — all qualifying dynamic events (~8–10 clips, ~7–9 min audio)
    """
    # Fixed anchors — always present, highest priority.
    # fulltime at minute 87 (not 90) so it has speaking room before the file ends.
    moments: list[dict] = [
        {"minute": 0, "kind": "intro", "priority": -1},
        {"minute": 45, "kind": "halftime", "priority": -1},
        {"minute": 87, "kind": "fulltime", "priority": -1},
    ]

    # Collect dynamic candidates
    candidates: list[dict] = []
    for e in match_events:
        minute = e.get("minute") or 0
        etype = e.get("type", "")
        outcome = e.get("shot_outcome", "")

        if minute <= 0 or minute >= 89:
            continue

        if etype == "Shot" and outcome in _SHOT_PRIORITY:
            candidates.append(
                {
                    "minute": minute,
                    "kind": "goal" if outcome == "Goal" else "shot",
                    "priority": _SHOT_PRIORITY[outcome],
                    "event": e,
                }
            )
        elif etype == "Foul Committed" and e.get("foul_committed_card"):
            candidates.append(
                {
                    "minute": minute,
                    "kind": "card",
                    "priority": 5,
                    "event": e,
                }
            )

    # Sort by importance then time; insert each only if it respects MIN_MATCH_GAP
    candidates.sort(key=lambda x: (x["priority"], x["minute"]))

    # Quick mode: cap at 2 dynamic events (the two most significant moments)
    if mode == "quick":
        candidates = candidates[:2]

    for c in candidates:
        min_dist = min(abs(c["minute"] - m["minute"]) for m in moments)
        if min_dist >= MIN_MATCH_GAP:
            moments.append(c)

    moments.sort(key=lambda m: m["minute"])

    # Attach build-up context: last 8 tactical events in the 4 minutes before each moment
    for m in moments:
        ctx = [
            e
            for e in match_events
            if 0 < (m["minute"] - (e.get("minute") or 0)) <= 4
            and e.get("type") not in _CTX_NOISE
        ]
        m["context_events"] = ctx[-8:]

    return moments


# ── Unified script generation ─────────────────────────────────────────────────


def _moment_desc(m: dict) -> str:
    """One-line tactical brief for a moment, embedded in the unified prompt."""
    kind = m["kind"]
    minute = m["minute"]
    e = m.get("event", {})
    ctx = _fmt_ctx_events(m.get("context_events", []))
    ctx_block = (
        "\n  Build-up:\n" + "\n".join("    " + l for l in ctx.splitlines())
        if ctx
        else ""
    )

    if kind == "intro":
        return (
            f"[MOMENT:intro@{minute}] — The match kicked off. Morocco structured a 4-1-4-1 low block, "
            "with Amrabat as a single pivot cutting the passing lane to Fernandes. Deconstruct the initial "
            f"tactical organization and shape of both teams.{ctx_block}"
        )
    if kind == "goal":
        player = e.get("player") or "Youssef En-Nesyri"
        xg = e.get("shot_xg") or 0.13
        tech = e.get("shot_technique") or "Header"
        zone = _zone(e.get("location_x"), e.get("location_y"))
        return (
            f"[MOMENT:goal@{minute}] — Goal analysis: {player} ({tech} {zone}, xG {xg:.2f}). "
            "Tactical review: dissect the diagonal run that beat the defensive line, how Morocco's shape "
            f"created space, and the defensive breakdown in Portugal's structure.{ctx_block}"
        )
    if kind == "halftime":
        return (
            f"[MOMENT:halftime@{minute}] — Half-time tactical analysis (Morocco 1–0 Portugal). "
            "Focus on the structural dynamics: Amrabat's pivot dominance, Portugal's failure to "
            f"penetrate Morocco's compact lines, and the tactical options for Fernando Santos.{ctx_block}"
        )
    if kind == "fulltime":
        return (
            f"[MOMENT:fulltime@{minute}] — Full-time tactical post-mortem (Morocco 1–0 Portugal). "
            "Deconstruct how Morocco's low block successfully choked spaces, Amrabat's midfield control, "
            f"and the structural blueprint of this historic defensive masterclass.{ctx_block}"
        )
    if kind == "shot":
        player = e.get("player") or "Unknown"
        team = e.get("team") or ""
        outcome = e.get("shot_outcome") or ""
        tech = e.get("shot_technique") or ""
        xg = e.get("shot_xg") or 0
        zone = _zone(e.get("location_x"), e.get("location_y"))
        out_desc = {
            "Saved": "saved",
            "Saved To Post": "saved onto the post",
            "Post": "woodwork",
            "Blocked": "blocked",
        }.get(outcome, "off target")
        return (
            f"[MOMENT:shot@{minute}] — Shot analysis: {player} ({team}) attempted a {tech} {zone} resulting in {out_desc} "
            f"(xG {xg:.2f}). Deconstruct the tactical sequence: the off-the-ball movement that created "
            f"the space, the passing lane that was exploited, and the defensive response.{ctx_block}"
        )
    if kind == "card":
        player = e.get("player") or "Unknown"
        team = e.get("team") or ""
        card = e.get("foul_committed_card") or "Yellow Card"
        zone = _zone(e.get("location_x"), e.get("location_y"))
        return (
            f"[MOMENT:card@{minute}] — Tactical caution: {card} shown to {player} ({team}) {zone}. "
            "Tactical context: analyze if this was a cynical press-trigger, a structural foul, or a defensive "
            f"breakdown, and how this booking affected the team's pressing structure.{ctx_block}"
        )
    return f"[MOMENT:{kind}@{minute}] — Tactical moment at minute {minute}."


def _build_script_prompt(moments: list[dict], target_words: int) -> str:
    """Build the unified ONE-SCRIPT prompt with [MOMENT:kind@minute] markers."""
    sections = "\n\n".join(_moment_desc(m) for m in moments)
    return (
        "You are a football tactical analyst providing a retrospective breakdown on a BBC radio podcast — analytically "
        "precise, deeply knowledgeable, and genuinely passionate. You are reflecting on the historic "
        "2022 Football Championship quarter-final: Morocco vs Portugal (which Morocco won 1–0).\n\n"
        f"Write roughly {target_words} words of ONE continuous, organic, and in-depth retrospective tactical review "
        "covering the full match. Flow naturally through these key moments in order, "
        "placing the EXACT marker shown at the start of each section (the markers are invisible "
        "to the listener — they are purely technical section dividers):\n\n"
        f"{sections}\n\n"
        "For each section, explain the TACTICAL INTENT: WHY players made specific movements, "
        "WHAT the team shape was trying to create or deny, HOW a defensive structure was "
        "exploited or held firm. Make statements like ‘X did Y explicitly so that Z could "
        "happen.’ Use specific player names, pitch zones, and xG data from the build-up "
        "context when given. Focus strictly on deep tactical analysis (such as formations, pressing schemes, "
        "spaces, and transitions) rather than play-by-play action commentary.\n\n"
        "Critical: this must sound like ONE unbroken, podcast-style tactical breakdown — no stilted transitions, "
        "no ‘moving on to…’, no list-reading, and no play-by-play live action commentary. Maintain a narrative "
        "focused on structural analysis and tactical precision throughout. Maintain absolute consistency and a "
        "strong narrative through-line across the entire match timeline. No stage directions, no parenthetical "
        "hints, no brackets other than the [MOMENT:x@y] markers themselves. Pure spoken English, past tense. "
        "Do NOT include the words 'FIFA' or 'World Cup' anywhere in the generated script under any circumstances."
    )


# _parse_moment_sections is deprecated, parsing is handled natively by the SDK response.parsed property.


def _walk_wav_chunks(data: bytes):
    """Yield (chunk_id, body_bytes) for every chunk in a WAV file."""
    i = 12  # skip RIFF(4) + file-size(4) + WAVE(4)
    while i + 8 <= len(data):
        chunk_id = data[i : i + 4]
        chunk_size = int.from_bytes(data[i + 4 : i + 8], "little")
        body = data[i + 8 : i + 8 + chunk_size]
        yield chunk_id, body
        i += 8 + chunk_size + (chunk_size & 1)  # WAV chunks are word-aligned


def _parse_wav_fmt(data: bytes):
    """Return (audio_format, channels, sample_rate, bits_per_sample) from fmt chunk, or None."""
    for chunk_id, body in _walk_wav_chunks(data):
        if chunk_id == b"fmt " and len(body) >= 16:
            audio_format = int.from_bytes(body[0:2], "little")
            channels = int.from_bytes(body[2:4], "little")
            rate = int.from_bytes(body[4:8], "little")
            bits = int.from_bytes(body[14:16], "little")
            return audio_format, channels, rate, bits
    return None


def _find_wav_data_chunk(data: bytes) -> bytes:
    """Return raw bytes of the WAV 'data' sub-chunk, or b'' if not found."""
    for chunk_id, body in _walk_wav_chunks(data):
        if chunk_id == b"data":
            return body
    return b""


def _extract_pcm(data: bytes) -> bytes:
    """Return raw mono 16-bit 24 kHz PCM from one inline_data blob.

    Every failure mode that can produce loud noise is explicitly guarded:

    1. Multi-part WAV blobs: call this per-part before joining (caller's job).
    2. WAV with fact/WAVEFORMATEXTENSIBLE header: _walk_wav_chunks() finds the
       'data' chunk regardless of header size — never a fixed-offset skip.
    3. WAV fallback validates the fmt chunk FIRST. Returning a data chunk from
       an ADPCM, float, or extensible WAV as if it were raw 16-bit PCM is what
       causes the worst noise; we return b'' instead.
    4. Stereo output: down-mixed to mono.
    5. Stray prefix before RIFF: align to RIFF within first 16 bytes.
    6. Known compressed formats: rejected by magic bytes before any decode.
    7. Odd-length raw-PCM blob: trimmed to sample boundary — an odd byte shifts
       every subsequent 16-bit sample by one byte (cascade misalignment noise).
    """
    import struct as _struct

    if not data:
        return b""

    # Reject blobs that are definitely compressed (can't be treated as raw PCM).
    if data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return b""  # MP3
    if data[:4] in (b"OggS", b"fLaC"):
        return b""  # Ogg / FLAC

    # Align to RIFF if there are a few stray prefix bytes.
    riff_pos = data.find(b"RIFF", 0, 16)
    if 0 < riff_pos < 16:
        data = data[riff_pos:]

    if data[:4] != b"RIFF":
        # Raw LINEAR16 PCM — enforce sample boundary (odd length → misalignment).
        return data if len(data) % SAMPLE_WIDTH == 0 else data[:-1]

    try:
        import io as _io, wave as _wave

        with _wave.open(_io.BytesIO(data)) as wf:
            if wf.getsampwidth() != SAMPLE_WIDTH:
                return b""  # not 16-bit — refuse to guess
            frames = wf.readframes(wf.getnframes())
            if wf.getnchannels() == 2:  # stereo → mono
                n = len(frames) // 4
                pairs = _struct.unpack(f"<{n * 2}h", frames)
                frames = _struct.pack(
                    f"<{n}h",
                    *(
                        max(-32768, min(32767, (pairs[i * 2] + pairs[i * 2 + 1]) // 2))
                        for i in range(n)
                    ),
                )
            return frames
    except Exception:
        # wave.open() rejected this WAV variant (ADPCM, IEEE float, extensible…).
        # CRITICAL: do NOT blindly extract the data chunk — its bytes are encoded,
        # not raw 16-bit PCM.  Validate the fmt chunk first; return b'' if in doubt.
        fmt = _parse_wav_fmt(data)
        if fmt is None:
            return b""
        audio_format, channels, rate, bits = fmt
        if audio_format != 1 or bits != SAMPLE_WIDTH * 8:
            return b""  # not WAVE_FORMAT_PCM or not 16-bit
        raw = _find_wav_data_chunk(data)
        # Stereo fallback: down-mix manually if needed.
        if channels == 2 and len(raw) % 4 == 0:
            n = len(raw) // 4
            pairs = _struct.unpack(f"<{n * 2}h", raw)
            raw = _struct.pack(
                f"<{n}h",
                *(
                    max(-32768, min(32767, (pairs[i * 2] + pairs[i * 2 + 1]) // 2))
                    for i in range(n)
                ),
            )
        elif channels != 1:
            return b""  # unexpected channel count
        return raw if len(raw) % SAMPLE_WIDTH == 0 else raw[:-1]


# Compressed MIME types that cannot be decoded as raw PCM without a library.
_COMPRESSED_AUDIO_MIME = {
    "audio/mpeg",
    "audio/mp3",
    "audio/ogg",
    "audio/opus",
    "audio/flac",
    "audio/aac",
    "audio/aiff",
}


def _clip_clean(pcm: bytes) -> bytes:
    """Strip leading breath/silence artifacts then apply fade-in and fade-out.

    Root cause of the 'blowing / catching breath' artifact
    -------------------------------------------------------
    The Charon TTS voice (and neural TTS in general) synthesises a short
    breath intake before speech — typically 50–300 ms of low-to-moderate
    amplitude broadband noise.  Because each clip begins right after a block
    of PCM silence, that breath plays at full volume the moment the silence
    ends, which sounds like 'blowing into the mic'.

    A 30 ms fade-in only covers 30 ms; a 200 ms breath still plays at full
    volume from ms 30 onwards.  The solution is to locate the first 30 ms
    window whose RMS exceeds a speech-level threshold and trim everything
    before a short pre-roll (20 ms) back from that point.  The 80 ms
    fade-in then smooths any residual edge left after the trim.

    Timing is not affected: the silence padding before each clip is what
    determines when it starts, not the clip's own first sample.  Stripping
    a 200 ms breath just means the clip starts 200 ms later inside its
    silence gap — the gap is always large enough to absorb this.
    """
    import struct as _struct

    n_samples = len(pcm) // SAMPLE_WIDTH
    if not n_samples:
        return pcm

    WIN = int(SAMPLE_RATE * 0.030)  # 30 ms analysis window (720 samples)
    HOP = WIN // 3  # 10 ms hop between windows
    LIMIT = int(SAMPLE_RATE * 0.500)  # never strip more than 500 ms
    ROLL = int(SAMPLE_RATE * 0.020)  # keep 20 ms before detected onset
    # −28 dBFS ≈ 1035 (out of 32 767).  Speech is typically > −20 dBFS ≈ 3277.
    # This threshold skips silence and quiet breath sounds without cutting speech.
    THRESH = 1200

    onset = 0  # default: no stripping
    i = 0
    while i + WIN <= min(n_samples, LIMIT):
        chunk = pcm[i * SAMPLE_WIDTH : (i + WIN) * SAMPLE_WIDTH]
        samples = _struct.unpack(f"<{WIN}h", chunk)
        rms = int((sum(s * s for s in samples) / WIN) ** 0.5)
        if rms > THRESH:
            onset = max(0, i - ROLL)
            break
        i += HOP

    pcm = pcm[onset * SAMPLE_WIDTH :]
    n_samples = len(pcm) // SAMPLE_WIDTH

    # 80 ms fade-in: long enough to taper any residual artifact after the trim,
    # short enough that it's inaudible on real speech content.
    # 30 ms fade-out: prevents a click at the hard clip boundary.
    N_IN = int(SAMPLE_RATE * 0.080)
    N_OUT = int(SAMPLE_RATE * 0.030)
    if n_samples < N_IN + N_OUT + 1:
        return pcm

    arr = bytearray(pcm)
    for i in range(N_IN):
        gain = i / N_IN
        off = i * SAMPLE_WIDTH
        val = _struct.unpack_from("<h", arr, off)[0]
        _struct.pack_into("<h", arr, off, int(val * gain))
    for i in range(N_OUT):
        gain = i / N_OUT
        off = (n_samples - 1 - i) * SAMPLE_WIDTH
        val = _struct.unpack_from("<h", arr, off)[0]
        _struct.pack_into("<h", arr, off, int(val * gain))

    return bytes(arr)


async def _synth(
    client: genai.Client, text: str, label: str = "", voice: str = TTS_VOICE
) -> bytes:
    """Call TTS API with up to 3 retries on transient 5xx errors.

    Returns b"" on permanent failure so the assembly loop skips this clip
    gracefully instead of crashing the entire SSE stream.
    """
    import asyncio as _asyncio
    from google.genai import errors as _gerrors

    with _tracer.start_as_current_span("commentary.tts_synth") as span:
        span.set_attribute("tts.model", TTS_MODEL)
        span.set_attribute("tts.voice", voice)
        if label:
            span.set_attribute("tts.label", label)

        prompt = f"""
**Audio Profile:** A seasoned, authoritative, and evocative English football commentator and master storyteller. Wordsmith-like, charismatic, and deeply passionate, bringing a rich, dramatic broadcast presence that commands the gantry. Think the gravitas of Peter Drury mixed with the traditional cadence of Martin Tyler or John Motson.  
**Scene:** An electric, high-stakes atmosphere in a premium broadcasting gantry, overlooking a packed, roaring historic stadium under the floodlights, surrounded by the deafening hum of passionate fans.  
**Director's Notes:**

* Style: Authoritative, poetic, and deeply dramatic. Captures the natural gravitas and elevated vocabulary of a classic British broadcaster. Deliver with the authentic passion of a commentator who treats "the beautiful game" like a grand theater production—weaving tactical insight with sweeping narrative arcs.  
* Pacing & Cadence: A masterclass in cadence and the "crescendo." Calm, measured, and observational during the build-up play, but rising sharply in pitch, energy, and volume as the action enters the final third. Explode with controlled, throat-tingling passion for key moments (goals, near-misses), followed by brief, meaningful pauses to let the stadium atmosphere breathe. Never rushed; always rhythmic.  
* Accent & Vocabulary: An authentic British broadcast accent (Standard Southern British / RP, or a warm, authoritative regional tone like a North-West or Yorkshire grit). Flawless articulation with a rich, resonant timbre. Seamlessly uses traditional English football terminology (e.g., *"pitch," "gantry," "absolute cracker," "the terraces," "breezed past"*).

**Transcript:**  
{text}
        """

        last_exc: Exception | None = None
        resp = None
        attempts = 0
        for attempt in range(3):
            attempts = attempt + 1
            try:
                resp = await client.aio.models.generate_content(
                    model=TTS_MODEL,
                    contents=prompt,
                    config=gtypes.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=gtypes.SpeechConfig(
                            language_code="en-US",
                            voice_config=gtypes.VoiceConfig(
                                prebuilt_voice_config=gtypes.PrebuiltVoiceConfig(
                                    voice_name=voice
                                )
                            ),
                        ),
                    ),
                )
                break  # success — exit retry loop
            except _gerrors.ServerError as exc:
                last_exc = exc
                if attempt < 2:
                    await _asyncio.sleep(2**attempt)  # 1 s, then 2 s back-off
                continue
            except Exception as exc:
                last_exc = exc
                break  # non-retryable — give up now
        else:
            # All retries exhausted
            span.set_attribute("tts.attempts", attempts)
            span.set_attribute("tts.pcm_bytes", 0)
            return b""

        span.set_attribute("tts.attempts", attempts)

        if last_exc is not None and not resp:
            span.set_attribute("tts.pcm_bytes", 0)
            return b""

        if resp.usage_metadata:
            span.set_attribute(
                "llm.prompt_tokens", resp.usage_metadata.prompt_token_count or 0
            )
            span.set_attribute(
                "llm.output_tokens", resp.usage_metadata.candidates_token_count or 0
            )
            span.set_attribute(
                "llm.total_tokens", resp.usage_metadata.total_token_count or 0
            )
            record_tokens(
                resp.usage_metadata.prompt_token_count or 0,
                "input",
                TTS_MODEL,
                "audio_synthesis",
            )
            record_tokens(
                resp.usage_metadata.candidates_token_count or 0,
                "output",
                TTS_MODEL,
                "audio_synthesis",
            )

        # Extract PCM from EACH part independently before joining — joining first
        # lets WAV2's header bleed into WAV1's sample data (burst of loud noise).
        # Filter by MIME type so non-audio inline_data blobs are never treated
        # as raw PCM (some API responses include metadata blobs alongside audio).
        pcm_parts: list[bytes] = []
        for p in resp.candidates[0].content.parts:
            if not (p.inline_data and p.inline_data.data):
                continue
            mt = (p.inline_data.mime_type or "").lower().split(";")[0].strip()
            if mt and not mt.startswith("audio/"):
                continue  # not audio at all — skip
            if mt in _COMPRESSED_AUDIO_MIME:
                continue  # compressed — can't decode as PCM
            pcm_parts.append(_extract_pcm(p.inline_data.data))

        result = _clip_clean(b"".join(pcm_parts))
        span.set_attribute("tts.pcm_bytes", len(result))
        return result


# ── Main generator ────────────────────────────────────────────────────────────

# Proportional gap: ms of silence per match-minute between clips.
# Raise _GAP_MS_PER_MIN to slow the brief down; lower it to speed it up.
# _GAP_MAX_SECS is set high enough that it only kicks in for extreme jumps —
# at the default 450 ms/min even a 40-min gap is only 18 s, well under the cap.
_GAP_MS_PER_MIN = 600
_GAP_MIN_SECS = 2.0
_GAP_MAX_SECS = 60.0


async def generate_commentary_stream(
    client: genai.Client,
    match_events: list[dict],
    mode: str = "full",
):
    """Yield SSE progress strings, then a final ('audio', wav_bytes, meta) tuple.

    Architecture:
      1. Generate ONE cohesive script with [MOMENT:kind@minute] section markers.
      2. Split at markers → N text sections (no forced word counts per section).
      3. Synthesise each section → actual PCM; measure real durations.
      4. Assemble with a proportional silence gap (450 ms per match-minute) between clips.
      5. Emit clip-timing metadata so the frontend can map audio time → match minute.

    The audio duration drives the visual timeline, not vice versa — so no clip
    is ever cut off and the voice always finishes naturally before the next begins.

    mode="quick" — top 2 dynamic events + anchors; ~35 words/moment
    mode="full"  — all qualifying events + anchors; ~55 words/moment
    """
    moments = _select_moments(match_events, mode=mode)
    n = len(moments)
    # Word target guides the LLM's depth per section; final audio length is organic.
    words_per_moment = 35 if mode == "quick" else 55
    target_words = max(60, n * words_per_moment)

    yield f"data: {n} moments — writing {mode} brief ({target_words} words)…\n\n"

    with _tracer.start_as_current_span("commentary.gen_script") as span:
        span.set_attribute("llm.model", MODEL)
        span.set_attribute("llm.target_words", target_words)
        resp = await client.aio.models.generate_content(
            model=MODEL,
            contents=_build_script_prompt(moments, target_words),
            config=gtypes.GenerateContentConfig(
                thinking_config=gtypes.ThinkingConfig(thinking_budget=0),
                max_output_tokens=2500,
                response_mime_type="application/json",
                response_schema=MatchCommentaryScript,
            ),
        )
        if resp.usage_metadata:
            span.set_attribute(
                "llm.prompt_tokens", resp.usage_metadata.prompt_token_count or 0
            )
            span.set_attribute(
                "llm.output_tokens", resp.usage_metadata.candidates_token_count or 0
            )
            record_tokens(
                resp.usage_metadata.prompt_token_count or 0,
                "input",
                MODEL,
                "commentary_script_generation",
            )
            record_tokens(
                resp.usage_metadata.candidates_token_count or 0,
                "output",
                MODEL,
                "commentary_script_generation",
            )

    full_script = ""
    if resp.parsed:
        full_script = resp.parsed.full_script.strip()
    if not full_script:
        yield "data: ERROR: script generation failed\n\n"
        return

    # Split at [MOMENT:kind@minute] markers
    import re as _re
    ids = [f"{m['kind']}@{m['minute']}" for m in moments]
    pattern = r"\[MOMENT:(" + "|".join(_re.escape(s) for s in ids) + r")\]"
    cleaned = _re.sub(r"\[MOMENT:([^\]]+)\]\s*\(~?\d+\s*words?\)", r"[MOMENT:\1]", full_script)
    parts = _re.split(pattern, cleaned.strip())
    result_map: dict[str, str] = {}
    i = 1
    while i + 1 < len(parts):
        mid = parts[i].strip()
        body = parts[i + 1].strip()
        if mid in ids and body:
            result_map[mid] = body
        i += 2
    section_texts = [result_map.get(f"{m['kind']}@{m['minute']}", "") for m in moments]

    # Synthesise each section in parallel and assemble — clip durations are the source of truth.
    # All byte arithmetic uses integer sample counts to guarantee PCM alignment.
    assembled: list[bytes] = []
    clip_meta: list[dict] = []
    cursor_samps = 0  # running total in samples

    yield f"data: Synthesising {n} moments in parallel…\n\n"

    async def synth_one(idx, m, text):
        label = f"{m['kind']} @ {m['minute']}'"
        if not text:
            return idx, b""
        try:
            pcm = await _synth(client, text, label=label)
            return idx, pcm
        except Exception:
            return idx, b""

    tasks = {
        asyncio.create_task(synth_one(idx, m, text)): (idx, m)
        for idx, (m, text) in enumerate(zip(moments, section_texts))
    }

    pcm_results = [b""] * n
    for fut in asyncio.as_completed(tasks.keys()):
        idx, pcm = await fut
        m = moments[idx]
        label = f"{m['kind']} @ {m['minute']}'"
        if not pcm:
            yield f"data: ⚠ {label} — synthesis failed or returned no audio\n\n"
        else:
            yield f"data: Synthesised {label} ({len(pcm) // 1024} KB)\n\n"
        pcm_results[idx] = pcm

    for i, (m, pcm) in enumerate(zip(moments, pcm_results)):
        label = f"{m['kind']} @ {m['minute']}'"
        if not pcm:
            # Skip if synthesis failed or yielded no text
            continue

        # Byte-align (defensive — _synth should already guarantee this)
        pcm = pcm[: (len(pcm) // SAMPLE_WIDTH) * SAMPLE_WIDTH]
        clip_samps = len(pcm) // SAMPLE_WIDTH

        audio_start = cursor_samps / SAMPLE_RATE
        audio_end = (cursor_samps + clip_samps) / SAMPLE_RATE

        clip_meta.append(
            {
                "kind": m["kind"],
                "minute": m["minute"],
                "audio_start": round(audio_start, 3),
                "audio_end": round(audio_end, 3),
            }
        )

        assembled.append(pcm)
        cursor_samps += clip_samps

        # Proportional silence gap — scales with match-minute distance to the next clip
        if i < n - 1:
            next_minute = moments[i + 1]["minute"]
            minute_diff = max(0, next_minute - m["minute"])
            gap_secs = min(
                _GAP_MAX_SECS, max(_GAP_MIN_SECS, minute_diff * _GAP_MS_PER_MIN / 1000)
            )
            gap_samples = round(gap_secs * SAMPLE_RATE)
            assembled.append(b"\x00" * (gap_samples * SAMPLE_WIDTH))
            cursor_samps += gap_samples

    total_secs = cursor_samps / SAMPLE_RATE
    wav = _to_wav(assembled)
    meta = {"total_duration": round(total_secs, 3), "clips": clip_meta}

    yield f"data: Done — {len(wav) // 1024} KB, {total_secs:.1f}s ready\n\n"
    yield ("audio", wav, meta)


# ── Cache helpers ─────────────────────────────────────────────────────────────


def cache_path(mode: str) -> Path:
    return _CACHE_DIR / f"brief_{mode}.wav"


def cache_meta_path(mode: str) -> Path:
    return _CACHE_DIR / f"brief_{mode}_meta.json"


def cache_script_path(mode: str) -> Path:
    return _CACHE_DIR / f"brief_{mode}_script.txt"


def cache_script_path(duration_minutes: float) -> Path:
    return _CACHE_DIR / f"commentary_{duration_minutes:.1f}min.txt"
