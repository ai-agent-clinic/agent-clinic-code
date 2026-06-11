import { useRef, useEffect } from 'react';

const BARS     = 32;
const BAR_GAP  = 2;
const AMBER    = [255, 153, 0];

export default function Waveform({ analyserRef, playing }) {
  const canvasRef = useRef(null);
  const rafRef    = useRef(null);
  const dataArr   = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    function draw() {
      rafRef.current = requestAnimationFrame(draw);
      const analyser = analyserRef.current;
      const W = canvas.offsetWidth, H = canvas.offsetHeight;
      if (!W || !H) return;

      const dpr = window.devicePixelRatio || 1;
      if (canvas.width !== Math.round(W * dpr) || canvas.height !== Math.round(H * dpr)) {
        canvas.width  = Math.round(W * dpr);
        canvas.height = Math.round(H * dpr);
      }
      const ctx = canvas.getContext('2d');
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);

      if (!analyser || !playing) return;

      if (!dataArr.current || dataArr.current.length !== analyser.frequencyBinCount) {
        dataArr.current = new Uint8Array(analyser.frequencyBinCount);
      }
      analyser.getByteFrequencyData(dataArr.current);

      const bw   = (W - BAR_GAP * (BARS - 1)) / BARS;
      const step = Math.floor(dataArr.current.length / BARS);

      for (let i = 0; i < BARS; i++) {
        const val = dataArr.current[i * step] / 255;
        const bh  = Math.max(3, val * H);
        const x   = i * (bw + BAR_GAP);
        const y   = H - bh;
        const a   = 0.25 + val * 0.75;
        ctx.fillStyle = `rgba(${AMBER[0]},${AMBER[1]},${AMBER[2]},${a.toFixed(2)})`;
        ctx.fillRect(x, y, bw, bh);
      }
    }

    draw();
    return () => cancelAnimationFrame(rafRef.current);
  }, [analyserRef, playing]);

  return <canvas ref={canvasRef} className="wf-canvas" />;
}
