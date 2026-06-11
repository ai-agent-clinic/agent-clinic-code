/**
 * UpcomingPregame — full-screen cinematic pre-game show for any WC 2026 match.
 *
 * Six visual scenes driven by audio clip metadata:
 *   opener  → team identity split screen
 *   venue   → stadium reveal card
 *   group   → group table with all 4 sides
 *   home    → home-team spotlight with AI-generated facts
 *   away    → away-team spotlight
 *   kickoff → pitch outline + upcoming match date
 *
 * Mirrors the PreGame.jsx architecture: audio is source of truth,
 * clip metadata maps audio time → scene.
 */

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// ── Constants ─────────────────────────────────────────────────────────────────

const FALLBACK_SCENES = [
  { id: 'opener',  label: 'Opening',      start: 0.00 },
  { id: 'venue',   label: 'The Venue',    start: 0.17 },
  { id: 'group',   label: 'Group Stakes', start: 0.33 },
  { id: 'home',    label: 'Home Team',    start: 0.50 },
  { id: 'away',    label: 'Away Team',    start: 0.67 },
  { id: 'kickoff', label: 'Kickoff',      start: 0.83 },
];

function getActiveScene(p, scenes) {
  let s = scenes[0];
  for (const sc of scenes) if (p >= sc.start) s = sc;
  return s;
}

function sceneLocal(p, id, scenes) {
  const idx   = scenes.findIndex(s => s.id === id);
  if (idx === -1) return 0;
  const start = scenes[idx].start;
  const end   = scenes[idx + 1]?.start ?? 1;
  return Math.min(1, Math.max(0, (p - start) / (end - start)));
}

function fmtTime(s) {
  const m   = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${String(sec).padStart(2, '0')}`;
}

function fmtLocalDate(local) {
  if (!local) return '';
  const [d, t] = local.split(' ');
  if (!d) return local;
  const [mo, day, yr] = d.split('/');
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${months[parseInt(mo) - 1] || ''} ${parseInt(day)}, ${yr}${t ? ` · ${t}` : ''}`;
}

// ── Flag ──────────────────────────────────────────────────────────────────────

function Flag({ iso2, name, size = 48 }) {
  const [err, setErr] = useState(false);
  const src = iso2 ? `https://flagsdb.com/img/flags/${iso2.toLowerCase()}.png` : null;
  if (!src || err) {
    return (
      <div className="upg-flag-ph"
        style={{ width: size, height: Math.round(size * 0.66) }}>
        {(name || '?').slice(0, 3).toUpperCase()}
      </div>
    );
  }
  return (
    <img src={src} alt={name}
      className="upg-flag"
      style={{ width: size, height: 'auto' }}
      onError={() => setErr(true)}
    />
  );
}

// ── Waveform ──────────────────────────────────────────────────────────────────

const WV_BARS = 44;
const WV_GAP  = 2;

function Waveform({ analyserRef, playing }) {
  const canvasRef = useRef(null);
  const rafRef    = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const draw = () => {
      rafRef.current = requestAnimationFrame(draw);
      const W = canvas.offsetWidth, H = canvas.offsetHeight;
      if (!W || !H) return;
      const dpr = window.devicePixelRatio || 1;
      if (canvas.width !== Math.round(W * dpr) || canvas.height !== Math.round(H * dpr)) {
        canvas.width  = Math.round(W * dpr);
        canvas.height = Math.round(H * dpr);
      }
      const ctx = canvas.getContext('2d');
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);
      const bw       = (W - WV_GAP * (WV_BARS - 1)) / WV_BARS;
      const analyser = analyserRef.current;
      if (!analyser || !playing) return;
      const data = new Uint8Array(analyser.frequencyBinCount);
      analyser.getByteFrequencyData(data);
      const step = Math.max(1, Math.floor(data.length / WV_BARS));
      for (let i = 0; i < WV_BARS; i++) {
        const val = data[i * step] / 255;
        const bh  = Math.max(2, val * H);
        ctx.fillStyle = `rgba(255,153,0,${(0.25 + val * 0.75).toFixed(2)})`;
        ctx.fillRect(i * (bw + WV_GAP), H - bh, bw, bh);
      }
    };
    draw();
    return () => cancelAnimationFrame(rafRef.current);
  }, [analyserRef, playing]);

  return <canvas ref={canvasRef} className="upg-waveform" />;
}

// ── Scene: Opener ─────────────────────────────────────────────────────────────

function OpenerScene({ progress, scenes, match }) {
  const lp   = sceneLocal(progress, 'opener', scenes);
  const home = match.home_team;
  const away = match.away_team;
  const fadeL = Math.min(1, lp * 3.5);
  const fadeR = Math.min(1, lp * 3.5);
  const fadeC = Math.min(1, Math.max(0, (lp - 0.28) * 3.5));

  return (
    <div className="upg-scene upg-scene--opener">
      {/* Blurred flag backgrounds */}
      {home.iso2 && (
        <div className="upg-opener-bgflag upg-opener-bgflag--home"
          style={{ backgroundImage: `url(https://flagsdb.com/img/flags/${home.iso2}.png)`, opacity: fadeL * 0.07 }} />
      )}
      {away.iso2 && (
        <div className="upg-opener-bgflag upg-opener-bgflag--away"
          style={{ backgroundImage: `url(https://flagsdb.com/img/flags/${away.iso2}.png)`, opacity: fadeR * 0.07 }} />
      )}

      {/* Particles */}
      <div className="upg-particles" aria-hidden>
        {Array.from({ length: 22 }, (_, i) => (
          <div key={i} className="upg-particle" style={{
            left:              `${(i * 41 + 7) % 100}%`,
            animationDelay:    `${(i * 0.27) % 3}s`,
            animationDuration: `${3 + (i * 0.19) % 2}s`,
          }} />
        ))}
      </div>

      {/* Home team */}
      <div className="upg-opener-team" style={{
        opacity:   fadeL,
        transform: `translateX(${(1 - fadeL) * -32}px)`,
      }}>
        <Flag iso2={home.iso2} name={home.name} size={80} />
        <div className="upg-opener-teamname upg-opener-teamname--home">{home.name}</div>
        <div className="upg-opener-code">{home.fifa_code}</div>
      </div>

      {/* Center */}
      <div className="upg-opener-center" style={{
        opacity:   fadeC,
        transform: `scale(${0.65 + fadeC * 0.35})`,
      }}>
        <div className="upg-opener-vs">VS</div>
        <div className="upg-opener-comp">2026 FIFA World Cup</div>
        <div className="upg-opener-group">Group {match.group} · Matchday {match.matchday}</div>
      </div>

      {/* Away team */}
      <div className="upg-opener-team" style={{
        opacity:   fadeR,
        transform: `translateX(${(1 - fadeR) * 32}px)`,
      }}>
        <Flag iso2={away.iso2} name={away.name} size={80} />
        <div className="upg-opener-teamname upg-opener-teamname--away">{away.name}</div>
        <div className="upg-opener-code">{away.fifa_code}</div>
      </div>
    </div>
  );
}

// ── Scene: Venue (Leaflet flyTo map) ─────────────────────────────────────────

function VenueScene({ progress, scenes, match }) {
  const lp      = sceneLocal(progress, 'venue', scenes);
  const stadium = match.stadium;
  const mapRef  = useRef(null);
  const mapObj  = useRef(null);
  const flyDone = useRef(false);
  const timers  = useRef([]);
  const [overlayVis, setOverlayVis] = useState(false);

  // Initialize map once on mount
  useEffect(() => {
    if (!mapRef.current) return;
    const lat = parseFloat(stadium.lat);
    const lng = parseFloat(stadium.lng);
    if (isNaN(lat) || isNaN(lng)) return;

    const map = L.map(mapRef.current, {
      zoomControl: false, attributionControl: false,
      dragging: false, scrollWheelZoom: false,
      doubleClickZoom: false, touchZoom: false, keyboard: false,
    }).setView([39, -100], 3);

    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
      maxZoom: 19,
      className: 'high-contrast-map-tiles',
    }).addTo(map);

    mapObj.current = map;
    return () => {
      timers.current.forEach(clearTimeout);
      map.remove();
      mapObj.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Trigger fly sequence once when venue scene goes active
  useEffect(() => {
    if (lp < 0.01 || flyDone.current || !mapObj.current) return;
    const lat = parseFloat(stadium.lat);
    const lng = parseFloat(stadium.lng);
    if (isNaN(lat) || isNaN(lng)) return;

    flyDone.current = true;
    const map = mapObj.current;
    map.invalidateSize();

    // Fly to city level
    timers.current.push(setTimeout(() => map.flyTo([lat, lng], 11, { duration: 2.0 }), 200));
    // Fly to stadium level + add marker + show overlay
    timers.current.push(setTimeout(() => {
      map.flyTo([lat, lng], 16, { duration: 2.2 });
      const icon = L.divIcon({
        className: '',
        html: '<div class="upg-map-marker"><div class="upg-map-marker-ring"></div><div class="upg-map-marker-dot"></div></div>',
        iconSize: [40, 40], iconAnchor: [20, 20],
      });
      L.marker([lat, lng], { icon }).addTo(map);
      timers.current.push(setTimeout(() => setOverlayVis(true), 1100));
    }, 2600));
  }, [lp]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="upg-scene upg-scene--venue">
      <div className="upg-map" ref={mapRef} />
      <div className={`upg-venue-overlay${overlayVis ? ' upg-venue-overlay--vis' : ''}`}>
        <div className="upg-venue-eyebrow">Match Venue</div>
        <div className="upg-venue-stadium">{stadium.name}</div>
        <div className="upg-venue-city">{stadium.city}, {stadium.country}</div>
        <div className="upg-venue-divider" />
        <div className="upg-venue-stats">
          <div className="upg-venue-stat">
            <span className="upg-venue-stat-val">{stadium.capacity}</span>
            <span className="upg-venue-stat-lbl">Capacity</span>
          </div>
          <div className="upg-venue-stat-sep" />
          <div className="upg-venue-stat">
            <span className="upg-venue-stat-val">Group {match.group}</span>
            <span className="upg-venue-stat-lbl">Stage</span>
          </div>
          <div className="upg-venue-stat-sep" />
          <div className="upg-venue-stat">
            <span className="upg-venue-stat-val">MD {match.matchday}</span>
            <span className="upg-venue-stat-lbl">Matchday</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Scene: Group ──────────────────────────────────────────────────────────────

function GroupScene({ progress, scenes, match, groupTeams }) {
  const lp    = sceneLocal(progress, 'group', scenes);
  const teams = groupTeams ?? [];

  // Put home + away first for visual clarity
  const sorted = [
    ...teams.filter(t => t.id === match.home_team.id),
    ...teams.filter(t => t.id === match.away_team.id),
    ...teams.filter(t => t.id !== match.home_team.id && t.id !== match.away_team.id),
  ];

  return (
    <div className="upg-scene upg-scene--group">
      <div className="upg-group-badge" style={{ opacity: Math.min(1, lp * 6) }}>
        Group {match.group}
      </div>

      <div className="upg-group-grid">
        {sorted.map((t, i) => {
          const isHome = t.id === match.home_team.id;
          const isAway = t.id === match.away_team.id;
          const vis    = lp > 0.08 + i * 0.14;
          return (
            <div key={t.id}
              className={`upg-gteam${isHome ? ' upg-gteam--home' : isAway ? ' upg-gteam--away' : ''}`}
              style={{
                opacity:    vis ? 1 : 0,
                transform:  vis ? 'translateY(0)' : 'translateY(22px)',
                transition: `opacity 0.50s ${i * 0.08}s, transform 0.50s ${i * 0.08}s`,
              }}
            >
              <Flag iso2={t.iso2} name={t.name} size={42} />
              <div className="upg-gteam-name">{t.name}</div>
              <div className="upg-gteam-code">{t.fifa_code}</div>
              {(isHome || isAway) && (
                <div className="upg-gteam-role">{isHome ? 'Home' : 'Away'}</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Scene: Team spotlight (home or away) ──────────────────────────────────────

function TeamScene({ progress, scenes, sceneId, team, teamFact }) {
  const lp     = sceneLocal(progress, sceneId, scenes);
  const isHome = sceneId === 'home';

  const flagOp = Math.min(1, lp * 3);
  const nameOp = Math.min(1, Math.max(0, (lp - 0.18) * 4));
  const textOp = Math.min(1, Math.max(0, (lp - 0.44) * 4));

  return (
    <div className={`upg-scene upg-scene--team${isHome ? ' upg-scene--home' : ' upg-scene--away'}`}>
      <div className="upg-team-layout">
        {/* Flag side */}
        <div className="upg-team-flag-wrap" style={{
          opacity:   flagOp,
          transform: `scale(${0.65 + flagOp * 0.35})`,
        }}>
          <Flag iso2={team.iso2} name={team.name} size={128} />
          <div className="upg-team-code-big">{team.fifa_code}</div>
        </div>

        {/* Info side */}
        <div className="upg-team-info">
          <div className="upg-team-eyebrow" style={{ opacity: nameOp }}>
            {isHome ? 'Home Side' : 'Away Side'}
          </div>
          <div className="upg-team-name-big" style={{
            opacity:   nameOp,
            transform: `translateX(${(1 - nameOp) * 24}px)`,
          }}>
            {team.name}
          </div>
          {teamFact && (
            <>
              <div className="upg-team-headline" style={{ opacity: textOp }}>
                {teamFact.headline}
              </div>
              <div className="upg-team-fact" style={{ opacity: textOp }}>
                {teamFact.fact}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Scene: Kickoff ────────────────────────────────────────────────────────────

function KickoffScene({ progress, scenes, match }) {
  const lp      = sceneLocal(progress, 'kickoff', scenes);
  const pitchOp = Math.min(1, lp * 3);
  const badgeOp = Math.min(1, Math.max(0, (lp - 0.28) * 4));
  const teamsOp = Math.min(1, Math.max(0, (lp - 0.56) * 4));

  return (
    <div className="upg-scene upg-scene--kickoff">
      {/* Pitch outline */}
      <div className="upg-pitch-wrap" style={{ opacity: pitchOp }}>
        <svg className="upg-pitch-svg" viewBox="0 0 420 272" xmlns="http://www.w3.org/2000/svg">
          <rect x="2" y="2" width="416" height="268" rx="5"
            fill="none" stroke="rgba(255,153,0,0.18)" strokeWidth="2" />
          <line x1="210" y1="2" x2="210" y2="270"
            stroke="rgba(255,153,0,0.11)" strokeWidth="1.5" />
          <circle cx="210" cy="136" r="44"
            fill="none" stroke="rgba(255,153,0,0.11)" strokeWidth="1.5" />
          <circle cx="210" cy="136" r="3.5" fill="rgba(255,153,0,0.32)" />
          {/* Left box */}
          <rect x="2" y="76" width="76" height="120" rx="2"
            fill="none" stroke="rgba(255,153,0,0.10)" strokeWidth="1.5" />
          <rect x="2" y="104" width="28" height="64" rx="2"
            fill="none" stroke="rgba(255,153,0,0.07)" strokeWidth="1" />
          {/* Right box */}
          <rect x="342" y="76" width="76" height="120" rx="2"
            fill="none" stroke="rgba(255,153,0,0.10)" strokeWidth="1.5" />
          <rect x="390" y="104" width="28" height="64" rx="2"
            fill="none" stroke="rgba(255,153,0,0.07)" strokeWidth="1" />
          {/* Penalty spots */}
          <circle cx="68"  cy="136" r="2.5" fill="rgba(255,153,0,0.22)" />
          <circle cx="352" cy="136" r="2.5" fill="rgba(255,153,0,0.22)" />
          {/* Center glow */}
          <circle cx="210" cy="136" r="10"  fill="rgba(255,153,0,0.05)" />
        </svg>
      </div>

      {/* Upcoming badge */}
      <div className="upg-kickoff-badge" style={{
        opacity:   badgeOp,
        transform: `scale(${0.65 + badgeOp * 0.35})`,
      }}>
        <div className="upg-kickoff-label">Upcoming Match</div>
        <div className="upg-kickoff-date">{fmtLocalDate(match.local_date)}</div>
      </div>

      {/* Team matchup */}
      <div className="upg-kickoff-matchup" style={{ opacity: teamsOp }}>
        <span className="upg-kickoff-teamname">{match.home_team.name}</span>
        <span className="upg-kickoff-vs">vs</span>
        <span className="upg-kickoff-teamname">{match.away_team.name}</span>
      </div>
    </div>
  );
}

// ── Timeline bar ──────────────────────────────────────────────────────────────

function PregameTimeline({ playing, scenes, currentSceneId, onPlayPause, onSkipSection, fillRef, timeRef }) {
  const scene    = scenes.find(s => s.id === currentSceneId) ?? scenes[0];
  const sceneIdx = scenes.indexOf(scene);
  const isLast   = sceneIdx >= scenes.length - 1;

  return (
    <div className="upg-timeline">
      <div className="upg-tl-left">
        <div className="upg-tl-badge">Pre-Match</div>
        <div className="upg-tl-scene">{scene.label}</div>
      </div>

      <div className="upg-tl-track-wrap">
        <div className="upg-tl-track">
          <div className="upg-tl-fill" ref={fillRef} />
          {scenes.map((s, i) => (
            <div key={s.id}
              className={`upg-tl-marker${i <= sceneIdx ? ' upg-tl-marker--done' : ''}`}
              style={{ left: `${s.start * 100}%` }}
              title={s.label}
            />
          ))}
        </div>
        <div className="upg-tl-labels">
          {scenes.map(s => (
            <div key={s.id} className="upg-tl-label-item"
              style={{ left: `${s.start * 100}%` }}>
              {s.label}
            </div>
          ))}
        </div>
      </div>

      <div className="upg-tl-right">
        <span className="upg-tl-time" ref={timeRef}>0:00 / 0:00</span>
        <button className="upg-tl-playpause" onClick={onPlayPause} title={playing ? 'Pause' : 'Play'}>
          <span style={{ transform: playing ? 'none' : 'translateX(1px)' }}>{playing ? '⏸' : '▶'}</span>
        </button>
        <button
          className="upg-tl-skip-section"
          onClick={onSkipSection}
          disabled={isLast}
          title={isLast ? 'Last section' : `Next: ${scenes[sceneIdx + 1]?.label}`}
        ><span style={{ transform: 'translateX(1px)' }}>⏭</span></button>
      </div>
    </div>
  );
}

// ── Root component ────────────────────────────────────────────────────────────

export default function UpcomingPregame({ match, onClose }) {
  const [phase,      setPhase]      = useState('loading'); // loading | prompt | generating | playing | error
  const [genMsg,     setGenMsg]     = useState('');
  const [pgData,     setPgData]     = useState(null);
  const [audioReady, setAudioReady] = useState(false);
  const [playing,    setPlaying]    = useState(false);
  const [playTime,   setPlayTime]   = useState(0);
  const [duration,   setDuration]   = useState(120);
  const [dynScenes,  setDynScenes]  = useState(null);

  const audioRef       = useRef(null);
  const actxRef        = useRef(null);
  const analyserRef    = useRef(null);
  const rafRef         = useRef(null);
  const fillRef        = useRef(null);
  const timeRef        = useRef(null);
  const durRef         = useRef(120);
  const abortRef       = useRef(null);
  const generatingRef  = useRef(false);

  const resolvedScenes = useMemo(() => dynScenes ?? FALLBACK_SCENES, [dynScenes]);
  const progress       = duration > 0 ? Math.min(1, playTime / duration) : 0;
  const currentSceneId = useMemo(
    () => getActiveScene(progress, resolvedScenes).id,
    [progress, resolvedScenes]
  );

  const mountedRef = useRef(true);

  // Close on Escape
  useEffect(() => {
    const onKey = e => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  // Cleanup on unmount
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      cancelAnimationFrame(rafRef.current);
      abortRef.current?.abort();
      const a = audioRef.current;
      if (a) { a.pause(); a.src = ''; }
    };
  }, []);

  function applyClipMeta(meta) {
    if (!meta?.clips?.length) return;
    const total = meta.total_duration || 120;
    durRef.current = total;
    setDuration(total);
    setDynScenes(meta.clips.map(c => ({
      id:    c.scene,
      label: c.label,
      start: c.audio_start / total,
    })));
  }

  // Fetch pregame data + check audio cache on mount
  useEffect(() => {
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    fetch(`/api/wc2026/pregame/data?match_id=${match.id}`, { signal: ctrl.signal })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!data) {
          setPhase(p => (p === 'loading' ? 'prompt' : p));
          return;
        }
        setPgData(data);
        if (data.audio_cache_enabled) {
          fetch(`/api/wc2026/pregame/audio-meta?match_id=${match.id}`, { signal: ctrl.signal })
            .then(r => r.ok ? r.json() : null)
            .then(meta => {
              if (meta) {
                setAudioReady(true);
                applyClipMeta(meta);
              }
              setPhase(p => (p === 'loading' ? 'prompt' : p));
            })
            .catch(() => {
              setPhase(p => (p === 'loading' ? 'prompt' : p));
            });
        } else {
          setPhase(p => (p === 'loading' ? 'prompt' : p));
        }
      })
      .catch(err => {
        if (err.name !== 'AbortError') setPhase(p => (p === 'loading' ? 'prompt' : p));
      });
  }, [match.id]);

  const finish = useCallback(() => {
    cancelAnimationFrame(rafRef.current);
    const a = audioRef.current;
    if (a) { a.pause(); a.src = ''; }
    setPlaying(false);
    setPhase('prompt');
  }, []);

  const startPlayback = useCallback(() => {
    cancelAnimationFrame(rafRef.current);
    const prev = audioRef.current;
    if (prev) { prev.pause(); prev.src = ''; }
    actxRef.current?.close().catch(() => {});
    actxRef.current = null;

    setPhase('playing');
    const audio = new Audio(`/api/wc2026/pregame/audio?match_id=${match.id}`);
    audioRef.current = audio;
    audio.playbackRate = 1.2;
    audio.defaultPlaybackRate = 1.2;
    audio.addEventListener('loadedmetadata', () => {
      audio.playbackRate = 1.2;
      const dur = audio.duration || 120;
      durRef.current = dur;
      setDuration(dur);
    });
    audio.addEventListener('ended', finish);

    fetch(`/api/wc2026/pregame/audio-meta?match_id=${match.id}`)
      .then(r => r.ok ? r.json() : null).then(applyClipMeta).catch(() => {});

    const actx    = new AudioContext();
    actxRef.current = actx;
    const analyser  = actx.createAnalyser();
    analyser.fftSize = 64;
    analyserRef.current = analyser;
    const src = actx.createMediaElementSource(audio);
    src.connect(analyser);
    analyser.connect(actx.destination);

    audio.play().then(() => setPlaying(true)).catch(() => {});

    const tick = () => {
      const a = audioRef.current;
      if (a) {
        const ct  = a.currentTime || 0;
        const dur = durRef.current || 120;
        if (fillRef.current) fillRef.current.style.width = `${Math.min(100, (ct / dur) * 100)}%`;
        if (timeRef.current) timeRef.current.textContent = `${fmtTime(ct)} / ${fmtTime(dur)}`;
        setPlayTime(ct);
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
  }, [match.id, finish]);

  const handlePlayPause = useCallback(async () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (playing) {
      audio.pause(); setPlaying(false);
    } else {
      await actxRef.current?.resume();
      audio.playbackRate = 1.2;
      await audio.play(); setPlaying(true);
    }
  }, [playing]);

  useEffect(() => {
    if (phase !== 'playing') return;
    const onKey = e => {
      if (e.code === 'Space') {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
        e.preventDefault();
        handlePlayPause();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [phase, handlePlayPause]);

  const handleSkipSection = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const idx  = resolvedScenes.findIndex(s => s.id === currentSceneId);
    const next = resolvedScenes[idx + 1];
    if (!next) return;
    audio.currentTime = next.start * durRef.current;
  }, [resolvedScenes, currentSceneId]);

  const handleWatch = useCallback(async () => {
    if (audioReady) { startPlayback(); return; }
    if (generatingRef.current) return;
    generatingRef.current = true;
    setPhase('generating');
    setGenMsg('Preparing your pre-match experience…');

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      const resp   = await fetch(`/api/wc2026/pregame/generate?match_id=${match.id}`, { 
        method: 'POST',
        signal: ctrl.signal
      });
      const reader = resp.body.getReader();
      const dec    = new TextDecoder();
      let buf = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        if (!mountedRef.current) {
          reader.cancel();
          break;
        }
        buf += dec.decode(value, { stream: true });
        const lines = buf.split('\n'); buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const msg = line.slice(6).trim();
          if (msg === 'DONE') { 
            generatingRef.current = false; 
            if (!mountedRef.current) return;
            setAudioReady(true); 
            startPlayback(); 
            return; 
          }
          if (msg.startsWith('ERROR')) { 
            generatingRef.current = false; 
            if (!mountedRef.current) return;
            setPhase('error'); 
            setGenMsg(msg); 
            return; 
          }
          if (mountedRef.current) {
            setGenMsg(msg);
          }
        }
      }
    } catch (err) {
      generatingRef.current = false;
      if (mountedRef.current && err.name !== 'AbortError') { 
        setPhase('error'); 
        setGenMsg('Network error — is the server running?'); 
      }
    }
  }, [audioReady, match.id, startPlayback]);

  // ── Derived data ──────────────────────────────────────────────────────────
  const home = match.home_team;
  const away = match.away_team;
  const tf   = pgData?.team_facts ?? {};
  const gt   = pgData?.group_teams ?? [];

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="upg-backdrop" onClick={onClose}>
      {/* Blurred flag color tints */}
      {home.iso2 && (
        <div className="upg-bg upg-bg--home"
          style={{ backgroundImage: `url(https://flagsdb.com/img/flags/${home.iso2}.png)` }} />
      )}
      {away.iso2 && (
        <div className="upg-bg upg-bg--away"
          style={{ backgroundImage: `url(https://flagsdb.com/img/flags/${away.iso2}.png)` }} />
      )}
      <div className="upg-bg-vignette" />

      <div className="upg-root" onClick={e => e.stopPropagation()}>
        <button className="upg-close" onClick={onClose} aria-label="Close">✕</button>

        {/* ── Loading / Prompt ── */}
        {(phase === 'loading' || phase === 'prompt') && (
          <div className="upg-prompt">
            <div className="upg-prompt-particles" aria-hidden>
              {Array.from({ length: 18 }, (_, i) => (
                <div key={i} className="upg-particle" style={{
                  left:              `${(i * 43 + 9) % 100}%`,
                  top:               `${(i * 31 + 15) % 70 + 12}%`,
                  animationDelay:    `${(i * 0.27) % 3}s`,
                  animationDuration: `${3 + (i * 0.21) % 2}s`,
                }} />
              ))}
            </div>

            <div className="upg-prompt-card">
              <div className="upg-prompt-eyebrow">Upcoming · 2026 FIFA World Cup</div>

              <div className="upg-prompt-matchup">
                <div className="upg-prompt-team">
                  <Flag iso2={home.iso2} name={home.name} size={52} />
                  <span>{home.name}</span>
                </div>
                <div className="upg-prompt-vs">vs</div>
                <div className="upg-prompt-team upg-prompt-team--r">
                  <Flag iso2={away.iso2} name={away.name} size={52} />
                  <span>{away.name}</span>
                </div>
              </div>

              <div className="upg-prompt-meta">
                Group {match.group} · Matchday {match.matchday}
                {match.stadium?.name ? ` · ${match.stadium.name}, ${match.stadium.city}` : ''}
              </div>

              <div className="upg-prompt-divider" />

              <div className="upg-prompt-blurb">
                <span className="upg-prompt-blurb-icon">🎙</span>
                <div>
                  <strong>Watch the AI pre-match show</strong> — venue spotlight, group stakes,
                  team identity, and cinematic buildup for this upcoming clash.
                </div>
              </div>

              <div className="upg-prompt-actions">
                <button
                  className="upg-prompt-watch"
                  onClick={handleWatch}
                  disabled={phase === 'loading'}
                >
                  {phase === 'loading'
                    ? 'Loading…'
                    : audioReady
                      ? '▶  Replay Pre-Match Show'
                      : '▶  Watch Pre-Match Show'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── Generating ── */}
        {phase === 'generating' && (
          <div className="upg-generating">
            <div className="upg-gen-ball">⚽</div>
            <div className="upg-gen-title">Preparing your pre-match experience</div>
            <div className="upg-gen-msg">{genMsg || 'Starting…'}</div>
            <div className="upg-gen-bar"><div className="upg-gen-fill" /></div>
          </div>
        )}

        {/* ── Error ── */}
        {phase === 'error' && (
          <div className="upg-generating">
            <div className="upg-gen-ball" style={{ filter: 'grayscale(0.6)' }}>⚠</div>
            <div className="upg-gen-title">Something went wrong</div>
            <div className="upg-gen-msg">{genMsg}</div>
            <button className="upg-prompt-watch" style={{ marginTop: 20, maxWidth: 260 }}
              onClick={() => { setPhase('prompt'); setGenMsg(''); }}>
              Try again
            </button>
          </div>
        )}

        {/* ── Playing ── */}
        {phase === 'playing' && (
          <>
            <div className="upg-scenes">
              {resolvedScenes.map(s => {
                const isActive = s.id === currentSceneId;
                return (
                  <div key={s.id}
                    className={`upg-scene-slot${isActive ? ' upg-scene-slot--active' : ''}`}>
                    {s.id === 'opener'  && <OpenerScene  progress={progress} scenes={resolvedScenes} match={match} />}
                    {s.id === 'venue'   && <VenueScene   progress={progress} scenes={resolvedScenes} match={match} />}
                    {s.id === 'group'   && <GroupScene   progress={progress} scenes={resolvedScenes} match={match} groupTeams={gt} />}
                    {s.id === 'home'    && <TeamScene    progress={progress} scenes={resolvedScenes} sceneId="home" team={home} teamFact={tf.home} />}
                    {s.id === 'away'    && <TeamScene    progress={progress} scenes={resolvedScenes} sceneId="away" team={away} teamFact={tf.away} />}
                    {s.id === 'kickoff' && <KickoffScene progress={progress} scenes={resolvedScenes} match={match} />}
                  </div>
                );
              })}
            </div>

            <Waveform analyserRef={analyserRef} playing={playing} />

            <PregameTimeline
              playing={playing}
              scenes={resolvedScenes}
              currentSceneId={currentSceneId}
              onPlayPause={handlePlayPause}
              onSkipSection={handleSkipSection}
              fillRef={fillRef}
              timeRef={timeRef}
            />
          </>
        )}
      </div>
    </div>
  );
}
