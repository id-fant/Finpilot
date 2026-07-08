// views.jsx — PageHead + the FinPilot-native views built on real API data:
//   CommandView   — the decision cockpit (home): today's signals with their
//                   ML score + analyst verdict, quick actions, live feed.
//   PositionsView — open book, allocation donut, holdings table.
//   TradesView    — real order history from /api/portfolio/orders/.

const { useState: vUseState, useMemo: vUseMemo } = React;

function PageHead({ title, subtitle, right }) {
  return (
    <div className="page-head">
      <div style={{ flex: 1 }}>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

const DONUT_COLORS = ['#2563eb', '#22c55e', '#f59e0b', '#a855f7', '#ec4899', '#14b8a6', '#ef4444', '#64748b'];
const sigClass = (t) => t === 'BUY' ? 'act-buy' : t === 'SELL' ? 'act-sell' : 'act-hold';

// Build {SYMBOL: latest verdict} maps from today's journal, so each signal card
// can show whether the analyst/ML gate approved, reduced, vetoed or skipped it.
function latestByStage(journal, stage) {
  const out = {};
  for (const e of journal) {
    if (e.stage === stage && e.symbol && !(stripNS(e.symbol) in out)) {
      out[stripNS(e.symbol)] = e;
    }
  }
  return out;
}

// ── Command (home) ──────────────────────────────────────────────────────────
function CommandView({ data, actions }) {
  const { signals, positions, orders, journal, system } = data;
  const analystByStage = vUseMemo(() => latestByStage(journal, 'analyst'), [journal]);
  const mlByStage = vUseMemo(() => latestByStage(journal, 'ml'), [journal]);

  const counts = vUseMemo(() => {
    const c = { BUY: 0, SELL: 0, HOLD: 0 };
    for (const s of signals) c[s.signal_type] = (c[s.signal_type] || 0) + 1;
    return c;
  }, [signals]);

  // Actionable first (BUY/SELL), then HOLD; each alphabetical.
  const ordered = vUseMemo(() => {
    const rank = { BUY: 0, SELL: 0, HOLD: 1 };
    return [...signals].sort((a, b) =>
      (rank[a.signal_type] - rank[b.signal_type]) || a.symbol.localeCompare(b.symbol));
  }, [signals]);

  const openCount = positions?.open_count ?? 0;
  const totalPnl = Number(positions?.total_pnl ?? 0);
  const ml = system?.gates?.ml;
  const analyst = system?.gates?.analyst;

  return (
    <div className="view-enter">
      <PageHead title="Command"
                subtitle="Today's signals, what each decision gate said, and the actions to trade on them." />

      <div className="stat-grid">
        <div className="stat">
          <div className="stat-label">Signals today</div>
          <div className="stat-value">{signals.length}</div>
          <div className="stat-foot">
            <span className="pos">{counts.BUY} BUY</span> ·
            <span className="neg">{counts.SELL} SELL</span> ·
            <span className="muted">{counts.HOLD} HOLD</span>
          </div>
        </div>
        <div className="stat">
          <div className="stat-label">Open positions</div>
          <div className="stat-value">{openCount}</div>
          <div className="stat-foot">
            unrealised{' '}
            <span className={totalPnl >= 0 ? 'pos' : 'neg'}>{formatINR(totalPnl)}</span>
          </div>
        </div>
        <div className="stat">
          <div className="stat-label">Orders (all time)</div>
          <div className="stat-value">{system?.data?.orders_total ?? orders.length}</div>
          <div className="stat-foot muted">broker: {system?.broker || '—'}</div>
        </div>
        <div className="stat">
          <div className="stat-label">Decision gates</div>
          <div className="stat-value" style={{ fontSize: 15, marginTop: 12 }}>
            <span className={ml?.enabled ? 'pos' : 'muted'}>ML {ml?.enabled ? `AUC ${ml.oos_auc}` : 'off'}</span>
          </div>
          <div className="stat-foot">
            <span className={analyst?.enabled ? 'pos' : 'muted'}>
              analyst {analyst?.enabled ? 'on' : 'off'}
            </span>
          </div>
        </div>
      </div>

      <div className="cmd-grid">
        <div>
          <div className="card">
            <div className="card-head">
              <div>
                <div className="card-title">Today's signals</div>
                <div className="card-sub">
                  {system?.data?.latest_signal_date
                    ? `for ${system.data.latest_signal_date} · click a row for the AI explanation`
                    : 'no signals yet — run a refresh'}
                </div>
              </div>
              <div className="card-spacer" />
              <div className="row gap-8">
                <button className="btn" disabled={actions.busy.refresh}
                        onClick={actions.refreshSignals}>
                  {actions.busy.refresh ? 'refreshing…' : 'Refresh signals'}
                </button>
                <button className="btn-primary" disabled={actions.busy.execute}
                        onClick={actions.executeOrders}>
                  {actions.busy.execute ? 'routing…' : 'Execute orders'}
                </button>
              </div>
            </div>
            {actions.note && (
              <div className="muted" style={{ fontSize: 12, marginBottom: 10,
                     color: actions.note.startsWith('error') ? 'var(--red)' : 'var(--text-2)' }}>
                {actions.note}
              </div>
            )}
            {ordered.length === 0 ? (
              <div className="muted" style={{ fontSize: 13, padding: '10px 0' }}>
                No signals in the database yet. Click <b>Refresh signals</b> (needs the
                API on :8000 with network) to generate today's run.
              </div>
            ) : (
              <div className="sig-list">
                {ordered.map(s => {
                  const bare = stripNS(s.symbol);
                  const verdict = analystByStage[bare];
                  const mlSkip = mlByStage[bare];
                  const prob = s.ml_prob;
                  return (
                    <button key={s.id} className={'sig-card ' + sigClass(s.signal_type)}
                            onClick={() => window.openSignalExplainer?.(bare)}>
                      <div>
                        <div className="sig-sym">{bare}</div>
                        <div className="sig-meta">₹{s.price}</div>
                      </div>
                      <div className="row gap-8" style={{ flexWrap: 'wrap' }}>
                        <span className={'tag ' + s.signal_type.toLowerCase()}>{s.signal_type}</span>
                        {verdict && (
                          <span className={'verdict ' + verdict.decision.toLowerCase()}>
                            analyst: {verdict.decision}
                          </span>
                        )}
                        {mlSkip && (
                          <span className="verdict skip">ML skip</span>
                        )}
                      </div>
                      <div className="sig-metrics">
                        <div className="sig-metric">
                          <div className="k">RSI</div>
                          <div className="v">{s.rsi != null ? s.rsi.toFixed(0) : '—'}</div>
                        </div>
                        <div className="sig-metric">
                          <div className="k">P(profit)</div>
                          {prob != null ? (
                            <>
                              <div className="v">{(prob * 100).toFixed(0)}%</div>
                              <div className="prob-bar"><span style={{ width: `${Math.min(100, prob * 100)}%` }} /></div>
                            </>
                          ) : <div className="v">—</div>}
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        <div>
          <div className="card">
            <div className="card-title">Recent decisions</div>
            <div className="card-sub" style={{ marginBottom: 10 }}>the agent's journal</div>
            {journal.length === 0 ? (
              <div className="muted" style={{ fontSize: 12.5 }}>
                Nothing yet. Verdicts and exits land here when the pipeline runs.
              </div>
            ) : journal.slice(0, 8).map(e => {
              const tone = ['APPROVE', 'DONE', 'START'].includes(e.decision) ? 'var(--green)'
                         : ['VETO', 'FAILED', 'SELL'].includes(e.decision) ? 'var(--red)'
                         : e.decision === 'REDUCE' ? 'var(--amber)' : 'var(--text-3)';
              return (
                <div className="feed-item" key={e.id}>
                  <span className="feed-dot" style={{ background: tone }} />
                  <div style={{ flex: 1 }}>
                    <div><b>{e.stage}</b> {e.symbol ? stripNS(e.symbol) : ''} · <span style={{ color: tone }}>{e.decision}</span></div>
                    <div className="muted" style={{ fontSize: 11.5, marginTop: 2 }}>
                      {(e.detail || '').slice(0, 90)}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="card">
            <div className="card-title">Open positions</div>
            {openCount === 0 ? (
              <div className="muted" style={{ fontSize: 12.5, marginTop: 6 }}>
                No open positions. They appear once an order fills.
              </div>
            ) : (positions.open_positions || []).slice(0, 6).map(p => {
              const pnl = Number(p.pnl);
              return (
                <div className="row" key={p.id} style={{ justifyContent: 'space-between', padding: '7px 0', borderTop: '1px solid var(--line)' }}>
                  <span style={{ fontWeight: 600 }}>{stripNS(p.symbol)}</span>
                  <span className="num muted">×{p.quantity} @ ₹{p.avg_entry_price}</span>
                  <span className={'num ' + (pnl >= 0 ? 'pos' : 'neg')}>{formatINR(pnl)}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Positions ────────────────────────────────────────────────────────────────
function PositionsView({ data }) {
  const positions = data.positions;
  const open = positions?.open_positions || [];
  const rows = open.map((p, i) => ({
    sym: stripNS(p.symbol),
    qty: Number(p.quantity),
    avg: Number(p.avg_entry_price),
    pnl: Number(p.pnl),
    value: Number(p.quantity) * Number(p.avg_entry_price),
    color: DONUT_COLORS[i % DONUT_COLORS.length],
  }));
  const total = rows.reduce((a, r) => a + r.value, 0);
  const sorted = [...rows].sort((a, b) => b.value - a.value);

  const R = 64, sw = 16, C = 2 * Math.PI * R;
  let acc = 0;
  const segs = sorted.map(p => {
    const frac = total ? p.value / total : 0;
    const dash = frac * C;
    const seg = { ...p, dash, offset: -acc, frac };
    acc += dash;
    return seg;
  });

  return (
    <div className="view-enter">
      <PageHead title="Positions"
                subtitle="Open holdings, allocation, and mark-to-market P&L from the paper book." />
      {rows.length === 0 ? (
        <div className="card muted" style={{ fontSize: 13 }}>
          No open positions yet. When an order fills, the position is booked here
          (and on the Command view). Try <b>Execute orders</b> from Command on a
          day with an actionable BUY.
        </div>
      ) : (
        <>
          <div className="stat-grid">
            <div className="stat"><div className="stat-label">Open positions</div><div className="stat-value">{rows.length}</div></div>
            <div className="stat"><div className="stat-label">Invested (at entry)</div><div className="stat-value" style={{ fontSize: 20 }}>{formatCompactINR(total)}</div></div>
            <div className="stat"><div className="stat-label">Total P&L</div>
              <div className={'stat-value ' + (Number(positions.total_pnl) >= 0 ? 'pos' : 'neg')} style={{ fontSize: 20 }}>
                {formatINR(Number(positions.total_pnl))}
              </div>
            </div>
          </div>
          <div className="card">
            <div className="card-title" style={{ marginBottom: 14 }}>Allocation</div>
            <div className="donut-wrap">
              <svg width="170" height="170" viewBox="-85 -85 170 170" style={{ transform: 'rotate(-90deg)' }}>
                <circle r={R} fill="none" stroke="var(--card-2)" strokeWidth={sw} />
                {segs.map((s, i) => (
                  <circle key={i} r={R} fill="none" stroke={s.color} strokeWidth={sw}
                          strokeDasharray={`${s.dash} ${C - s.dash}`} strokeDashoffset={s.offset}
                          style={{ transition: 'stroke-dasharray 0.6s ease' }} />
                ))}
                <g style={{ transform: 'rotate(90deg)' }}>
                  <text textAnchor="middle" y={-2} fontSize="16" fontWeight="600" fill="var(--text)">{formatCompactINR(total)}</text>
                  <text textAnchor="middle" y={14} fontSize="9" fill="var(--text-3)" letterSpacing="0.06em">INVESTED</text>
                </g>
              </svg>
              <div className="alloc-legend">
                {segs.map(s => (
                  <div className="alloc-row" key={s.sym}>
                    <span className="swatch" style={{ background: s.color }} />
                    <span className="sym">{s.sym}</span>
                    <span className="pct">{(s.frac * 100).toFixed(1)}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="card">
            <div className="card-title" style={{ marginBottom: 6 }}>Holdings</div>
            <table className="tbl">
              <thead><tr><th>Symbol</th><th style={{ textAlign: 'right' }}>Qty</th><th style={{ textAlign: 'right' }}>Avg entry</th><th style={{ textAlign: 'right' }}>Value</th><th style={{ textAlign: 'right' }}>P&L</th></tr></thead>
              <tbody>
                {sorted.map(r => (
                  <tr key={r.sym}>
                    <td style={{ fontWeight: 600 }}>{r.sym}</td>
                    <td className="num" style={{ textAlign: 'right' }}>{r.qty}</td>
                    <td className="num" style={{ textAlign: 'right' }}>₹{r.avg.toFixed(2)}</td>
                    <td className="num" style={{ textAlign: 'right' }}>{formatCompactINR(r.value)}</td>
                    <td className={'num ' + (r.pnl >= 0 ? 'pos' : 'neg')} style={{ textAlign: 'right' }}>{formatINR(r.pnl)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

// ── Trades ───────────────────────────────────────────────────────────────────
function TradesView({ data }) {
  const orders = data.orders || [];
  const statusTone = (st) => st === 'COMPLETE' ? 'pos' : st === 'REJECTED' || st === 'CANCELLED' ? 'neg' : 'muted';
  return (
    <div className="view-enter">
      <PageHead title="Trades"
                subtitle={`${orders.length} order(s) routed through the broker — newest first.`} />
      {orders.length === 0 ? (
        <div className="card muted" style={{ fontSize: 13 }}>
          No orders yet. Rejections are recorded too (they're audit material), so
          this fills up the first time <b>Execute orders</b> routes an actionable signal.
        </div>
      ) : (
        <div className="card tight">
          <table className="tbl">
            <thead>
              <tr>
                <th>Symbol</th><th>Side</th><th style={{ textAlign: 'right' }}>Qty</th>
                <th style={{ textAlign: 'right' }}>Price</th><th>Status</th><th>Mode</th><th>Time</th>
              </tr>
            </thead>
            <tbody>
              {orders.map(o => (
                <tr key={o.id}>
                  <td style={{ fontWeight: 600 }}>{stripNS(o.symbol)}</td>
                  <td><span className={'tag ' + (o.side || '').toLowerCase()}>{o.side}</span></td>
                  <td className="num" style={{ textAlign: 'right' }}>{o.quantity}</td>
                  <td className="num" style={{ textAlign: 'right' }}>₹{o.price}</td>
                  <td className={statusTone(o.status)}>{o.status}</td>
                  <td className="muted">{o.is_paper ? 'paper' : 'LIVE'}</td>
                  <td className="muted num" style={{ fontSize: 12 }}>
                    {new Date(o.created_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

Object.assign(window, { PageHead, CommandView, PositionsView, TradesView });
