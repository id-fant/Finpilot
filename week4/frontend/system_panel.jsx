// system_panel.jsx — the agent's control room.
//
// Reads /api/system/ (config, gates, data state, running actions) and hosts
// the two "run now" buttons that POST to the production tasks. Polls every
// 10s so a button flips back to idle when its background task finishes.
//
// Exported on window: SystemView

const { useState: sUseState } = React;

const SYS_POLL_MS = 10_000;

function SysChip({ label, value, tone }) {
  const color = tone === 'good' ? 'var(--green)'
              : tone === 'bad' ? 'var(--red)'
              : 'var(--text)';
  return (
    <div style={{ minWidth: 150, padding: '10px 14px',
                  border: '1px solid var(--line)', borderRadius: 10 }}>
      <div className="muted" style={{ fontSize: 11 }}>{label}</div>
      <div className="mono" style={{ fontSize: 15, marginTop: 3, color }}>{value}</div>
    </div>
  );
}

function ActionButton({ name, label, path, running, onLaunched }) {
  const [busy, setBusy] = sUseState(false);
  const [note, setNote] = sUseState(null);
  const disabled = running || busy;

  async function fire() {
    setBusy(true); setNote(null);
    try {
      const res = await fetch(`${window.FINPILOT_API}${path}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
      });
      const body = await res.json().catch(() => ({}));
      if (res.status === 202) setNote('started…');
      else setNote(body.error || body.status || `HTTP ${res.status}`);
      onLaunched?.();
    } catch (e) {
      setNote(`failed: ${e.message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <button className="btn" disabled={disabled} onClick={fire}
              style={{ padding: '8px 16px', borderRadius: 8, cursor: disabled ? 'wait' : 'pointer',
                       border: '1px solid var(--line)',
                       background: disabled ? 'transparent' : 'var(--text)',
                       color: disabled ? 'var(--text-2)' : 'var(--bg)' }}>
        {running ? `${label} — running…` : label}
      </button>
      {note && <span className="muted" style={{ fontSize: 12 }}>{note}</span>}
    </div>
  );
}

function SystemView() {
  const { data: sys, error, refetch: load } = useApi('/system/', { poll: SYS_POLL_MS });

  const actions = sys?.actions || {};
  const lastResult = (name) => {
    const a = actions[name];
    if (!a || a.running) return null;
    if (a.error) return `last run FAILED: ${a.error}`;
    if (a.result) return `last run: ${JSON.stringify(a.result)}`;
    return null;
  };

  return (
    <div className="view-enter">
      <PageHead title="System"
                subtitle="Configuration, decision gates, and manual controls for the agentic pipeline" />

      {error && (
        <div className="card muted" style={{ color: 'var(--red)' }}>
          error: {error}
          {/fetch|network/i.test(error)
            ? `. Is the Django API running on ${window.FINPILOT_API}?` : ''}
        </div>
      )}

      {sys && (
        <>
          <div className="card">
            <div className="card-title">Pipeline configuration</div>
            <div className="row gap-12" style={{ flexWrap: 'wrap', marginTop: 10 }}>
              <SysChip label="Broker" value={sys.broker.toUpperCase()}
                       tone={sys.broker === 'paper' ? 'good' : 'bad'} />
              <SysChip label="ML gate (quant/04)"
                       value={sys.gates.ml.enabled
                         ? `on · AUC ${sys.gates.ml.oos_auc} · thr ${sys.gates.ml.threshold}`
                         : 'off — no model'}
                       tone={sys.gates.ml.enabled ? 'good' : undefined} />
              <SysChip label="LLM analyst (week3)"
                       value={sys.gates.analyst.enabled
                         ? `on · ${sys.gates.analyst.model}` : 'off — no API key'}
                       tone={sys.gates.analyst.enabled ? 'good' : undefined} />
              <SysChip label="Risk caps"
                       value={`₹${Number(sys.risk.max_trade_value).toLocaleString('en-IN')} / trade · ${sys.risk.max_positions} pos · ${sys.risk.max_daily_orders}/day`} />
            </div>
          </div>

          <div className="card">
            <div className="card-title">Data state</div>
            <div className="row gap-12" style={{ flexWrap: 'wrap', marginTop: 10 }}>
              <SysChip label="Tracked stocks" value={sys.data.tracked_stocks} />
              <SysChip label="Latest signals"
                       value={`${sys.data.signals_on_latest_date} on ${sys.data.latest_signal_date || '—'}`} />
              <SysChip label="Open positions" value={sys.data.open_positions} />
              <SysChip label="Orders (all time)" value={sys.data.orders_total} />
            </div>
          </div>

          <div className="card">
            <div className="card-title">Run now</div>
            <p className="muted" style={{ fontSize: 12, margin: '6px 0 14px' }}>
              The same production tasks the 09:05 / 09:20 IST schedule fires —
              signal refresh can take minutes when LLM enrichment runs. Every
              run is journalled; all gates and risk caps still apply.
            </p>
            <div className="row gap-16" style={{ flexWrap: 'wrap' }}>
              <div>
                <ActionButton name="refresh-signals" label="Refresh signals"
                              path="/signals/refresh/"
                              running={actions['refresh-signals']?.running}
                              onLaunched={load} />
                <div className="muted mono" style={{ fontSize: 11, marginTop: 6, maxWidth: 380 }}>
                  {lastResult('refresh-signals')}
                </div>
              </div>
              <div>
                <ActionButton name="execute-orders" label="Execute orders"
                              path="/portfolio/execute-orders/"
                              running={actions['execute-orders']?.running}
                              onLaunched={load} />
                <div className="muted mono" style={{ fontSize: 11, marginTop: 6, maxWidth: 380 }}>
                  {lastResult('execute-orders')}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

Object.assign(window, { SystemView });
