import { useState, useRef, useEffect, useCallback } from 'react';

// ── Suggested questions ───────────────────────────────────────────────────────
function getSuggestions(event) {
  if (event?._overview) return [
    "What's the tactical shape of both teams in this phase of play?",
    "Who's dominating possession and why?",
    "What's been happening in the last few minutes?",
  ];

  const scorer   = event?.team;
  const other    = scorer === 'Morocco' ? 'Portugal' : 'Morocco';
  const lastName = (event?.player || '').trim().split(/\s+/).pop();
  const outcome  = event?.shot_outcome;

  if (outcome === 'Goal') return [
    `What was ${scorer}'s tactical advantage that led to this goal?`,
    `What went wrong in ${other}'s defensive shape?`,
    `How did the build-up develop before ${lastName}'s shot?`,
  ];
  if (outcome === 'Saved' || outcome === 'Saved To Post') return [
    `Why was the shot saved?`,
    `How well did ${lastName} create this chance?`,
    `Was the goalkeeper well-positioned, or did ${lastName} make it easy?`,
  ];
  if (outcome === 'Off T' || outcome === 'Wayward') return [
    `Why did ${lastName}'s shot miss the target?`,
    `Was ${scorer} under too much pressure in that moment?`,
    `What would have been a better decision there?`,
  ];
  if (outcome === 'Blocked') return [
    `How did ${other} block that shot?`,
    `Was the defender well-positioned, or was it lucky?`,
    `Did ${lastName} have better options than shooting?`,
  ];
  if (outcome === 'Post') return [
    `How close was ${lastName} to scoring?`,
    `Was the goalkeeper beaten on that attempt?`,
    `What went wrong with the finishing?`,
  ];
  if (event?.type === 'Foul Committed') {
    const card = /red/i.test(event?.foul_committed_card || '') ? 'red card' : 'yellow card';
    return [
      `What kind of foul earned this ${card}?`,
      `How does this ${card} change ${scorer}'s game plan?`,
      `Was ${lastName} out of position before the foul?`,
    ];
  }
  return [
    `What was the tactical context in this moment?`,
    `How did this affect the momentum of the match?`,
    `What should have happened differently?`,
  ];
}

const OUTCOME_LABEL = {
  Goal:            'GOAL',
  Saved:           'SHOT SAVED',
  'Saved To Post': 'SAVED TO POST',
  Blocked:         'SHOT BLOCKED',
  'Off T':         'OFF TARGET',
  Post:            'OFF THE POST',
  Wayward:         'WAYWARD',
};

// ── Step list ─────────────────────────────────────────────────────────────────
function StepList({ steps, pending }) {
  return (
    <div className="ap-steps">
      {steps.map((s, i) => {
        const pipeIdx = s.indexOf(' | ');
        const label   = pipeIdx >= 0 ? s.slice(0, pipeIdx) : s;
        const detail  = pipeIdx >= 0 ? s.slice(pipeIdx + 3) : null;
        return (
          <div key={i} className="ap-step">
            <span className="ap-step-dot ap-step-dot--done" />
            <div className="ap-step-content">
              <span className="ap-step-label">{label}</span>
              {detail && <span className="ap-step-detail">{detail}</span>}
            </div>
          </div>
        );
      })}
      {pending && (
        <div className="ap-step ap-step--active">
          <span className="ap-step-dot ap-step-dot--pulse" />
          <div className="ap-step-content">
            <span className="ap-step-label">Thinking…</span>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function AgentPanel({ event, nearestEvent, onClose }) {
  const [history,     setHistory]    = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [inputVal,    setInputVal]   = useState('');
  const [customSuggestions, setCustomSuggestions] = useState(null);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const bodyRef        = useRef(null);
  const readerRef      = useRef(null);
  const inputRef       = useRef(null);
  const lockedCtxRef   = useRef(null);  // backend context locked after first message

  const isOverview = Boolean(event?._overview);

  // Reset conversation when the core context changes (panel closed/reopened)
  const contextKey = isOverview ? event?.minute : event?.event_id;
  useEffect(() => {
    setHistory([]);
    setInputVal('');
    lockedCtxRef.current = null;
    setCustomSuggestions(null);
  }, [contextKey]);

  // Scroll to bottom as messages arrive
  useEffect(() => {
    const el = bodyRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [history]);

  const sendQuestion = useCallback(async (question) => {
    if (isStreaming || !question.trim()) return;

    // Lock the backend context on the first message so follow-ups stay coherent
    // even if the user scrubs the timeline mid-conversation.
    if (!lockedCtxRef.current) {
      lockedCtxRef.current = isOverview && nearestEvent
        ? { event_id: nearestEvent.event_id, minute: null }
        : { event_id: isOverview ? null : event?.event_id, minute: isOverview ? event?.minute : null };
    }
    const ctx = lockedCtxRef.current;

    // Strip failed exchanges (empty assistant response + its paired user message)
    // so the backend never sees a model turn with empty content, which confuses Gemini.
    const historyForBackend = [];
    for (const m of history) {
      if (m.role === 'assistant' && !m.content.trim()) {
        historyForBackend.pop(); // drop the paired user message too
      } else {
        historyForBackend.push({ role: m.role, content: m.content });
      }
    }

    setHistory(h => [
      ...h,
      { role: 'user', content: question },
      { role: 'assistant', content: '', steps: [], streaming: true },
    ]);
    setIsStreaming(true);
    setInputVal('');

    try {
      const resp = await fetch('/api/agent-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          event_id: ctx.event_id,
          minute:   ctx.minute,
          question,
          history: historyForBackend,
        }),
      });
      if (!resp.ok) throw new Error(`Server error ${resp.status}`);

      const reader = resp.body.getReader();
      readerRef.current = reader;
      const decoder = new TextDecoder();
      let buf = '';
      let analysisMode = false;

      const updateLast = fn =>
        setHistory(h => h.map((m, i) => i === h.length - 1 ? fn(m) : m));

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });

        if (analysisMode) {
          updateLast(m => ({ ...m, content: m.content + chunk }));
          continue;
        }

        buf += chunk;
        const nlIdx = buf.lastIndexOf('\n');
        if (nlIdx === -1) continue;

        const complete = buf.slice(0, nlIdx + 1);
        buf = buf.slice(nlIdx + 1);

        for (const line of complete.split('\n')) {
          if (line.startsWith('[STEP] ')) {
            updateLast(m => ({ ...m, steps: [...m.steps, line.slice(7)] }));
          } else if (line === '[DONE]') {
            analysisMode = true;
            if (buf) { updateLast(m => ({ ...m, content: m.content + buf })); buf = ''; }
          } else if (line.startsWith('[ERROR]')) {
            analysisMode = true;
            updateLast(m => ({ ...m, content: line.slice(7).trim() || 'Something went wrong.' }));
          }
        }
      }
    } catch (err) {
      setHistory(h => h.map((m, i) =>
        i === h.length - 1 ? { ...m, content: `Something went wrong: ${err.message}` } : m
      ));
    }

    setHistory(h => h.map((m, i) =>
      i === h.length - 1 ? { ...m, streaming: false } : m
    ));
    setIsStreaming(false);
    setTimeout(() => inputRef.current?.focus(), 50);
  }, [event, nearestEvent, history, isStreaming, isOverview]);

  const handleRegenerateSuggestions = useCallback(async () => {
    if (isRegenerating) return;
    setIsRegenerating(true);
    try {
      const ctx = isOverview && nearestEvent
        ? { event_id: nearestEvent.event_id, minute: null }
        : { event_id: isOverview ? null : event?.event_id, minute: isOverview ? event?.minute : null };

      const resp = await fetch('/api/suggest-questions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          event_id: ctx.event_id,
          minute: ctx.minute,
        }),
      });
      if (!resp.ok) throw new Error(`Server error ${resp.status}`);
      const data = await resp.json();
      if (data.suggestions && data.suggestions.length === 3) {
        setCustomSuggestions(data.suggestions);
      }
    } catch (err) {
      console.error("Failed to regenerate suggestions:", err);
    } finally {
      setIsRegenerating(false);
    }
  }, [event, nearestEvent, isOverview, isRegenerating]);

  const handleKeyDown = useCallback(e => {
    if (e.key === 'Enter' && !e.shiftKey && !isStreaming) {
      e.preventDefault();
      sendQuestion(inputVal);
    }
  }, [sendQuestion, inputVal, isStreaming]);

  // In overview mode, use the nearest key event for contextual suggestions if available
  const suggestionSource = isOverview && nearestEvent ? nearestEvent : event;
  const suggestions  = customSuggestions || getSuggestions(suggestionSource);
  const outcomeLabel = OUTCOME_LABEL[event?.shot_outcome] || event?.type || 'EVENT';

  return (
    <div className="ap-panel">
      {/* ── Header ── */}
      <div className="ap-header">
        <div className="ap-header-left">
          <div className="ap-outcome">
            {isOverview
              ? (nearestEvent ? (OUTCOME_LABEL[nearestEvent.shot_outcome] || nearestEvent.type) : 'MATCH ANALYST')
              : outcomeLabel}
          </div>
          <div className="ap-detail-row">
            {isOverview ? (
              nearestEvent ? (
                <>
                  <span className="ap-player">{nearestEvent.player}</span>
                  <span className="ap-sep">·</span>
                  <span className="ap-team">{nearestEvent.team}</span>
                  <span className="ap-sep">·</span>
                  <span className="ap-minute">{nearestEvent.minute}'</span>
                </>
              ) : (
                <>
                  <span className="ap-player">Minute {event?.minute}</span>
                  <span className="ap-sep">·</span>
                  <span className="ap-team">AI Overview</span>
                </>
              )
            ) : (
              <>
                <span className="ap-player">{event?.player}</span>
                <span className="ap-sep">·</span>
                <span className="ap-team">{event?.team}</span>
                <span className="ap-sep">·</span>
                <span className="ap-minute">{event?.minute}'</span>
              </>
            )
            }
          </div>
        </div>
        <button className="ap-close" onClick={onClose} aria-label="Close panel">✕</button>
      </div>

      {/* ── Body ── */}
      <div className="ap-body" ref={bodyRef}>
        {history.length === 0 ? (
          <div className="ap-suggestions">
            <div className="ap-suggestions-header">
              <div className="ap-suggestions-label">Ask the AI analyst</div>
              <button
                className={`ap-suggestions-regen ${isRegenerating ? 'loading' : ''}`}
                onClick={handleRegenerateSuggestions}
                disabled={isRegenerating}
                title="Generate custom AI questions via Gemini"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2c-.5 3-2.5 5-5.5 5.5 3 .5 5 2.5 5.5 5.5.5-3 2.5-5 5.5-5.5-3-.5-5-2.5-5.5-5.5zm-8 12c-.3 1.8-1.5 3-3.3 3.3 1.8.3 3 1.5 3.3 3.3.3-1.8 1.5-3 3.3-3.3-1.8-.3-3-1.5-3.3-3.3zm13.5 1.5c-.2 1.2-1 2-2.2 2.2 1.2.2 2 1 2.2 2.2.2-1 1-1.8 2.2-2.2-1.2-.2-2-1-2.2-2.2z" />
                </svg>
                <span>Ask Gemini</span>
              </button>
            </div>
            {suggestions.map((q, i) => (
              <button key={i} className="ap-suggestion" onClick={() => sendQuestion(q)}>
                <span className="ap-suggestion-icon">→</span>
                {q}
              </button>
            ))}
          </div>
        ) : (
          history.map((msg, i) => (
            <div key={i} className={`ap-msg ap-msg--${msg.role}`}>
              {msg.role === 'assistant' && (
                <>
                  {(msg.steps?.length > 0 || (msg.streaming && !msg.content)) && (
                    <StepList steps={msg.steps || []} pending={msg.streaming && !msg.content} />
                  )}
                  {(msg.content || (!msg.streaming && msg.steps?.length > 0)) && (
                    <div className="ap-bubble ap-bubble--assistant">
                      {msg.content}
                      {msg.streaming && msg.content && <span className="ap-cursor" />}
                    </div>
                  )}
                </>
              )}
              {msg.role === 'user' && (
                <div className="ap-bubble ap-bubble--user">{msg.content}</div>
              )}
            </div>
          ))
        )}
      </div>

      {/* ── Input ── */}
      <div className="ap-input-row">
          <input
            ref={inputRef}
            className="ap-input"
            placeholder={history.length === 0 ? 'Ask anything about this moment…' : 'Ask a follow-up question…'}
            value={inputVal}
            onChange={e => setInputVal(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isStreaming}
          />
          <button
            className="ap-send"
            onClick={() => sendQuestion(inputVal)}
            disabled={!inputVal.trim() || isStreaming}
            aria-label="Send"
          >↑</button>
        </div>
    </div>
  );
}
