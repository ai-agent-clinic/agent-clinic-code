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
