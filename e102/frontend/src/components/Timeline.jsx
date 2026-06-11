import { useRef, useEffect, useCallback, useState } from 'react';

const N_MIN   = 96;
const RULER_H = 20;

// ── Marker icon ───────────────────────────────────────────────────────────────
function MarkerIcon({ ev }) {
  if (ev.shot_outcome === 'Goal') {
    return (
      <div style={{
        width: '13px', height: '13px', background: '#FF9900', flexShrink: 0,
        clipPath: 'polygon(50% 0%,61% 35%,98% 35%,68% 57%,79% 91%,50% 70%,21% 91%,32% 57%,2% 35%,39% 35%)',
        filter: 'drop-shadow(0 0 5px rgba(255,153,0,0.95))',
      }} />
    );
  }
  if (ev.type === 'Shot') {
    const on = ev.shot_outcome === 'Saved' || ev.shot_outcome === 'Saved To Post';
    return (
      <div style={{
        width: '7px', height: '7px', borderRadius: '50%', flexShrink: 0,
        background: on ? 'rgba(255,175,55,0.85)' : 'rgba(255,255,255,0.17)',
        boxShadow: on ? '0 0 6px rgba(255,140,0,0.55)' : 'none',
      }} />
    );
  }
  if (ev.type === 'Foul Committed') {
    const isRed = /red|second yellow/i.test(ev.description || '');
    return <div style={{ width:'6px', height:'8px', borderRadius:'1px', flexShrink:0, background: isRed ? '#FF2828' : '#FFD000' }} />;
  }
  if (ev.type === 'Substitution') {
    return <div style={{ width:'7px', height:'7px', background:'rgba(60,190,85,0.65)', transform:'rotate(45deg)', flexShrink:0 }} />;
  }
  return <div style={{ width:'5px', height:'5px', borderRadius:'50%', background:'rgba(100,175,255,0.38)', flexShrink:0 }} />;
}

// ── Timeline Component ────────────────────────────────────────────────────────
export default function Timeline({
  tlData, keyEvents, currentMinute, onMinuteChange,
  playing, speedLabel, speedInterval, onPlayPause, onToggleSpeed, onNextHotMoment, onPrevHotMoment,
  onMarkerClick,
}) {
  const canvasRef = useRef(null);
  const wrapRef   = useRef(null);
  const dragging  = useRef(false);
  const tlDataRef = useRef([]);
  const [tip, setTip] = useState({ visible: false, text: '', x: 0, y: 0 });

  // ── Stable draw (reads from tlDataRef) ────────────────────────────────────
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const W = canvas.offsetWidth, H = canvas.offsetHeight;
    if (!W || !H) { requestAnimationFrame(draw); return; }

    const dpr = window.devicePixelRatio || 1;
    if (canvas.width !== Math.round(W * dpr) || canvas.height !== Math.round(H * dpr)) {
      canvas.width  = Math.round(W * dpr);
      canvas.height = Math.round(H * dpr);
    }
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);

    ctx.fillStyle = '#09090F'; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = '#0C0C16'; ctx.fillRect(0, 0, W, RULER_H);
    ctx.fillStyle = 'rgba(255,255,255,0.05)'; ctx.fillRect(0, RULER_H - 1, W, 1);

    ctx.textBaseline = 'middle'; ctx.textAlign = 'center';
    for (let m = 0; m <= 95; m++) {
      const x = (m / 95) * W;
      const isMaj = m % 15 === 0, isMid = m % 5 === 0, isHT = m === 45;
      const tkH = isMaj ? 6 : isMid ? 3 : 0;
      if (!tkH) continue;
      ctx.fillStyle = isHT ? 'rgba(255,153,0,0.55)' : isMaj ? 'rgba(255,255,255,0.25)' : 'rgba(255,255,255,0.09)';
      ctx.fillRect(x - 0.5, RULER_H - tkH, 1, tkH);
      if (isMaj && m < 91) {
        ctx.font      = `${isHT ? 600 : 400} 8px ui-monospace,'SF Mono',monospace`;
        ctx.fillStyle = isHT ? 'rgba(255,153,0,0.65)' : 'rgba(255,255,255,0.27)';
        ctx.fillText(isHT ? 'HT' : String(m), x, (RULER_H - tkH) / 2);
      }
    }

    const data = tlDataRef.current;
    if (!data.length) return;

    const BAR_AREA = H - RULER_H;
    const sw = W / N_MIN;
    data.forEach((d, i) => {
      const v = d.intensity_score, x = i * sw;
      const barH = Math.max(2, v * BAR_AREA * 0.95);
      const y    = RULER_H + (BAR_AREA - barH);
      const a    = 0.35 + v * 0.65;
      const grad = ctx.createLinearGradient(x, y + barH, x, y);
      grad.addColorStop(0,   `rgba(${Math.round(45+v*60)},${Math.round(10+v*22)},0,${(a*0.45).toFixed(2)})`);
      grad.addColorStop(0.5, `rgba(${Math.round(95+v*80)},${Math.round(28+v*55)},0,${(a*0.75).toFixed(2)})`);
      grad.addColorStop(1,   `rgba(${Math.round(145+v*110)},${Math.round(50+v*103)},0,${a.toFixed(2)})`);
      ctx.fillStyle = grad;
      ctx.fillRect(x + 0.5, y, Math.max(1, sw - 1), barH);
    });

    const htX = Math.round((45 / 95) * W) + 0.5;
    ctx.save();
    ctx.strokeStyle = 'rgba(255,153,0,0.52)'; ctx.lineWidth = 1; ctx.setLineDash([4, 5]);
    ctx.beginPath(); ctx.moveTo(htX, RULER_H); ctx.lineTo(htX, H); ctx.stroke();
    ctx.restore();
  }, []);

  useEffect(() => { tlDataRef.current = tlData; draw(); }, [tlData, draw]);
  useEffect(() => {
    const obs = new ResizeObserver(draw);
    obs.observe(canvasRef.current);
    return () => obs.disconnect();
  }, [draw]);

  // ── Scrubbing ─────────────────────────────────────────────────────────────
  const pxToMin = useCallback((clientX) => {
    const r = wrapRef.current.getBoundingClientRect();
    return Math.round((Math.max(0, Math.min(r.width, clientX - r.left)) / r.width) * 95);
  }, []);

  const handleMouseDown = useCallback((e) => {
    if (e.button !== 0) return;
    dragging.current = true;
    document.body.style.cursor = 'grabbing';
    onMinuteChange(pxToMin(e.clientX));
  }, [onMinuteChange, pxToMin]);

  useEffect(() => {
    const onMove = (e) => { if (dragging.current) onMinuteChange(pxToMin(e.clientX)); };
    const onUp   = ()  => { if (!dragging.current) return; dragging.current = false; document.body.style.cursor = ''; };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
    return () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); };
  }, [onMinuteChange, pxToMin]);

  // ── Tooltip ────────────────────────────────────────────────────────────────
  const showTip = useCallback((e, text) => setTip({ visible: true, text, x: e.clientX, y: e.clientY }), []);
  const moveTip = useCallback((e) => setTip(t => ({ ...t, x: e.clientX, y: e.clientY })), []);
  const hideTip = useCallback(() => setTip(t => ({ ...t, visible: false })), []);

  const tipStyle = (() => {
    const pad = 14;
    let x = tip.x + pad, y = tip.y - 40;
    if (x + 290 > window.innerWidth - 6) x = tip.x - 290 - pad;
    if (y < 6) y = tip.y + pad;
    return { left: x, top: y };
  })();

  return (
    <div id="bottom">
      <div id="tl-header">
        <div id="now-row">
          <span id="now-min">{Math.floor(currentMinute)}</span>
          <span id="now-apos">'</span>
        </div>

        <div id="tl-controls">
          <button className="ctrl-btn" onClick={onPrevHotMoment} title="Previous key moment">⏮</button>
          <button className={`ctrl-btn play-btn${playing ? ' active' : ''}`} onClick={onPlayPause}>
            {playing ? '⏸' : '▶'}
          </button>
          <button className="ctrl-btn" onClick={onNextHotMoment} title="Next key moment">⏭</button>
          {onToggleSpeed && (
            <button className="ctrl-btn speed-btn" onClick={onToggleSpeed}>{speedLabel}</button>
          )}
        </div>

        <div id="tl-track-label">Intensity Track</div>
      </div>

      <div
        id="tl-wrap"
        ref={wrapRef}
        onMouseDown={handleMouseDown}
        onSelectCapture={e => e.preventDefault()}
      >
        <div id="tl-markers">
          {keyEvents.map(ev => {
            const pct = (Math.min(ev.minute ?? 0, 95) / 95) * 100;
            const isClickable = ev.type === 'Shot' || (ev.type === 'Foul Committed' && ev.foul_committed_card);
            return (
              <div
                key={ev.event_id}
                className={`mk${isClickable ? ' mk--clickable' : ''}`}
                style={{ left: `${pct}%` }}
                onMouseEnter={e => showTip(e, ev.description)}
                onMouseMove={moveTip}
                onMouseLeave={hideTip}
                onClick={isClickable ? (e) => { e.stopPropagation(); hideTip(); onMarkerClick?.(ev); } : undefined}
              >
                <MarkerIcon ev={ev} />
                <div className="mk-stem" />
              </div>
            );
          })}
        </div>

        <canvas ref={canvasRef} id="tl-canvas" />
        <div
          id="scrubber"
          style={{
            left: `${(currentMinute / 95) * 100}%`,
            transition: playing && speedInterval > 0 ? `left ${speedInterval}ms linear` : 'none',
          }}
        />
      </div>

      {tip.visible && (
        <div className="tip" style={tipStyle}>{tip.text}</div>
      )}
    </div>
  );
}
