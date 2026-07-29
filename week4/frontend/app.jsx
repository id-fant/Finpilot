// app.jsx — FinPilot dashboard shell (routing + live data + mode toggle).

const { useState, useEffect, useCallback, useMemo } = React;

// UI mode ("terminal" | "friendly") persists across reloads; the attribute on
// <html> is what styles.css keys every token off.
function useUiMode() {
  const [mode, setMode] = useState(() => {
    const saved = localStorage.getItem('fp-ui');
    return saved === 'minimal' ? 'friendly' : (saved || 'friendly');
  });
  useEffect(() => {
    document.documentElement.dataset.ui = mode;
    localStorage.setItem('fp-ui', mode);
  }, [mode]);
  return [mode, setMode];
}

class DashboardErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error('FinPilot rendering failed', error, info);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <main className="fatal-screen" role="alert">
        <div className="fatal-panel">
          <div className="fatal-code">UI / RECOVERY</div>
          <h1>The dashboard hit a display error</h1>
          <p>
            Your data is still safe. Reload the interface to reconnect the
            frontend and API versions.
          </p>
          <details>
            <summary>Technical detail</summary>
            <code>{this.state.error.message || 'Unknown render error'}</code>
          </details>
          <div className="row gap-8">
            <button className="btn-primary" onClick={() => location.reload()}>
              Reload dashboard
            </button>
            <button
              className="btn"
              onClick={() => {
                localStorage.removeItem('fp-ui');
                location.reload();
              }}
            >
              Reset interface mode
            </button>
          </div>
        </div>
      </main>
    );
  }
}

function App() {
  const [view, setView] = useState('Command');
  const [menuOpen, setMenuOpen] = useState(false);
  const [uiMode, setUiMode] = useUiMode();
  const data = useFinPilot();
  const chord = React.useRef(null);
  const [shortcutHint, setShortcutHint] = useState('');
  const closeMenu = useCallback(() => setMenuOpen(false), []);
  const openMenu = useCallback(() => setMenuOpen(true), []);
  const clearShortcutHint = useCallback(() => setShortcutHint(''), []);

  useEffect(() => {
    const routes = {
      c: 'Command', p: 'Positions', t: 'Trades', j: 'Journal',
      n: 'News', q: 'Quant Lab', s: 'System',
    };
    const onKeyDown = event => {
      const target = event.target;
      if (target?.matches?.('input, textarea, select, [contenteditable="true"]')) {
        if (event.key === 'Escape') target.blur();
        return;
      }
      if (event.key === 'Escape') {
        setMenuOpen(false);
        setShortcutHint('');
        return;
      }
      if (event.key === '/') {
        event.preventDefault();
        setView('Stock Detail');
        return;
      }
      if (event.key === '?') {
        setShortcutHint('G C Command · G P Positions · G T Trades · / Stock search · Esc Close');
        return;
      }
      const key = event.key.toLowerCase();
      if (chord.current === 'g' && routes[key]) {
        event.preventDefault();
        setView(routes[key]);
        chord.current = null;
        return;
      }
      chord.current = key === 'g' ? 'g' : null;
      if (chord.current) setTimeout(() => { chord.current = null; }, 800);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  // ── Action buttons (Refresh signals / Execute orders) ────────────────────
  const [busy, setBusy] = useState({ refresh: false, execute: false });
  const [note, setNote] = useState(null);

  const runAction = useCallback(async (key, path, label) => {
    setBusy(b => ({ ...b, [key]: true }));
    setNote(`${label}…`);
    try {
      const { status, body } = await postAction(path);
      if (status === 202) {
        setNote(`${label} started — watch the journal for the result.`);
        // The task runs server-side on a thread; poll a few times to catch
        // the DB update without waiting for the 30s cycle.
        [3000, 8000, 15000].forEach(ms => setTimeout(() => data.refetch(), ms));
      } else if (status === 409) {
        setNote(`${label}: already running.`);
      } else if (status === 403) {
        setNote('error: actions disabled (set ACTIONS_TOKEN or run with DEBUG=True).');
      } else {
        setNote(`error: ${body.error || 'HTTP ' + status}`);
      }
    } catch (e) {
      setNote(`error: ${e.message} — is the API on :8000 running?`);
    } finally {
      setBusy(b => ({ ...b, [key]: false }));
    }
  }, [data.refetch]);

  const refreshSignals = useCallback(
    () => runAction('refresh', '/signals/refresh/', 'Signal refresh'),
    [runAction],
  );
  const executeOrders = useCallback(
    () => runAction('execute', '/portfolio/execute-orders/', 'Order routing'),
    [runAction],
  );
  const actions = useMemo(() => ({
    busy,
    note,
    refreshSignals,
    executeOrders,
  }), [busy, note, refreshSignals, executeOrders]);

  return (
    <div className="app">
      {menuOpen && <div className="scrim" onClick={closeMenu} />}
      <Sidebar active={view} onNavigate={setView} open={menuOpen} onClose={closeMenu} />
      <main className="main" id="main-content">
        <Topbar view={view} online={data.online} lastUpdated={data.lastUpdated}
                error={data.error} connection={data.connection}
                onRefresh={data.refetch}
                uiMode={uiMode} onToggleMode={setUiMode}
                onOpenMenu={openMenu} />
        <MarketRibbon signals={data.signals} online={data.online} />
        {shortcutHint && (
          <div className="shortcut-hint" role="status" onClick={clearShortcutHint}>
            {shortcutHint}
          </div>
        )}

        <div className="workspace" key={view}>
          {view === 'Command' && <CommandView data={data} actions={actions} />}
          {view === 'Journal' && <JournalView />}
          {view === 'Positions' && <PositionsView data={data} />}
          {view === 'Trades' && <TradesView data={data} />}
          {view === 'Stock Detail' && <StockDetailView />}
          {view === 'News' && <NewsView />}
          {view === 'Simulation' && <MonteCarloView />}
          {view === 'Quant Lab' && <QuantView />}
          {view === 'System' && <SystemView />}
        </div>
      </main>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <DashboardErrorBoundary>
    <ExplainerProvider><App /></ExplainerProvider>
  </DashboardErrorBoundary>
);
