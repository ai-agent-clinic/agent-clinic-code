import { useState, useRef, useEffect } from 'react';

const SCENES = [
  { id: 'opener',  label: 'Opening'      },
  { id: 'venue',   label: 'The Venue'    },
  { id: 'group',   label: 'Group Stakes' },
  { id: 'home',    label: 'Home Team'    },
  { id: 'away',    label: 'Away Team'    },
  { id: 'kickoff', label: 'Kickoff'      },
];

function Flag({ code, size = 48 }) {
  return (
    <div className="up-flag-code-large" style={{ fontSize: size * 0.45 }}>
      {code}
    </div>
  );
}

export default function UpcomingPreview({ match, onClose }) {
  const [status,       setStatus]       = useState('idle'); // idle | generating | ready | error
  const [progress,     setProgress]     = useState('');
  const [playing,      setPlaying]      = useState(false);
  const [clipMeta,     setClipMeta]     = useState(null);  // [{scene, audio_start, audio_end}]
  const [activeScene,  setActiveScene]  = useState(null);
  const [currentTime,  setCurrentTime]  = useState(0);
  const [duration,     setDuration]     = useState(0);

  const audioRef  = useRef(null);
  const rafRef    = useRef(null);
  const abortRef  = useRef(null);

  const home    = match.home_team;
  const away    = match.away_team;
  const stadium = match.stadium;

  // Format local date nicely: "06/11/2026 13:00" → "Jun 11, 2026 · 13:00"
  function fmtDate(local) {
    if (!local) return '';
    const [d, t] = local.split(' ');
    if (!d) return local;
    const [m, day, yr] = d.split('/');
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    return `${months[parseInt(m) - 1]} ${parseInt(day)}, ${yr}${t ? ` · ${t}` : ''}`;
  }

  function sceneFromTime(ct) {
    if (!clipMeta) return null;
    for (const c of clipMeta) {
      if (ct >= c.audio_start && ct <= c.audio_end) return c.scene;
    }
    // In a gap — attribute to previous scene
    let last = null;
    for (const c of clipMeta) {
      if (ct > c.audio_end) last = c.scene;
    }
    return last;
  }

  function fmtTime(s) {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, '0')}`;
  }

  // RAF tick while playing
  useEffect(() => {
    if (!playing) return;
    const audio = audioRef.current;
    if (!audio) return;
    const tick = () => {
      if (audio.ended) { setPlaying(false); setActiveScene(null); return; }
      setCurrentTime(audio.currentTime);
      setActiveScene(sceneFromTime(audio.currentTime));
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [playing, clipMeta]);

  // Close on Escape
  useEffect(() => {
    const onKey = e => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  // Cleanup audio on unmount
  useEffect(() => {
    return () => {
      const a = audioRef.current;
      if (a) { a.pause(); a.src = ''; }
      cancelAnimationFrame(rafRef.current);
      abortRef.current?.abort();
    };
  }, []);

  async function handleGenerate() {
    setStatus('generating');
    setProgress('Connecting…');
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      const resp = await fetch(`/api/wc2026/preview/generate?match_id=${match.id}`, {
        method: 'POST',
        signal: ctrl.signal,
      });
      const reader = resp.body.getReader();
      const dec    = new TextDecoder();
      let buf = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split('\n'); buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const msg = line.slice(6).trim();
          if (msg === 'DONE') {
            // Load audio + meta
            const audio = new Audio(`/api/wc2026/preview/audio?match_id=${match.id}`);
            audio.preload = 'auto';
            audioRef.current = audio;
            audio.playbackRate = 1.2;
            audio.defaultPlaybackRate = 1.2;
            audio.addEventListener('loadedmetadata', () => {
              audio.playbackRate = 1.2;
              setDuration(audio.duration);
            });
            audio.addEventListener('ended', () => { setPlaying(false); setActiveScene(null); });

            const metaResp = await fetch(`/api/wc2026/preview/audio-meta?match_id=${match.id}`);
            if (metaResp.ok) {
              const data = await metaResp.json();
              setClipMeta(data.clips);
              setDuration(data.total_duration);
            }
            setStatus('ready');
            setProgress('');
            return;
          } else if (msg.startsWith('ERROR')) {
            setStatus('error'); setProgress(msg);
          } else {
            setProgress(msg);
          }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') { setStatus('error'); setProgress('Request failed.'); }
    }
  }

  async function handlePlayPause() {
    const audio = audioRef.current;
    if (!audio) return;
    if (playing) { audio.pause(); setPlaying(false); }
    else {
      try {
        audio.playbackRate = 1.2;
        await audio.play(); setPlaying(true);
      }
      catch { setPlaying(false); }
    }
  }

  function handleNextScene() {
    const audio = audioRef.current;
    if (!audio || !clipMeta) return;
    const next = clipMeta.find(c => c.audio_start > audio.currentTime + 0.5);
    if (next) audio.currentTime = next.audio_start;
  }

  function handlePrevScene() {
    const audio = audioRef.current;
    if (!audio || !clipMeta) return;
    const prev = [...clipMeta].reverse().find(c => c.audio_start < audio.currentTime - 1.0);
    if (prev) audio.currentTime = prev.audio_start;
  }

  function handleSeek(e) {
    const audio = audioRef.current;
    if (!audio || !duration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const frac = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    audio.currentTime = frac * duration;
    setCurrentTime(frac * duration);
  }

  const fillPct = duration ? (currentTime / duration) * 100 : 0;

  return (
    <div className="up-backdrop" onClick={onClose}>
      <div className="up-bg-vignette" />

      <div className="up-modal" onClick={e => e.stopPropagation()}>
        <button className="up-close" onClick={onClose}>✕</button>

        {/* Match header */}
        <div className="up-header">
          <div className="up-team up-team--home">
            <Flag code={home.fifa_code} size={56} />
            <div className="up-team-name">{home.name}</div>
          </div>

          <div className="up-center">
            <div className="up-group-badge">Group {match.group} · MD{match.matchday}</div>
            <div className="up-vs">vs</div>
            <div className="up-date">{fmtDate(match.local_date)}</div>
            <div className="up-stadium">{stadium.name}</div>
            <div className="up-city">{stadium.city}, {stadium.country}</div>
            <div className="up-capacity">{stadium.capacity} capacity</div>
          </div>

          <div className="up-team up-team--away">
            <Flag code={away.fifa_code} size={56} />
            <div className="up-team-name">{away.name}</div>
          </div>
        </div>

        <div className="up-divider" />

        {/* Scene list */}
        <div className="up-scenes">
          {SCENES.map(s => (
            <div
              key={s.id}
              className={`up-scene${activeScene === s.id ? ' up-scene--active' : ''}`}
            >
              <span className="up-scene-dot" />
              <span className="up-scene-label">{s.label}</span>
            </div>
          ))}
        </div>

        {/* Controls */}
        <div className="up-controls">
          {status === 'idle' && (
            <button className="up-btn up-btn--primary" onClick={handleGenerate}>
              🎙 Generate AI Preview
            </button>
          )}

          {status === 'generating' && (
            <div className="up-generating">
              <span className="up-spinner" />
              <span className="up-progress-text">{progress}</span>
            </div>
          )}

          {status === 'error' && (
            <>
              <div className="up-error">{progress}</div>
              <button className="up-btn up-btn--primary" onClick={handleGenerate}>Retry</button>
            </>
          )}

          {status === 'ready' && (
            <div className="up-player">
              <div className="up-player-btns">
                <button className="up-icon-btn" onClick={handlePrevScene} title="Previous scene">⏮</button>
                <button className="up-play-btn" onClick={handlePlayPause}>
                  {playing ? '⏸' : '▶'}
                </button>
                <button className="up-icon-btn" onClick={handleNextScene} title="Next scene">⏭</button>
              </div>
              <div className="up-seek" onClick={handleSeek}>
                <div className="up-seek-fill" style={{ width: `${fillPct}%` }} />
              </div>
              <div className="up-time">{fmtTime(currentTime)} / {fmtTime(duration)}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
