// explainer.jsx — Signal explainer side-panel.
//
// Wires Cardinal to FinPilot's GET /api/signals/<symbol>/explain/ endpoint.
// Clicking a BUY/SELL badge in the watchlist opens this panel; it fetches the
// LLM explanation on demand and shows a loading state while Gemini answers.
//
// INTEGRATION: deliberately loose. This file exposes ONE global opener —
//   window.openSignalExplainer(symbol)
// The watchlist badge calls it with optional chaining, so if this file isn't
// loaded the click is a no-op — no breakage.
//
// Mount: app.jsx wraps <App> in <ExplainerProvider>. That's the only edit
// needed in app.jsx (one line).

const EXPLAIN_API = (window.FINPILOT_API_BASE || 'http://127.0.0.1:8000/api');

// ── Hook: fetch the explanation for one symbol ──────────────────────────
// `symbol` null/undefined means "no fetch" — used to clear state on close.
function useExplanation(symbol) {
  const [state, setState] = React.useState({
    status: 'idle', explanation: null, error: null, meta: null,
  });

  React.useEffect(() => {
    if (!symbol) {
      setState({ status: 'idle', explanation: null, error: null, meta: null });
      return;
    }
    let cancelled = false;
    setState({ status: 'loading', explanation: null, error: null, meta: null });

    fetch(`${EXPLAIN_API}/signals/${encodeURIComponent(symbol)}/explain/`)
      .then(async (r) => {
        const body = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(body.error || `HTTP ${r.status}`);
        return body;
      })
      .then((body) => {
        if (cancelled) return;
        setState({
          status: 'ready',
          explanation: body.explanation,
          error: null,
          meta: {
            symbol: body.symbol,
            date: body.date,
            signal_type: body.signal_type,
            cached: body.cached,
            technical_reason: body.technical_reason,
            price: body.price,
            rsi: body.rsi,
          },
        });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({ status: 'error', explanation: null, error: err.message, meta: null });
      });

    return () => { cancelled = true; };
  }, [symbol]);

  return state;
}

// ── Panel ───────────────────────────────────────────────────────────────
function SignalExplainerPanel({ symbol, onClose }) {
  const open = !!symbol;
  const state = useExplanation(symbol);

  // Close on Escape — matches the Popover keyboard pattern in components.jsx.
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;
  const meta = state.meta;
  const tag = meta?.signal_type?.toLowerCase() || '';

  return (
    <>
      <div className="explainer-scrim" onClick={onClose} />
      <aside className="explainer-panel" role="dialog" aria-label={`Explain ${symbol}`}>
        <div className="explainer-head">
          <div style={{ minWidth: 0 }}>
            <div className="explainer-symbol">{symbol}</div>
            <div className="explainer-sub">
              {meta ? `${meta.signal_type} · ${meta.date}` : 'Loading…'}
            </div>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close">
            <Icon.Close />
          </button>
        </div>

        {meta && (
          <div className="explainer-stats">
            <div>
              <div className="lbl">Signal</div>
              <div className={'tag ' + tag}>{meta.signal_type}</div>
            </div>
            <div>
              <div className="lbl">Price</div>
              <div className="val mono">{meta.price}</div>
            </div>
            <div>
              <div className="lbl">RSI</div>
              <div className="val mono">
                {typeof meta.rsi === 'number' ? meta.rsi.toFixed(1) : '—'}
              </div>
            </div>
          </div>
        )}

        <div className="explainer-body">
          {state.status === 'loading' && (
            <div className="explainer-loading">
              <div className="explainer-spinner" />
              <div>Asking Gemini why this signal fired…</div>
              <div className="explainer-hint">
                First call takes 2–4 s. Cached for 24 h after.
              </div>
            </div>
          )}

          {state.status === 'ready' && (
            <>
              <div className="explainer-section-label">AI explanation</div>
              <div className="explainer-text">{state.explanation}</div>
              {meta?.technical_reason && (
                <>
                  <div className="explainer-section-label">Technical reason</div>
                  <div className="explainer-text dim">{meta.technical_reason}</div>
                </>
              )}
              <div className="explainer-foot">
                {meta?.cached ? '✓ Cached' : '✨ Freshly generated'}
              </div>
            </>
          )}

          {state.status === 'error' && (
            <div className="explainer-error">
              <div className="explainer-section-label">Could not generate</div>
              <div className="explainer-text">{state.error}</div>
              <div className="explainer-hint">
                Check GEMINI_API_KEY in week3/.env, and that the Django backend
                is running with week3/ on its path.
              </div>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}

// Stub the opener immediately so a race-condition click before mount is a no-op
// rather than a TypeError. The provider replaces it with the real one on mount.
window.openSignalExplainer = window.openSignalExplainer || function () {};

// ── Provider — wraps <App> in app.jsx ──────────────────────────────────
function ExplainerProvider({ children }) {
  const [symbol, setSymbol] = React.useState(null);

  React.useEffect(() => {
    window.openSignalExplainer = (sym) => setSymbol(sym || null);
    return () => { window.openSignalExplainer = () => {}; };
  }, []);

  return (
    <>
      {children}
      <SignalExplainerPanel symbol={symbol} onClose={() => setSymbol(null)} />
    </>
  );
}

Object.assign(window, { ExplainerProvider, SignalExplainerPanel, useExplanation });
