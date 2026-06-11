import { useState, useRef, useCallback } from 'react';

const OUTCOME_CONFIG = {
  Goal:          { title: 'GOAL!',              btn: 'Explain the tactic',  cls: 'kep-goal'   },
  Saved:         { title: 'SHOT SAVED',         btn: 'What happened?',      cls: 'kep-shot'   },
  'Saved To Post':{ title: 'SAVED TO POST',     btn: 'What happened?',      cls: 'kep-shot'   },
  Blocked:       { title: 'SHOT BLOCKED',       btn: 'What went wrong?',    cls: 'kep-shot'   },
  'Off T':       { title: 'SHOT OFF TARGET',    btn: 'What went wrong?',    cls: 'kep-shot'   },
  Post:          { title: 'OFF THE POST!',      btn: 'So close — why?',     cls: 'kep-shot'   },
  Wayward:       { title: 'SHOT WAYWARD',       btn: 'What went wrong?',    cls: 'kep-shot'   },
};

export default function KeyEventPopup({ event, onDismiss }) {
  const [steps,    setSteps]    = useState([]);
  const [analysis, setAnalysis] = useState('');
  const [phase,    setPhase]    = useState('idle');  // idle | loading | streaming | done
  const readerRef = useRef(null);

  const cfg = OUTCOME_CONFIG[event?.shot_outcome] || { title: 'KEY EVENT', btn: 'Explain', cls: 'kep-shot' };

  const handleExplain = useCallback(async () => {
    setPhase('loading');
    setSteps([]);
    setAnalysis('');

    try {
      const resp = await fetch('/api/explain-agent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ event_id: event.event_id }),
      });
      if (!resp.ok) throw new Error(`${resp.status}`);

      const reader = resp.body.getReader();
      readerRef.current = reader;
      const decoder = new TextDecoder();
      let buf = '';
      let analysisMode = false;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });

        if (analysisMode) {
          setAnalysis(a => a + chunk);
          continue;
        }

        buf += chunk;
        const nlIdx = buf.lastIndexOf('\n');
        if (nlIdx === -1) continue;

        const complete = buf.slice(0, nlIdx + 1);
        buf = buf.slice(nlIdx + 1);

        for (const line of complete.split('\n')) {
          if (line.startsWith('[STEP] ')) {
            setSteps(s => [...s, line.slice(7)]);
          } else if (line === '[DONE]') {
            analysisMode = true;
            setPhase('streaming');
            if (buf) { setAnalysis(buf); buf = ''; }
          }
        }
      }
    } catch (err) {
      setAnalysis(`Error: ${err.message}`);
    }

    setPhase('done');
  }, [event]);

  const handleDismiss = useCallback(() => {
    readerRef.current?.cancel();
    onDismiss();
  }, [onDismiss]);

  const isGoal = event?.shot_outcome === 'Goal';
  const player  = event?.player || 'Unknown';
  const team    = event?.team   || '';
  const minute  = event?.minute ?? 0;
  const xg      = event?.shot_xg ? `xG ${Number(event.shot_xg).toFixed(2)}` : null;

  return (
    <div className="kep-backdrop" onClick={e => { if (e.target === e.currentTarget) handleDismiss(); }}>
      <div className={`kep-card ${cfg.cls}`}>

        {/* Ball */}
        <div className={`kep-ball ${isGoal ? 'kep-ball--goal' : 'kep-ball--shot'}`}>⚽</div>

        {/* Title */}
        <div className="kep-title">{cfg.title}</div>

        {/* Event info */}
        <div className="kep-info">
          <span className="kep-player">{player}</span>
          <span className="kep-sep">·</span>
          <span className="kep-team">{team}</span>
          <span className="kep-sep">·</span>
          <span className="kep-minute">{minute}'</span>
          {xg && <><span className="kep-sep">·</span><span className="kep-xg">{xg}</span></>}
        </div>

        {/* Analysis panel */}
        {(steps.length > 0 || analysis) && (
          <div className="kep-analysis">
            {steps.length > 0 && (
              <div className="kep-steps">
                {steps.map((s, i) => (
                  <div key={i} className="kep-step">
                    <span className="kep-step-dot" />
                    {s}
                  </div>
                ))}
                {phase === 'loading' && (
                  <div className="kep-step kep-step--active">
                    <span className="kep-step-dot kep-step-dot--spin" />
                    Thinking…
                  </div>
                )}
              </div>
            )}
            {analysis && (
              <p className="kep-text">{analysis}{phase === 'streaming' && <span className="kep-cursor" />}</p>
            )}
          </div>
        )}

        {/* Loading spinner (before first step arrives) */}
        {phase === 'loading' && steps.length === 0 && (
          <div className="kep-spinner-wrap">
            <div className="kep-spinner" />
          </div>
        )}

        {/* Buttons */}
        <div className="kep-actions">
          {phase === 'idle' && (
            <button className="kep-btn kep-btn--explain" onClick={handleExplain}>
              {cfg.btn}
            </button>
          )}
          <button className="kep-btn kep-btn--dismiss" onClick={handleDismiss}>
            {phase === 'idle' ? 'Skip' : 'Close'}
          </button>
        </div>
      </div>
    </div>
  );
}
