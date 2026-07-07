// components.jsx — UI components

// ── Icons (minimal, inline SVG, single-stroke) ─────────────
const Icon = {
  Dashboard: ({s=16}) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="2" y="2" width="5" height="5" rx="1.2"/><rect x="9" y="2" width="5" height="5" rx="1.2"/><rect x="2" y="9" width="5" height="5" rx="1.2"/><rect x="9" y="9" width="5" height="5" rx="1.2"/></svg>,
  Chart: ({s=16}) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M2 13L6 8L9 11L14 4"/><path d="M10 4h4v4" strokeLinecap="round"/></svg>,
  Watch: ({s=16}) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="8" cy="8" r="6"/><path d="M8 5v3l2 1.5"/></svg>,
  Wallet: ({s=16}) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="2" y="4" width="12" height="9" rx="1.5"/><path d="M2 7h12"/><circle cx="11.5" cy="10" r="0.8" fill="currentColor"/></svg>,
  Trades: ({s=16}) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M3 5h8M11 5l-2-2M11 5l-2 2"/><path d="M13 11H5M5 11l2-2M5 11l2 2"/></svg>,
  News: ({s=16}) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="2" y="3" width="12" height="10" rx="1.2"/><path d="M4.5 6h7M4.5 8.5h7M4.5 11h4"/></svg>,
  Alerts: ({s=16}) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M4 11V7a4 4 0 118 0v4l1 1.5H3L4 11z"/><path d="M6.5 13.5a1.5 1.5 0 003 0"/></svg>,
  Settings: ({s=16}) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="8" cy="8" r="2"/><path d="M8 1.5v2M8 12.5v2M14.5 8h-2M3.5 8h-2M12.6 3.4l-1.4 1.4M4.8 11.2l-1.4 1.4M12.6 12.6l-1.4-1.4M4.8 4.8L3.4 3.4"/></svg>,
  Search: ({s=14}) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14" strokeLinecap="round"/></svg>,
  Check: ({s=14}) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M3 8.5l3 3 7-7" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  Menu: ({s=18}) => <svg width={s} height={s} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M3 5h12M3 9h12M3 13h12" strokeLinecap="round"/></svg>,
  Bell: ({s=15}) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M4 11V7a4 4 0 118 0v4l1 1.5H3L4 11z"/><path d="M6.5 13.5a1.5 1.5 0 003 0"/></svg>,
  Help: ({s=15}) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="8" cy="8" r="6"/><path d="M6.5 6a1.5 1.5 0 113 0c0 1-1.5 1-1.5 2.2"/><circle cx="8" cy="11" r="0.5" fill="currentColor"/></svg>,
  ArrowUp: ({s=11}) => <svg width={s} height={s} viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M6 9.5V2.5M6 2.5l-3 3M6 2.5l3 3" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  ArrowDown: ({s=11}) => <svg width={s} height={s} viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M6 2.5v7M6 9.5l-3-3M6 9.5l3-3" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  Plus: ({s=14}) => <svg width={s} height={s} viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M7 3v8M3 7h8" strokeLinecap="round"/></svg>,
  Close: ({s=14}) => <svg width={s} height={s} viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M3.5 3.5l7 7M10.5 3.5l-7 7" strokeLinecap="round"/></svg>,
  Star: ({s=12, filled=false}) => <svg width={s} height={s} viewBox="0 0 12 12" fill={filled?'currentColor':'none'} stroke="currentColor" strokeWidth="1.4"><path d="M6 1.5l1.4 2.9 3.1.4-2.3 2.2.6 3.1L6 8.6l-2.8 1.5.6-3.1L1.5 4.8l3.1-.4L6 1.5z" strokeLinejoin="round"/></svg>,
  Filter: ({s=14}) => <svg width={s} height={s} viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M2 3h10M3.5 7h7M5 11h4" strokeLinecap="round"/></svg>,
};

// ── Sidebar ────────────────────────────────────────────────
const NAV_SECTIONS = [
  { label: 'Workspace', items: [
    { name: 'Dashboard', icon: 'Dashboard' },
    { name: 'Markets', icon: 'Chart' },
    { name: 'Watchlist', icon: 'Watch' },
  ]},
  { label: 'Account', items: [
    { name: 'Portfolio', icon: 'Wallet' },
    { name: 'Trades', icon: 'Trades' },
    { name: 'Simulation', icon: 'Chart' },
    { name: 'Journal', icon: 'News' },
    { name: 'News & Insights', icon: 'News' },
  ]},
  { label: 'Other', items: [
    { name: 'Alerts', icon: 'Alerts' },
    { name: 'Settings', icon: 'Settings' },
  ]},
];

function Sidebar({ active, onNavigate, open, onClose }) {
  const market = useMarket();
  return (
    <aside className={'sidebar ' + (open ? 'open' : '')}>
      <div className="brand">
        <div className="brand-mark">C</div>
        <div>
          <div className="brand-name">Cardinal</div>
          <div className="brand-sub">Pro · Markets</div>
        </div>
      </div>
      {NAV_SECTIONS.map(sec => (
        <div className="nav-section" key={sec.label}>
          <div className="nav-label">{sec.label}</div>
          {sec.items.map(it => {
            const IconCmp = Icon[it.icon];
            return (
              <button key={it.name}
                      className={'nav-item ' + (active === it.name ? 'active' : '')}
                      onClick={() => { onNavigate(it.name); onClose?.(); }}>
                <IconCmp />
                <span>{it.name}</span>
                {active === it.name && <span className="dot" />}
              </button>
            );
          })}
        </div>
      ))}
      <div className="sidebar-footer">
        <div className="title">{market.exchange} · Live</div>
        <div className="sub">{market.hours}</div>
      </div>
    </aside>
  );
}

// ── Topbar ────────────────────────────────────────────────
function Popover({ open, onClose, children, align = 'right', width = 260 }) {
  const ref = React.useRef(null);
  React.useEffect(() => {
    if (!open) return;
    const close = (e) => { if (ref.current && !ref.current.contains(e.target)) onClose(); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div ref={ref} className="popover" style={{ [align]: 0, width }}>
      {children}
    </div>
  );
}

function Topbar({ view, onNavigate, onCommand, market, onMarketChange, onOpenMenu }) {
  const [help, setHelp] = React.useState(false);
  const [bell, setBell] = React.useState(false);
  const [user, setUser] = React.useState(false);
  const [mktOpen, setMktOpen] = React.useState(false);
  const inputRef = React.useRef(null);
  const [query, setQuery] = React.useState('');

  React.useEffect(() => {
    const k = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        inputRef.current?.focus();
      }
      if (e.key === 'Escape') {
        setHelp(false); setBell(false); setUser(false);
        inputRef.current?.blur();
      }
    };
    document.addEventListener('keydown', k);
    return () => document.removeEventListener('keydown', k);
  }, []);

  const notifications = [
    { sym: 'NVDA', msg: 'Crossed above $1,140 target', time: '2m', up: true },
    { sym: 'TSLA', msg: 'Down 3.4% in last hour', time: '14m', up: false },
    { sym: 'BTC',  msg: 'Volume spike detected', time: '38m', up: true },
    { sym: 'AAPL', msg: 'Earnings call scheduled tomorrow', time: '2h', up: null },
  ];

  function submitSearch(e) {
    e.preventDefault();
    if (!query.trim()) return;
    onCommand?.(query.trim().toUpperCase());
    setQuery('');
    inputRef.current?.blur();
  }

  return (
    <div className="topbar">
      <button className="hamburger" onClick={onOpenMenu} aria-label="Open menu">
        <Icon.Menu />
      </button>
      <div className="crumb">{market.label} · {market.exchange} &nbsp;/&nbsp; <b>{view}</b></div>
      <form className="search" onSubmit={submitSearch}>
        <Icon.Search />
        <input ref={inputRef} value={query} onChange={e => setQuery(e.target.value)}
               placeholder="Search symbol or run command…" />
        <span className="kbd">⌘ K</span>
      </form>
      <div className="topbar-spacer" />

      <div style={{position:'relative'}}>
        <button className="market-chip" onClick={() => { setMktOpen(!mktOpen); setHelp(false); setBell(false); setUser(false); }}>
          <span className="market-flag">{market.flag}</span>
          <span>{market.label}</span>
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.4"><path d="M2.5 4L5 6.5 7.5 4" strokeLinecap="round" strokeLinejoin="round"/></svg>
        </button>
        <Popover open={mktOpen} onClose={() => setMktOpen(false)} width={220}>
          <div className="pop-head">Market</div>
          {Object.values(MARKETS).map(m => (
            <button key={m.code}
                    className={'pop-item btn ' + (market.code === m.code ? 'sel' : '')}
                    onClick={() => { onMarketChange(m.code); setMktOpen(false); }}>
              <span style={{display:'flex', alignItems:'center', gap:10}}>
                <span style={{fontSize:18}}>{m.flag}</span>
                <span>
                  <div style={{fontSize:13}}>{m.label}</div>
                  <div style={{fontSize:11, color:'var(--text-3)'}}>{m.exchange} · {m.currencyCode}</div>
                </span>
              </span>
              {market.code === m.code && <Icon.Check />}
            </button>
          ))}
        </Popover>
      </div>

      <div style={{position:'relative'}}>
        <button className="icon-btn" onClick={() => { setHelp(!help); setBell(false); setUser(false); }}>
          <Icon.Help />
        </button>
        <Popover open={help} onClose={() => setHelp(false)} width={240}>
          <div className="pop-head">Help & shortcuts</div>
          <div className="pop-item"><span>Open command</span><span className="kbd">⌘ K</span></div>
          <div className="pop-item"><span>Toggle theme</span><span className="kbd">⌘ ⇧ D</span></div>
          <div className="pop-item"><span>New alert</span><span className="kbd">A</span></div>
          <div className="pop-item"><span>Refresh data</span><span className="kbd">R</span></div>
          <div className="pop-divider"></div>
          <div className="pop-item"><span>Documentation</span></div>
          <div className="pop-item"><span>Contact support</span></div>
        </Popover>
      </div>

      <div style={{position:'relative'}}>
        <button className="icon-btn" onClick={() => { setBell(!bell); setHelp(false); setUser(false); }}>
          <Icon.Bell /><span className="pip"></span>
        </button>
        <Popover open={bell} onClose={() => setBell(false)} width={300}>
          <div className="pop-head">
            <span>Notifications</span>
            <span className="pill" style={{marginLeft:'auto'}}>{notifications.length} new</span>
          </div>
          {notifications.map((n, i) => (
            <div className="pop-row" key={i} onClick={() => { onNavigate('Alerts'); setBell(false); }}>
              <div className="watch-icon" style={{background: (n.up===true?'var(--green-dim)':n.up===false?'var(--red-dim)':'var(--card-2)'), color:(n.up===true?'var(--green)':n.up===false?'var(--red)':'var(--text-2)')}}>{n.sym.slice(0,2)}</div>
              <div style={{flex:1, minWidth:0}}>
                <div style={{fontSize:13}}>{n.msg}</div>
                <div style={{fontSize:11, color:'var(--text-3)', marginTop:2}}>{n.sym} · {n.time} ago</div>
              </div>
            </div>
          ))}
          <div className="pop-divider"></div>
          <button className="pop-item" style={{width:'100%', background:'transparent', border:0, color:'var(--green)'}}
                  onClick={() => { onNavigate('Alerts'); setBell(false); }}>View all alerts →</button>
        </Popover>
      </div>

      <div style={{position:'relative'}}>
        <button className="user-chip" style={{border:0}} onClick={() => { setUser(!user); setHelp(false); setBell(false); }}>
          <div className="avatar">AR</div>
          <div style={{textAlign:'left'}}>
            <div className="name">Alex Rivera</div>
            <div className="role">Trader · Tier 3</div>
          </div>
        </button>
        <Popover open={user} onClose={() => setUser(false)} width={220}>
          <div className="pop-head">alex@cardinal.app</div>
          <button className="pop-item btn" onClick={() => { onNavigate('Portfolio'); setUser(false); }}>Portfolio</button>
          <button className="pop-item btn" onClick={() => { onNavigate('Settings'); setUser(false); }}>Account settings</button>
          <button className="pop-item btn">Billing & plan</button>
          <button className="pop-item btn">API keys</button>
          <div className="pop-divider"></div>
          <button className="pop-item btn" style={{color:'var(--red)'}}>Sign out</button>
        </Popover>
      </div>
    </div>
  );
}

// ── Ticker (sliding) ──────────────────────────────────────
function Ticker({ stocks }) {
  const market = useMarket();
  // Track previous prices to flash colour
  const prevRef = React.useRef({});
  const items = stocks.concat(stocks); // duplicate for seamless loop
  return (
    <div className="ticker-wrap">
      <div className="ticker-pill"><span className="live-dot"/> Live</div>
      <div className="ticker-track">
        {items.map((s, idx) => {
          const prev = prevRef.current[s.sym] ?? s.price;
          const up = s.changePct >= 0;
          const flash = s.price > prev ? 'flash-up' : s.price < prev ? 'flash-down' : '';
          prevRef.current[s.sym] = s.price;
          return (
            <div className="ticker-item" key={idx}>
              <span className="ticker-symbol" style={{ color: s.color }}>{s.sym}</span>
              <span className={'ticker-price mono ' + flash}>
                {market.currency}{formatNum(s.price, market.code, s.price < 10 ? 3 : 2)}
              </span>
              <span className={'ticker-change ' + (up ? 'up' : 'down')}>
                {up ? <Icon.ArrowUp/> : <Icon.ArrowDown/>}
                {Math.abs(s.changePct).toFixed(2)}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── KPI row ───────────────────────────────────────────────
function KpiRow({ stocks }) {
  const market = useMarket();
  const lotMult = market.code === 'IN' ? 80 : 12;
  const totalValue = stocks.reduce((s, x) => s + x.price * (lotMult + x.sym.charCodeAt(0) % 8), 0);
  const todayPnL = stocks.reduce((s, x) => s + x.change * (lotMult + x.sym.charCodeAt(0) % 8), 0);
  const todayPct = totalValue ? (todayPnL / totalValue) * 100 : 0;
  const winRate = 68.4;
  return (
    <div className="kpi-row">
      <div className="kpi">
        <div className="kpi-label">Portfolio Value</div>
        <div className="kpi-value">{formatCompact(totalValue, market.code)}</div>
        <div className="kpi-foot"><span className="muted">{stocks.length} positions · {market.exchange}</span></div>
      </div>
      <div className="kpi">
        <div className="kpi-label">Today's P&L</div>
        <div className="kpi-value" style={{color: todayPnL >= 0 ? 'var(--green)' : 'var(--red)'}}>
          {todayPnL >= 0 ? '+' : '−'}{formatCompact(Math.abs(todayPnL), market.code)}
        </div>
        <div className="kpi-foot">
          <span className={'pill ' + (todayPnL >= 0 ? 'up' : 'down')}>
            {todayPnL >= 0 ? <Icon.ArrowUp/> : <Icon.ArrowDown/>}
            {Math.abs(todayPct).toFixed(2)}%
          </span>
          <span className="muted">vs yesterday</span>
        </div>
      </div>
      <div className="kpi">
        <div className="kpi-label">Win Rate · 30d</div>
        <div className="kpi-value">{winRate.toFixed(1)}%</div>
        <div className="kpi-foot">
          <span className="pill up"><Icon.ArrowUp/>3.2%</span>
          <span className="muted">42 trades</span>
        </div>
      </div>
    </div>
  );
}

// ── Watchlist ─────────────────────────────────────────────
function Watchlist({ stocks, selected, onSelect, onAdd, available, signalMap }) {
  const market = useMarket();
  const [showAdd, setShowAdd] = React.useState(false);
  const [q, setQ] = React.useState('');
  const filtered = available.filter(a => !stocks.find(s => s.sym === a.sym))
    .filter(a => !q || a.sym.toLowerCase().includes(q.toLowerCase()) || a.name.toLowerCase().includes(q.toLowerCase()));
  // WHY signalMap is optional: when running on GLOBAL market (or with the
  // FinPilot backend down) this is undefined/empty, the BUY/SELL pill simply
  // doesn't render, and the row looks exactly as it always did.
  const hasSignals = signalMap && Object.keys(signalMap).length > 0;
  return (
    <div className="card" style={{position: 'relative'}}>
      <div className="card-head">
        <div className="card-title">Watchlist</div>
        <span className="pill"><span style={{width:6,height:6,background:'var(--green)',borderRadius:'50%'}}/>{stocks.length} symbols</span>
        {hasSignals && (
          <span className="pill" style={{marginLeft:6}} title="Live FinPilot signals">
            <span style={{width:6,height:6,background:'var(--violet)',borderRadius:'50%'}}/>FinPilot
          </span>
        )}
        <div className="card-spacer" />
        <button className="icon-btn" style={{width:28, height:28}}><Icon.Filter s={13}/></button>
      </div>
      <div className="watchlist">
        {stocks.map(s => {
          const sig = signalMap?.[s.sym];
          return (
          <div key={s.sym}
               className={'watch-row ' + (selected === s.sym ? 'selected' : '')}
               onClick={() => onSelect(s.sym)}>
            <div className="watch-left">
              <div className="watch-icon" style={{background: s.color + '22', color: s.color}}>{s.sym.slice(0,2)}</div>
              <div style={{minWidth: 0}}>
                <div className="watch-symbol">
                  {s.sym}
                  {sig && (
                    <button
                      type="button"
                      className={'fp-sig fp-' + sig.signal_type.toLowerCase()}
                      title="Click for AI explanation"
                      onClick={(e) => {
                        // WHY stopPropagation: the row itself has onSelect; the
                        // badge click is for the explainer, not "select this row".
                        e.stopPropagation();
                        window.openSignalExplainer?.(s.sym);
                      }}>
                      {sig.signal_type}
                    </button>
                  )}
                </div>
                <div className="watch-name" style={{whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis'}}>{s.name}</div>
              </div>
            </div>
            <Sparkline data={s.spark} color={s.changePct >= 0 ? 'var(--green)' : 'var(--red)'} width={70} height={22} />
            <div>
              <div className="watch-price mono">{market.currency}{formatNum(s.price, market.code, s.price < 10 ? 3 : 2)}</div>
              <div className="watch-change mono" style={{color: s.changePct >= 0 ? 'var(--green)' : 'var(--red)'}}>
                {s.changePct >= 0 ? '+' : ''}{s.changePct.toFixed(2)}%
              </div>
            </div>
          </div>
        );})}
        <button className="watch-add" onClick={() => setShowAdd(true)}>
          <span className="watch-add-icon"><Icon.Plus s={14}/></span>
          <span>Add a symbol to watchlist</span>
        </button>
      </div>
      {showAdd && (
        <div className="add-panel">
          <div className="row gap-12" style={{marginBottom: 10}}>
            <div className="card-title">Add symbol</div>
            <div className="card-spacer" />
            <button className="icon-btn" style={{width:28,height:28}} onClick={() => setShowAdd(false)}><Icon.Close/></button>
          </div>
          <div className="add-search">
            <Icon.Search/>
            <input autoFocus placeholder="Search by ticker or company" value={q} onChange={e => setQ(e.target.value)} />
          </div>
          <div className="add-list">
            {filtered.length === 0 && <div style={{padding: 12, color: 'var(--text-3)', fontSize: 12}}>No matches.</div>}
            {filtered.map(a => (
              <div key={a.sym} className="add-row" onClick={() => { onAdd(a.sym); setShowAdd(false); setQ(''); }}>
                <div className="watch-icon" style={{background: (a.color||'#888') + '22', color: a.color||'#aaa'}}>{a.sym.slice(0,2)}</div>
                <div className="grow">
                  <div className="watch-symbol">{a.sym}</div>
                  <div className="watch-name">{a.name}</div>
                </div>
                <div className="mono" style={{fontSize: 12, color: 'var(--text-2)'}}>{market.currency}{formatNum(a.price, market.code)}</div>
                <Icon.Plus s={14}/>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Market depth ──────────────────────────────────────────
function MarketDepth({ stock }) {
  const market = useMarket();
  // Deterministic order book from price
  const book = React.useMemo(() => {
    const p = stock.price;
    const tick = p > 1000 ? 1 : p > 100 ? 0.1 : 0.05;
    const rng = (seed) => { let t = seed; return () => { t = (t * 9301 + 49297) % 233280; return t / 233280; }; };
    const r = rng(Math.floor(p * 100));
    const asks = [];
    const bids = [];
    let acc = 0;
    for (let i = 0; i < 6; i++) {
      const size = +(0.2 + r() * 4.5).toFixed(2);
      acc += size;
      asks.push({ price: +(p + tick * (i + 1)).toFixed(2), size, total: +acc.toFixed(2) });
    }
    acc = 0;
    for (let i = 0; i < 6; i++) {
      const size = +(0.2 + r() * 4.5).toFixed(2);
      acc += size;
      bids.push({ price: +(p - tick * (i + 1)).toFixed(2), size, total: +acc.toFixed(2) });
    }
    const maxTotal = Math.max(asks[asks.length-1].total, bids[bids.length-1].total);
    return { asks: asks.reverse(), bids, maxTotal, spread: (asks[0].price - bids[0].price).toFixed(2) };
  }, [Math.round(stock.price * 10)]);

  return (
    <div className="card tight">
      <div className="card-head">
        <div className="card-title">Order book</div>
        <div className="card-spacer" />
        <span className="pill">{stock.sym}</span>
      </div>
      <div style={{display:'grid', gridTemplateColumns:'1fr 1fr 1fr', fontSize:10, color:'var(--text-3)', textTransform:'uppercase', letterSpacing:'0.06em', padding:'0 8px 6px'}}>
        <div>Price</div><div style={{textAlign:'right'}}>Size</div><div style={{textAlign:'right'}}>Total</div>
      </div>
      <div className="depth">
        {book.asks.map((a, i) => (
          <div className="depth-row ask" key={'a'+i}>
            <span className="bar" style={{width: (a.total/book.maxTotal*100) + '%'}} />
            <span className="price">{a.price.toFixed(2)}</span>
            <span className="size">{a.size.toFixed(2)}</span>
            <span className="total">{a.total.toFixed(2)}</span>
          </div>
        ))}
      </div>
      <div className="depth-spread">
        Spread <span style={{color:'var(--text)'}}>{book.spread}</span>
        <span style={{margin:'0 8px', color:'var(--text-3)'}}>·</span>
        Mid <span style={{color:'var(--text)'}}>{market.currency}{formatNum(stock.price, market.code)}</span>
      </div>
      <div className="depth">
        {book.bids.map((b, i) => (
          <div className="depth-row bid" key={'b'+i}>
            <span className="bar" style={{width: (b.total/book.maxTotal*100) + '%'}} />
            <span className="price">{b.price.toFixed(2)}</span>
            <span className="size">{b.size.toFixed(2)}</span>
            <span className="total">{b.total.toFixed(2)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Recent trades / positions ─────────────────────────────
function Positions({ stocks, title = 'Open positions', limit = 6, realPositions = null }) {
  const market = useMarket();
  const [filter, setFilter] = React.useState('All');
  const filters = ['All', 'Stocks', 'Crypto'];
  const cryptoSet = new Set(['BTC','ETH','SOL','XRP','DOGE','COIN']);

  // WHY this branch: when realPositions is non-null and has at least one open
  // position, we render REAL FinPilot holdings — quantity, avg entry, P&L all
  // come from the Django backend. Falling back to the derived rows when the
  // list is empty keeps the demo UI populated for "no trades yet" days.
  const usingReal = realPositions
    && Array.isArray(realPositions.open_positions)
    && realPositions.open_positions.length > 0;

  let rows;
  if (usingReal) {
    rows = realPositions.open_positions.slice(0, limit).map(p => {
      const bareSym = (p.symbol || '').replace(/\.(NS|BO|NSE|BSE)$/i, '');
      const stock = stocks.find(s => s.sym === bareSym);
      const last = stock ? stock.price : Number(p.avg_entry_price);
      const avg = Number(p.avg_entry_price);
      const qty = Number(p.quantity);
      return {
        sym: bareSym,
        name: stock?.name || bareSym,
        color: stock?.color || '#5fa0ff',
        side: 'BUY',                              // open positions are long
        qty, avg, last,
        mv: qty * last,
        pnl: Number(p.pnl ?? 0),
      };
    });
  } else {
    const filteredStocks = stocks.filter(s =>
      filter === 'All' ? true :
      filter === 'Crypto' ? cryptoSet.has(s.sym) :
      !cryptoSet.has(s.sym)
    );
    const lotBase = market.code === 'IN' ? 40 : 10;
    rows = filteredStocks.slice(0, limit).map((s, i) => {
      const qty = (lotBase + s.sym.charCodeAt(0) % 18);
      const avg = s.open;
      const mv = qty * s.price;
      const pnl = qty * (s.price - avg);
      return { sym: s.sym, name: s.name, color: s.color, side: i % 4 === 3 ? 'SELL' : 'BUY', qty, avg, last: s.price, mv, pnl };
    });
  }
  return (
    <div className="card tight">
      <div className="card-head">
        <div className="card-title">{title}</div>
        {usingReal && (
          <span className="pill" style={{marginLeft:8}} title="Live from FinPilot /api/portfolio/">
            <span style={{width:6,height:6,background:'var(--violet)',borderRadius:'50%'}}/>FinPilot
          </span>
        )}
        <div className="card-spacer" />
        {!usingReal && (
          <div className="seg">
            {filters.map(f => (
              <button key={f} className={filter===f?'active':''} onClick={() => setFilter(f)}>{f}</button>
            ))}
          </div>
        )}
      </div>
      <table className="trades-table">
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Side</th>
            <th style={{textAlign:'right'}}>Qty</th>
            <th style={{textAlign:'right'}}>Avg</th>
            <th style={{textAlign:'right'}}>Last</th>
            <th style={{textAlign:'right'}}>Market value</th>
            <th style={{textAlign:'right'}}>P&L</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.sym}>
              <td>
                <div style={{display:'flex',alignItems:'center',gap:10}}>
                  <div className="watch-icon" style={{width:24,height:24,background:r.color+'22',color:r.color}}>{r.sym.slice(0,2)}</div>
                  <div>
                    <div style={{fontWeight:600,fontSize:13}}>{r.sym}</div>
                    <div style={{fontSize:11,color:'var(--text-3)'}}>{r.name}</div>
                  </div>
                </div>
              </td>
              <td><span className={'tag ' + (r.side === 'BUY' ? 'buy' : 'sell')}>{r.side}</span></td>
              <td style={{textAlign:'right'}}>{r.qty}</td>
              <td style={{textAlign:'right',color:'var(--text-2)'}}>{formatNum(r.avg, market.code)}</td>
              <td style={{textAlign:'right'}}>{formatNum(r.last, market.code)}</td>
              <td style={{textAlign:'right'}}>{formatCompact(r.mv, market.code)}</td>
              <td style={{textAlign:'right',color: r.pnl >= 0 ? 'var(--green)' : 'var(--red)'}}>
                {r.pnl >= 0 ? '+' : '−'}{formatCompact(Math.abs(r.pnl), market.code)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── News ───────────────────────────────────────────────────
function News({ selected }) {
  const market = useMarket();
  const items = market.code === 'IN' ? [
    { sym: selected, src: 'Mint',           time: '12m', glyph: 'IMG · headline', head: `${selected} jumps after strong Q4 results; brokerages raise target prices on margin outlook.` },
    { sym: 'RBI',   src: 'Business Standard', time: '38m', glyph: 'IMG · macro',  head: 'RBI minutes signal extended pause on rates; market prices in cuts by Q3 FY26.' },
    { sym: 'NIFTY', src: 'Economic Times',  time: '1h',  glyph: 'IMG · markets',  head: 'Nifty 50 ends at fresh record high as IT and banks lead gains; SIP inflows hit ₹26,000 Cr.' },
    { sym: 'FII',   src: 'Moneycontrol',    time: '2h',  glyph: 'IMG · flows',    head: 'FII inflows cross ₹18,500 Cr in October; DII buying remains supportive of broader markets.' },
  ] : [
    { sym: selected, src: 'Bloomberg', time: '12m', glyph: 'IMG · headline', head: `${selected} beats Q2 earnings expectations; raises full-year guidance on AI demand.` },
    { sym: 'FED',   src: 'Reuters',   time: '38m', glyph: 'IMG · macro',    head: 'Fed minutes hint at potential rate pause; markets price in 78% probability.' },
    { sym: 'BTC',   src: 'CoinDesk',  time: '1h',  glyph: 'IMG · crypto',   head: 'Bitcoin hovers near 71k as institutional inflows climb for third week.' },
    { sym: 'MKT',   src: 'WSJ',       time: '2h',  glyph: 'IMG · markets',  head: 'Semiconductor index leads S&P higher amid renewed AI capex outlook.' },
  ];
  return (
    <div className="card tight">
      <div className="card-head">
        <div className="card-title">Insights</div>
        <span className="card-sub">Filtered for your positions</span>
        <div className="card-spacer" />
        <button className="pill">View all</button>
      </div>
      <div>
        {items.map((it, i) => (
          <div className="news-item" key={i}>
            <div className="news-thumb"><div className="glyph">{it.glyph}</div></div>
            <div style={{minWidth:0}}>
              <div className="news-head">{it.head}</div>
              <div className="news-meta">
                <span className="src">{it.src}</span>
                <span>·</span>
                <span>{it.time} ago</span>
                <span>·</span>
                <span className="mono" style={{color: 'var(--text-2)'}}>{it.sym}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

Object.assign(window, {
  Icon, Sidebar, Topbar, Ticker, KpiRow,
  Watchlist, MarketDepth, Positions, News,
  Popover, BottomNav,
});

// ── Bottom nav (mobile) ───────────────────────────────────
function BottomNav({ active, onNavigate }) {
  const items = [
    { name: 'Dashboard', icon: 'Dashboard' },
    { name: 'Markets', icon: 'Chart' },
    { name: 'Watchlist', icon: 'Watch' },
    { name: 'Portfolio', icon: 'Wallet' },
    { name: 'Alerts', icon: 'Alerts' },
  ];
  return (
    <nav className="bottom-nav">
      {items.map(it => {
        const I = Icon[it.icon];
        return (
          <button key={it.name}
                  className={active === it.name ? 'active' : ''}
                  onClick={() => onNavigate(it.name)}>
            <I s={20} />
            <span>{it.name}</span>
          </button>
        );
      })}
    </nav>
  );
}
window.BottomNav = BottomNav;
