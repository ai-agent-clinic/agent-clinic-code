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

import { useState, useEffect, useRef, useCallback } from 'react';
import ShotAnimation from './ShotAnimation';

// ── Per-type config ───────────────────────────────────────────────────────────

const TYPE_CFG = {
  goal:   { label: 'Goal',          icon: '⚽', dismissMs: 7000 },
  saved:  { label: 'Saved',         icon: '🧤', dismissMs: 5500 },
  post:   { label: 'Off the Post',  icon: '⚽', dismissMs: 5000 },
  block:  { label: 'Blocked',       icon: '⚽', dismissMs: 4500 },
  miss:   { label: 'Off Target',    icon: '⚽', dismissMs: 4000 },
  yellow: { label: 'Yellow Card',   icon: null,  dismissMs: 5500 },
  red:    { label: 'Red Card',      icon: null,  dismissMs: 6000 },
};

function getTypeKey(event) {
  if (event.type === 'Foul Committed') {
    if (event._isSecondYellow) return 'red';
    return /red/i.test(event.foul_committed_card || '') ? 'red' : 'yellow';
  }
  const o = event.shot_outcome || '';
  if (o === 'Goal')                           return 'goal';
  if (o === 'Saved' || o === 'Saved To Post') return 'saved';
  if (o === 'Post')                           return 'post';
  if (o === 'Blocked')                        return 'block';
  return 'miss';
}

// ── Toast card ────────────────────────────────────────────────────────────────

function ToastCard({ event, onDismiss, forceExit }) {
  const typeKey = getTypeKey(event);
  const cfg     = TYPE_CFG[typeKey];
  const [selfExit, setSelfExit] = useState(false);
  const cbRef   = useRef(onDismiss);
  useEffect(() => { cbRef.current = onDismiss; });

  const exiting = forceExit || selfExit;

  // Self-dismiss timers — suppressed when a force-exit is in progress
  useEffect(() => {
    if (forceExit) return;
    const t1 = setTimeout(() => setSelfExit(true), cfg.dismissMs - 440);
    const t2 = setTimeout(() => cbRef.current(),   cfg.dismissMs);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [cfg.dismissMs, forceExit]);

  // Force-exit: play exit animation then hand off to parent
  useEffect(() => {
    if (!forceExit) return;
    const t = setTimeout(() => cbRef.current(), 440);
    return () => clearTimeout(t);
  }, [forceExit]);

  const handleClick = useCallback(() => {
    if (exiting) return;
    setSelfExit(true);
    setTimeout(() => cbRef.current(), 440);
  }, [exiting]);

  const isCard = typeKey === 'yellow' || typeKey === 'red';
  const xg     = (!isCard && event.shot_xg != null) ? event.shot_xg : null;
  const xgPct  = xg != null ? `${Math.min(100, Math.round(xg * 100))}%` : '0%';

  return (
    <div
      className={`ev-toast ev-t--${typeKey}${exiting ? ' ev-toast--exit' : ''}`}
      onClick={handleClick}
      role="status"
    >
      {/* Entry flash */}
      <div className="ev-toast-flash" aria-hidden />

      {/* Goal shimmer sweep */}
      {typeKey === 'goal' && <div className="ev-toast-shimmer" aria-hidden />}

      {/* Pulsing border for goal */}
      {typeKey === 'goal' && <div className="ev-toast-glow" aria-hidden />}

      {/* Left accent stripe */}
      <div className="ev-toast-stripe" />

      {/* Content */}
      <div className="ev-toast-body">

        {/* ── Row 1: event type + minute ── */}
        <div className="ev-toast-head">
          <div className="ev-toast-kind">
            {isCard
              ? <div className={`ev-card-pip ev-card-pip--${typeKey}`} />
              : <span className="ev-toast-ico" aria-hidden>{cfg.icon}</span>
            }
            <span className="ev-toast-label">{cfg.label}</span>
          </div>
          <span className="ev-toast-min">{event.minute}'</span>
        </div>

        {/* ── Separator ── */}
        <div className="ev-toast-rule" />

        {/* ── Row 2: player + team ── */}
        <div className="ev-toast-player">{event.player}</div>
        <div className="ev-toast-team">{event.team}</div>

        {/* ── Row 3: xG bar (shots only) ── */}
        {xg != null && (
          <div className="ev-toast-xg">
            <div className="ev-xg-meta">
              <span className="ev-xg-tag">xG</span>
              <span className="ev-xg-num">{xg.toFixed(2)}</span>
            </div>
            <div className="ev-xg-track">
              <div className="ev-xg-fill" style={{ '--xg': xgPct }} />
              {[25, 50, 75].map(v => (
                <div key={v} className="ev-xg-tick" style={{ left: `${v}%` }} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Export ────────────────────────────────────────────────────────────────────

export default function EventOverlay({ event, onDismiss }) {
  const [shown, setShown]         = useState(null);
  const [forceExit, setForceExit] = useState(false);
  const shownRef  = useRef(null);
  const nextRef   = useRef(null);

  useEffect(() => {
    if (!event) return;
    const cur = shownRef.current;
    if (!cur) {
      // Nothing on screen — show immediately
      shownRef.current = event;
      setShown(event);
      return;
    }
    if (event.event_id === cur.event_id) return; // same event, ignore
    // New event while one is visible — queue it and force-exit the current one
    nextRef.current = event;
    setForceExit(true);
  }, [event]);

  const handleDismiss = useCallback(() => {
    const next = nextRef.current;
    nextRef.current = null;
    setForceExit(false);
    if (next) {
      // Swap in the queued event — key change on ToastCard remounts it,
      // replaying the full entry animation so the new event is unmistakable
      shownRef.current = next;
      setShown(next);
    } else {
      shownRef.current = null;
      setShown(null);
      onDismiss();
    }
  }, [onDismiss]);

  if (!shown) return null;
  const typeKey = getTypeKey(shown);
  return (
    <>
      <ShotAnimation key={`sa-${shown.event_id}`} typeKey={typeKey} event={shown} />
      <ToastCard
        key={shown.event_id}
        event={shown}
        forceExit={forceExit}
        onDismiss={handleDismiss}
      />
    </>
  );
}
