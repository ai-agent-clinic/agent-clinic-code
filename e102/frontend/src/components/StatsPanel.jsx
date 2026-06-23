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

const ROWS = [
  { key: 'shots',     label: 'Shots'     },
  { key: 'on_target', label: 'On Target' },
  { key: 'passes',    label: 'Passes'    },
  { key: 'fouls',     label: 'Fouls'     },
];

const ZERO = { possession: 0, shots: 0, on_target: 0, passes: 0, fouls: 0 };

export default function StatsPanel({ currentMinute, matchStats }) {
  const isKickoff = currentMinute < 1;
  const idx = Math.min(Math.floor(currentMinute), 95);
  const mor = isKickoff ? ZERO : (matchStats?.Morocco?.[idx]  ?? null);
  const por = isKickoff ? ZERO : (matchStats?.Portugal?.[idx] ?? null);

  if (!mor || !por) return null;

  return (
    <div id="stats-panel">
      <div className="sp-header">
        <span className="sp-team">MAR</span>
        <span className="sp-title">Stats</span>
        <span className="sp-team sp-team--por">POR</span>
      </div>

      <div className="sp-poss">
        <div className="sp-poss-nums">
          <span className="sp-poss-pct">{mor.possession}%</span>
          <span className="sp-poss-lbl">Possession</span>
          <span className="sp-poss-pct sp-poss-pct--por">{por.possession}%</span>
        </div>
        <div className="sp-poss-track">
          <div className="sp-poss-fill" style={{ width: `${mor.possession}%` }} />
        </div>
      </div>

      <div className="sp-divider" />

      {ROWS.map(({ key, label }) => {
        const mv = mor[key], pv = por[key];
        const total = mv + pv;
        const morPct = total ? (mv / total) * 100 : 0;
        return (
          <div key={key} className="sp-row">
            <span className="sp-num sp-num--mor">{mv}</span>
            <div className="sp-mid">
              <div className="sp-bar-track">
                <div className="sp-bar-fill--mor" style={{ width: `${morPct}%` }} />
              </div>
              <span className="sp-lbl">{label}</span>
              <div className="sp-bar-track sp-bar-track--rev">
                <div className="sp-bar-fill--por" style={{ width: `${100 - morPct}%` }} />
              </div>
            </div>
            <span className="sp-num sp-num--por">{pv}</span>
          </div>
        );
      })}
    </div>
  );
}
