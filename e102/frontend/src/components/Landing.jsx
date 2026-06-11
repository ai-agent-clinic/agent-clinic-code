import { useState, useEffect, useMemo } from 'react';
import UpcomingPregame from './UpcomingPregame.jsx';

const MATCHDAYS = [1, 2, 3];
const PAGE_SIZE = 8;

function flagUrl(iso2) {
  return iso2 ? `https://flagsdb.com/img/flags/${iso2.toLowerCase()}.png` : null;
}

function Flag({ iso2, name, size = 32 }) {
  const [err, setErr] = useState(false);
  const src = flagUrl(iso2);
  if (!src || err) {
    return (
      <span className="ld-flag-placeholder" style={{ width: size, height: size * 0.66, fontSize: size * 0.25 }}>
        {(name || '?').slice(0, 3).toUpperCase()}
      </span>
    );
  }
  return (
    <img
      src={src} alt={name}
      className="ld-flag"
      style={{ width: size, height: 'auto' }}
      onError={() => setErr(true)}
    />
  );
}

function MatchCard({ match, onPreview }) {
  const home    = match.home_team;
  const away    = match.away_team;
  const stadium = match.stadium;

  function fmtDate(local) {
    if (!local) return '';
    const [d, t] = local.split(' ');
    const [mo, day] = (d || '').split('/');
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    return `${months[parseInt(mo) - 1] || ''} ${parseInt(day) || ''}${t ? ` · ${t}` : ''}`;
  }

  function daysUntil() {
    const diff = Math.ceil((new Date(match.date) - new Date()) / 864e5);
    if (diff <= 0) return null;
    if (diff === 1) return 'Tomorrow';
    if (diff <= 14) return `In ${diff} days`;
    return null;
  }
  const countdown = daysUntil();

  return (
    <div className="ld-card" onClick={() => onPreview(match)}>
      <div className="ld-card-top">
        <span className="ld-group-badge">Group {match.group}</span>
        <span className="ld-md-badge">MD{match.matchday}</span>
        {countdown && <span className="ld-countdown">{countdown}</span>}
      </div>

      <div className="ld-teams">
        <div className="ld-team ld-team--home">
          <Flag iso2={home.iso2} name={home.name} size={36} />
          <span className="ld-team-name">{home.name}</span>
          <span className="ld-team-code">{home.fifa_code}</span>
        </div>
        <div className="ld-versus">vs</div>
        <div className="ld-team ld-team--away">
          <Flag iso2={away.iso2} name={away.name} size={36} />
          <span className="ld-team-name">{away.name}</span>
          <span className="ld-team-code">{away.fifa_code}</span>
        </div>
      </div>

      <div className="ld-card-bottom">
        <span className="ld-card-date">{fmtDate(match.local_date)}</span>
        <span className="ld-card-stadium">{stadium.name}, {stadium.city}</span>
      </div>

      <div className="ld-card-action">
        <span className="ld-preview-btn">AI Preview ▶</span>
      </div>
    </div>
  );
}

export default function Landing({ onEnterMatch }) {
  const [matches,      setMatches]      = useState([]);
  const [matchday,     setMatchday]     = useState(1);
  const [showAll,      setShowAll]      = useState(false);
  const [previewMatch, setPreviewMatch] = useState(null);
  const [heroReady,    setHeroReady]    = useState(false);

  useEffect(() => {
    fetch('/api/wc2026/matches').then(r => r.json()).then(setMatches).catch(console.error);
    const t = setTimeout(() => setHeroReady(true), 80);
    return () => clearTimeout(t);
  }, []);

  // Reset pagination when switching matchday
  useEffect(() => { setShowAll(false); }, [matchday]);

  const filtered  = useMemo(() => matches.filter(m => m.matchday === matchday), [matches, matchday]);
  const displayed = showAll ? filtered : filtered.slice(0, PAGE_SIZE);
  const hasMore   = !showAll && filtered.length > PAGE_SIZE;

  return (
    <div id="landing" className={heroReady ? 'landing--ready' : ''}>

      {/* ── Hero ──────────────────────────────────────────────────────── */}
      <div id="ld-hero">
        <div className="ld-hero-glow" />

        <div className="ld-hero-eyebrow">FIFA</div>
        <h1 className="ld-hero-title">
          <span className="ld-title-word">WORLD</span>
          <span className="ld-title-word">CUP</span>
        </h1>
        <div className="ld-hero-year">2026</div>
        <div className="ld-hero-hosts">Canada &nbsp;·&nbsp; Mexico &nbsp;·&nbsp; United States</div>
        <div className="ld-hero-dates">June 11 – July 19, 2026</div>

        <div className="ld-hero-appname">
          <span className="ld-appname-play">PLAYBACK</span>
          <span className="ld-appname-iq"> IQ</span>
        </div>
      </div>

      {/* ── Upcoming matches ───────────────────────────────────────────── */}
      <section id="ld-upcoming">
        <div className="ld-section-header">
          <h2 className="ld-section-title">Upcoming Matches</h2>
          <div className="ld-tabs">
            {MATCHDAYS.map(md => (
              <button
                key={md}
                className={`ld-tab${matchday === md ? ' ld-tab--active' : ''}`}
                onClick={() => setMatchday(md)}
              >
                Matchday {md}
              </button>
            ))}
          </div>
        </div>

        <div className="ld-card-grid">
          {displayed.map((m, i) => (
            <div key={m.id} className="ld-card-wrap" style={{ '--card-i': i }}>
              <MatchCard match={m} onPreview={setPreviewMatch} />
            </div>
          ))}
        </div>

        {hasMore && (
          <div className="ld-load-more-row">
            <button className="ld-load-more-btn" onClick={() => setShowAll(true)}>
              Show {filtered.length - PAGE_SIZE} more matches ↓
            </button>
          </div>
        )}
      </section>

      {/* ── Past matches ───────────────────────────────────────────────── */}
      <section id="ld-past">
        <h2 className="ld-section-title">Past Matches</h2>

        <div className="ld-past-card" onClick={onEnterMatch}>
          <div className="ld-past-glow" />
          <div className="ld-past-badge">2022 FIFA World Cup · Quarter-Final</div>

          <div className="ld-past-teams">
            <div className="ld-past-team">
              <Flag iso2="ma" name="Morocco" size={52} />
              <span className="ld-past-name">Morocco</span>
            </div>
            <div className="ld-past-score">
              <span className="ld-score-num">1</span>
              <span className="ld-score-dash">–</span>
              <span className="ld-score-num">0</span>
            </div>
            <div className="ld-past-team">
              <Flag iso2="pt" name="Portugal" size={52} />
              <span className="ld-past-name">Portugal</span>
            </div>
          </div>

          <div className="ld-past-meta">
            Dec 10, 2022 &nbsp;·&nbsp; Al Thumama Stadium, Doha
          </div>

          <div className="ld-past-action">
            <span className="ld-replay-btn">Replay ▶</span>
          </div>
        </div>
      </section>

      {previewMatch && (
        <UpcomingPregame match={previewMatch} onClose={() => setPreviewMatch(null)} />
      )}
    </div>
  );
}
