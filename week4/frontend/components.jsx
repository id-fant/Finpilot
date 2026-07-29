// components.jsx — FinPilot shell: icons, sidebar, topbar, shared widgets.

const Icon = {
  Command: ({s=16}) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="2" y="2" width="5" height="5" rx="1.2"/><rect x="9" y="2" width="5" height="5" rx="1.2"/><rect x="2" y="9" width="5" height="5" rx="1.2"/><rect x="9" y="9" width="5" height="5" rx="1.2"/></svg>,
  Journal: ({s=16}) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="2.5" y="2" width="11" height="12" rx="1.5"/><path d="M5 5.5h6M5 8h6M5 10.5h4"/></svg>,
  Wallet: ({s=16}) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="2" y="4" width="12" height="9" rx="1.5"/><path d="M2 7h12"/><circle cx="11.5" cy="10" r="0.8" fill="currentColor"/></svg>,
  Trades: ({s=16}) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M3 5h8M11 5l-2-2M11 5l-2 2"/><path d="M13 11H5M5 11l2-2M5 11l2 2"/></svg>,
  Search: ({s=16}) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14" strokeLinecap="round"/></svg>,
  Chart: ({s=16}) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M2 13L6 8L9 11L14 4"/><path d="M10 4h4v4" strokeLinecap="round"/></svg>,
  Flask: ({s=16}) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M6.5 2v4L3 12.5a1 1 0 00.9 1.5h8.2a1 1 0 00.9-1.5L9.5 6V2"/><path d="M5.5 2h5M5 9.5h6"/></svg>,
  News: ({s=16}) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="2" y="3" width="12" height="10" rx="1.2"/><path d="M4.5 6h4M4.5 8.5h4M4.5 11h3M10.5 6h1.5v5h-1.5z"/></svg>,
  Settings: ({s=16}) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="8" cy="8" r="2"/><path d="M8 1.5v2M8 12.5v2M14.5 8h-2M3.5 8h-2M12.6 3.4l-1.4 1.4M4.8 11.2l-1.4 1.4M12.6 12.6l-1.4-1.4M4.8 4.8L3.4 3.4"/></svg>,
  Refresh: ({s=15}) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M13.5 8a5.5 5.5 0 11-1.6-3.9M13.5 2v3h-3" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  Terminal: ({s=14}) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="2" y="3" width="12" height="10" rx="1.5"/><path d="M5 6l2 2-2 2M8.5 10.5h3" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  Sun: ({s=14}) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="8" cy="8" r="3"/><path d="M8 1v1.5M8 13.5V15M1 8h1.5M13.5 8H15M3 3l1 1M12 12l1 1M13 3l-1 1M4 12l-1 1" strokeLinecap="round"/></svg>,
  Menu: ({s=18}) => <svg width={s} height={s} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M3 5h12M3 9h12M3 13h12" strokeLinecap="round"/></svg>,
};

const NAV = [
  { label: 'Decide', items: [
    { name: 'Command', icon: 'Command' },
    { name: 'Journal', icon: 'Journal' },
  ]},
  { label: 'Trade', items: [
    { name: 'Positions', icon: 'Wallet' },
    { name: 'Trades', icon: 'Trades' },
  ]},
  { label: 'Research', items: [
    { name: 'Stock Detail', icon: 'Search' },
    { name: 'News', icon: 'News' },
    { name: 'Simulation', icon: 'Chart' },
    { name: 'Quant Lab', icon: 'Flask' },
  ]},
  { label: 'Ops', items: [
    { name: 'System', icon: 'Settings' },
  ]},
];

// ── Tiny sparkline (replaces the old charts.jsx dependency) ────────────────
function Spark({ data, color = 'var(--accent)', w = 96, h = 26 }) {
  if (!data || data.length < 2) return null;
  const min = Math.min(...data), max = Math.max(...data), range = max - min || 1;
  const step = w / (data.length - 1);
  const pts = data.map((v, i) => `${i * step},${h - ((v - min) / range) * h}`).join(' ');
  return (
    <svg width={w} height={h} style={{ display: 'block' }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5"
                strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// ── Sidebar ────────────────────────────────────────────────────────────────
function Sidebar({ active, onNavigate, open, onClose }) {
  return (
    <aside className={'sidebar' + (open ? ' open' : '')}>
      <div className="brand">
        <div className="brand-mark">F</div>
        <div>
          <div className="brand-name">FinPilot</div>
          <div className="brand-sub">NIFTY 50 · decision system</div>
        </div>
      </div>
      {NAV.map(sec => (
        <div className="nav-section" key={sec.label}>
          <div className="nav-label">{sec.label}</div>
          {sec.items.map(it => {
            const IconCmp = Icon[it.icon];
            return (
              <button key={it.name}
                      className={'nav-item ' + (active === it.name ? 'active' : '')}
                      onClick={() => { onNavigate(it.name); onClose?.(); }}>
                <IconCmp /> {it.name}
              </button>
            );
          })}
        </div>
      ))}
      <div className="side-foot">
        <div className="muted" style={{ fontSize: 11, padding: '0 10px', lineHeight: 1.5 }}>
          <span className="side-foot-label">Session</span>
          Paper broker · signal cycle 09:05 IST
        </div>
      </div>
    </aside>
  );
}

// ── Topbar: title, live status, refresh, mode toggle ───────────────────────
function Topbar({ view, online, lastUpdated, error, connection, onRefresh, uiMode, onToggleMode, onOpenMenu }) {
  return (
    <div className="topbar">
      <button className="hamburger" onClick={onOpenMenu}><Icon.Menu /></button>
      <div className="topbar-title">{view}</div>
      <div className="topbar-spacer" />
      <div className={'status-chip ' + (online ? 'online' : error ? 'offline' : '')}>
        <span className="dot" />
        {online && lastUpdated ? `${connection?.stream === 'connected' ? 'live' : 'snapshot'} · ${lastUpdated.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}`
          : error ? 'API offline' : 'connecting…'}
      </div>
      <button className="btn" title="Refresh data now"
              style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}
              onClick={onRefresh}>
        <Icon.Refresh /> Refresh
      </button>
      <div className="mode-toggle" role="group" aria-label="Choose interface style">
        <span className="mode-toggle-label">View</span>
        <button className={uiMode === 'friendly' ? 'active' : ''}
                aria-pressed={uiMode === 'friendly'}
                onClick={() => onToggleMode('friendly')}>
          <Icon.Sun /> Friendly
        </button>
        <button className={uiMode === 'terminal' ? 'active' : ''}
                aria-pressed={uiMode === 'terminal'}
                onClick={() => onToggleMode('terminal')}>
          <Icon.Terminal /> Terminal
        </button>
      </div>
    </div>
  );
}

// A compact market tape anchors Terminal mode and becomes a calm context
// summary in Friendly mode. It only reflects API data; no synthetic prices.
function MarketRibbon({ signals = [], online }) {
  const rows = signals.slice(0, 8);
  if (!rows.length) {
    return (
      <div className="market-ribbon is-empty" aria-label="Market data status">
        <span className="market-kicker">NSE</span>
        <span>{online ? 'Waiting for today’s signal snapshot' : 'Connect the API to load market context'}</span>
      </div>
    );
  }
  return (
    <div className="market-ribbon" aria-label="Latest tracked prices">
      <span className="market-kicker">NSE / LIVE</span>
      <div className="market-track">
        {rows.map(row => (
          <span className="market-quote" key={row.id || row.symbol}>
            <b>{stripNS(row.symbol)}</b>
            <span className="mono">₹{row.price}</span>
            <span className={(row.signal_type || '').toLowerCase()}>{row.signal_type}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Shared: signal type pill that opens the explainer ──────────────────────
function SignalPill({ signal, symbol }) {
  if (!signal) return null;
  const t = String(signal).toLowerCase();
  return (
    <button className={'fp-sig fp-' + t}
            title="Click for AI explanation"
            onClick={(e) => { e.stopPropagation(); window.openSignalExplainer?.(stripNS(symbol)); }}>
      {String(signal).toUpperCase()}
    </button>
  );
}

Object.assign(window, {
  Icon,
  Sidebar,
  Topbar: React.memo(Topbar),
  MarketRibbon: React.memo(MarketRibbon),
  Spark: React.memo(Spark),
  SignalPill: React.memo(SignalPill),
  NAV,
});
