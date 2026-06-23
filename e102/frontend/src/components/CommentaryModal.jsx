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

import { useState, useRef } from 'react';

const MODES = [
  {
    id: 'quick',
    label: 'Quick Brief',
    sub: '~3–4 min · 5 key moments',
    desc: 'The goal, top shot, decisive card — straight to the pivotal plays.',
  },
  {
    id: 'full',
    label: 'Full Analysis',
    sub: '~7–9 min · All key moments',
    desc: 'Complete tactical breakdown from kick-off to full time.',
  },
];

export default function CommentaryModal({ onStart, onClose }) {
  const [mode,     setMode]     = useState('full');
  const [status,   setStatus]   = useState('idle');   // idle | generating | done | error
  const [progress, setProgress] = useState('');
  const abortRef = useRef(null);

  async function handleGenerate() {
    setStatus('generating');
    setProgress('Connecting...');

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      const resp = await fetch('/api/commentary/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
        signal: ctrl.signal,
      });

      const reader = resp.body.getReader();
      const dec    = new TextDecoder();
      let buf = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const msg = line.slice(6).trim();
          if (msg === 'DONE') {
            setStatus('done');
            setProgress('Brief ready!');
            onStart(mode);
            return;
          } else if (msg.startsWith('ERROR')) {
            setStatus('error');
            setProgress(msg);
          } else {
            setProgress(msg);
          }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        setStatus('error');
        setProgress('Request failed.');
      }
    }
  }

  function handleCancel() {
    abortRef.current?.abort();
    onClose();
  }

  return (
    <div className="cm-backdrop" onClick={handleCancel}>
      <div className="cm-modal" onClick={e => e.stopPropagation()}>
        <div className="cm-header">
          <span className="cm-title">Tactical Brief</span>
          <button className="cm-close" onClick={handleCancel}>✕</button>
        </div>

        <p className="cm-desc">
          AI-narrated tactical analysis anchored to real match data — xG, build-up
          sequences, defensive shape. The timeline syncs to the audio.
        </p>

        <div className="cm-mode-row">
          {MODES.map(m => (
            <button
              key={m.id}
              className={`cm-mode-card${mode === m.id ? ' cm-mode-card--active' : ''}`}
              onClick={() => setMode(m.id)}
              disabled={status === 'generating'}
            >
              <div className="cm-mode-label">{m.label}</div>
              <div className="cm-mode-sub">{m.sub}</div>
              <div className="cm-mode-desc">{m.desc}</div>
            </button>
          ))}
        </div>

        {progress && (
          <div className={`cm-progress${status === 'error' ? ' cm-progress--err' : ''}`}>
            {status === 'generating' && <span className="cm-spinner" />}
            {progress}
          </div>
        )}

        <div className="cm-footer">
          {status === 'done' ? (
            <button className="cm-btn cm-btn--primary" onClick={() => onStart(mode)}>
              ▶ Start brief
            </button>
          ) : (
            <button
              className="cm-btn cm-btn--primary"
              onClick={handleGenerate}
              disabled={status === 'generating'}
            >
              {status === 'generating' ? 'Generating…' : 'Generate'}
            </button>
          )}
          <button className="cm-btn" onClick={handleCancel}>Cancel</button>
        </div>
      </div>
    </div>
  );
}
