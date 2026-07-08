// app.jsx — FinPilot dashboard shell (routing + live data + mode toggle).

const { useState, useEffect, useCallback } = React;

// UI mode ("terminal" | "minimal") persists across reloads; the attribute on
// <html> is what styles.css keys every token off.
function useUiMode() {
  const [mode, setMode] = useState(() => localStorage.getItem('fp-ui') || 'terminal');
  useEffect(() => {
    document.documentElement.dataset.ui = mode;
    localStorage.setItem('fp-ui', mode);
  }, [mode]);
  return [mode, setMode];
}

function App() {
  const [view, setView] = useState('Command');
  const [menuOpen, setMenuOpen] = useState(false);
  const [uiMode, setUiMode] = useUiMode();
  const data = useFinPilot();

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
  }, [data]);

  const actions = {
    busy, note,
    refreshSignals: () => runAction('refresh', '/signals/refresh/', 'Signal refresh'),
    executeOrders: () => runAction('execute', '/portfolio/execute-orders/', 'Order routing'),
  };

  return (
    <div className="app">
      {menuOpen && <div className="scrim" onClick={() => setMenuOpen(false)} />}
      <Sidebar active={view} onNavigate={setView} open={menuOpen} onClose={() => setMenuOpen(false)} />
      <main className="main">
        <Topbar view={view} online={data.online} lastUpdated={data.lastUpdated}
                error={data.error} onRefresh={data.refetch}
                uiMode={uiMode} onToggleMode={setUiMode}
                onOpenMenu={() => setMenuOpen(true)} />

        {view === 'Command' && <CommandView data={data} actions={actions} />}
        {view === 'Journal' && <JournalView />}
        {view === 'Positions' && <PositionsView data={data} />}
        {view === 'Trades' && <TradesView data={data} />}
        {view === 'Stock Detail' && <StockDetailView />}
        {view === 'News' && <NewsView />}
        {view === 'Simulation' && <MonteCarloView />}
        {view === 'Quant Lab' && <QuantView />}
        {view === 'System' && <SystemView />}
      </main>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <ExplainerProvider><App /></ExplainerProvider>
);
