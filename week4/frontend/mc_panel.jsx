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

const { useState: mUseState, useEffect: mUseEffect } = React;

// Default symbol set — matches the rows in week1/nifty_comparison.csv. If the
// user supplies their own list (from FinPilot signals), it overrides this.
const MC_DEFAULT_SYMBOLS = [
  'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS',
  'INFY.NS', 'WIPRO.NS', 'ICICIBANK.NS',
];


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
function MonteCarloPanel({ availableSymbols }) {
  const symbols = (availableSymbols && availableSymbols.length)
    ? availableSymbols : MC_DEFAULT_SYMBOLS;
  const [symbol, setSymbol] = mUseState(symbols[0]);
  const [capital, setCapital] = mUseState(1000);
  const [horizon, setHorizon] = mUseState(5);
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
      + `&capital=${capital}&horizon_days=${horizon}`;
    fetch(url)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => { if (!cancelled) { setResult(d); setLoading(false); } })
      .catch((e) => { if (!cancelled) { setError(e.message); setLoading(false); } });
    return () => { cancelled = true; };
  }, [symbol, capital, horizon]);

  return (
    <div className="card">
      <div className="card-title">Monte Carlo projection</div>
      <p className="muted" style={{ fontSize: 12, marginBottom: 14 }}>
        Bootstraps {result?.n_sims || 2000} trade paths from the 1-yr backtest
        stats, applies Zerodha CNC costs, returns the probability cone for the
        next {horizon} trading days.
      </p>

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
          error: {error}. Is the Django API running on {window.FINPILOT_API}?
        </div>
      )}
      {loading && !result && <div className="muted">loading…</div>}

      {result && (
        <>
          <FanChart data={result} />

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
            buy, DP charge ₹15.93 flat per sell day. Normal-returns model — real
            markets have fat tails, so the 5th-percentile loss UNDERSTATES the
            worst case. See <code>LEARNINGS.md #70a</code>.
          </p>
        </>
      )}
    </div>
  );
}


// ── Sidebar-nav wrapper ─────────────────────────────────────────────────────
function MonteCarloView({ stocks }) {
  // Build a symbol picker from the FinPilot signal map if available, otherwise
  // fall back to the static basket. Cardinal stores bare symbols ("RELIANCE");
  // the API wants NSE-suffixed ("RELIANCE.NS"), so re-attach .NS.
  const symbols = stocks?.length
    ? stocks.map((s) => `${s.sym}.NS`)
    : MC_DEFAULT_SYMBOLS;
  return (
    <div className="view-enter">
      <PageHead
        title="Monte Carlo Simulation"
        subtitle="1-week probability cone from real backtest stats + Zerodha cost stack" />
      <MonteCarloPanel availableSymbols={symbols} />
    </div>
  );
}


Object.assign(window, { FanChart, MonteCarloPanel, MonteCarloView });
