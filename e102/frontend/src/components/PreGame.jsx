/**
 * Pre-game show — cinematic intro that plays before the match.
 *
 * Phase machine:  prompt → generating → playing → (calls onComplete)
 *
 * During "playing", audio drives a progress value 0→1.
 * Six scene windows are mapped onto that range:
 *   0.00–0.10  Title       (Morocco vs Portugal identity split)
 *   0.10–0.30  Road to QF  (both teams' path to the quarterfinal)
 *   0.30–0.48  Venue       (Leaflet map flyTo Al Thumama)
 *   0.48–0.65  Weather     (live Dec 10 2022 Doha data)
 *   0.65–0.80  Spotlights  (4 player cards, cycling)
 *   0.80–1.00  Lineups     (both XIs reveal)
 */

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import 'leaflet/dist/leaflet.css';

// ── Constants ─────────────────────────────────────────────────────────────────

const STADIUM_LAT = 25.2350;
const STADIUM_LNG = 51.5187;

const WMO_LABELS = {
  0: 'Clear Sky', 1: 'Mainly Clear', 2: 'Partly Cloudy', 3: 'Overcast',
  45: 'Fog', 51: 'Light Drizzle', 61: 'Light Rain', 63: 'Rain',
  71: 'Light Snow', 80: 'Showers', 95: 'Thunderstorm',
};

const SCENES = [
  { id: 'title',      label: 'Preview',      start: 0.00 },
  { id: 'road',       label: 'The Journey',  start: 0.10 },
  { id: 'venue',      label: 'The Venue',    start: 0.30 },
  { id: 'weather',    label: 'Conditions',   start: 0.48 },
  { id: 'spotlights', label: 'Key Players',  start: 0.65 },
  { id: 'lineups',    label: 'Lineups',      start: 0.80 },
];

function activeScene(p, scenes = SCENES) {
  let s = scenes[0];
  for (const sc of scenes) if (p >= sc.start) s = sc;
  return s;
}

// Within-scene progress (0→1 inside that scene's window)
function sceneLocal(p, id, scenes = SCENES) {
  const idx   = scenes.findIndex(s => s.id === id);
  if (idx === -1) return 0;
  const start = scenes[idx].start;
  const end   = scenes[idx + 1]?.start ?? 1;
  return Math.min(1, Math.max(0, (p - start) / (end - start)));
}

function fmtTime(s) {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${String(sec).padStart(2, '0')}`;
}

// ── Waveform canvas ───────────────────────────────────────────────────────────

const BARS = 56;
const BAR_GAP = 1.5;

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
        canvas.width = Math.round(W * dpr);
        canvas.height = Math.round(H * dpr);
      }
      const ctx = canvas.getContext('2d');
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);
      const bw = (W - BAR_GAP * (BARS - 1)) / BARS;
      const analyser = analyserRef.current;
      if (!analyser || !playing) {
        const t = Date.now() / 700;
        for (let i = 0; i < BARS; i++) {
          const amp = 0.07 + 0.05 * Math.sin(t + i * 0.37) + 0.03 * Math.sin(t * 1.9 + i * 0.22);
          ctx.fillStyle = 'rgba(255,153,0,0.13)';
          ctx.fillRect(i * (bw + BAR_GAP), H - Math.max(2, amp * H), bw, Math.max(2, amp * H));
        }
        return;
      }
      const data = new Uint8Array(analyser.frequencyBinCount);
      analyser.getByteFrequencyData(data);
      const step = Math.max(1, Math.floor(data.length / BARS));
      for (let i = 0; i < BARS; i++) {
        const val = data[i * step] / 255;
        const bh  = Math.max(2, val * H);
        ctx.fillStyle = `rgba(255,153,0,${(0.22 + val * 0.78).toFixed(2)})`;
        ctx.fillRect(i * (bw + BAR_GAP), H - bh, bw, bh);
      }
    };
    draw();
    return () => cancelAnimationFrame(rafRef.current);
  }, [analyserRef, playing]);

  return <canvas ref={canvasRef} className="pg2-waveform" />;
}

// ── Scene: Title ──────────────────────────────────────────────────────────────

function TitleScene({ progress, scenes }) {
  const lp = sceneLocal(progress, 'title', scenes);
  return (
    <div className="pg2-scene pg2-scene--title">
      <div className="pg2-title-left"  style={{ opacity: Math.min(1, lp * 4) }}>
        <span className="pg2-title-country pg2-title-country--mor">Morocco</span>
      </div>
      <div className="pg2-title-right" style={{ opacity: Math.min(1, lp * 4) }}>
        <span className="pg2-title-country pg2-title-country--por">Portugal</span>
      </div>

      <div className="pg2-title-center" style={{ opacity: Math.min(1, Math.max(0, (lp - 0.25) * 3)) }}>
        <div className="pg2-title-vs">VS</div>
        <div className="pg2-title-comp">2022 Football Championship · Quarter-Final</div>
        <div className="pg2-title-meta">
          <span>Al Thumama Stadium</span>
          <span className="pg2-title-sep">·</span>
          <span>Doha, Qatar</span>
          <span className="pg2-title-sep">·</span>
          <span>December 10, 2022</span>
        </div>
      </div>

      <div className="pg2-particles">
        {Array.from({ length: 24 }, (_, i) => (
          <div key={i} className="pg2-particle" style={{
            left: `${(i * 37 + 11) % 100}%`,
            animationDelay: `${(i * 0.31) % 3}s`,
            animationDuration: `${3 + (i * 0.17) % 2}s`,
          }} />
        ))}
      </div>
    </div>
  );
}

// ── Journey visualization data ────────────────────────────────────────────────

const VB_W    = 1000;
const VB_H    = 520;
const MOR_Y   = 188;
const POR_Y   = 338;
const GNODE_X = [148, 292, 436, 576]; // GS×3 + R16
const QF_X    = 840;
const QF_Y    = Math.round((MOR_Y + POR_Y) / 2); // 263

const MOR_MATCHES = [
  { flag: '🇭🇷', opp: 'Croatia',     us: 0, them: 0, result: 'D' },
  { flag: '🇧🇪', opp: 'Belgium',     us: 2, them: 0, result: 'W' },
  { flag: '🇨🇦', opp: 'Canada',      us: 2, them: 1, result: 'W' },
  { flag: '🇪🇸', opp: 'Spain',       us: 0, them: 0, result: 'W', note: 'Pens 3–0' },
];
const POR_MATCHES = [
  { flag: '🇬🇭', opp: 'Ghana',       us: 3, them: 2, result: 'W' },
  { flag: '🇺🇾', opp: 'Uruguay',     us: 2, them: 0, result: 'W' },
  { flag: '🇰🇷', opp: 'S. Korea',    us: 1, them: 2, result: 'L' },
  { flag: '🇨🇭', opp: 'Switzerland', us: 6, them: 1, result: 'W' },
];

// SVG path strings — built once at module load
const _cp1x = GNODE_X[3] + 140; // bezier control point 1 x
const _cp2x = QF_X - 40;        // bezier control point 2 x
const _morGS   = `M ${GNODE_X[0]},${MOR_Y} L ${GNODE_X[1]},${MOR_Y} L ${GNODE_X[2]},${MOR_Y} L ${GNODE_X[3]},${MOR_Y}`;
const _porGS   = `M ${GNODE_X[0]},${POR_Y} L ${GNODE_X[1]},${POR_Y} L ${GNODE_X[2]},${POR_Y} L ${GNODE_X[3]},${POR_Y}`;
const _morConv = `M ${GNODE_X[3]},${MOR_Y} C ${_cp1x},${MOR_Y} ${_cp2x},${QF_Y} ${QF_X},${QF_Y}`;
const _porConv = `M ${GNODE_X[3]},${POR_Y} C ${_cp1x},${POR_Y} ${_cp2x},${QF_Y} ${QF_X},${QF_Y}`;
const _morFull = `${_morGS} C ${_cp1x},${MOR_Y} ${_cp2x},${QF_Y} ${QF_X},${QF_Y}`;
const _porFull = `${_porGS} C ${_cp1x},${POR_Y} ${_cp2x},${QF_Y} ${QF_X},${QF_Y}`;

// SVG viewBox → CSS % helper (used for HTML overlay nodes)
const vbpct = (x, y) => ({ left: `${(x / VB_W) * 100}%`, top: `${(y / VB_H) * 100}%` });

// ── Journey match node (HTML card overlaid on SVG canvas) ────────────────────

function JourneyNode({ match, color, x, y, visible, isR16 }) {
  const isWin  = match.result === 'W';
  const isDraw = match.result === 'D';
  const scoreColor = isWin ? color : isDraw ? '#888' : '#e05050';

  return (
    <div
      className={`pg2-jnode${isR16 ? ' pg2-jnode--r16' : ''}`}
      style={{
        ...vbpct(x, y),
        opacity:     visible ? 1 : 0,
        transform:   visible
          ? 'translate(-50%,-50%) scale(1)'
          : 'translate(-50%,-50%) scale(0.5)',
        transition:  'opacity 0.5s ease, transform 0.5s cubic-bezier(0.34,1.56,0.64,1)',
        borderColor: isWin ? `${color}55` : isDraw ? 'rgba(255,255,255,0.13)' : 'rgba(255,255,255,0.07)',
        boxShadow:   isWin ? `0 0 ${isR16 ? 24 : 13}px ${color}45, 0 0 ${isR16 ? 48 : 26}px ${color}1a` : 'none',
        background:  isWin ? `${color}0e` : 'rgba(10,8,22,0.85)',
      }}
    >
      <div className="pg2-jnode-flag">{match.flag}</div>
      <div className="pg2-jnode-opp">{match.opp}</div>
      <div className="pg2-jnode-score" style={{ color: scoreColor }}>
        {match.us}–{match.them}
      </div>
      {match.note && (
        <div className="pg2-jnode-note" style={{ color }}>✦ {match.note}</div>
      )}
      <span className={`pg2-jnode-res pg2-jnode-res--${match.result.toLowerCase()}`}>
        {match.result}
      </span>
    </div>
  );
}

// ── Scene: Road to the Quarterfinal ──────────────────────────────────────────

function RoadScene({ progress, scenes, isActive }) {
  const lp = sceneLocal(progress, 'road', scenes);

  // Node reveals — staggered left to right
  const morVis = MOR_MATCHES.map((_, i) => lp > 0.05 + i * 0.12);
  const porVis = POR_MATCHES.map((_, i) => lp > 0.08 + i * 0.12);
  const qfVis  = lp > 0.78;
  const labVis = lp > 0.01;
  const stgVis = lp > 0.02;

  // Group-section paths draw: lp 0.04→0.44 (both start together)
  const morGrpD  = Math.min(1, Math.max(0, (lp - 0.04) / 0.40));
  const porGrpD  = Math.min(1, Math.max(0, (lp - 0.04) / 0.40));
  // Convergence arms draw: lp 0.44→0.72 (both start together)
  const morConvD = Math.min(1, Math.max(0, (lp - 0.44) / 0.28));
  const porConvD = Math.min(1, Math.max(0, (lp - 0.44) / 0.28));
  // Pulse opacity fades in after paths start drawing
  const pulseOp  = Math.min(1, Math.max(0, (lp - 0.15) / 0.18));

  return (
    <div className="pg2-scene pg2-scene--road">
      <div className="pg2-road-eyebrow"
        style={{ opacity: labVis ? 1 : 0, transform: labVis ? 'none' : 'translateY(-14px)', transition: 'all 0.8s ease' }}>
        Road to the Quarterfinal
      </div>

      <div className="pg2-road-canvas">

        {/* ══ SVG: journey paths + energy pulses ══ */}
        <svg className="pg2-road-svg" viewBox={`0 0 ${VB_W} ${VB_H}`} preserveAspectRatio="none"
          xmlns="http://www.w3.org/2000/svg">

          {/* Morocco group section — glow + main line */}
          <path d={_morGS} fill="none" stroke="#ffb347" strokeWidth="8"
            strokeOpacity="0.12" strokeLinecap="round"
            pathLength="1" strokeDasharray="1" strokeDashoffset={1 - morGrpD} />
          <path d={_morGS} fill="none" stroke="#ffb347" strokeWidth="1.8"
            strokeOpacity="0.82" strokeLinecap="round"
            pathLength="1" strokeDasharray="1" strokeDashoffset={1 - morGrpD} />

          {/* Morocco convergence arm */}
          <path d={_morConv} fill="none" stroke="#ffb347" strokeWidth="8"
            strokeOpacity="0.12" strokeLinecap="round"
            pathLength="1" strokeDasharray="1" strokeDashoffset={1 - morConvD} />
          <path d={_morConv} fill="none" stroke="#ffb347" strokeWidth="1.8"
            strokeOpacity="0.82" strokeLinecap="round"
            pathLength="1" strokeDasharray="1" strokeDashoffset={1 - morConvD} />

          {/* Portugal group section */}
          <path d={_porGS} fill="none" stroke="#cc1133" strokeWidth="8"
            strokeOpacity="0.12" strokeLinecap="round"
            pathLength="1" strokeDasharray="1" strokeDashoffset={1 - porGrpD} />
          <path d={_porGS} fill="none" stroke="#cc1133" strokeWidth="1.8"
            strokeOpacity="0.82" strokeLinecap="round"
            pathLength="1" strokeDasharray="1" strokeDashoffset={1 - porGrpD} />

          {/* Portugal convergence arm */}
          <path d={_porConv} fill="none" stroke="#cc1133" strokeWidth="8"
            strokeOpacity="0.12" strokeLinecap="round"
            pathLength="1" strokeDasharray="1" strokeDashoffset={1 - porConvD} />
          <path d={_porConv} fill="none" stroke="#cc1133" strokeWidth="1.8"
            strokeOpacity="0.82" strokeLinecap="round"
            pathLength="1" strokeDasharray="1" strokeDashoffset={1 - porConvD} />

          {/* Energy pulses — only mounted when scene is active (SMIL animations
              bypass CSS animation-play-state so we gate them in JS instead) */}
          {isActive && [0, 1.7, 3.4].map((delay, i) => (
            <circle key={`mg${i}`} r="9" fill="#ffb347" fillOpacity={pulseOp * 0.22}>
              <animateMotion dur="5s" begin={`${delay}s`} repeatCount="indefinite" path={_morFull} />
            </circle>
          ))}
          {isActive && [0, 1.7, 3.4].map((delay, i) => (
            <circle key={`mc${i}`} r="3.5" fill="#ffe080" fillOpacity={pulseOp * 0.95}>
              <animateMotion dur="5s" begin={`${delay}s`} repeatCount="indefinite" path={_morFull} />
            </circle>
          ))}
          {isActive && [0, 1.7, 3.4].map((delay, i) => (
            <circle key={`pg${i}`} r="9" fill="#cc1133" fillOpacity={pulseOp * 0.22}>
              <animateMotion dur="5s" begin={`${delay}s`} repeatCount="indefinite" path={_porFull} />
            </circle>
          ))}
          {isActive && [0, 1.7, 3.4].map((delay, i) => (
            <circle key={`pc${i}`} r="3.5" fill="#ff6688" fillOpacity={pulseOp * 0.95}>
              <animateMotion dur="5s" begin={`${delay}s`} repeatCount="indefinite" path={_porFull} />
            </circle>
          ))}
        </svg>

        {/* ══ Stage labels ══ */}
        {[
          { label: 'GROUP STAGE',   x: 29.2, gold: false },
          { label: 'ROUND OF 16',   x: 57.6, gold: false },
          { label: 'QUARTER-FINAL', x: 84.0, gold: true  },
        ].map(({ label, x, gold }) => (
          <div key={label} className="pg2-road-stage"
            style={{
              left: `${x}%`, top: '7%',
              color: gold ? '#ffd700' : undefined,
              opacity: stgVis ? (gold ? 0.85 : 0.40) : 0,
              transition: 'opacity 0.8s ease',
            }}>
            {label}
          </div>
        ))}

        {/* ══ Team labels ══ */}
        <div className="pg2-road-tlabel"
          style={{ ...vbpct(30, MOR_Y - 84), opacity: labVis ? 1 : 0, transition: 'opacity 0.7s' }}>
          <span className="pg2-road-tlflag">🇲🇦</span>
          <div>
            <div className="pg2-road-tlname" style={{ color: '#ffb347' }}>Morocco</div>
            <div className="pg2-road-tlsub">Group B · 1st Place</div>
          </div>
        </div>

        <div className="pg2-road-tlabel"
          style={{ ...vbpct(30, POR_Y - 84), opacity: labVis ? 1 : 0, transition: 'opacity 0.8s 0.1s' }}>
          <span className="pg2-road-tlflag">🇵🇹</span>
          <div>
            <div className="pg2-road-tlname" style={{ color: '#cc1133' }}>Portugal</div>
            <div className="pg2-road-tlsub">Group H · 1st Place</div>
          </div>
        </div>

        {/* ══ Match nodes ══ */}
        {MOR_MATCHES.map((m, i) => (
          <JourneyNode key={`m${i}`} match={m} color="#ffb347"
            x={GNODE_X[i]} y={MOR_Y} visible={morVis[i]} isR16={i === 3} />
        ))}
        {POR_MATCHES.map((m, i) => (
          <JourneyNode key={`p${i}`} match={m} color="#cc1133"
            x={GNODE_X[i]} y={POR_Y} visible={porVis[i]} isR16={i === 3} />
        ))}

        {/* ══ QF badge ══ */}
        <div className="pg2-jqf"
          style={{
            ...vbpct(QF_X, QF_Y),
            opacity:   qfVis ? 1 : 0,
            transform: qfVis
              ? 'translate(-50%,-50%) scale(1)'
              : 'translate(-50%,-50%) scale(0.15)',
            transition: 'all 1s cubic-bezier(0.34,1.56,0.64,1)',
          }}>
          <div className="pg2-jqf-ball">⚽</div>
          <div className="pg2-jqf-label">Quarter-Final</div>
          <div className="pg2-jqf-date">Dec 10 · 2022</div>
        </div>

      </div>
    </div>
  );
}

// ── Scene: Venue ──────────────────────────────────────────────────────────────

function VenueScene({ progress, scenes, mapRef, mapInst, animStartedRef }) {
  const lp = sceneLocal(progress, 'venue', scenes);
  const isActive = progress >= (scenes ?? SCENES).find(s => s.id === 'venue').start;

  // Init map on first render (tiles preload while scene is invisible)
  useEffect(() => {
    import('leaflet').then(mod => {
      const L = mod.default ?? mod;
      if (mapInst.current) return;

      const map = L.map(mapRef.current, {
        center: [25, 45], zoom: 3,
        zoomControl: false, attributionControl: false,
        dragging: false, scrollWheelZoom: false, doubleClickZoom: false,
      });
      mapInst.current = map;

      L.tileLayer(
        'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
        { maxZoom: 19, subdomains: 'abcd', className: 'high-contrast-map-tiles' }
      ).addTo(map);
    });
  }, [mapRef, mapInst]);

  // Trigger flyTo sequence only when scene becomes active, once
  useEffect(() => {
    if (!isActive) return;
    if (animStartedRef.current) return;
    animStartedRef.current = true;

    import('leaflet').then(mod => {
      const L = mod.default ?? mod;
      const map = mapInst.current;
      if (!map) return;

      // Step 1 → Africa / Arabian Peninsula (after short settle)
      const t1 = setTimeout(() => map.flyTo([23, 35], 4, { duration: 2.8 }), 400);
      // Step 2 → Doha city
      const t2 = setTimeout(() => map.flyTo([25.28, 51.53], 10, { duration: 2.5 }), 3800);
      // Step 3 → Al Thumama Stadium + drop marker
      const t3 = setTimeout(() => {
        map.flyTo([STADIUM_LAT, STADIUM_LNG], 16, { duration: 3.5 });

        L.marker([STADIUM_LAT, STADIUM_LNG], {
          icon: L.divIcon({
            className: '',
            html: `<div class="pg2-marker">
              <div class="pg2-marker-ring"></div>
              <div class="pg2-marker-dot">⚽</div>
            </div>`,
            iconSize: [48, 48], iconAnchor: [24, 24],
          }),
        })
          .bindPopup(
            '<b style="font-size:13px;color:#DFE0EC">Al Thumama Stadium</b>' +
            '<br><span style="font-size:11px;color:#888">Doha, Qatar · 40,000 seats</span>',
            { closeButton: false, className: 'pg2-popup', offset: [0, -20] }
          )
          .addTo(map)
          .openPopup();
      }, 7000);

      return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); };
    });
  }, [isActive, mapInst, animStartedRef]);

  return (
    <div className="pg2-scene pg2-scene--venue">
      <div ref={mapRef} className="pg2-map" />

      <div className="pg2-venue-card" style={{ opacity: Math.min(1, Math.max(0, (lp - 0.55) * 4)) }}>
        <div className="pg2-venue-label">Match Venue</div>
        <div className="pg2-venue-name">Al Thumama Stadium</div>
        <div className="pg2-venue-detail">Doha, Qatar · December 10, 2022</div>
        <div className="pg2-venue-stats">
          <span>Capacity: 40,000</span>
          <span className="pg2-venue-dot">·</span>
          <span>Kickoff: 22:00 AST</span>
        </div>
      </div>
    </div>
  );
}

// ── Scene: Weather ────────────────────────────────────────────────────────────

function WeatherScene({ progress, scenes, weather }) {
  const lp  = sceneLocal(progress, 'weather', scenes);
  const [dispTemp, setDispTemp] = useState(0);

  useEffect(() => {
    if (!weather || lp < 0.1) { setDispTemp(0); return; }
    const target = weather.temp;
    const start  = performance.now();
    const dur    = 1400;
    let raf;
    const tick = (now) => {
      const t = Math.min(1, (now - start) / dur);
      setDispTemp(Math.round(t * target));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [weather, lp > 0.1]);   // re-run when scene becomes visible

  const icon = weather
    ? (weather.code === 0 || weather.code === 1 ? '🌙' : weather.code <= 3 ? '⛅' : '🌧️')
    : '🌙';

  return (
    <div className="pg2-scene pg2-scene--weather">
      <div className="pg2-stars">
        {Array.from({ length: 60 }, (_, i) => (
          <div key={i} className="pg2-star" style={{
            left:  `${(i * 53 + 7) % 100}%`,
            top:   `${(i * 37 + 13) % 90}%`,
            animationDelay: `${(i * 0.22) % 2.5}s`,
            width:  `${1 + (i % 2)}px`,
            height: `${1 + (i % 2)}px`,
          }} />
        ))}
      </div>

      <div className="pg2-weather-scene" style={{ opacity: Math.min(1, lp * 3) }}>
        <div className="pg2-weather-icon-big">{icon}</div>
        <div className="pg2-weather-temp-big">
          {dispTemp}<span>°C</span>
        </div>
        <div className="pg2-weather-label">
          {weather ? (WMO_LABELS[weather.code] ?? 'Clear Sky') : 'Clear Sky'}
        </div>

        <div className="pg2-weather-row" style={{ opacity: Math.min(1, Math.max(0, (lp - 0.35) * 5)) }}>
          <div className="pg2-wrow-item">
            <span className="pg2-wrow-icon">💨</span>
            <span className="pg2-wrow-val">{weather?.wind ?? '14'}</span>
            <span className="pg2-wrow-unit">km/h wind</span>
          </div>
          <div className="pg2-wrow-sep" />
          <div className="pg2-wrow-item">
            <span className="pg2-wrow-icon">💧</span>
            <span className="pg2-wrow-val">{weather?.humidity ?? '41'}</span>
            <span className="pg2-wrow-unit">% humidity</span>
          </div>
        </div>

        <div className="pg2-weather-when" style={{ opacity: Math.min(1, Math.max(0, (lp - 0.55) * 5)) }}>
          Doha, Qatar · December 10, 2022 · 22:00 AST
          <br /><span className="pg2-weather-src">Open-Meteo historical archive</span>
        </div>
      </div>
    </div>
  );
}

// ── Scene: Spotlights ─────────────────────────────────────────────────────────

function SpotlightScene({ progress, scenes, spots }) {
  const lp = sceneLocal(progress, 'spotlights', scenes);
  // Which card is "featured" (0-3)
  const featIdx = Math.min(3, Math.floor(lp * 4));

  return (
    <div className="pg2-scene pg2-scene--spots">
      <div className="pg2-spots-heading" style={{ opacity: Math.min(1, lp * 5) }}>
        Key Players to Watch
      </div>

      <div className="pg2-spots-grid">
        {(spots ?? []).map((s, i) => {
          const visible = lp >= i * 0.25;
          const featured = i === featIdx;
          return (
            <div
              key={s.name}
              className={`pg2-scard${featured ? ' pg2-scard--feat' : ''}`}
              style={{
                opacity:   visible ? 1 : 0,
                transform: visible ? 'translateY(0)' : 'translateY(28px)',
                transition: `opacity 0.55s ${i * 0.08}s, transform 0.55s ${i * 0.08}s`,
              }}
            >
              <div className={`pg2-scard-jersey pg2-scard-jersey--${s.team === 'Morocco' ? 'mor' : 'por'}`}>
                #{s.jersey}
              </div>
              <div className="pg2-scard-name">{s.name}</div>
              <div className="pg2-scard-pos">{s.position} · {s.team}</div>
              <div className="pg2-scard-badge">{s.highlight}</div>
              <div className="pg2-scard-fact">{s.fact}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Scene: Lineups ────────────────────────────────────────────────────────────

function LineupScene({ progress, scenes, lineups }) {
  const lp   = sceneLocal(progress, 'lineups', scenes);
  const morXI = (lineups?.Morocco  ?? []).slice(0, 11);
  const porXI = (lineups?.Portugal ?? []).slice(0, 11);
  const showKickoff = lp > 0.85;

  return (
    <div className="pg2-scene pg2-scene--lineup">
      <div className="pg2-lineup-wrap">
        {/* Morocco */}
        <div className="pg2-lineup-col">
          <div className="pg2-lineup-team pg2-lineup-team--mor"
            style={{ opacity: Math.min(1, lp * 4) }}>
            Morocco
          </div>
          {morXI.map((p, i) => (
            <div key={i} className="pg2-lplayer pg2-lplayer--mor" style={{
              opacity:   lp > i * 0.07 ? 1 : 0,
              transform: lp > i * 0.07 ? 'translateX(0)' : 'translateX(-20px)',
              transition: `opacity 0.4s ${i * 0.04}s, transform 0.4s ${i * 0.04}s`,
            }}>
              <span className="pg2-lnum">{p.jersey_number}</span>
              <span className="pg2-lname">{p.player_name}</span>
            </div>
          ))}
        </div>

        {/* Centre divider */}
        <div className="pg2-lineup-mid">
          <div className="pg2-lineup-vs" style={{ opacity: Math.min(1, lp * 5) }}>VS</div>
          {showKickoff && (
            <div className="pg2-kickoff">
              <div className="pg2-kickoff-label">Match Starting</div>
              <div className="pg2-kickoff-ball">⚽</div>
            </div>
          )}
        </div>

        {/* Portugal */}
        <div className="pg2-lineup-col pg2-lineup-col--por">
          <div className="pg2-lineup-team pg2-lineup-team--por"
            style={{ opacity: Math.min(1, lp * 4) }}>
            Portugal
          </div>
          {porXI.map((p, i) => (
            <div key={i} className="pg2-lplayer pg2-lplayer--por" style={{
              opacity:   lp > i * 0.07 ? 1 : 0,
              transform: lp > i * 0.07 ? 'translateX(0)' : 'translateX(20px)',
              transition: `opacity 0.4s ${i * 0.04}s, transform 0.4s ${i * 0.04}s`,
            }}>
              <span className="pg2-lnum pg2-lnum--por">{p.jersey_number}</span>
              <span className="pg2-lname">{p.player_name}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Pre-game timeline bar ─────────────────────────────────────────────────────

function PreGameTimeline({ playing, scenes, currentSceneId, onSkip, onSkipSection, onPlayPause, fillRef, timeDisplayRef }) {
  const resolvedScenes = scenes ?? SCENES;
  const scene          = resolvedScenes.find(s => s.id === currentSceneId) ?? resolvedScenes[0];
  const sceneIdx       = resolvedScenes.indexOf(scene);
  const isLast         = sceneIdx >= resolvedScenes.length - 1;

  return (
    <div className="pg2-timeline">
      {/* Left: scene name */}
      <div className="pg2-tl-left">
        <div className="pg2-tl-badge">Pre-Match</div>
        <div className="pg2-tl-scene">{scene.label}</div>
      </div>

      {/* Center: progress track + scene markers */}
      <div className="pg2-tl-track-wrap">
        <div className="pg2-tl-track">
          <div className="pg2-tl-fill" ref={fillRef} />

          {resolvedScenes.map((s, i) => (
            <div key={s.id} className={`pg2-tl-marker${i <= sceneIdx ? ' pg2-tl-marker--done' : ''}`}
              style={{ left: `${s.start * 100}%` }}
              title={s.label}
            />
          ))}
        </div>
        <div className="pg2-tl-labels">
          {resolvedScenes.map(s => (
            <div key={s.id} className="pg2-tl-label-item" style={{ left: `${s.start * 100}%` }}>
              {s.label}
            </div>
          ))}
        </div>
      </div>

      {/* Right: time + play/pause + section skip + match skip */}
      <div className="pg2-tl-right">
        <span className="pg2-tl-time" ref={timeDisplayRef}>0:00 / 0:00</span>
        <button className="pg2-tl-playpause" onClick={onPlayPause} title={playing ? 'Pause' : 'Play'}>
          <span style={{ transform: playing ? 'none' : 'translateX(1px)' }}>{playing ? '⏸' : '▶'}</span>
        </button>
        <button
          className="pg2-tl-skip-section"
          onClick={onSkipSection}
          disabled={isLast}
          title={isLast ? 'Last section' : `Next: ${resolvedScenes[sceneIdx + 1]?.label}`}
        ><span style={{ transform: 'translateX(1px)' }}>⏭</span></button>
        <button className="pg2-tl-skip" onClick={onSkip}>Skip to Match ›</button>
      </div>
    </div>
  );
}

// ── Prompt screen ─────────────────────────────────────────────────────────────

function PromptScreen({ onWatch, onSkip, audioReady }) {
  return (
    <div className="pg2-prompt">
      <div className="pg2-prompt-bg">
        {Array.from({ length: 18 }, (_, i) => (
          <div key={i} className="pg2-particle" style={{
            left: `${(i * 53 + 7) % 100}%`,
            top: `${(i * 37 + 13) % 80 + 10}%`,
            animationDelay: `${(i * 0.31) % 3}s`,
            animationDuration: `${3 + (i * 0.17) % 2}s`,
          }} />
        ))}
      </div>

      <div className="pg2-prompt-card">
        <div className="pg2-prompt-eyebrow">Tonight's Match</div>

        <div className="pg2-prompt-matchup">
          <span className="pg2-prompt-team pg2-prompt-team--mor">Morocco</span>
          <span className="pg2-prompt-vs">vs</span>
          <span className="pg2-prompt-team pg2-prompt-team--por">Portugal</span>
        </div>

        <div className="pg2-prompt-event">
          2022 Football Championship · Quarter-Final<br />
          Al Thumama Stadium, Doha · Dec 10, 2022
        </div>

        <div className="pg2-prompt-divider" />

        <div className="pg2-prompt-pitch">
          <div className="pg2-prompt-pitch-icon">🎙</div>
          <div className="pg2-prompt-pitch-copy">
            <strong>Watch the AI pre-match show</strong> — an immersive cinematic preview with
            live stadium location, real match-night weather, player spotlights, and starting lineups,
            narrated by an AI voice.
          </div>
        </div>

        <div className="pg2-prompt-features">
          {['📍 Interactive stadium map', '🌤 Live match-night weather', '⚽ AI voice narration', '👕 Starting lineups'].map(f => (
            <div key={f} className="pg2-prompt-feat">{f}</div>
          ))}
        </div>

        <div className="pg2-prompt-actions">
          <button className="pg2-prompt-watch" onClick={onWatch}>
            {audioReady ? '▶  Replay Pre-Match Show' : '▶  Watch Pre-Match Show'}
          </button>
          <button className="pg2-prompt-skip" onClick={onSkip}>Skip to Match</button>
        </div>
      </div>
    </div>
  );
}

// ── Generating screen ─────────────────────────────────────────────────────────

function GeneratingScreen({ msg }) {
  return (
    <div className="pg2-generating">
      <div className="pg2-gen-ball">⚽</div>
      <div className="pg2-gen-title">Preparing your pre-match experience</div>
      <div className="pg2-gen-msg">{msg || 'Starting…'}</div>
      <div className="pg2-gen-bar">
        <div className="pg2-gen-fill" />
      </div>
    </div>
  );
}

// ── Root component ────────────────────────────────────────────────────────────

export default function PreGame({ onComplete, onSkip }) {
  const [phase,      setPhase]      = useState('prompt');
  const [genMsg,     setGenMsg]     = useState('');
  const [data,       setData]       = useState(null);
  const [weather,    setWeather]    = useState(null);
  const [audioReady, setAudioReady] = useState(false);
  const [exiting,    setExiting]    = useState(false);

  // Audio / playback state
  const [playTime,      setPlayTime]      = useState(0);
  const [duration,      setDuration]      = useState(180);
  const [playing,       setPlaying]       = useState(false);
  // Dynamic scene boundaries loaded from /api/pregame/audio-meta after generation
  const [dynamicScenes, setDynamicScenes] = useState(null);

  const audioRef       = useRef(null);
  const actxRef        = useRef(null);
  const analyserRef    = useRef(null);
  const generatingRef  = useRef(false);
  const rafRef         = useRef(null);
  const mapRef         = useRef(null);
  const mapInst        = useRef(null);
  const animStartedRef = useRef(false);
  const mountedRef     = useRef(true);
  const abortRef       = useRef(null);

  // DOM refs for fill bar + time display (bypass React render cycle)
  const fillRef        = useRef(null);
  const timeDisplayRef = useRef(null);
  const durationRef    = useRef(180);

  // ── Scene metadata ────────────────────────────────────────────────────────
  const loadSceneMeta = useCallback(() => {
    fetch('/api/pregame/audio-meta')
      .then(r => { if (r.ok) return r.json(); throw new Error('no meta'); })
      .then(meta => {
        if (!meta?.scenes?.length) return;
        setDynamicScenes(meta.scenes.map(s => ({
          id:    s.id,
          label: SCENES.find(sc => sc.id === s.id)?.label ?? s.id,
          start: s.frac ?? 0,
        })));
      })
      .catch(() => {});
  }, []);

  // ── Load data on mount ────────────────────────────────────────────────────
  useEffect(() => {
    fetch('/api/pregame/data')
      .then(r => r.json())
      .then(d => {
        setData(d);
        if (d?.audio_cache_enabled) {
          fetch('/api/pregame/audio-meta')
            .then(r => { if (r.ok) { setAudioReady(true); loadSceneMeta(); } })
            .catch(() => {});
        }
      })
      .catch(console.error);

    fetch(
      'https://archive-api.open-meteo.com/v1/archive' +
      '?latitude=25.28&longitude=51.53' +
      '&start_date=2022-12-10&end_date=2022-12-10' +
      '&hourly=temperature_2m,weathercode,windspeed_10m,relativehumidity_2m' +
      '&timezone=Asia%2FDoha'
    )
      .then(r => r.json())
      .then(d => {
        const h = d.hourly;
        setWeather({ temp: Math.round(h.temperature_2m[22]), code: h.weathercode[22], wind: Math.round(h.windspeed_10m[22]), humidity: Math.round(h.relativehumidity_2m[22]) });
      })
      .catch(() => setWeather({ temp: 26, code: 0, wind: 14, humidity: 41 }));
  }, []);

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

  // ── Transition to match ───────────────────────────────────────────────────
  const finish = useCallback(() => {
    setExiting(true);
    if (audioRef.current) { audioRef.current.pause(); audioRef.current.src = ''; }
    cancelAnimationFrame(rafRef.current);
    setTimeout(onComplete, 700);
  }, [onComplete]);

  const handleSkip = useCallback(() => {
    if (audioRef.current) { audioRef.current.pause(); audioRef.current.src = ''; }
    cancelAnimationFrame(rafRef.current);
    onSkip();
  }, [onSkip]);

  // ── Start playback ────────────────────────────────────────────────────────
  const startPlayback = useCallback(() => {
    cancelAnimationFrame(rafRef.current);
    const prev = audioRef.current;
    if (prev) { prev.pause(); prev.src = ''; }
    actxRef.current?.close().catch(() => {});
    actxRef.current = null;

    setPhase('playing');
    loadSceneMeta();

    const audio = new Audio('/api/pregame/audio');
    audioRef.current = audio;
    audio.playbackRate = 1.2;
    audio.defaultPlaybackRate = 1.2;
    audio.addEventListener('loadedmetadata', () => {
      audio.playbackRate = 1.2;
      const dur = audio.duration || 180;
      durationRef.current = dur;
      setDuration(dur);
    });
    audio.addEventListener('ended', finish);

    const actx    = new AudioContext();
    actxRef.current = actx;
    const analyser = actx.createAnalyser();
    analyser.fftSize = 64;
    analyserRef.current = analyser;
    const src = actx.createMediaElementSource(audio);
    src.connect(analyser);
    analyser.connect(actx.destination);

    audio.play().then(() => setPlaying(true)).catch(() => {});

    const tick = () => {
      const audio = audioRef.current;
      if (audio) {
        const ct  = audio.currentTime || 0;
        const dur = durationRef.current || 180;
        const pct = Math.min(100, (ct / dur) * 100);

        // Fill bar + time: DOM refs (zero React overhead)
        if (fillRef.current)        fillRef.current.style.width = `${pct}%`;
        if (timeDisplayRef.current) timeDisplayRef.current.textContent = `${fmtTime(ct)} / ${fmtTime(dur)}`;

        // Scene progress: full 60fps so lp-driven inline styles stay smooth
        setPlayTime(ct);
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
  }, [finish, loadSceneMeta]);

  // ── Play / Pause ──────────────────────────────────────────────────────────
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

  // ── Generate & start ──────────────────────────────────────────────────────
  const handleWatch = useCallback(async () => {
    if (audioReady) { startPlayback(); return; }
    if (generatingRef.current) return;
    generatingRef.current = true;
    setPhase('generating');
    setGenMsg('Generating your pre-match narration…');

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      const res    = await fetch('/api/pregame/generate', { 
        method: 'POST',
        signal: ctrl.signal
      });
      const reader = res.body.getReader();
      const dec    = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        if (!mountedRef.current) {
          reader.cancel();
          break;
        }
        for (const line of dec.decode(value).split('\n')) {
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
            setPhase('prompt'); 
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
        setPhase('prompt'); 
        setGenMsg('Network error — is the server running?'); 
      }
    }
  }, [audioReady, startPlayback]);

  // ── Render ────────────────────────────────────────────────────────────────
  const progress = duration > 0 ? Math.min(1, playTime / duration) : 0;

  // Stable array reference — only changes when dynamicScenes loads (once per session)
  const resolvedScenes = useMemo(() => dynamicScenes ?? SCENES, [dynamicScenes]);

  // Computed once per render, not once per scene-slot in the map below
  const currentSceneId = useMemo(
    () => activeScene(progress, resolvedScenes).id,
    [progress, resolvedScenes]
  );

  const handleSkipSection = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const idx  = resolvedScenes.findIndex(s => s.id === currentSceneId);
    const next = resolvedScenes[idx + 1];
    if (!next) return;
    audio.currentTime = next.start * durationRef.current;
  }, [resolvedScenes, currentSceneId]);

  const spots   = data?.spotlights ?? [];
  const lineups = data?.lineups ?? {};

  return (
    <div className={`pg2-root${exiting ? ' pg2-root--exit' : ''}`}>
      {phase === 'prompt' && (
        <PromptScreen onWatch={handleWatch} onSkip={handleSkip} audioReady={audioReady} />
      )}

      {phase === 'generating' && <GeneratingScreen msg={genMsg} />}

      {phase === 'playing' && (
        <>
          <div className="pg2-scenes">
            {resolvedScenes.map(s => {
              const isActive = s.id === currentSceneId;
              return (
                <div key={s.id} className={`pg2-scene-slot${isActive ? ' pg2-scene-slot--active' : ''}`}>
                  {s.id === 'title'      && <TitleScene      progress={progress} scenes={resolvedScenes} />}
                  {s.id === 'road'       && <RoadScene       progress={progress} scenes={resolvedScenes} isActive={isActive} />}
                  {s.id === 'venue'      && <VenueScene      progress={progress} scenes={resolvedScenes} mapRef={mapRef} mapInst={mapInst} animStartedRef={animStartedRef} />}
                  {s.id === 'weather'    && <WeatherScene    progress={progress} scenes={resolvedScenes} weather={weather} />}
                  {s.id === 'spotlights' && <SpotlightScene  progress={progress} scenes={resolvedScenes} spots={spots} />}
                  {s.id === 'lineups'    && <LineupScene     progress={progress} scenes={resolvedScenes} lineups={lineups} />}
                </div>
              );
            })}
          </div>

          <PreGameTimeline
            playing={playing}
            scenes={resolvedScenes}
            currentSceneId={currentSceneId}
            onSkip={handleSkip}
            onSkipSection={handleSkipSection}
            onPlayPause={handlePlayPause}
            fillRef={fillRef}
            timeDisplayRef={timeDisplayRef}
          />
        </>
      )}
    </div>
  );
}
