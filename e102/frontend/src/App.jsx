import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import Pitch from './components/Pitch.jsx';
import Timeline from './components/Timeline.jsx';
import EventOverlay from './components/EventOverlay.jsx';
import AgentPanel from './components/AgentPanel.jsx';
import CommentaryModal from './components/CommentaryModal.jsx';
import Waveform from './components/Waveform.jsx';
import StatsPanel from './components/StatsPanel.jsx';
import PreGame from './components/PreGame.jsx';
import Landing from './components/Landing.jsx';

const SPEEDS       = [1500, 750];
const SPEED_LABELS = ['×1', '×2'];

export default function App() {
  // 'landing' → hub; 'pregame' → cinematic intro; 'match' → normal match view
  const [appPhase, setAppPhase] = useState('landing');

  const [currentMinute,  setCurrentMinute]  = useState(0);
  const [tlData,         setTlData]         = useState([]);
  const [keyEvents,      setKeyEvents]      = useState([]);
  const [goals,          setGoals]          = useState([]);
  const [lineupsByName,  setLineupsByName]  = useState({});
  const [matchStats,     setMatchStats]     = useState(null);
  const [playing,        setPlaying]        = useState(false);
  const [speedIdx,       setSpeedIdx]       = useState(0);
  const [activeOverlay,  setActiveOverlay]  = useState(null);
  const [agentContext,   setAgentContext]   = useState(null);

  // Commentary
  const [showCommentaryModal, setShowCommentaryModal] = useState(false);
  const [commentaryActive,    setCommentaryActive]    = useState(false);
  const [audioTotalSecs,      setAudioTotalSecs]      = useState(null);
  const [commentaryMeta,      setCommentaryMeta]      = useState(null); // [{kind,minute,audio_start,audio_end}]

  const playIntervalRef  = useRef(null);
  const mediaRafRef      = useRef(null);
  const currentMinuteRef = useRef(0);
  const seekSerialRef    = useRef(0);
  const prevMinuteRef    = useRef(-1);

  // Audio — decoupled from React state, managed imperatively
  const audioRef    = useRef(null);
  const actxRef     = useRef(null);
  const analyserRef = useRef(null);

  useEffect(() => {
    currentMinuteRef.current = currentMinute;
  }, [currentMinute]);

  // ── Init data (starts loading immediately in background) ─────────────────
  useEffect(() => {
    async function fetchInit() {
      const [r1, r2, r3, r4] = await Promise.all([
        fetch('/api/timeline'),
        fetch('/api/key-events'),
        fetch('/api/lineups'),
        fetch('/api/match-stats'),
      ]);
      const [timeline, keys, lineups, stats] = await Promise.all([
        r1.json(), r2.json(), r3.json(), r4.json()
      ]);
      setTlData(timeline);
      setKeyEvents(keys);
      setGoals(keys.filter(e => e.shot_outcome === 'Goal').map(e => ({ team: e.team, minute: e.minute ?? 0 })));
      const byName = {};
      for (const [team, players] of Object.entries(lineups))
        for (const p of players) byName[p.player_name] = { jersey: p.jersey_number, position: p.position, team };
      setLineupsByName(byName);
      setMatchStats(stats);
    }
    fetchInit().catch(console.error);
  }, []);

  // ── Audio helpers ─────────────────────────────────────────────────────────
  function ensureAudio() {
    if (audioRef.current) return audioRef.current;
    const el = new Audio();
    el.preload = 'auto';
    audioRef.current = el;
    return el;
  }

  function ensureAnalyser() {
    if (analyserRef.current) return;
    const audio   = ensureAudio();
    const actx    = new AudioContext();
    actxRef.current = actx;
    const analyser = actx.createAnalyser();
    analyser.fftSize = 64;
    analyserRef.current = analyser;
    const src = actx.createMediaElementSource(audio);
    src.connect(analyser);
    analyser.connect(actx.destination);
  }

  function audioTimeForMinute(minute, duration) {
    if (!duration || !isFinite(duration)) return null;
    return (Math.min(95, Math.max(0, minute)) / 90) * duration;
  }

  function waitForAudioMetadata(audio) {
    if (audio.duration && isFinite(audio.duration)) return Promise.resolve();
    return new Promise(resolve => {
      const done = () => {
        audio.removeEventListener('loadedmetadata', done);
        audio.removeEventListener('durationchange', done);
        resolve();
      };
      audio.addEventListener('loadedmetadata', done, { once: true });
      audio.addEventListener('durationchange', done, { once: true });
      setTimeout(done, 1200);
    });
  }

  function waitForSeek(audio, serial) {
    return new Promise(resolve => {
      const done = () => {
        audio.removeEventListener('seeked', done);
        audio.removeEventListener('canplay', done);
        resolve();
      };
      audio.addEventListener('seeked', done, { once: true });
      audio.addEventListener('canplay', done, { once: true });
      setTimeout(done, 1200);
    }).then(() => serial === seekSerialRef.current);
  }

  async function parkAudioAtMinute(audio, minute, waitForSettle = false) {
    const serial = ++seekSerialRef.current;
    await waitForAudioMetadata(audio);
    if (serial !== seekSerialRef.current) return false;
    const target = audioTimeForMinute(minute, audio.duration);
    if (target == null) return false;
    if (Math.abs(audio.currentTime - target) > 0.05) {
      const settled = waitForSettle ? waitForSeek(audio, serial) : null;
      audio.currentTime = target;
      if (settled) return settled;
    }
    return true;
  }

  function setPlayheadMinute(minute) {
    const next = Math.min(95, Math.max(0, minute));
    currentMinuteRef.current = next;
    setCurrentMinute(next);
  }

  // Map audio currentTime → match minute using clip timing metadata.
  // If ct falls inside a clip, return that clip's match minute.
  // If ct falls in a gap between clips, linearly interpolate toward the next clip's minute.
  // Fallback: linear mapping across the full audio duration.
  function minuteFromAudioTime(ct, meta) {
    if (!meta || !meta.length) {
      const audio = audioRef.current;
      if (!audio || !audio.duration) return 0;
      return Math.min(95, (ct / audio.duration) * 90);
    }
    let lastClip = null;
    for (let i = 0; i < meta.length; i++) {
      const clip = meta[i];
      if (ct >= clip.audio_start && ct <= clip.audio_end) return clip.minute;
      if (ct > clip.audio_end) lastClip = { clip, i };
    }
    if (lastClip) {
      const { clip, i } = lastClip;
      const nextClip = meta[i + 1];
      if (!nextClip) return clip.minute;
      const gapLen = nextClip.audio_start - clip.audio_end;
      if (gapLen <= 0) return nextClip.minute;
      const progress = Math.min(1, (ct - clip.audio_end) / gapLen);
      return clip.minute + progress * (nextClip.minute - clip.minute);
    }
    return meta[0].minute;
  }

  // Commentary mode: audio element owns the playhead clock.
  useEffect(() => {
    if (!commentaryActive || !playing) return;
    const audio = audioRef.current;
    if (!audio) return;
    const tick = () => {
      if (!audio.duration || !isFinite(audio.duration)) { mediaRafRef.current = requestAnimationFrame(tick); return; }
      if (audio.seeking)                                 { mediaRafRef.current = requestAnimationFrame(tick); return; }
      const m = minuteFromAudioTime(audio.currentTime, commentaryMeta);
      setPlayheadMinute(m);
      if (audio.ended) { setPlaying(false); setPlayheadMinute(95); return; }
      mediaRafRef.current = requestAnimationFrame(tick);
    };
    mediaRafRef.current = requestAnimationFrame(tick);
    return () => { if (mediaRafRef.current) cancelAnimationFrame(mediaRafRef.current); mediaRafRef.current = null; };
  }, [commentaryActive, playing, commentaryMeta]);

  useEffect(() => {
    if (!commentaryActive) return;
    const audio = audioRef.current;
    if (!audio) return;
    const onEnded = () => { setPlaying(false); setPlayheadMinute(95); };
    audio.addEventListener('ended', onEnded);
    return () => audio.removeEventListener('ended', onEnded);
  }, [commentaryActive]);

  // ── Playback interval — only when commentary is NOT active ────────────────
  useEffect(() => {
    clearInterval(playIntervalRef.current);
    if (!playing || commentaryActive) return;
    playIntervalRef.current = setInterval(() => {
      setCurrentMinute(m => { if (m >= 95) { setPlaying(false); return m; } return m + 1; });
    }, SPEEDS[speedIdx]);
    return () => clearInterval(playIntervalRef.current);
  }, [playing, speedIdx, commentaryActive]);

  // ── Event detection ───────────────────────────────────────────────────────
  useEffect(() => {
    const wholeMinute = Math.floor(currentMinute);
    const prev = prevMinuteRef.current;
    prevMinuteRef.current = wholeMinute;
    if (!playing || wholeMinute === prev) return;
    const notable = keyEvents.find(e => {
      if ((e.minute ?? 0) !== wholeMinute) return false;
      return e.type === 'Shot' || (e.type === 'Foul Committed' && e.foul_committed_card);
    });
    if (notable) {
      let event = notable;
      if (notable.type === 'Foul Committed' && /yellow/i.test(notable.foul_committed_card || '')) {
        const hadEarlierYellow = keyEvents.some(e =>
          e.event_id !== notable.event_id &&
          e.type === 'Foul Committed' &&
          /yellow/i.test(e.foul_committed_card || '') &&
          e.player === notable.player &&
          (e.minute ?? 0) < (notable.minute ?? 0)
        );
        if (hadEarlierYellow) event = { ...notable, _isSecondYellow: true };
      }
      setActiveOverlay(event);
    }
  }, [currentMinute, playing, keyEvents]);

  // ── Scrub / play ──────────────────────────────────────────────────────────
  const handleManualScrub = useCallback((m) => {
    currentMinuteRef.current = m;
    setPlaying(false);
    setPlayheadMinute(m);
    const audio = audioRef.current;
    if (audio) { audio.pause(); parkAudioAtMinute(audio, m); }
  }, []);

  const onPlayPause = useCallback(async () => {
    if (commentaryActive) {
      ensureAnalyser();
      const audio = audioRef.current;
      if (!audio) return;
      if (playing) { audio.pause(); setPlaying(false); return; }
      const ready = await parkAudioAtMinute(audio, currentMinuteRef.current, true);
      if (!ready) return;
      try {
        await actxRef.current?.resume();
        audio.playbackRate = 1.2;
        await audio.play();
        setPlaying(true);
      } catch {
        setPlaying(false);
      }
      return;
    }
    setPlaying(p => !p);
  }, [commentaryActive, playing]);

  const onToggleSpeed = useCallback(() => setSpeedIdx(i => (i + 1) % SPEEDS.length), []);

  useEffect(() => {
    const onKey = (e) => {
      if (appPhase !== 'match') return;
      if (e.code !== 'Space') return;
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      e.preventDefault();
      onPlayPause();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onPlayPause, appPhase]);

  const onNextHotMoment = useCallback(() => {
    // During a brief: jump audio to the next clip's start time
    if (commentaryActive && commentaryMeta) {
      const audio = audioRef.current;
      if (!audio) return;
      const ct = audio.currentTime;
      const next = commentaryMeta.find(c => c.audio_start > ct + 0.5);
      if (next) { audio.currentTime = next.audio_start; }
      return;
    }
    if (!keyEvents.length) return;
    const next = keyEvents.find(e => (e.minute ?? 0) > currentMinute);
    handleManualScrub(next ? (next.minute ?? 0) : (keyEvents[0].minute ?? 0));
  }, [commentaryActive, commentaryMeta, keyEvents, currentMinute, handleManualScrub]);

  const onPrevHotMoment = useCallback(() => {
    // During a brief: strictly jump audio to the previous clip's start time
    if (commentaryActive && commentaryMeta) {
      const audio = audioRef.current;
      if (!audio) return;
      const ct = audio.currentTime;
      // Find the index of the clip we are currently in or past
      let currIdx = 0;
      for (let i = 0; i < commentaryMeta.length; i++) {
        if (ct >= commentaryMeta[i].audio_start - 0.5) {
          currIdx = i;
        }
      }
      // If we are somewhat into the current clip, going 'back' should take us to the PREVIOUS clip.
      // E.g., if currIdx is 1, jump to 0. If currIdx is 0, just restart 0.
      const prevIdx = Math.max(0, currIdx - 1);
      audio.currentTime = commentaryMeta[prevIdx].audio_start;
      return;
    }
    if (!keyEvents.length) return;
    const prev = [...keyEvents].reverse().find(e => (e.minute ?? 0) < currentMinute);
    if (prev) handleManualScrub(prev.minute ?? 0);
  }, [commentaryActive, commentaryMeta, keyEvents, currentMinute, handleManualScrub]);

  const handleMarkerClick = useCallback((ev) => {
    setAgentContext(prev => prev?.event_id === ev.event_id ? null : ev);
  }, []);

  const handleFabClick = useCallback(() => {
    setAgentContext(prev =>
      prev?._overview ? null : { _overview: true, minute: Math.floor(currentMinute) }
    );
  }, [currentMinute]);

  function handleCommentaryStart(mode) {
    setShowCommentaryModal(false);
    const audio = ensureAudio();
    audio.src = `/api/commentary/audio?mode=${mode}`;
    audio.load();
    audio.playbackRate = 1.2;
    audio.defaultPlaybackRate = 1.2;
    audio.addEventListener('loadedmetadata', () => {
      audio.playbackRate = 1.2;
      setAudioTotalSecs(audio.duration);
      parkAudioAtMinute(audio, currentMinuteRef.current);
    }, { once: true });
    setCommentaryActive(true);
    setSpeedIdx(0);
    fetch(`/api/commentary/audio-meta?mode=${mode}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data?.clips) setCommentaryMeta(data.clips); })
      .catch(() => {});
  }

  function handleCommentaryStop() {
    const audio = audioRef.current;
    if (audio) { audio.pause(); audio.src = ''; }
    if (mediaRafRef.current) cancelAnimationFrame(mediaRafRef.current);
    mediaRafRef.current = null;
    setCommentaryActive(false);
    setAudioTotalSecs(null);
    setCommentaryMeta(null);
    setPlaying(false);
  }

  // ── Derived values ────────────────────────────────────────────────────────
  const effectiveSpeedInterval = commentaryActive && audioTotalSecs ? 0 : SPEEDS[speedIdx];
  const wholeMinute = Math.min(95, Math.floor(currentMinute));

  const lastKeyEvent = useMemo(() => {
    const SUGGESTABLE = new Set(['Shot', 'Foul Committed']);
    return keyEvents.filter(e => (e.minute ?? 0) <= wholeMinute && SUGGESTABLE.has(e.type)).at(-1) ?? null;
  }, [keyEvents, wholeMinute]);

  const morScore = goals.filter(g => g.team === 'Morocco'  && g.minute <= wholeMinute).length;
  const porScore = goals.filter(g => g.team === 'Portugal' && g.minute <= wholeMinute).length;

  // ── Render ────────────────────────────────────────────────────────────────

  // Landing phase: match hub
  if (appPhase === 'landing') {
    return (
      <div id="app">
        <Landing onEnterMatch={() => setAppPhase('pregame')} />
      </div>
    );
  }

  // Pre-game phase: cinematic intro replaces everything
  if (appPhase === 'pregame') {
    return (
      <div id="app">
        <PreGame
          onComplete={() => setAppPhase('match')}
          onSkip={() => setAppPhase('match')}
        />
      </div>
    );
  }

  // Match phase: normal app
  return (
    <div id="app">
      {activeOverlay && (
        <EventOverlay event={activeOverlay} onDismiss={() => setActiveOverlay(null)} />
      )}

      {agentContext && (
        <AgentPanel
          event={agentContext}
          nearestEvent={agentContext?._overview ? lastKeyEvent : null}
          onClose={() => setAgentContext(null)}
        />
      )}

      {showCommentaryModal && (
        <CommentaryModal onStart={handleCommentaryStart} onClose={() => setShowCommentaryModal(false)} />
      )}

      <div id="main">
        <Pitch currentMinute={wholeMinute} lineupsByName={lineupsByName} />
        <StatsPanel currentMinute={wholeMinute} matchStats={matchStats} />

        <button id="hud-back" onClick={() => setAppPhase('landing')} title="Back to hub">
          ← Back
        </button>

        <div id="hud-top">
          <div id="match-teams">
            <div className="team-name home">Morocco</div>
            <div id="score-display">{morScore} – {porScore}</div>
            <div className="team-name away">Portugal</div>
          </div>
          <div id="match-meta">
            2022 Football Championship &nbsp;·&nbsp; Quarter-final &nbsp;·&nbsp; Dec 10, 2022
          </div>
        </div>

        {commentaryActive && (
          <div id="waveform-bar">
            <Waveform analyserRef={analyserRef} playing={playing} />
            <button id="commentary-stop" onClick={handleCommentaryStop} title="Stop brief">
              ✕ Brief
            </button>
          </div>
        )}

        <div id="fab-row">
          <button
            id="commentary-fab"
            className={commentaryActive ? 'commentary-fab--active' : ''}
            onClick={() => commentaryActive ? handleCommentaryStop() : setShowCommentaryModal(true)}
          >
            <div className="fab-icon-box">
              <span className="fab-glyph">
                {commentaryActive ? '🔇' : (
                  <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true">
                    <path d="M12 1a4 4 0 0 1 4 4v6a4 4 0 0 1-8 0V5a4 4 0 0 1 4-4zm-1.5 14.95A7.002 7.002 0 0 1 5 9H3a9 9 0 0 0 8 8.94V20H8v2h8v-2h-3v-2.06A9 9 0 0 0 21 9h-2a7 7 0 0 1-5.5 6.95z"/>
                  </svg>
                )}
              </span>
              {commentaryActive && <span className="fab-live-ring" />}
            </div>
            <div className="fab-text">
              <div className="fab-title">{commentaryActive ? 'Brief Active' : 'Tactical Brief'}</div>
              <div className="fab-sub">
                {commentaryActive ? 'Tap to stop · Use ⏭ to skip clips' : 'AI tactical analysis, narrated'}
              </div>
              {!commentaryActive && (
                <div className="fab-wave-bars" aria-hidden="true">
                  {[3,7,11,8,5,9,3].map((h, i) => (
                    <i key={i} style={{ '--fh': `${h}px`, '--fd': `${(i * 0.13).toFixed(2)}s` }} />
                  ))}
                </div>
              )}
            </div>
          </button>

          <button
            id="ai-fab"
            className={agentContext?._overview ? 'ai-fab--active' : ''}
            onClick={handleFabClick}
          >
            <div className="fab-icon-box ai-icon-box">
              <span className="ai-fab-dot" />
            </div>
            <div className="fab-text">
              <div className="fab-title">AI Analyst</div>
              <div className="fab-sub">Min {wholeMinute}' · Live match intelligence</div>
            </div>
          </button>
        </div>
      </div>

      <Timeline
        tlData={tlData}
        keyEvents={keyEvents}
        currentMinute={currentMinute}
        onMinuteChange={handleManualScrub}
        playing={playing}
        speedLabel={SPEED_LABELS[speedIdx]}
        speedInterval={effectiveSpeedInterval}
        onPlayPause={onPlayPause}
        onToggleSpeed={commentaryActive ? null : onToggleSpeed}
        onNextHotMoment={onNextHotMoment}
        onPrevHotMoment={onPrevHotMoment}
        onMarkerClick={handleMarkerClick}
      />
    </div>
  );
}
