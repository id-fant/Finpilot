// quant_panel.jsx — the Quant Lab: the research track, on screen.
//
// Four cards backed by /api/quant/*:
//   ML model card    — the meta-labeling model's honest OOS report
//   Backtest stats   — week1's results table (same CSV as the README)
//   Pairs scan       — Engle-Granger cointegration over the tracked universe
//   Markowitz        — max-Sharpe tangency weights
//
// Pairs/weights fetch ON DEMAND (button), not on mount: the first call
// fetches 1y × 8 stocks from yfinance (~10-20s, then cached server-side for
// an hour) — auto-firing that on every view visit would hammer the API.
//
// Exported on window: QuantView

const { useState: qUseState, useEffect: qUseEffect } = React;

function qFetch(path, set, setErr, setBusy) {
  setBusy?.(true); setErr(null);
  fetch(`${window.FINPILOT_API}${path}`)
    .then(async (r) => {
      const body = await r.json().catch(() => null);
      if (!r.ok) throw new Error((body && body.error) || `HTTP ${r.status}`);
      return body;
    })
    .then(set)
    .catch((e) => setErr(e.message))
    .finally(() => setBusy?.(false));
}

function QErr({ msg }) {
  return msg ? (
    <div className="muted" style={{ color: 'var(--red)', fontSize: 12, margin: '8px 0' }}>
      error: {msg}
    </div>
  ) : null;
}

// ── ML model card ────────────────────────────────────────────────────────────
function MLModelCard() {
  const [meta, setMeta] = qUseState(null);
  const [err, setErr] = qUseState(null);
  qUseEffect(() => { qFetch('/quant/ml-model/', setMeta, setErr); }, []);

  const imp = meta ? Object.entries(meta.permutation_importance || {})
    .sort((a, b) => b[1] - a[1]) : [];
  const maxImp = imp.length ? Math.max(...imp.map(([, v]) => v), 0.0001) : 1;

  return (
    <div className="card">
      <div className="card-title">Meta-labeling model (quant/04)</div>
      <QErr msg={err} />
      {meta && (
        <>
          <p className="muted" style={{ fontSize: 12, margin: '6px 0 12px' }}>
            P(signal clears costs) — walk-forward validated, gates BUYs below
            {' '}{meta.threshold}. Honest numbers: the gate cuts losses, it
            does not make the strategy profitable.
          </p>
          <div className="row gap-16 mono" style={{ fontSize: 13, flexWrap: 'wrap', marginBottom: 12 }}>
            <span>OOS AUC <b>{meta.oos_auc}</b></span>
            <span>EV/trade ₹{meta.oos_ev_unfiltered_rs} → <b>₹{meta.oos_ev_filtered_rs}</b></span>
            <span>{meta.dataset_rows} training signals</span>
            <span>gate: {meta.gate_mode}</span>
          </div>
          <div style={{ maxWidth: 460 }}>
            {imp.map(([f, v]) => (
              <div key={f} className="row" style={{ alignItems: 'center', gap: 8, padding: '2px 0' }}>
                <span className="mono muted" style={{ fontSize: 11, width: 100 }}>{f}</span>
                <div style={{ flex: 1, height: 8, background: 'var(--line)', borderRadius: 4 }}>
                  <div style={{ width: `${Math.max(0, v / maxImp) * 100}%`, height: 8,
                                background: '#2563EB', borderRadius: 4 }} />
                </div>
                <span className="mono muted" style={{ fontSize: 11, width: 56 }}>{v.toFixed(3)}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ── Backtest stats card ──────────────────────────────────────────────────────
function BacktestCard() {
  const [data, setData] = qUseState(null);
  const [err, setErr] = qUseState(null);
  qUseEffect(() => { qFetch('/quant/backtest-stats/', setData, setErr); }, []);

  return (
    <div className="card">
      <div className="card-title">1-yr backtest stats (week1)</div>
      <QErr msg={err} />
      {data && (
        <table className="mono" style={{ fontSize: 12, width: '100%', marginTop: 8,
                                          borderCollapse: 'collapse' }}>
          <thead>
            <tr className="muted" style={{ textAlign: 'right' }}>
              <th style={{ textAlign: 'left', padding: 4 }}>Symbol</th>
              <th style={{ padding: 4 }}>Return %</th>
              <th style={{ padding: 4 }}>Sharpe</th>
            </tr>
          </thead>
          <tbody>
            {data.stats.map((r) => (
              <tr key={r.symbol} style={{ textAlign: 'right', borderTop: '1px solid var(--line)' }}>
                <td style={{ textAlign: 'left', padding: 4 }}>{r.symbol}</td>
                <td style={{ padding: 4,
                             color: r.annual_return_pct >= 0 ? 'var(--green)' : 'var(--red)' }}>
                  {r.annual_return_pct.toFixed(1)}
                </td>
                <td style={{ padding: 4 }}>{r.annual_sharpe.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ── On-demand cards: pairs + weights ─────────────────────────────────────────
function PairsCard() {
  const [data, setData] = qUseState(null);
  const [err, setErr] = qUseState(null);
  const [busy, setBusy] = qUseState(false);

  return (
    <div className="card">
      <div className="card-title">Pairs cointegration (quant/01)</div>
      <p className="muted" style={{ fontSize: 12, margin: '6px 0 10px' }}>
        Engle-Granger over the tracked universe, 1y daily closes. First run
        fetches prices (~20s), then it's cached for an hour.
      </p>
      <button disabled={busy} onClick={() => qFetch('/quant/pairs/', setData, setErr, setBusy)}
              style={{ padding: '6px 14px', borderRadius: 8, cursor: 'pointer',
                       border: '1px solid var(--line)', background: 'transparent',
                       color: 'var(--text)' }}>
        {busy ? 'computing…' : data ? 'Re-run scan' : 'Run scan'}
      </button>
      <QErr msg={err} />
      {data && (
        <table className="mono" style={{ fontSize: 12, width: '100%', marginTop: 10,
                                          borderCollapse: 'collapse' }}>
          <thead>
            <tr className="muted">
              <th style={{ textAlign: 'left', padding: 4 }}>Pair</th>
              <th style={{ padding: 4 }}>p-value</th>
              <th style={{ padding: 4 }}>Hedge β</th>
              <th style={{ padding: 4 }}>Cointegrated?</th>
            </tr>
          </thead>
          <tbody>
            {data.pairs.slice(0, 8).map((p) => (
              <tr key={p.pair} style={{ textAlign: 'center', borderTop: '1px solid var(--line)' }}>
                <td style={{ textAlign: 'left', padding: 4 }}>{p.pair}</td>
                <td style={{ padding: 4 }}>{p.p_value}</td>
                <td style={{ padding: 4 }}>{p.hedge_ratio}</td>
                <td style={{ padding: 4,
                             color: p.cointegrated ? 'var(--green)' : 'var(--text-2)' }}>
                  {p.cointegrated ? 'yes (p<0.05)' : 'no'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function WeightsCard() {
  const [data, setData] = qUseState(null);
  const [err, setErr] = qUseState(null);
  const [busy, setBusy] = qUseState(false);
  const maxW = data ? Math.max(...data.weights.map((w) => w.weight), 0.0001) : 1;

  return (
    <div className="card">
      <div className="card-title">Markowitz max-Sharpe weights (quant/03)</div>
      <p className="muted" style={{ fontSize: 12, margin: '6px 0 10px' }}>
        Tangency portfolio over the tracked universe (1y daily returns).
      </p>
      <button disabled={busy} onClick={() => qFetch('/quant/weights/', setData, setErr, setBusy)}
              style={{ padding: '6px 14px', borderRadius: 8, cursor: 'pointer',
                       border: '1px solid var(--line)', background: 'transparent',
                       color: 'var(--text)' }}>
        {busy ? 'computing…' : data ? 'Re-compute' : 'Compute weights'}
      </button>
      <QErr msg={err} />
      {data && (
        <div style={{ maxWidth: 460, marginTop: 10 }}>
          {data.weights.map((w) => (
            <div key={w.symbol} className="row" style={{ alignItems: 'center', gap: 8, padding: '2px 0' }}>
              <span className="mono muted" style={{ fontSize: 11, width: 110 }}>{w.symbol}</span>
              <div style={{ flex: 1, height: 8, background: 'var(--line)', borderRadius: 4 }}>
                <div style={{ width: `${(w.weight / maxW) * 100}%`, height: 8,
                              background: '#2563EB', borderRadius: 4 }} />
              </div>
              <span className="mono muted" style={{ fontSize: 11, width: 52 }}>
                {(w.weight * 100).toFixed(1)}%
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function QuantView() {
  return (
    <div className="view-enter">
      <PageHead title="Quant Lab"
                subtitle="The research track served live — cointegration, portfolio optimisation, and the ML gate's report card" />
      <MLModelCard />
      <BacktestCard />
      <PairsCard />
      <WeightsCard />
    </div>
  );
}

Object.assign(window, { QuantView });
