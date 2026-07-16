// stock_panel.jsx — Stock Detail: signal history + "Ask FinPilot".
//
// Two long-orphaned backend capabilities finally on screen:
//   /api/signals/<symbol>/      — full signal history (existed since week 2)
//   /api/signals/<symbol>/ask/  — week3's multi-agent Q&A (router →
//                                 specialists → synthesis)
//
// Exported on window: StockDetailView

const { useState: dUseState, useEffect: dUseEffect } = React;

function sigColor(t) {
  return t === 'BUY' ? 'var(--green)' : t === 'SELL' ? 'var(--red)' : 'var(--text-2)';
}

function HistoryTable({ symbol }) {
  const { data, error: err, loading } = useApi(`/signals/${encodeURIComponent(symbol)}/`);
  const rows = loading ? null : unwrapDRF(data);

  if (err) return <div className="muted" style={{ color: 'var(--red)', fontSize: 12 }}>error: {err}</div>;
  if (!rows) return <div className="muted">loading…</div>;
  if (!rows.length) {
    return <div className="muted" style={{ fontSize: 13 }}>
      No signals recorded for {symbol} yet — run a signal refresh (System view).
    </div>;
  }
  return (
    <table className="mono" style={{ fontSize: 12, width: '100%', borderCollapse: 'collapse' }}>
      <thead>
        <tr className="muted" style={{ textAlign: 'left' }}>
          <th style={{ padding: 4 }}>Date</th>
          <th style={{ padding: 4 }}>Signal</th>
          <th style={{ padding: 4, textAlign: 'right' }}>Price</th>
          <th style={{ padding: 4, textAlign: 'right' }}>RSI</th>
          <th style={{ padding: 4, textAlign: 'right' }}>P(profit)</th>
          <th style={{ padding: 4 }}>Reason</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((s) => (
          <tr key={s.id} style={{ borderTop: '1px solid var(--line)', verticalAlign: 'top' }}>
            <td style={{ padding: 4, whiteSpace: 'nowrap' }}>{s.date}</td>
            <td style={{ padding: 4, fontWeight: 600, color: sigColor(s.signal_type) }}>
              {s.signal_type}
            </td>
            <td style={{ padding: 4, textAlign: 'right' }}>₹{s.price}</td>
            <td style={{ padding: 4, textAlign: 'right' }}>
              {s.rsi != null ? s.rsi.toFixed(1) : '—'}
            </td>
            <td style={{ padding: 4, textAlign: 'right' }}>
              {s.ml_prob != null ? `${(s.ml_prob * 100).toFixed(0)}%` : '—'}
            </td>
            <td className="muted" style={{ padding: 4, maxWidth: 420 }}>
              {(s.reason || '').slice(0, 140)}{(s.reason || '').length > 140 ? '…' : ''}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function AskBox({ symbol }) {
  const [question, setQuestion] = dUseState('');
  const [busy, setBusy] = dUseState(false);
  const [reply, setReply] = dUseState(null);
  const [err, setErr] = dUseState(null);

  async function ask() {
    if (!question.trim() || busy) return;
    setBusy(true); setErr(null); setReply(null);
    try {
      const res = await fetch(
        `${window.FINPILOT_API}/signals/${encodeURIComponent(symbol)}/ask/`,
        { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question }) });
      const body = await res.json().catch(() => null);
      if (!res.ok) throw new Error((body && body.error) || `HTTP ${res.status}`);
      setReply(body);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <div className="card-title">Ask FinPilot about {symbol}</div>
      <p className="muted" style={{ fontSize: 12, margin: '6px 0 10px' }}>
        Routed through the week3 multi-agent explainer — a router picks the
        technical / news / fundamentals specialists, then synthesises one
        answer grounded in the latest signal.
      </p>
      <div className="row gap-8" style={{ alignItems: 'center' }}>
        <input value={question} placeholder="e.g. Why is this a HOLD right now?"
               onChange={(e) => setQuestion(e.target.value)}
               onKeyDown={(e) => e.key === 'Enter' && ask()}
               style={{ flex: 1, padding: '8px 12px', borderRadius: 8,
                        border: '1px solid var(--line)', background: 'transparent',
                        color: 'var(--text)', fontSize: 13 }} />
        <button disabled={busy || !question.trim()} onClick={ask}
                style={{ padding: '8px 16px', borderRadius: 8, cursor: 'pointer',
                         border: '1px solid var(--line)',
                         background: busy ? 'transparent' : 'var(--text)',
                         color: busy ? 'var(--text-2)' : 'var(--bg)' }}>
          {busy ? 'thinking…' : 'Ask'}
        </button>
      </div>
      {err && (
        <div className="muted" style={{ color: 'var(--red)', fontSize: 12, marginTop: 10 }}>
          error: {err}
        </div>
      )}
      {reply && (
        <div style={{ marginTop: 14 }}>
          <div style={{ fontSize: 13, lineHeight: 1.6 }}>{reply.answer}</div>
          <div className="row gap-8" style={{ marginTop: 10 }}>
            {(reply.agents_used || []).map((a) => (
              <span key={a} className="mono muted"
                    style={{ fontSize: 11, padding: '2px 10px', borderRadius: 999,
                             border: '1px solid var(--line)' }}>
                {a} agent
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StockDetailView() {
  const [symbol, setSymbol] = dUseState(null);
  const stocksApi = useApi('/signals/stocks/');
  const stocks = unwrapDRF(stocksApi.data).map((s) => s.symbol);

  dUseEffect(() => {
    if (stocks.length && !symbol) setSymbol(stocks[0]);
  }, [stocks.length]);

  return (
    <div className="view-enter">
      <PageHead title="Stock Detail"
                subtitle="Per-stock signal history and multi-agent Q&A" />
      <div className="card">
        <div className="row gap-12" style={{ alignItems: 'center', marginBottom: 14 }}>
          <label className="muted" style={{ fontSize: 12 }}>Stock</label>
          <select value={symbol || ''} onChange={(e) => setSymbol(e.target.value)}
                  style={{ padding: '6px 10px', borderRadius: 8,
                           border: '1px solid var(--line)', background: 'transparent',
                           color: 'var(--text)' }}>
            {stocks.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        {symbol && <HistoryTable symbol={symbol} />}
      </div>
      {symbol && <AskBox symbol={symbol} />}
    </div>
  );
}

Object.assign(window, { StockDetailView });
