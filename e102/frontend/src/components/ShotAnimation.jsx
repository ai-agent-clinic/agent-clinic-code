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

import { useEffect, useState } from 'react';

const DURATION = {
  goal:   2800,
  saved:  2400,
  post:   2300,
  block:  2100,
  miss:   2000,
  yellow: 3200,
  red:    3400,
};

function GoalScene() {
  return (
    <div className="sa-scene sa-scene--goal">
      <div className="sa-net" />
      <div className="sa-goal-ball">{'⚽'}</div>
      {Array.from({ length: 12 }, (_, i) => (
        <div
          key={i}
          className="sa-particle"
          style={{
            '--angle': `${i * 30}deg`,
            '--speed': `${0.65 + (i % 4) * 0.15}s`,
            '--dist':  `${65 + (i % 5) * 22}px`,
            '--color': i % 3 === 0 ? '#FF9900' : i % 3 === 1 ? '#FFD700' : 'rgba(255,255,255,0.75)',
          }}
        />
      ))}
      <div className="sa-goal-text">GOAL!</div>
    </div>
  );
}

function SavedScene() {
  return (
    <div className="sa-scene sa-scene--saved">
      <div className="sa-saved-trail" />
      <div className="sa-saved-ball">{'⚽'}</div>
      <div className="sa-save-ripple" />
      <div className="sa-gloves">{'🧤'}</div>
      <div className="sa-saved-text">SAVED</div>
    </div>
  );
}

function PostScene() {
  return (
    <div className="sa-scene sa-scene--post">
      <div className="sa-post-frame" />
      <div className="sa-impact-ring" />
      <div className="sa-post-ball">{'⚽'}</div>
      <div className="sa-post-text">OFF THE POST</div>
    </div>
  );
}

function BlockScene() {
  return (
    <div className="sa-scene sa-scene--block">
      <div className="sa-block-trail" />
      <div className="sa-block-ball">{'⚽'}</div>
      <div className="sa-block-ripple" />
      <div className="sa-block-boot">{'🦵'}</div>
      <div className="sa-block-text">BLOCKED</div>
    </div>
  );
}

function MissScene() {
  return (
    <div className="sa-scene sa-scene--miss">
      <div className="sa-miss-trail" />
      <div className="sa-miss-ball">{'⚽'}</div>
      <div className="sa-miss-text">WIDE</div>
    </div>
  );
}

function CardScene({ color, event }) {
  const player = event?.player  ?? '';
  const minute = event?.minute  ?? '';
  const team   = event?.team    ?? '';

  return (
    <div className={`sa-scene sa-scene--${color}`}>
      <div className="sa-card-spotlight" />

      <div className={`sa-card-3d sa-card-3d--${color}`}>
        <div className={`sa-card-face sa-card-face--${color}`}>
          <div className="sa-card-sheen" />
          <div className="sa-card-top-band" />
          <div className="sa-card-content">
            <div className="sa-card-minute">{minute}&rsquo;</div>
            <div className="sa-card-rule" />
            <div className="sa-card-player">{player}</div>
            <div className="sa-card-team">{team}</div>
          </div>
        </div>
      </div>

      {/* Floating particles for yellow only */}
      {color === 'yellow' && Array.from({ length: 8 }, (_, i) => (
        <div
          key={i}
          className="sa-card-dust"
          style={{
            '--dx': `${(i % 4 - 1.5) * 55}px`,
            '--dy': `${-40 - (i % 3) * 30}px`,
            '--del': `${0.9 + i * 0.08}s`,
          }}
        />
      ))}

      <div className={`sa-card-label sa-card-label--${color}`}>
        {color === 'yellow' ? 'Yellow Card' : 'Red Card'}
      </div>
    </div>
  );
}

const SCENES = {
  goal:   GoalScene,
  saved:  SavedScene,
  post:   PostScene,
  block:  BlockScene,
  miss:   MissScene,
  yellow: (props) => <CardScene color="yellow" {...props} />,
  red:    (props) => <CardScene color="red"    {...props} />,
};

export default function ShotAnimation({ typeKey, event }) {
  const [phase, setPhase] = useState('in');
  const dur = DURATION[typeKey] ?? 2000;

  useEffect(() => {
    const t1 = setTimeout(() => setPhase('out'),  dur - 500);
    const t2 = setTimeout(() => setPhase('done'), dur);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [dur]);

  if (phase === 'done') return null;

  const Scene = SCENES[typeKey];
  if (!Scene) return null;

  return (
    <div className={`sa-wrap sa-wrap--${typeKey}${phase === 'out' ? ' sa-wrap--exit' : ''}`}>
      <Scene event={event} />
    </div>
  );
}
