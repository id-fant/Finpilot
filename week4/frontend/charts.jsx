// charts.jsx — Candlestick chart + sparkline

const { useState, useRef, useEffect, useMemo } = React;

// ── Sparkline ──────────────────────────────────────────────
function Sparkline({ data, color = 'currentColor', width = 70, height = 24, fill = false }) {
  if (!data?.length) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const stepX = width / (data.length - 1);
  const pts = data.map((v, i) => [i * stepX, height - ((v - min) / range) * (height - 2) - 1]);
  const d = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(2)} ${p[1].toFixed(2)}`).join(' ');
  const area = d + ` L ${width} ${height} L 0 ${height} Z`;
  const gradId = `sg-${Math.random().toString(36).slice(2, 7)}`;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ overflow: 'visible' }}>
      {fill && (
        <defs>
          <linearGradient id={gradId} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.35" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
      )}
      {fill && <path d={area} fill={`url(#${gradId})`} />}
      <path d={d} fill="none" stroke={color} strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

// ── Candlestick chart ──────────────────────────────────────
function CandleChart({ candles, accent = '#22e58a', height = 320, onHover }) {
  const ref = useRef(null);
  const [size, setSize] = useState({ w: 800, h: height });
  const [hover, setHover] = useState(null);

  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([e]) => {
      setSize({ w: e.contentRect.width, h: height });
    });
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, [height]);

  const padL = 50, padR = 16, padT = 14, padB = 28;
  const w = size.w, h = size.h;
  const chartW = Math.max(0, w - padL - padR);
  const chartH = Math.max(0, h - padT - padB);

  const data = candles || [];
  const { min, max, scaleY, scaleX, candleW } = useMemo(() => {
    if (!data.length) return { min: 0, max: 1, scaleY: () => 0, scaleX: () => 0, candleW: 0 };
    let lo = Infinity, hi = -Infinity;
    for (const c of data) { if (c.l < lo) lo = c.l; if (c.h > hi) hi = c.h; }
    const pad = (hi - lo) * 0.08 || 1;
    const min = lo - pad, max = hi + pad;
    const range = max - min;
    const candleW = chartW / data.length;
    return {
      min, max,
      scaleY: v => padT + (1 - (v - min) / range) * chartH,
      scaleX: i => padL + i * candleW + candleW / 2,
      candleW,
    };
  }, [data, chartH, chartW]);

  // Y-axis ticks
  const yTicks = useMemo(() => {
    const n = 5;
    const out = [];
    for (let i = 0; i < n; i++) {
      const v = min + (max - min) * (i / (n - 1));
      out.push({ v, y: scaleY(v) });
    }
    return out;
  }, [min, max, scaleY]);

  // X-axis ticks (every ~10 candles)
  const xTicks = useMemo(() => {
    if (!data.length) return [];
    const step = Math.max(1, Math.floor(data.length / 6));
    const out = [];
    for (let i = data.length - 1; i >= 0; i -= step) {
      out.push({ i, x: scaleX(i) });
    }
    return out.reverse();
  }, [data.length, scaleX]);

  function onMove(e) {
    const rect = ref.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const idx = Math.max(0, Math.min(data.length - 1, Math.floor((x - padL) / candleW)));
    const c = data[idx];
    if (c) setHover({ idx, x: scaleX(idx), y: scaleY(c.c), c });
  }
  function onLeave() { setHover(null); }

  const upColor = 'var(--green)';
  const downColor = 'var(--red)';

  // Area fill below close line (subtle background story)
  const closePath = data.map((c, i) => `${i ? 'L' : 'M'}${scaleX(i)} ${scaleY(c.c)}`).join(' ');
  const areaPath = closePath + ` L ${scaleX(data.length - 1)} ${padT + chartH} L ${scaleX(0)} ${padT + chartH} Z`;

  return (
    <div ref={ref} className="chart-host" onMouseMove={onMove} onMouseLeave={onLeave}>
      <svg width={w} height={h} style={{ display: 'block' }}>
        <defs>
          <linearGradient id="chart-bg-grad" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={accent} stopOpacity="0.10" />
            <stop offset="100%" stopColor={accent} stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* gridlines */}
        {yTicks.map((t, i) => (
          <g key={i}>
            <line x1={padL} x2={w - padR} y1={t.y} y2={t.y} stroke="rgba(255,255,255,0.04)" strokeDasharray="2 4" />
            <text x={padL - 8} y={t.y + 3} fontSize="10" fill="var(--text-3)" textAnchor="end" fontFamily="Geist Mono">
              {t.v.toFixed(t.v > 1000 ? 0 : 2)}
            </text>
          </g>
        ))}

        {/* area underlay */}
        <path d={areaPath} fill="url(#chart-bg-grad)" opacity="0.6" />

        {/* candles */}
        {data.map((c, i) => {
          const up = c.c >= c.o;
          const x = scaleX(i);
          const bodyTop = scaleY(Math.max(c.o, c.c));
          const bodyBot = scaleY(Math.min(c.o, c.c));
          const bodyH = Math.max(1, bodyBot - bodyTop);
          const wickTop = scaleY(c.h);
          const wickBot = scaleY(c.l);
          const bw = Math.max(2, candleW * 0.62);
          const color = up ? 'var(--green)' : 'var(--red)';
          return (
            <g key={i}>
              <line x1={x} x2={x} y1={wickTop} y2={wickBot} stroke={color} strokeWidth="1" />
              <rect x={x - bw / 2} y={bodyTop} width={bw} height={bodyH}
                    fill={up ? color : color} opacity={up ? 0.95 : 0.85}
                    rx="0.5" />
            </g>
          );
        })}

        {/* x labels */}
        {xTicks.map((t, i) => {
          const ago = data.length - 1 - t.i;
          const label = ago === 0 ? 'now' : `-${ago}`;
          return (
            <text key={i} x={t.x} y={h - padB + 16} fontSize="10" fill="var(--text-3)" textAnchor="middle" fontFamily="Geist Mono">
              {label}
            </text>
          );
        })}

        {/* current price line (last close) */}
        {data.length > 0 && (() => {
          const last = data[data.length - 1];
          const y = scaleY(last.c);
          const up = last.c >= last.o;
          return (
            <g>
              <line x1={padL} x2={w - padR} y1={y} y2={y} stroke={up ? 'var(--green)' : 'var(--red)'}
                    strokeDasharray="2 3" strokeWidth="1" opacity="0.6" />
              <rect x={w - padR - 56} y={y - 9} width="56" height="18" rx="4"
                    fill={up ? 'var(--green)' : 'var(--red)'} />
              <text x={w - padR - 28} y={y + 4} fontSize="11" fill="#062414" textAnchor="middle" fontFamily="Geist Mono" fontWeight="600">
                {last.c.toFixed(2)}
              </text>
            </g>
          );
        })()}

        {/* crosshair */}
        {hover && (
          <g>
            <line x1={hover.x} x2={hover.x} y1={padT} y2={padT + chartH}
                  stroke="rgba(255,255,255,0.20)" strokeDasharray="3 3" />
          </g>
        )}
      </svg>

      {hover && (
        <div className="chart-crosshair" style={{ left: hover.x, top: padT + 8 }}>
          <div className="row"><span className="label">O</span><span className="val">{hover.c.o.toFixed(2)}</span></div>
          <div className="row"><span className="label">H</span><span className="val">{hover.c.h.toFixed(2)}</span></div>
          <div className="row"><span className="label">L</span><span className="val">{hover.c.l.toFixed(2)}</span></div>
          <div className="row"><span className="label">C</span><span className="val">{hover.c.c.toFixed(2)}</span></div>
        </div>
      )}
    </div>
  );
}

// ── Line chart (alt to candle) ─────────────────────────────
function LineChart({ candles, accent = '#22e58a', height = 320 }) {
  const ref = useRef(null);
  const [size, setSize] = useState({ w: 800, h: height });
  const [hover, setHover] = useState(null);

  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([e]) => setSize({ w: e.contentRect.width, h: height }));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, [height]);

  const padL = 50, padR = 16, padT = 14, padB = 28;
  const w = size.w, h = size.h;
  const chartW = Math.max(0, w - padL - padR);
  const chartH = Math.max(0, h - padT - padB);
  const data = candles || [];

  const { min, max, scaleY, scaleX } = useMemo(() => {
    if (!data.length) return { min:0, max:1, scaleY:()=>0, scaleX:()=>0 };
    let lo = Infinity, hi = -Infinity;
    for (const c of data) { if (c.l < lo) lo = c.l; if (c.h > hi) hi = c.h; }
    const pad = (hi - lo) * 0.08 || 1;
    const min = lo - pad, max = hi + pad;
    const stepX = chartW / (data.length - 1);
    return {
      min, max,
      scaleY: v => padT + (1 - (v - min) / (max - min)) * chartH,
      scaleX: i => padL + i * stepX,
    };
  }, [data, chartH, chartW]);

  const yTicks = useMemo(() => {
    const n = 5; const out = [];
    for (let i = 0; i < n; i++) {
      const v = min + (max - min) * (i / (n - 1));
      out.push({ v, y: scaleY(v) });
    }
    return out;
  }, [min, max, scaleY]);

  const linePath = data.map((c, i) => `${i ? 'L' : 'M'}${scaleX(i)} ${scaleY(c.c)}`).join(' ');
  const areaPath = linePath + ` L ${scaleX(data.length-1)} ${padT+chartH} L ${scaleX(0)} ${padT+chartH} Z`;
  const last = data[data.length-1];
  const first = data[0];
  const up = last && first && last.c >= first.c;

  function onMove(e) {
    const rect = ref.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const stepX = chartW / (data.length - 1);
    const idx = Math.max(0, Math.min(data.length - 1, Math.round((x - padL) / stepX)));
    const c = data[idx];
    if (c) setHover({ idx, x: scaleX(idx), y: scaleY(c.c), c });
  }

  return (
    <div ref={ref} className="chart-host" onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
      <svg width={w} height={h} style={{display:'block'}}>
        <defs>
          <linearGradient id="line-grad" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={accent} stopOpacity="0.35"/>
            <stop offset="100%" stopColor={accent} stopOpacity="0"/>
          </linearGradient>
        </defs>
        {yTicks.map((t,i) => (
          <g key={i}>
            <line x1={padL} x2={w-padR} y1={t.y} y2={t.y} stroke="rgba(255,255,255,0.04)" strokeDasharray="2 4"/>
            <text x={padL-8} y={t.y+3} fontSize="10" fill="var(--text-3)" textAnchor="end" fontFamily="Geist Mono">
              {t.v.toFixed(t.v > 1000 ? 0 : 2)}
            </text>
          </g>
        ))}
        <path d={areaPath} fill="url(#line-grad)"/>
        <path d={linePath} fill="none" stroke={up ? 'var(--green)' : 'var(--red)'} strokeWidth="2" strokeLinejoin="round"/>
        {last && (() => {
          const y = scaleY(last.c);
          return (
            <g>
              <line x1={padL} x2={w-padR} y1={y} y2={y} stroke={up ? 'var(--green)' : 'var(--red)'} strokeDasharray="2 3" opacity="0.6"/>
              <circle cx={scaleX(data.length-1)} cy={y} r="4" fill={up ? 'var(--green)' : 'var(--red)'}/>
              <circle cx={scaleX(data.length-1)} cy={y} r="8" fill={up ? 'var(--green)' : 'var(--red)'} opacity="0.25">
                <animate attributeName="r" values="4;12;4" dur="2s" repeatCount="indefinite"/>
                <animate attributeName="opacity" values="0.4;0;0.4" dur="2s" repeatCount="indefinite"/>
              </circle>
              <rect x={w-padR-56} y={y-9} width="56" height="18" rx="4" fill={up ? 'var(--green)' : 'var(--red)'}/>
              <text x={w-padR-28} y={y+4} fontSize="11" fill="#062414" textAnchor="middle" fontFamily="Geist Mono" fontWeight="600">{last.c.toFixed(2)}</text>
            </g>
          );
        })()}
        {hover && <line x1={hover.x} x2={hover.x} y1={padT} y2={padT+chartH} stroke="rgba(255,255,255,0.20)" strokeDasharray="3 3"/>}
        {hover && <circle cx={hover.x} cy={hover.y} r="4" fill={accent} stroke="var(--card)" strokeWidth="2"/>}
      </svg>
      {hover && (
        <div className="chart-crosshair" style={{left: hover.x, top: padT + 8}}>
          <div className="row"><span className="label">Price</span><span className="val">{hover.c.c.toFixed(2)}</span></div>
          <div className="row"><span className="label">High</span><span className="val">{hover.c.h.toFixed(2)}</span></div>
        </div>
      )}
    </div>
  );
}

window.Sparkline = Sparkline;
window.CandleChart = CandleChart;
window.LineChart = LineChart;
