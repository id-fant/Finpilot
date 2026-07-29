// mc_panel.jsx — Monte Carlo projection panel for the Cardinal dashboard.
//
// Reads the same backtest stats as week1/one_week_simulation.py via the
// Django endpoint /api/portfolio/projection/, then renders the probability
// cone as raw SVG (matching the existing charts.jsx style — no Recharts /
// d3 dependency to ship).
//
// Components exported on window:
//   FanChart         — pure SVG visualisation of the percentile bands
//   MonteCarloPanel  — controls + fetch + FanChart + summary stats
//   MonteCarloView   — sidebar-nav wrapper (PageHead + MonteCarloPanel)

const {
  useState: mUseState,
  useEffect: mUseEffect,
  useMemo: mUseMemo,
  useRef: mUseRef,
} = React;

// Default symbol set — matches the rows in week1/nifty_comparison.csv. If the
// user supplies their own list (from FinPilot signals), it overrides this.
const MC_DEFAULT_SYMBOLS = [
  'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS',
  'INFY.NS', 'WIPRO.NS', 'ICICIBANK.NS',
];

const MC_METHODS = [
  {
    id: 'gaussian',
    label: 'Gaussian',
    detail: 'Normal returns',
    description: 'Arithmetic returns sampled from a normal distribution.',
  },
  {
    id: 'gbm',
    label: 'GBM',
    detail: 'Lognormal paths',
    description: 'Geometric Brownian motion with continuously compounded returns.',
  },
  {
    id: 'student_t',
    label: 'Student-t',
    detail: 'Fat-tail stress',
    description: 'Heavy-tailed shocks expose more extreme upside and downside paths.',
  },
  {
    id: 'mean_reversion',
    label: 'Mean reversion',
    detail: 'Trend anchored',
    description: 'Log prices are pulled toward the return trend after large moves.',
  },
];

const DEFAULT_SURFACE_CAMERA = Object.freeze({
  azimuth: -0.72,
  elevation: 0.58,
  zoom: 1,
});
const MIN_SURFACE_ELEVATION = 0.34;
const MAX_SURFACE_ELEVATION = 1.08;
const MIN_SURFACE_ZOOM = 0.72;
const MAX_SURFACE_ZOOM = 1.45;

function validSurfaceCamera(camera) {
  const candidate = camera
    && Number.isFinite(camera.azimuth)
    && Number.isFinite(camera.elevation)
    && Number.isFinite(camera.zoom)
    ? camera
    : DEFAULT_SURFACE_CAMERA;
  return {
    azimuth: candidate.azimuth,
    elevation: Math.max(
      MIN_SURFACE_ELEVATION,
      Math.min(MAX_SURFACE_ELEVATION, candidate.elevation),
    ),
    zoom: Math.max(
      MIN_SURFACE_ZOOM,
      Math.min(MAX_SURFACE_ZOOM, candidate.zoom),
    ),
  };
}


// ── FanChart — raw SVG, no chart library ────────────────────────────────────
function FanChart({ data, width = 760, height = 300 }) {
  if (!data) return null;
  const { days, percentiles, capital } = data;

  // Inner-plot box (account for axis labels at left + bottom).
  const m = { top: 16, right: 60, bottom: 28, left: 60 };
  const W = width - m.left - m.right;
  const H = height - m.top - m.bottom;

  // Y range — pad 2% beyond the widest band so the cone doesn't kiss the edge.
  const yMin = Math.min(...percentiles.p05) * 0.99;
  const yMax = Math.max(...percentiles.p95) * 1.01;
  const yRange = yMax - yMin || 1;

  const xAt = (d) => m.left + (W * d) / (days.length - 1);
  const yAt = (v) => m.top + H - ((v - yMin) / yRange) * H;

  // Build an SVG path for a filled band between an upper and lower series.
  // Walk along the upper curve forward, then back along the lower curve.
  function bandPath(upper, lower) {
    const top = upper.map((v, i) => `${i ? 'L' : 'M'}${xAt(days[i])} ${yAt(v)}`).join(' ');
    const bot = lower
      .slice().reverse()
      .map((v, i) => `L${xAt(days[days.length - 1 - i])} ${yAt(v)}`)
      .join(' ');
    return `${top} ${bot} Z`;
  }

  // Median line — solid, drawn on top of the bands.
  const medianD = percentiles.p50
    .map((v, i) => `${i ? 'L' : 'M'}${xAt(days[i])} ${yAt(v)}`)
    .join(' ');

  // Y-axis ticks — 4 evenly-spaced rounded levels.
  const yTicks = [];
  for (let i = 0; i <= 4; i++) {
    const v = yMin + (yRange * i) / 4;
    yTicks.push({ y: yAt(v), label: `₹${Math.round(v)}` });
  }

  const yCap = yAt(capital);

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}
         style={{ width: '100%', height: 'auto' }}>
      {/* Grid lines + Y-axis labels */}
      {yTicks.map((t, i) => (
        <g key={i}>
          <line x1={m.left} y1={t.y} x2={width - m.right} y2={t.y}
                stroke="var(--line)" strokeWidth="0.5" />
          <text x={m.left - 8} y={t.y + 4} fontSize="11"
                textAnchor="end" fill="var(--text-2)" className="mono">
            {t.label}
          </text>
        </g>
      ))}

      {/* 5-95% band — lighter, wider */}
      <path d={bandPath(percentiles.p95, percentiles.p05)}
            fill="#2563EB" fillOpacity="0.12" />
      {/* 25-75% band — darker, tighter */}
      <path d={bandPath(percentiles.p75, percentiles.p25)}
            fill="#2563EB" fillOpacity="0.28" />
      {/* Median path */}
      <path d={medianD} stroke="#1E3A8A" strokeWidth="2" fill="none" />

      {/* Starting-capital reference (dashed horizontal) */}
      <line x1={m.left} y1={yCap} x2={width - m.right} y2={yCap}
            stroke="#9CA3AF" strokeWidth="1" strokeDasharray="3 3" />
      <text x={width - m.right + 6} y={yCap + 4} fontSize="10"
            fill="#9CA3AF" className="mono">₹{Math.round(capital)}</text>

      {/* X-axis labels */}
      {days.map((d, i) => (
        <text key={i} x={xAt(d)} y={height - 8} fontSize="11"
              textAnchor="middle" fill="var(--text-2)">
          {d === 0 ? 'today' : `day ${d}`}
        </text>
      ))}

      {/* Legend */}
      <g transform={`translate(${m.left + 8}, ${m.top + 8})`}>
        <rect width="14" height="10" fill="#2563EB" fillOpacity="0.28" />
        <text x="20" y="9" fontSize="10" fill="var(--text-2)">25–75%</text>
        <rect x="80" width="14" height="10" fill="#2563EB" fillOpacity="0.12" />
        <text x="100" y="9" fontSize="10" fill="var(--text-2)">5–95%</text>
        <line x1="160" y1="5" x2="174" y2="5" stroke="#1E3A8A" strokeWidth="2" />
        <text x="180" y="9" fontSize="10" fill="var(--text-2)">median</text>
      </g>
    </svg>
  );
}


// ── Interactive 3D price surface ────────────────────────────────────────────
// Five percentile paths become a small probability surface: time runs along
// X, confidence percentile along Y, and projected stock price rises on Z.
// Raw SVG keeps the Vite bundle dependency-free; pointer/keyboard controls
// make the depth view functional rather than decorative.
function PriceSurface3D({ data }) {
  const [camera, setCamera] = mUseState(DEFAULT_SURFACE_CAMERA);
  const activeCamera = validSurfaceCamera(camera);
  const cameraRef = mUseRef(DEFAULT_SURFACE_CAMERA);
  const cameraFrame = mUseRef(null);
  const drag = mUseRef(null);
  const quantiles = ['p05', 'p25', 'p50', 'p75', 'p95'];
  const labels = ['5%', '25%', '50%', '75%', '95%'];
  const series = data.price_percentiles || data.percentiles;
  const values = quantiles.flatMap((key) => series[key] || []);
  const valueMin = Math.min(...values);
  const valueMax = Math.max(...values);
  const valueRange = valueMax - valueMin || 1;
  const days = data.days;

  const geometry = mUseMemo(() => {
    const cosA = Math.cos(activeCamera.azimuth);
    const sinA = Math.sin(activeCamera.azimuth);
    const cosE = Math.cos(activeCamera.elevation);
    const sinE = Math.sin(activeCamera.elevation);
    const scale = 200 * activeCamera.zoom;

    function project(dayIndex, quantileIndex, value) {
      const x = (dayIndex / Math.max(days.length - 1, 1) - 0.5) * 2.4;
      const y = (quantileIndex / (quantiles.length - 1) - 0.5) * 1.35;
      const z = ((value - valueMin) / valueRange - 0.5) * 1.5;
      const rotatedX = x * cosA - y * sinA;
      const rotatedY = x * sinA + y * cosA;
      const screenY = rotatedY * cosE - z * sinE;
      const depth = rotatedY * sinE + z * cosE;
      return {
        x: 450 + rotatedX * scale,
        y: 168 + screenY * scale,
        depth,
      };
    }

    const points = quantiles.map((key, q) =>
      series[key].map((value, d) => project(d, q, value)));
    const cells = [];
    for (let q = 0; q < quantiles.length - 1; q += 1) {
      for (let d = 0; d < days.length - 1; d += 1) {
        const corners = [
          points[q][d],
          points[q][d + 1],
          points[q + 1][d + 1],
          points[q + 1][d],
        ];
        cells.push({
          key: `${q}-${d}`,
          q,
          depth: corners.reduce((sum, point) => sum + point.depth, 0) / 4,
          path: corners.map((point) => `${point.x},${point.y}`).join(' '),
        });
      }
    }
    cells.sort((a, b) => a.depth - b.depth);

    const axisOrigin = project(0, 0, valueMin);
    function buildAxis(key, label, end, tickSpecs) {
      const dx = end.x - axisOrigin.x;
      const dy = end.y - axisOrigin.y;
      const length = Math.hypot(dx, dy) || 1;
      const ux = dx / length;
      const uy = dy / length;
      const nx = -uy;
      const ny = ux;
      return {
        key,
        label,
        start: axisOrigin,
        end,
        arrow: [
          `${end.x},${end.y}`,
          `${end.x - ux * 12 + nx * 5},${end.y - uy * 12 + ny * 5}`,
          `${end.x - ux * 12 - nx * 5},${end.y - uy * 12 - ny * 5}`,
        ].join(' '),
        labelPoint: {
          x: end.x - ux * 34 + nx * 12,
          y: end.y - uy * 34 + ny * 12,
        },
        ticks: tickSpecs.map((tick) => ({
          ...tick,
          x1: tick.point.x - nx * 4.5,
          y1: tick.point.y - ny * 4.5,
          x2: tick.point.x + nx * 4.5,
          y2: tick.point.y + ny * 4.5,
          labelX: tick.point.x + nx * 10,
          labelY: tick.point.y + ny * 10,
        })),
      };
    }

    const lastDayIndex = days.length - 1;
    const midDayIndex = Math.floor(lastDayIndex / 2);
    const midValue = valueMin + valueRange / 2;
    const axes = [
      buildAxis(
        'x',
        'X / TRADING DAY',
        project(
          lastDayIndex + Math.max(0.65, lastDayIndex * 0.16),
          0,
          valueMin,
        ),
        [
          { point: project(midDayIndex, 0, valueMin), label: `D${days[midDayIndex]}` },
          { point: project(lastDayIndex, 0, valueMin), label: `D${days[lastDayIndex]}` },
        ],
      ),
      buildAxis(
        'y',
        'Y / PERCENTILE',
        project(0, quantiles.length - 1 + 0.7, valueMin),
        [
          { point: project(0, 2, valueMin), label: 'P50' },
          { point: project(0, 4, valueMin), label: 'P95' },
        ],
      ),
      buildAxis(
        'z',
        'Z / PRICE',
        project(0, 0, valueMax + valueRange * 0.22),
        [
          { point: project(0, 0, midValue), value: midValue },
          { point: project(0, 0, valueMax), value: valueMax },
        ],
      ),
    ];

    return {
      points,
      cells,
      axisOrigin,
      axes,
    };
  }, [
    activeCamera.azimuth,
    activeCamera.elevation,
    activeCamera.zoom,
    days,
    series,
    valueMin,
    valueRange,
  ]);

  const formatPrice = (value) => (
    data.price_scale === 'indexed'
      ? `${value.toFixed(1)} idx`
      : `₹${value.toFixed(2)}`
  );

  // Pointer devices can emit far more move events than the display can draw.
  // Keep the camera authoritative in a ref and commit at most once per frame,
  // preventing React update queues from building up behind the cursor.
  function scheduleCamera(update) {
    const current = validSurfaceCamera(cameraRef.current);
    cameraRef.current = validSurfaceCamera(
      typeof update === 'function' ? update(current) : update,
    );
    if (cameraFrame.current != null) return;
    cameraFrame.current = requestAnimationFrame(() => {
      cameraFrame.current = null;
      setCamera(cameraRef.current);
    });
  }

  mUseEffect(() => () => {
    drag.current = null;
    if (cameraFrame.current != null) {
      cancelAnimationFrame(cameraFrame.current);
      cameraFrame.current = null;
    }
  }, []);

  function beginOrbit(event) {
    const current = validSurfaceCamera(cameraRef.current);
    drag.current = {
      x: event.clientX,
      y: event.clientY,
      azimuth: current.azimuth,
      elevation: current.elevation,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function orbit(event) {
    // Capture the drag origin before scheduling the state update. Pointer-up
    // clears the ref, and React may invoke this updater after that event.
    const dragStart = drag.current;
    if (!dragStart) return;
    const dx = event.clientX - dragStart.x;
    const dy = event.clientY - dragStart.y;
    scheduleCamera((current) => ({
      ...current,
      azimuth: dragStart.azimuth + dx * 0.008,
      elevation: Math.max(
        MIN_SURFACE_ELEVATION,
        Math.min(
          MAX_SURFACE_ELEVATION,
          dragStart.elevation + dy * 0.006,
        ),
      ),
    }));
  }

  function zoom(event) {
    event.preventDefault();
    scheduleCamera((current) => ({
      ...current,
      zoom: Math.max(
        MIN_SURFACE_ZOOM,
        Math.min(MAX_SURFACE_ZOOM, current.zoom - event.deltaY * 0.001),
      ),
    }));
  }

  function endOrbit(event) {
    drag.current = null;
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  function keyboardOrbit(event) {
    const moves = {
      ArrowLeft: [-0.12, 0],
      ArrowRight: [0.12, 0],
      ArrowUp: [0, -0.1],
      ArrowDown: [0, 0.1],
    };
    if (moves[event.key]) {
      event.preventDefault();
      scheduleCamera((current) => ({
        ...current,
        azimuth: current.azimuth + moves[event.key][0],
        elevation: Math.max(
          MIN_SURFACE_ELEVATION,
          Math.min(
            MAX_SURFACE_ELEVATION,
            current.elevation + moves[event.key][1],
          ),
        ),
      }));
    }
    if (event.key === '+' || event.key === '=') {
      scheduleCamera((current) => ({
        ...current,
        zoom: Math.min(MAX_SURFACE_ZOOM, current.zoom + 0.08),
      }));
    }
    if (event.key === '-') {
      scheduleCamera((current) => ({
        ...current,
        zoom: Math.max(MIN_SURFACE_ZOOM, current.zoom - 0.08),
      }));
    }
  }

  const medianPoints = geometry.points[2]
    .map((point) => `${point.x},${point.y}`)
    .join(' ');

  return (
    <section className="price-surface-panel">
      <div className="surface-head">
        <div>
          <div className="surface-kicker">3D probability surface</div>
          <div className="surface-title">
            {data.symbol} · {data.method_label || 'Projection model'}
          </div>
        </div>
        <div className="surface-actions">
          <span>drag to orbit · wheel to zoom</span>
          <button
            type="button"
            className="surface-reset"
            onClick={() => scheduleCamera(DEFAULT_SURFACE_CAMERA)}
          >
            Reset view
          </button>
        </div>
      </div>

      <div
        className="price-surface-stage"
        role="application"
        tabIndex="0"
        aria-label={`Interactive 3D projected price surface for ${data.symbol}. Drag to rotate, use the mouse wheel to zoom, or use arrow and plus/minus keys.`}
        onPointerDown={beginOrbit}
        onPointerMove={orbit}
        onPointerUp={endOrbit}
        onPointerCancel={endOrbit}
        onLostPointerCapture={() => { drag.current = null; }}
        onWheel={zoom}
        onKeyDown={keyboardOrbit}
      >
        <svg viewBox="0 0 900 430" aria-hidden="true">
          <defs>
            <linearGradient id="surfaceFade" x1="0" x2="1">
              <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.08" />
              <stop offset="100%" stopColor="var(--accent)" stopOpacity="0.56" />
            </linearGradient>
          </defs>

          <g className="surface-axes">
            {geometry.axes.map((axis) => {
              const { start, end } = axis;
              return (
                <g key={axis.key} className={`surface-axis-${axis.key}`}>
                  <line
                    x1={start.x}
                    y1={start.y}
                    x2={end.x}
                    y2={end.y}
                    className="surface-axis-line"
                  />
                  <polygon points={axis.arrow} className="surface-axis-arrow" />
                  {axis.ticks.map((tick, index) => (
                    <g key={`${axis.key}-tick-${index}`}>
                      <line
                        x1={tick.x1}
                        y1={tick.y1}
                        x2={tick.x2}
                        y2={tick.y2}
                        className="surface-axis-tick"
                      />
                      <text
                        x={tick.labelX}
                        y={tick.labelY}
                        textAnchor="middle"
                        className="surface-axis-tick-label"
                      >
                        {axis.key === 'z' ? formatPrice(tick.value) : tick.label}
                      </text>
                    </g>
                  ))}
                  <text
                    x={axis.labelPoint.x}
                    y={axis.labelPoint.y}
                    textAnchor="middle"
                    className="surface-axis-name"
                  >
                    {axis.label}
                  </text>
                </g>
              );
            })}
            <circle
              cx={geometry.axisOrigin.x}
              cy={geometry.axisOrigin.y}
              r="3.5"
              className="surface-axis-origin"
            />
            <text
              x={geometry.axisOrigin.x - 8}
              y={geometry.axisOrigin.y + 17}
              textAnchor="end"
              className="surface-axis-origin-label"
            >
              ORIGIN
            </text>
          </g>

          {geometry.cells.map((cell) => (
            <polygon
              key={cell.key}
              points={cell.path}
              fill="url(#surfaceFade)"
              fillOpacity={0.28 + cell.q * 0.09}
              stroke="var(--surface-grid)"
              strokeWidth="0.8"
            />
          ))}

          {geometry.points.map((line, q) => (
            <polyline
              key={quantiles[q]}
              points={line.map((point) => `${point.x},${point.y}`).join(' ')}
              fill="none"
              stroke={q === 2 ? 'var(--surface-median)' : 'var(--surface-line)'}
              strokeWidth={q === 2 ? 2.5 : 1}
              opacity={q === 2 ? 1 : 0.72}
            />
          ))}
          <polyline
            points={medianPoints}
            fill="none"
            stroke="var(--surface-median)"
            strokeWidth="2.5"
          />

          {geometry.points.map((line, q) => {
            const point = line[line.length - 1];
            return (
              <text
                key={`label-${quantiles[q]}`}
                x={point.x + 7}
                y={point.y + 4}
                className={q === 2 ? 'surface-label median' : 'surface-label'}
              >
                {labels[q]}
              </text>
            );
          })}

          {[0, Math.floor((days.length - 1) / 2), days.length - 1].map((d) => {
            const point = geometry.points[0][d];
            return (
              <text
                key={`day-${d}`}
                x={point.x}
                y={point.y + 22}
                textAnchor="middle"
                className="surface-axis"
              >
                {d === 0 ? 'today' : `day ${days[d]}`}
              </text>
            );
          })}
        </svg>
        <div className="surface-scale" aria-hidden="true">
          <span>{formatPrice(valueMax)}</span>
          <i />
          <span>{formatPrice(valueMin)}</span>
        </div>
      </div>

      <div className="surface-foot">
        <span>
          Z axis: {data.price_scale === 'indexed' ? 'indexed price' : 'stock price'}
        </span>
        <span>X axis: trading day</span>
        <span>Y axis: simulation percentile</span>
      </div>
      {data.price_scale === 'indexed' && (
        <p className="surface-note">
          No persisted market quote was available, so the surface is rebased to 100.
        </p>
      )}
    </section>
  );
}


// ── Stat — small KPI tile (matches existing card-stat style) ────────────────
function McStat({ label, value, color }) {
  return (
    <div style={{ minWidth: 110, padding: '8px 0' }}>
      <div className="muted" style={{ fontSize: 11 }}>{label}</div>
      <div className="mono" style={{
        fontSize: 18, marginTop: 2,
        color: color || 'var(--text)',
      }}>{value}</div>
    </div>
  );
}


// ── Main panel ──────────────────────────────────────────────────────────────
class SimulationChartBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error('Simulation chart rendering failed', error, info);
  }

  componentDidUpdate(previousProps) {
    if (this.state.error && previousProps.resetKey !== this.props.resetKey) {
      this.setState({ error: null });
    }
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <section className="price-surface-panel surface-local-error" role="alert">
        <div className="surface-kicker">3D renderer paused</div>
        <strong>The rest of FinPilot is still running.</strong>
        <p>{this.state.error.message || 'The chart could not be drawn.'}</p>
        <button
          type="button"
          className="surface-reset"
          onClick={() => this.setState({ error: null })}
        >
          Restart chart
        </button>
      </section>
    );
  }
}

function MonteCarloPanel({ availableSymbols }) {
  const symbols = (availableSymbols && availableSymbols.length)
    ? availableSymbols : MC_DEFAULT_SYMBOLS;
  const [symbol, setSymbol] = mUseState(symbols[0]);
  const [capital, setCapital] = mUseState(1000);
  const [horizon, setHorizon] = mUseState(5);
  const [method, setMethod] = mUseState('gaussian');
  const [result, setResult] = mUseState(null);
  const [loading, setLoading] = mUseState(false);
  const [error, setError] = mUseState(null);

  // Re-fetch on any input change. The endpoint is fast (~50ms) so we can
  // refresh as the user types — no debounce needed at n_sims=2000.
  mUseEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const url = `${window.FINPILOT_API}/portfolio/projection/`
      + `?symbol=${encodeURIComponent(symbol)}`
      + `&capital=${capital}&horizon_days=${horizon}`
      + `&method=${encodeURIComponent(method)}`;
    fetch(url)
      .then(async (r) => {
        if (!r.ok) {
          // The endpoint's error body says WHY (e.g. "no backtest stats for
          // 'X'") — surface that instead of a bare status code. A 404 here
          // means the API answered; only a failed fetch means it's down.
          const body = await r.json().catch(() => null);
          throw new Error((body && body.error) || `HTTP ${r.status}`);
        }
        return r.json();
      })
      .then((d) => { if (!cancelled) { setResult(d); setLoading(false); } })
      .catch((e) => { if (!cancelled) { setError(e.message); setLoading(false); } });
    return () => { cancelled = true; };
  }, [symbol, capital, horizon, method]);

  const selectedMethod = MC_METHODS.find((item) => item.id === method)
    || MC_METHODS[0];

  return (
    <div className="card">
      <div className="card-title">Monte Carlo projection</div>
      <p className="muted" style={{ fontSize: 12, marginBottom: 14 }}>
        Simulates {result?.n_sims || 2000} paths from the 1-yr backtest stats,
        applies Zerodha CNC costs, and redraws both charts when you change the
        calculation method.
      </p>

      <div className="method-switcher">
        <div className="method-switch-head">
          <div>
            <span className="surface-kicker">Prediction method</span>
            <strong>{selectedMethod.label}</strong>
          </div>
          <span className={loading ? 'model-status is-loading' : 'model-status'}>
            {loading ? 'recalculating…' : 'model ready'}
          </span>
        </div>
        <div className="method-tabs" role="group" aria-label="Prediction method">
          {MC_METHODS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={method === item.id ? 'method-tab is-active' : 'method-tab'}
              aria-pressed={method === item.id}
              onClick={() => setMethod(item.id)}
            >
              <strong>{item.label}</strong>
              <small>{item.detail}</small>
            </button>
          ))}
        </div>
        <p className="method-description" aria-live="polite">
          {result?.method === method
            ? result.method_description
            : selectedMethod.description}
        </p>
      </div>

      {/* Controls row */}
      <div className="row gap-12" style={{ marginBottom: 16, flexWrap: 'wrap' }}>
        <div className="field" style={{ minWidth: 180 }}>
          <label>Symbol</label>
          <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
            {symbols.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div className="field" style={{ minWidth: 140 }}>
          <label>Capital (₹)</label>
          <input type="number" value={capital} min={100} step={500}
                 onChange={(e) => setCapital(Math.max(100, +e.target.value || 100))} />
        </div>
        <div className="field" style={{ minWidth: 140 }}>
          <label>Horizon (days)</label>
          <input type="number" value={horizon} min={1} max={20} step={1}
                 onChange={(e) => setHorizon(Math.max(1, Math.min(20, +e.target.value || 1)))} />
        </div>
      </div>

      {error && (
        <div className="muted" style={{ color: 'var(--red)', marginBottom: 12 }}>
          error: {error}
          {/* "Failed to fetch" = connection refused → the API really is down.
              Anything else came FROM the API, so don't blame the connection. */}
          {/fetch|network/i.test(error)
            ? `. Is the Django API running on ${window.FINPILOT_API}?`
            : ''}
        </div>
      )}
      {loading && !result && <div className="muted">loading…</div>}

      {result && (
        <>
          <div className={loading ? 'simulation-visuals is-updating' : 'simulation-visuals'}>
            <section className="fan-chart-panel">
              <div className="surface-kicker">
                2D capital cone · {result.method_label || selectedMethod.label}
              </div>
              <FanChart data={result} />
            </section>
            <SimulationChartBoundary resetKey={`${result.symbol}-${result.method}`}>
              <PriceSurface3D data={result} />
            </SimulationChartBoundary>
          </div>

          {/* Summary stats row */}
          <div className="row gap-16" style={{
            marginTop: 14, flexWrap: 'wrap',
            borderTop: '1px solid var(--line)', paddingTop: 12,
          }}>
            <McStat label="Expected net %"
                    value={`${result.expected_net_pct >= 0 ? '+' : ''}${result.expected_net_pct.toFixed(2)}%`}
                    color={result.expected_net_pct >= 0 ? 'var(--green)' : 'var(--red)'} />
            <McStat label="Median end" value={`₹${result.p50_net_end_rs.toFixed(0)}`} />
            <McStat label="Bad week (5%)"
                    value={`₹${result.p05_net_end_rs.toFixed(0)}`}
                    color="var(--red)" />
            <McStat label="Good week (95%)"
                    value={`₹${result.p95_net_end_rs.toFixed(0)}`}
                    color="var(--green)" />
            <McStat label="P(profit)"
                    value={`${result.prob_profit_pct.toFixed(1)}%`} />
            <McStat label="Cost drag"
                    value={`${result.cost_drag_pct.toFixed(2)}%`}
                    color={result.cost_drag_pct >= 1 ? 'var(--red)' : 'var(--text)'} />
          </div>

          <p className="muted" style={{ fontSize: 11, marginTop: 14, lineHeight: 1.5 }}>
            Stats from <code>week1/nifty_comparison.csv</code> · costs from Zerodha
            equity-delivery (CNC): STT 0.1%/leg, exchange 0.003%, stamp 0.015% on
            buy, DP charge ₹15.93 flat per sell day. Each method is a scenario
            model, not a guaranteed forecast; compare their spread and tail risk
            instead of treating one path as a price target.
          </p>
        </>
      )}
    </div>
  );
}


// ── Sidebar-nav wrapper ─────────────────────────────────────────────────────
function MonteCarloView({ stocks }) {
  // Build a symbol picker from the watchlist, but only keep symbols the
  // projection endpoint has backtest stats for (the rows in
  // week1/nifty_comparison.csv). The watchlist can hold GLOBAL symbols
  // (NVDA, AAPL — blindly appending ".NS" made "NVDA.NS") or NSE names
  // outside week1's backtest set (SBIN, ITC) — those 404 on first fetch and
  // used to render a misleading "is the API running?" error.
  const candidates = (stocks || []).map((s) => `${s.sym}.NS`);
  const withStats = candidates.filter((s) => MC_DEFAULT_SYMBOLS.includes(s));
  const symbols = withStats.length ? withStats : MC_DEFAULT_SYMBOLS;
  return (
    <div className="view-enter">
      <PageHead
        title="Monte Carlo Simulation"
        subtitle="1-week probability cone from real backtest stats + Zerodha cost stack" />
      <MonteCarloPanel availableSymbols={symbols} />
    </div>
  );
}


Object.assign(window, {
  FanChart: React.memo(FanChart),
  PriceSurface3D: React.memo(PriceSurface3D),
  MonteCarloPanel: React.memo(MonteCarloPanel),
  MonteCarloView: React.memo(MonteCarloView),
});
