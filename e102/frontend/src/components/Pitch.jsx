/*
 * Copyright 2026 Sami Maghnaoui
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import { useRef, useEffect, useCallback, useState } from 'react';

// ── Constants ──────────────────────────────────────────────────────────────────
const PW = 120, PH = 80;
const PLAYER_R   = 11;
const ANON_R     = 7;
const BALL_R     = 6;
const ANIM_MS    = 750;
const FETCH_DELAY = 200;

const TEAM_COLOR = {
  Morocco:  { fill: '#1a9e4a', text: '#ffffff', glow: 'rgba(26,158,74,0.5)' },
  Portugal: { fill: '#cc1122', text: '#ffffff', glow: 'rgba(204,17,34,0.5)' },
};

const NOISE = new Set([
  'Ball Receipt*', 'Starting XI', 'Half Start', 'Half End',
  'Referee Ball-Drop', 'Block', 'Goalkeeper',
]);

// ── Drawing helpers ────────────────────────────────────────────────────────────
function calcTf(W, H) {
  const padX = Math.max(14, W * 0.04);
  const padY = Math.max(14, H * 0.06);
  const s    = Math.min((W - 2 * padX) / PW, (H - 2 * padY) / PH);
  const ox   = (W - s * PW) / 2;
  const oy   = (H - s * PH) / 2;
  return { s, ox, oy, toX: x => ox + x * s, toY: y => oy + y * s };
}

function lerp(a, b, t) { return a + (b - a) * t; }
function easeOut(t)     { return 1 - (1 - t) ** 3; }

function initials(name) {
  if (!name) return '';
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

// ── Pitch markings ─────────────────────────────────────────────────────────────
function drawMarkings(ctx, tf) {
  const { s, ox, oy, toX, toY } = tf;
  const LINE = 'rgba(255,255,255,0.22)';
  ctx.strokeStyle = LINE;
  ctx.lineWidth   = 1;
  ctx.lineCap     = 'round';

  ctx.strokeRect(ox, oy, PW * s, PH * s);

  ctx.beginPath(); ctx.moveTo(toX(60), oy); ctx.lineTo(toX(60), oy + PH * s); ctx.stroke();

  ctx.beginPath(); ctx.arc(toX(60), toY(40), 10 * s, 0, Math.PI * 2); ctx.stroke();

  ctx.fillStyle = LINE;
  ctx.beginPath(); ctx.arc(toX(60), toY(40), Math.max(2, s * 0.8), 0, Math.PI * 2); ctx.fill();

  ctx.strokeRect(ox,       toY(18), 18 * s, 44 * s);
  ctx.strokeRect(toX(102), toY(18), 18 * s, 44 * s);
  ctx.strokeRect(ox,       toY(30),  6 * s, 20 * s);
  ctx.strokeRect(toX(114), toY(30),  6 * s, 20 * s);

  // Goals — drawn outside the boundary
  ctx.strokeRect(ox - 2.5 * s, toY(36), 2.5 * s, 8 * s);
  ctx.strokeRect(toX(120),     toY(36), 2.5 * s, 8 * s);

  const sr = Math.max(2, s * 0.9);
  ctx.fillStyle = LINE;
  [toX(12), toX(108)].forEach(px => {
    ctx.beginPath(); ctx.arc(px, toY(40), sr, 0, Math.PI * 2); ctx.fill();
  });

  const theta = Math.acos(0.6);
  ctx.beginPath(); ctx.arc(toX(12),  toY(40), 10 * s, -theta, theta);                ctx.stroke();
  ctx.beginPath(); ctx.arc(toX(108), toY(40), 10 * s, Math.PI - theta, Math.PI + theta); ctx.stroke();

  const cr = s;
  ctx.beginPath(); ctx.arc(ox,       oy,       cr, 0,            Math.PI / 2);       ctx.stroke();
  ctx.beginPath(); ctx.arc(toX(120), oy,       cr, Math.PI / 2,  Math.PI);           ctx.stroke();
  ctx.beginPath(); ctx.arc(ox,       toY(80),  cr, -Math.PI / 2, 0);                 ctx.stroke();
  ctx.beginPath(); ctx.arc(toX(120), toY(80),  cr, Math.PI,      Math.PI * 3 / 2);   ctx.stroke();
}

// ── Event visualization ────────────────────────────────────────────────────────
function drawArrow(ctx, x1, y1, x2, y2, color) {
  const angle = Math.atan2(y2 - y1, x2 - x1);
  const h = 10;
  ctx.strokeStyle = color; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(x2, y2);
  ctx.lineTo(x2 - h * Math.cos(angle - Math.PI / 6), y2 - h * Math.sin(angle - Math.PI / 6));
  ctx.lineTo(x2 - h * Math.cos(angle + Math.PI / 6), y2 - h * Math.sin(angle + Math.PI / 6));
  ctx.closePath(); ctx.fill();
}

function drawEventViz(ctx, ev, tf) {
  if (!ev) return;
  const { toX, toY } = tf;
  const x1 = ev.location_x, y1 = ev.location_y;
  if (x1 == null || y1 == null) return;
  const x2 = ev.end_location_x, y2 = ev.end_location_y;
  if (x2 == null || y2 == null) return;

  ctx.save();
  if (ev.type === 'Pass') {
    drawArrow(ctx, toX(x1), toY(y1), toX(x2), toY(y2), 'rgba(255,153,0,0.75)');
  } else if (ev.type === 'Shot') {
    const isGoal = ev.shot_outcome === 'Goal';
    drawArrow(ctx, toX(x1), toY(y1), toX(x2), toY(y2),
      isGoal ? 'rgba(255,80,80,0.90)' : 'rgba(255,153,0,0.65)');
  } else if (ev.type === 'Carry') {
    ctx.strokeStyle = 'rgba(160,200,255,0.55)'; ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);
    ctx.beginPath(); ctx.moveTo(toX(x1), toY(y1)); ctx.lineTo(toX(x2), toY(y2)); ctx.stroke();
    ctx.setLineDash([]);
  }
  ctx.restore();
}

// ── Ball: 2-phase path + arc + trail ─────────────────────────────────────────
// t is always the RAW (un-eased) animation progress [0,1]
const ACTION_TYPES = new Set(['Pass', 'Shot', 'Carry']);

function ballCanvasPos(prevEv, ev, t, tf) {
  const { toX, toY } = tf;
  const hasAction = ACTION_TYPES.has(ev.type) && ev.end_location_x != null;

  // Previous position: prefer end location (where ball was after last action)
  const prevX = prevEv?.end_location_x ?? prevEv?.location_x ?? ev.location_x;
  const prevY = prevEv?.end_location_y ?? prevEv?.location_y ?? ev.location_y;
  const endX  = hasAction ? ev.end_location_x : ev.location_x;
  const endY  = hasAction ? ev.end_location_y : ev.location_y;

  const SPLIT = 0.38; // fraction of animation spent "arriving" at the actor

  if (!hasAction || t < SPLIT) {
    // Phase 1: ball glides from previous position to event's start location
    const t1   = easeOut(hasAction ? t / SPLIT : t);
    const dstX = hasAction ? ev.location_x : endX;
    const dstY = hasAction ? ev.location_y : endY;
    return { px: lerp(toX(prevX), toX(dstX), t1), py: lerp(toY(prevY), toY(dstY), t1), arc: 0 };
  }

  // Phase 2: ball travels from event start → end (the actual action)
  const tRaw   = (t - SPLIT) / (1 - SPLIT);
  const tEased = easeOut(tRaw);
  const px     = lerp(toX(ev.location_x), toX(endX), tEased);
  const py     = lerp(toY(ev.location_y), toY(endY), tEased);
  const distPx = Math.hypot(toX(endX) - toX(ev.location_x), toY(endY) - toY(ev.location_y));
  const maxArc = ev.type === 'Shot'  ? Math.min(distPx * 0.38, 62)
               : ev.type === 'Pass'  ? Math.min(distPx * 0.22, 42)
               : 0;
  return { px, py: py - Math.sin(tRaw * Math.PI) * maxArc, arc: maxArc };
}

function drawBall(ctx, prevEv, ev, t, tf) {
  if (!ev || ev.location_x == null) return;

  const pos = ballCanvasPos(prevEv, ev, t, tf);

  // Motion trail — fading ghost circles behind the ball when airborne
  if (t >= 0.38 && pos.arc > 4) {
    for (let i = 4; i >= 1; i--) {
      const tTrail = Math.max(0.38, t - i * 0.055);
      const trail  = ballCanvasPos(prevEv, ev, tTrail, tf);
      ctx.save();
      ctx.globalAlpha = 0.22 * (5 - i) / 4;
      ctx.beginPath(); ctx.arc(trail.px, trail.py, BALL_R * (1 - i * 0.12), 0, Math.PI * 2);
      ctx.fillStyle = '#ffffff'; ctx.fill();
      ctx.restore();
    }
  }

  // Main ball
  ctx.save();
  const airborne = pos.arc > 4;
  ctx.shadowColor = airborne ? 'rgba(255,255,220,0.95)' : 'rgba(255,255,255,0.80)';
  ctx.shadowBlur  = airborne ? 20 : 12;
  ctx.beginPath(); ctx.arc(pos.px, pos.py, BALL_R, 0, Math.PI * 2);
  ctx.fillStyle = '#ffffff'; ctx.fill();
  ctx.shadowBlur = 0;

  // Seam ring
  ctx.strokeStyle = 'rgba(30,30,30,0.48)'; ctx.lineWidth = 1.5;
  ctx.stroke();

  // Three small dark patches — football pentagon suggestion
  ctx.fillStyle = 'rgba(40,40,40,0.26)';
  for (let k = 0; k < 3; k++) {
    const a  = (k / 3) * Math.PI * 2 + 0.42;
    const cx = pos.px + BALL_R * 0.44 * Math.cos(a);
    const cy = pos.py + BALL_R * 0.44 * Math.sin(a);
    ctx.beginPath(); ctx.arc(cx, cy, BALL_R * 0.28, 0, Math.PI * 2); ctx.fill();
  }
  ctx.restore();
}

// ── Player matching & interpolation ───────────────────────────────────────────
function matchPlayers(prev, next) {
  return next.map(np => {
    const m = prev.find(pp =>
      (np.id && pp.id && np.id === pp.id) ||
      (np.name && pp.name && np.name === pp.name)
    );
    return { ...np, fromX: m ? m.x : np.x, fromY: m ? m.y : np.y };
  });
}

function drawPlayers(ctx, pairs, t, tf, selectedName, lineupsByName) {
  const { toX, toY } = tf;
  ctx.textAlign    = 'center';
  ctx.textBaseline = 'middle';

  pairs.forEach(p => {
    const hasName = Boolean(p.name);
    const isActor = Boolean(p.isActor);
    const r       = hasName ? PLAYER_R : ANON_R;
    const px      = toX(lerp(p.fromX, p.x, t));
    const py      = toY(lerp(p.fromY, p.y, t));
    const tc      = TEAM_COLOR[p.team] || { fill: '#6688aa', text: '#fff', glow: 'rgba(100,136,170,0.4)' };
    const isSel   = selectedName && p.name === selectedName;

    // Outer pulse ring for the event actor (shooter / passer)
    if (isActor) {
      ctx.save();
      ctx.beginPath(); ctx.arc(px, py, r + 5, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(255,215,50,0.85)';
      ctx.lineWidth   = 2.5;
      ctx.stroke();
      ctx.restore();
    }

    if (isSel)       { ctx.shadowColor = 'rgba(255,153,0,0.80)'; ctx.shadowBlur = 18; }
    else if (isActor){ ctx.shadowColor = 'rgba(255,215,50,0.75)'; ctx.shadowBlur = 20; }
    else             { ctx.shadowColor = tc.glow; ctx.shadowBlur = 6; }

    ctx.beginPath(); ctx.arc(px, py, r, 0, Math.PI * 2);
    ctx.fillStyle = tc.fill;
    ctx.fill();

    ctx.shadowColor = 'transparent'; ctx.shadowBlur = 0;
    ctx.strokeStyle = isSel ? 'rgba(255,153,0,1)' : isActor ? 'rgba(255,215,50,0.9)' : 'rgba(255,255,255,0.60)';
    ctx.lineWidth   = (isSel || isActor) ? 2.5 : 1.5;
    ctx.stroke();

    if (hasName) {
      const info   = lineupsByName[p.name] || {};
      const label  = info.jersey != null ? String(info.jersey) : initials(p.name);
      ctx.font      = `700 ${Math.round(r * 0.85)}px ui-monospace,'SF Mono',monospace`;
      ctx.fillStyle = tc.text;
      ctx.fillText(label, px, py + 0.5);
    }
  });
}

// ── Hit test: nearest player wins; actor preferred when tied ──────────────────
function hitPlayer(pairs, mx, my, tf) {
  let hit = null, minDist = Infinity;
  for (const p of pairs) {
    const r    = p.name ? PLAYER_R : ANON_R;
    const dist = Math.hypot(mx - tf.toX(p.x), my - tf.toY(p.y));
    if (dist > r + 7) continue;
    if (!hit || (p.isActor && !hit.isActor) || (!hit.isActor && dist < minDist)) {
      hit = p; minDist = dist;
    }
  }
  return hit;
}

// ── Pitch Component ────────────────────────────────────────────────────────────
export default function Pitch({ currentMinute, lineupsByName }) {
  const canvasRef   = useRef(null);
  const tooltipRef  = useRef(null);
  const fetchTimer  = useRef(null);
  const [selectedPlayer, setSelectedPlayer] = useState(null);

  // All mutable canvas state in a ref — stable refs avoid stale closures in RAF
  const cs = useRef({
    prev:          [],
    next:          [],
    prevEvent:     null,
    event:         null,
    animStart:     null,
    rafId:         null,
    selectedName:  null,
    lineupsByName: {},
  });

  useEffect(() => { cs.current.lineupsByName = lineupsByName; }, [lineupsByName]);

  useEffect(() => {
    cs.current.selectedName = selectedPlayer?.name ?? null;
    if (!cs.current.rafId) doRender(1);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedPlayer]);

  // ── Stable render (reads everything from cs.current) ──────────────────────
  const doRender = useCallback((t = 1) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
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

    ctx.fillStyle = '#0C1A0C';
    ctx.fillRect(0, 0, W, H);

    const tf = calcTf(W, H);

    // Subtle alternating stripes
    for (let i = 0; i < 12; i++) {
      if (i % 2 === 0) {
        ctx.fillStyle = 'rgba(0,0,0,0.055)';
        ctx.fillRect(tf.ox + i * tf.s * 10, tf.oy, tf.s * 10, PH * tf.s);
      }
    }

    drawMarkings(ctx, tf);

    const tRaw  = Math.min(t, 1);
    const te    = easeOut(tRaw);
    const pairs = matchPlayers(cs.current.prev, cs.current.next);

    drawEventViz(ctx, cs.current.event, tf);
    drawPlayers(ctx, pairs, te, tf, cs.current.selectedName, cs.current.lineupsByName);
    drawBall(ctx, cs.current.prevEvent, cs.current.event, tRaw, tf);  // drawn last = always on top
  }, []);

  // ── RAF animation loop ─────────────────────────────────────────────────────
  const animFrame = useCallback((ts) => {
    const t = Math.min((ts - cs.current.animStart) / ANIM_MS, 1);
    doRender(t);
    if (t < 1) {
      cs.current.rafId = requestAnimationFrame(animFrame);
    } else {
      cs.current.rafId = null;
      cs.current.prev  = cs.current.next;
    }
  }, [doRender]);

  const startAnim = useCallback(() => {
    cs.current.animStart = performance.now();
    if (!cs.current.rafId) cs.current.rafId = requestAnimationFrame(animFrame);
  }, [animFrame]);

  // ── Fetch freeze frame for a minute ───────────────────────────────────────
  const fetchData = useCallback(async (minute) => {
    try {
      const r = await fetch(`/api/events?minute_from=${minute}&minute_to=${minute}`);
      if (!r.ok) return;
      const evs = await r.json();

      const candidates = evs.filter(e => !NOISE.has(e.type));
      if (!candidates.length) return;

      // Priority: goal shot > any shot > key pass > foul > last event
      const best =
        candidates.find(e => e.type === 'Shot' && e.shot_outcome === 'Goal') ||
        candidates.find(e => e.type === 'Shot') ||
        candidates.find(e => e.is_key_pass) ||
        candidates.find(e => e.type === 'Foul Committed') ||
        candidates[candidates.length - 1];

      const fr = await fetch(`/api/freeze-frame/${best.event_id}`);

      cs.current.prevEvent = cs.current.event;
      cs.current.event     = best;

      if (!fr.ok) { doRender(1); return; }

      const ff = await fr.json();
      if (!ff.length) { doRender(1); return; }

      // Client-side fallback: ensure actor appears if server-side injection missed
      const actorMissing = best.player &&
        !ff.some(p => p.player_name === best.player);
      if (actorMissing && best.location_x != null) {
        ff.push({
          player_id:   best.player_id ?? null,
          player_name: best.player,
          team:        best.team,
          is_teammate: true,
          is_actor:    true,
          location_x:  best.location_x,
          location_y:  best.location_y,
        });
      }

      const newPlayers = ff
        .filter(p => p.location_x != null && p.location_y != null)
        .map(p => ({
          id:      p.player_id,
          name:    p.player_name,
          team:    p.team,
          x:       p.location_x,
          y:       p.location_y,
          isActor: Boolean(p.is_actor),
        }));

      cs.current.prev = cs.current.next.length ? cs.current.next : newPlayers;
      cs.current.next = newPlayers;
      startAnim();
    } catch (e) {
      console.warn('[Pitch] fetch error', e);
    }
  }, [doRender, startAnim]);

  // ── Debounced fetch on minute change ──────────────────────────────────────
  useEffect(() => {
    clearTimeout(fetchTimer.current);
    if (currentMinute === 0) {
      cs.current.prev = [];
      cs.current.next = [];
      cs.current.event = null;
      cs.current.prevEvent = null;
      doRender(1);
      return;
    }
    fetchTimer.current = setTimeout(() => fetchData(currentMinute), FETCH_DELAY);
  }, [currentMinute, fetchData, doRender]);

  // ── Initial render + resize ────────────────────────────────────────────────
  useEffect(() => {
    doRender(1);
    const obs = new ResizeObserver(() => doRender(1));
    obs.observe(canvasRef.current);
    return () => obs.disconnect();
  }, [doRender]);

  // ── Cleanup ───────────────────────────────────────────────────────────────
  useEffect(() => () => {
    clearTimeout(fetchTimer.current);
    if (cs.current.rafId) cancelAnimationFrame(cs.current.rafId);
  }, []);

  // ── Click: select player ──────────────────────────────────────────────────
  const handleClick = useCallback((e) => {
    const canvas = canvasRef.current;
    const rect   = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    const tf = calcTf(canvas.offsetWidth, canvas.offsetHeight);
    const pairs = matchPlayers(cs.current.prev, cs.current.next);
    const hit = hitPlayer(pairs, mx, my, tf);

    if (hit?.name) {
      setSelectedPlayer(prev =>
        prev?.name === hit.name ? null
          : { name: hit.name, team: hit.team, info: cs.current.lineupsByName[hit.name] || {} }
      );
    } else {
      setSelectedPlayer(null);
    }
    if (!cs.current.rafId) doRender(1);
  }, [doRender]);

  // ── Hover: imperative tooltip (no React re-render on mousemove) ───────────
  const handleMouseMove = useCallback((e) => {
    const canvas  = canvasRef.current;
    const tooltip = tooltipRef.current;
    if (!canvas || !tooltip) return;

    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    const tf = calcTf(canvas.offsetWidth, canvas.offsetHeight);
    const pairs = matchPlayers(cs.current.prev, cs.current.next);

    const hit = hitPlayer(pairs, mx, my, tf);

    if (hit?.name) {
      const info = cs.current.lineupsByName[hit.name] || {};
      const parts = [
        hit.team,
        info.jersey != null ? `#${info.jersey}` : null,
        info.position || null,
        hit.isActor ? '⚽ event actor' : null,
      ].filter(Boolean);

      tooltip.querySelector('.pt-name').textContent  = hit.name;
      tooltip.querySelector('.pt-detail').textContent = parts.join(' · ');
      tooltip.style.display = 'block';

      const pad = 14;
      let tx = e.clientX + pad;
      let ty = e.clientY - tooltip.offsetHeight - pad;
      if (tx + tooltip.offsetWidth > window.innerWidth - 6) tx = e.clientX - tooltip.offsetWidth - pad;
      if (ty < 6) ty = e.clientY + pad;
      tooltip.style.left = `${tx}px`;
      tooltip.style.top  = `${ty}px`;
      canvas.style.cursor = 'pointer';
    } else {
      tooltip.style.display = 'none';
      canvas.style.cursor = 'default';
    }
  }, []);

  const handleMouseLeave = useCallback(() => {
    if (tooltipRef.current) tooltipRef.current.style.display = 'none';
  }, []);

  return (
    <div id="pitch-container">
      <canvas
        ref={canvasRef}
        id="pitch-canvas"
        onClick={handleClick}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      />

      {/* Imperative hover tooltip — updated without React re-render */}
      <div ref={tooltipRef} className="player-tooltip" style={{ display: 'none' }}>
        <div className="pt-name" />
        <div className="pt-detail" />
      </div>

      {/* Click-to-select panel */}
      {selectedPlayer && (
        <div id="player-info">
          <div id="pi-name">{selectedPlayer.name}</div>
          <div id="pi-meta">
            {selectedPlayer.team}
            {selectedPlayer.info.jersey != null ? ` · #${selectedPlayer.info.jersey}` : ''}
            {selectedPlayer.info.position ? ` · ${selectedPlayer.info.position}` : ''}
          </div>
        </div>
      )}
    </div>
  );
}
