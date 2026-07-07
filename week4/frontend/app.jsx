// app.jsx — Cardinal Financial Dashboard (router + live data)

const { useState, useEffect, useRef, useMemo } = React;

function StockHero({ stock }) {
  const market = useMarket();
  const prev = useRef(stock.price);
  const [flash, setFlash] = useState('');
  useEffect(() => {
    if (stock.price > prev.current) setFlash('flash-up');
    else if (stock.price < prev.current) setFlash('flash-down');
    prev.current = stock.price;
    const t = setTimeout(() => setFlash(''), 600);
    return () => clearTimeout(t);
  }, [stock.price]);

  const up = stock.changePct >= 0;
  return (
    <div className="stock-head">
      <div className="stock-icon" style={{background: stock.color + '22', color: stock.color}}>
        {stock.sym.slice(0, 2)}
      </div>
      <div style={{flex:1, minWidth:0}}>
        <div className="stock-name">{stock.name} · {stock.exchange || market.exchange}</div>
        <div className="stock-symbol">{stock.sym}</div>
        <div className={"stock-price " + flash} style={{color: flash ? (up ? 'var(--green)' : 'var(--red)') : undefined}}>
          {market.currency}{formatNum(stock.price, market.code, stock.price < 10 ? 3 : 2)}
        </div>
        <div className="stock-meta">
          <span className={'pill ' + (up ? 'up' : 'down')}>
            {up ? <Icon.ArrowUp/> : <Icon.ArrowDown/>}
            {up ? '+' : ''}{stock.change.toFixed(2)} · {stock.changePct.toFixed(2)}%
          </span>
          <span className="muted">Today</span>
          <span className="dim">·</span>
          <span className="muted">H <span className="mono" style={{color:'var(--text)'}}>{formatNum(stock.high, market.code)}</span></span>
          <span className="muted">L <span className="mono" style={{color:'var(--text)'}}>{formatNum(stock.low, market.code)}</span></span>
          <span className="muted">Vol <span className="mono" style={{color:'var(--text)'}}>{stock.vol}</span></span>
          <span className="muted">Mkt cap <span className="mono" style={{color:'var(--text)'}}>{formatCompact(stock.mcap, market.code)}</span></span>
        </div>
      </div>
    </div>
  );
}

function ChartCard({ stock }) {
  const [tf, setTf] = useState('1D');
  const [type, setType] = useState('candle');
  const tfs = ['15m', '1H', '1D', '1W', '1M', 'ALL'];
  // Slice candles by timeframe for visual variation
  const sliced = useMemo(() => {
    const n = { '15m': 24, '1H': 36, '1D': stock.candles.length, '1W': stock.candles.length, '1M': stock.candles.length, 'ALL': stock.candles.length }[tf];
    return stock.candles.slice(-n);
  }, [tf, stock.candles]);

  return (
    <div className="card">
      <StockHero stock={stock} />
      <div className="row gap-12" style={{marginBottom: 14}}>
        <div className="seg">
          {tfs.map(t => (
            <button key={t} className={tf===t?'active':''} onClick={() => setTf(t)}>{t}</button>
          ))}
        </div>
        <div className="card-spacer" />
        <div className="seg">
          <button className={type==='candle'?'active':''} onClick={() => setType('candle')}>Candles</button>
          <button className={type==='line'?'active':''} onClick={() => setType('line')}>Line</button>
        </div>
      </div>
      {type === 'candle'
        ? <CandleChart candles={sliced} accent={stock.color} height={340} />
        : <LineChart candles={sliced} accent={stock.color} height={340} />}
    </div>
  );
}

// ── Dashboard view (default) ──────────────────────────────
function DashboardView({ stocks, selected, setSelected, onAdd, available,
                        signalMap, realPositions }) {
  const stock = stocks.find(s => s.sym === selected) || stocks[0];
  if (!stock) return null;
  return (
    <div className="view-enter">
      <KpiRow stocks={stocks} />
      <div style={{height: 16}} />
      <div className="dash-grid">
        <div className="col">
          <ChartCard stock={stock} />
          <Positions stocks={stocks} realPositions={realPositions} />
        </div>
        <div className="col">
          <Watchlist
            stocks={stocks}
            selected={selected}
            onSelect={setSelected}
            onAdd={onAdd}
            available={available}
            signalMap={signalMap}
          />
          <MarketDepth stock={stock} />
          <News selected={stock.sym} />
        </div>
      </div>
    </div>
  );
}

// Small connection-status pill, rendered just under the ticker when on the IN
// market. Mirrors the same pattern the old plain-fetch dashboard used: tell
// the user *why* the data isn't moving instead of leaving them to guess.
function FinPilotStatus({ state }) {
  const { online, lastUpdated, error } = state;
  let label, cls;
  if (online && lastUpdated) {
    label = `FinPilot · live · updated ${lastUpdated.toLocaleTimeString()}`;
    cls = 'fp-status online';
  } else if (!online && error) {
    label = `FinPilot offline (${error}). Showing simulated baseline.`;
    cls = 'fp-status offline';
  } else {
    label = 'FinPilot · connecting…';
    cls = 'fp-status loading';
  }
  return <div className={cls}>{label}</div>;
}

// ── Root App ──────────────────────────────────────────────
function App() {
  const [view, setView] = useState('Dashboard');
  const [menuOpen, setMenuOpen] = useState(false);
  const [marketCode, setMarketCode] = useState('IN');
  const market = MARKETS[marketCode];

  // Per-market watchlist + selection, persisted across switches
  const [watchByMarket, setWatchByMarket] = useState({
    IN: MARKETS.IN.seed.map(s => s.sym),
    GLOBAL: MARKETS.GLOBAL.seed.map(s => s.sym),
  });
  const [selectedByMarket, setSelectedByMarket] = useState({
    IN: 'RELIANCE',
    GLOBAL: 'NVDA',
  });

  const watchSymbols = watchByMarket[marketCode];
  const selected = selectedByMarket[marketCode];

  const initialStocks = useMemo(() => BUILT_MARKETS[marketCode].seed, [marketCode]);
  const catalogInit = useMemo(() => BUILT_MARKETS[marketCode].catalog, [marketCode]);

  const live = useLiveMarket(initialStocks);
  const liveCatalog = useLiveMarket(catalogInit);

  // FinPilot bridge — poll the Django REST API for real signals, positions,
  // and orders. Enabled only on the IN market: FinPilot's universe is NSE,
  // and there's no point pinging the API while viewing US stocks.
  const finpilot = useFinPilotData(marketCode === 'IN');

  // Merge live + catalog so newly-added symbols still receive ticks
  const mergedLive = useMemo(() => {
    const map = new Map(live.map(s => [s.sym, s]));
    for (const sym of watchSymbols) {
      if (!map.has(sym)) {
        const c = liveCatalog.find(s => s.sym === sym);
        if (c) map.set(sym, c);
      }
    }
    return Array.from(map.values());
  }, [live, liveCatalog, watchSymbols]);

  // Overlay FinPilot's real prices + signal type onto the live stock objects.
  // The simulation keeps animating the chart; FinPilot anchors the "now" price.
  // When marketCode !== 'IN' the signalMap is empty and this is a no-op.
  const fpStocks = useMemo(
    () => mergeFinPilotPrices(mergedLive, finpilot.signalMap),
    [mergedLive, finpilot.signalMap],
  );
  const fpCatalog = useMemo(
    () => mergeFinPilotPrices(liveCatalog, finpilot.signalMap),
    [liveCatalog, finpilot.signalMap],
  );

  const visibleStocks = watchSymbols
    .map(sym => fpStocks.find(s => s.sym === sym))
    .filter(Boolean);

  function addStock(sym) {
    if (watchSymbols.includes(sym)) return;
    setWatchByMarket(prev => ({ ...prev, [marketCode]: [...prev[marketCode], sym] }));
    setSelectedByMarket(prev => ({ ...prev, [marketCode]: sym }));
  }
  function removeStock(sym) {
    setWatchByMarket(prev => {
      const next = prev[marketCode].filter(s => s !== sym);
      return { ...prev, [marketCode]: next };
    });
    if (selected === sym) {
      const next = watchSymbols.find(s => s !== sym);
      if (next) setSelectedByMarket(prev => ({ ...prev, [marketCode]: next }));
    }
  }
  function setSelected(sym) {
    setSelectedByMarket(prev => ({ ...prev, [marketCode]: sym }));
  }

  function onCommand(input) {
    const cat = fpCatalog.find(s => s.sym === input);
    if (cat) {
      if (!watchSymbols.includes(input)) addStock(input);
      setSelected(input);
      setView('Dashboard');
    }
  }

  useEffect(() => {
    const onKey = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
      if (e.key.toLowerCase() === 'a' && !e.metaKey && !e.ctrlKey) setView('Alerts');
      if (e.key.toLowerCase() === 'r' && !e.metaKey && !e.ctrlKey) {
        document.querySelector('.ticker-track')?.animate(
          [{ opacity: 0.4 }, { opacity: 1 }], { duration: 300 }
        );
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  return (
    <MarketContext.Provider value={market}>
      <div className="app">
        {menuOpen && <div className="scrim" onClick={() => setMenuOpen(false)} />}
        <Sidebar active={view} onNavigate={setView} open={menuOpen} onClose={() => setMenuOpen(false)} />
        <main className="main">
          <Topbar view={view} onNavigate={setView} onCommand={onCommand}
                  market={market} onMarketChange={setMarketCode}
                  onOpenMenu={() => setMenuOpen(true)} />
          <Ticker stocks={fpStocks.slice(0, 12)} />
          {marketCode === 'IN' && (
            <FinPilotStatus state={finpilot} />
          )}

          {view === 'Dashboard' && (
            <DashboardView
              stocks={visibleStocks}
              selected={selected}
              setSelected={setSelected}
              onAdd={addStock}
              available={fpCatalog}
              signalMap={finpilot.signalMap}
              realPositions={finpilot.positions}
            />
          )}
          {view === 'Markets' && (
            <MarketsView stocks={fpCatalog} onSelect={onCommand} />
          )}
          {view === 'Watchlist' && (
            <WatchlistView
              stocks={visibleStocks}
              onSelect={(sym) => { setSelected(sym); setView('Dashboard'); }}
              onAdd={addStock}
              onRemove={removeStock}
              available={fpCatalog}
            />
          )}
          {view === 'Portfolio' && (
            <PortfolioView stocks={visibleStocks} realPositions={finpilot.positions} />
          )}
          {view === 'Trades' && (
            <TradesView stocks={visibleStocks} realOrders={finpilot.orders} />
          )}
          {view === 'Simulation' && (
            <MonteCarloView stocks={visibleStocks} />
          )}
          {view === 'Journal' && <JournalView />}
          {view === 'News & Insights' && <NewsView stocks={visibleStocks} />}
          {view === 'Alerts' && <AlertsView />}
          {view === 'Settings' && <SettingsView />}
        </main>
        <BottomNav active={view} onNavigate={setView} />
      </div>
    </MarketContext.Provider>
  );
}

// Wrapped in ExplainerProvider so the signal-explainer panel (explainer.jsx)
// is mounted once, controllable from anywhere via window.openSignalExplainer().
ReactDOM.createRoot(document.getElementById('root')).render(
  <ExplainerProvider><App /></ExplainerProvider>
);
