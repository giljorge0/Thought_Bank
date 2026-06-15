import { useEffect, useRef, useState } from 'react';

const DOMAIN_COLORS = {
  Tech: '#3b82f6',
  Science: '#8b5cf6',
  Art: '#ec4899',
  Social: '#f97316',
  Commerce: '#22c55e',
  Nature: '#10b981',
  Philosophy: '#a855f7',
  Engineering: '#6366f1',
  Psychology: '#f59e0b',
  General: '#6b7280',
};

const DENSITY_COLORS = {
  SATURATED: '#ef4444',
  DENSE: '#f97316',
  POPULATED: '#eab308',
  SPARSE: '#22c55e',
  FRONTIER: '#3b82f6',
  VOID: '#8b5cf6',
};

export default function ThoughtMap({ thoughts, newPing, colorBy = 'domain' }) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const tooltipRef = useRef(null);
  const [tooltip, setTooltip] = useState(null);
  const [dims, setDims] = useState({ w: 600, h: 400 });
  const pingRef = useRef(null);

  // Resize observer
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      setDims({
        w: entry.contentRect.width,
        h: Math.max(300, entry.contentRect.height),
      });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Ping animation
  useEffect(() => {
    if (newPing) {
      pingRef.current = { ...newPing, age: 0 };
    }
  }, [newPing]);

  // Render
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    canvas.width = dims.w * dpr;
    canvas.height = dims.h * dpr;
    ctx.scale(dpr, dpr);

    const toX = (v) => ((v + 1) / 2) * (dims.w - 40) + 20;
    const toY = (v) => ((v + 1) / 2) * (dims.h - 40) + 20;

    // Background
    ctx.fillStyle = '#0a0a0f';
    ctx.fillRect(0, 0, dims.w, dims.h);

    // Grid
    ctx.strokeStyle = 'rgba(255,255,255,0.04)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 10; i++) {
      const x = (dims.w / 10) * i;
      const y = (dims.h / 10) * i;
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, dims.h); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(dims.w, y); ctx.stroke();
    }

    // Plot thoughts
    for (const t of thoughts) {
      const x = toX(t.mapCoordinates?.x || 0);
      const y = toY(t.mapCoordinates?.y || 0);
      const colors = colorBy === 'domain' ? DOMAIN_COLORS : DENSITY_COLORS;
      const key = colorBy === 'domain' ? t.domain : t.density;
      const color = colors[key] || '#6b7280';
      const radius = Math.max(2.5, Math.min(5, (100 - (t.score || 50)) / 20));

      ctx.beginPath();
      ctx.arc(x, y, radius, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.globalAlpha = 0.7;
      ctx.fill();
      ctx.globalAlpha = 1;
    }

    // Ping animation for new thought
    if (pingRef.current) {
      const p = pingRef.current;
      const x = toX(p.mapCoordinates?.x || 0);
      const y = toY(p.mapCoordinates?.y || 0);
      const age = p.age || 0;

      for (let ring = 0; ring < 3; ring++) {
        const r = 5 + age * 2 + ring * 8;
        const alpha = Math.max(0, 0.6 - age * 0.02 - ring * 0.15);
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(255, 255, 255, ${alpha})`;
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }

      p.age++;
      if (p.age < 30) {
        requestAnimationFrame(() => {
          // Trigger re-render for animation
          setDims(d => ({ ...d }));
        });
      } else {
        pingRef.current = null;
      }
    }
  }, [thoughts, dims, colorBy, newPing]);

  // Hover tooltip
  const handleMouseMove = (e) => {
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    const toX = (v) => ((v + 1) / 2) * (dims.w - 40) + 20;
    const toY = (v) => ((v + 1) / 2) * (dims.h - 40) + 20;

    let closest = null;
    let minDist = 15; // pixel threshold

    for (const t of thoughts) {
      const x = toX(t.mapCoordinates?.x || 0);
      const y = toY(t.mapCoordinates?.y || 0);
      const d = Math.sqrt((mx - x) ** 2 + (my - y) ** 2);
      if (d < minDist) {
        closest = t;
        minDist = d;
      }
    }

    if (closest) {
      setTooltip({
        x: mx,
        y: my,
        thought: closest.thought,
        score: closest.score,
        density: closest.density,
        domain: closest.domain,
      });
    } else {
      setTooltip(null);
    }
  };

  return (
    <div className="thought-map" ref={containerRef}>
      <canvas
        ref={canvasRef}
        style={{ width: '100%', height: '100%', cursor: 'crosshair' }}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setTooltip(null)}
      />
      {tooltip && (
        <div
          className="map-tooltip"
          style={{ left: tooltip.x + 12, top: tooltip.y - 10 }}
        >
          <div className="tooltip-thought">
            {tooltip.thought.slice(0, 80)}{tooltip.thought.length > 80 ? '…' : ''}
          </div>
          <div className="tooltip-meta">
            <span>{tooltip.score}/100</span>
            <span>{tooltip.density}</span>
            <span>{tooltip.domain}</span>
          </div>
        </div>
      )}
    </div>
  );
}
