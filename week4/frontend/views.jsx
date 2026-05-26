// views.jsx — secondary view screens routed by Sidebar nav

const { useState: vUseState, useMemo: vUseMemo } = React;

// ── Page header ───────────────────────────────────────────
function PageHead({ title, subtitle, right }) {
  return (
    <div className="page-head">
      <div style={{flex:1}}>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

// ── Markets view ──────────────────────────────────────────
function MarketsView({ stocks, onSelect }) {
  const market = useMarket();
  const [sort, setSort] = vUseState({ key: 'changePct', dir: -1 });
  const sorted = vUseMemo(() => {
    const s = [...stocks];
    s.sort((a, b) => (a[sort.key] - b[sort.key]) * sort.dir);
    return s;
  }, [stocks, sort]);

  const cols = [
    { k: 'sym', label: 'Symbol' },
    { k: 'price', label: 'Price', right: true },
    { k: 'changePct', label: '24h %', right: true },
    { k: 'change', label: '24h $', right: true },
    { k: 'high', label: 'High', right: true },
    { k: 'low', label: 'Low', right: true },
    { k: 'spark', label: 'Trend', right: false, nosort: true },
  ];

  function toggle(k) {
    setSort(s => s.key === k ? { key: k, dir: -s.dir } : { key: k, dir: -1 });
  }

  return (
    <div className="view-enter">
      <PageHead title="Markets" subtitle={`${stocks.length} instruments · live`}
        right={
          <div className="seg">
            <button className="active">All</button>
            <button>Equities</button>
            <button>Crypto</button>
            <button>FX</button>
          </div>
        }
      />
      <div className="card tight">
        <table className="markets-table">
          <thead>
            <tr>
              {cols.map(c => (
                <th key={c.k} style={{textAlign: c.right ? 'right' : 'left'}}
                    onClick={() => !c.nosort && toggle(c.k)}>
                  {c.label}
                  {sort.key === c.k && !c.nosort && (
                    <span className="sort-ind">{sort.dir < 0 ? '↓' : '↑'}</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map(s => (
              <tr key={s.sym} onClick={() => onSelect(s.sym)}>
                <td>
                  <div style={{display:'flex',alignItems:'center',gap:10}}>
                    <div className="watch-icon" style={{background:s.color+'22',color:s.color}}>{s.sym.slice(0,2)}</div>
                    <div>
                      <div style={{fontWeight:600}}>{s.sym}</div>
                      <div style={{fontSize:11, color:'var(--text-3)'}}>{s.name}</div>
                    </div>
                  </div>
                </td>
                <td style={{textAlign:'right'}}>{market.currency}{formatNum(s.price, market.code, s.price < 10 ? 3 : 2)}</td>
                <td style={{textAlign:'right', color: s.changePct >= 0 ? 'var(--green)' : 'var(--red)'}}>
                  {s.changePct >= 0 ? '+' : ''}{s.changePct.toFixed(2)}%
                </td>
                <td style={{textAlign:'right', color: s.change >= 0 ? 'var(--green)' : 'var(--red)'}}>
                  {s.change >= 0 ? '+' : ''}{s.change.toFixed(2)}
                </td>
                <td style={{textAlign:'right', color:'var(--text-2)'}}>{formatNum(s.high, market.code)}</td>
                <td style={{textAlign:'right', color:'var(--text-2)'}}>{formatNum(s.low, market.code)}</td>
                <td><Sparkline data={s.spark} color={s.changePct >= 0 ? 'var(--green)' : 'var(--red)'} width={90} height={28} fill /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Watchlist view (full page) ────────────────────────────
function WatchlistView({ stocks, onSelect, onAdd, onRemove, available }) {
  const market = useMarket();
  return (
    <div className="view-enter">
      <PageHead title="Watchlist" subtitle={`${stocks.length} symbols tracked`}
        right={
          <div className="seg">
            <button className="active">Default</button>
            <button>Tech</button>
            <button>Crypto</button>
          </div>
        }
      />
      <div style={{display:'grid', gridTemplateColumns:'repeat(auto-fill, minmax(260px, 1fr))', gap:14}}>
        {stocks.map(s => (
          <div key={s.sym} className="card" style={{cursor:'pointer'}} onClick={() => onSelect(s.sym)}>
            <div style={{display:'flex', alignItems:'center', gap:10, marginBottom:12}}>
              <div className="watch-icon" style={{width:34,height:34,background:s.color+'22',color:s.color, fontSize:13}}>{s.sym.slice(0,2)}</div>
              <div style={{flex:1, minWidth:0}}>
                <div style={{fontWeight:600}}>{s.sym}</div>
                <div style={{fontSize:11, color:'var(--text-3)', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis'}}>{s.name}</div>
              </div>
              <button className="icon-btn" style={{width:24,height:24}} onClick={(e) => { e.stopPropagation(); onRemove(s.sym); }}>
                <Icon.Close s={10}/>
              </button>
            </div>
            <div style={{fontSize:22, fontWeight:600, letterSpacing:'-0.02em', fontVariantNumeric:'tabular-nums'}}>
              {market.currency}{formatNum(s.price, market.code, s.price < 10 ? 3 : 2)}
            </div>
            <div style={{fontSize:12, color: s.changePct >= 0 ? 'var(--green)' : 'var(--red)', marginTop:2, marginBottom:10}}>
              {s.changePct >= 0 ? '+' : ''}{s.changePct.toFixed(2)}% · {s.change >= 0 ? '+' : ''}{market.currency}{Math.abs(s.change).toFixed(2)}
            </div>
            <Sparkline data={s.spark} color={s.changePct >= 0 ? 'var(--green)' : 'var(--red)'} width={230} height={48} fill />
          </div>
        ))}
        <AddSymbolCard available={available} stocks={stocks} onAdd={onAdd} />
      </div>
    </div>
  );
}

function AddSymbolCard({ available, stocks, onAdd }) {
  const [open, setOpen] = vUseState(false);
  const [q, setQ] = vUseState('');
  const filtered = available
    .filter(a => !stocks.find(s => s.sym === a.sym))
    .filter(a => !q || a.sym.toLowerCase().includes(q.toLowerCase()) || a.name.toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="card" style={{display:'flex', flexDirection:'column', justifyContent:'center', alignItems:'center', border:'1px dashed var(--line-strong)', minHeight:178}}>
      {!open ? (
        <button className="watch-add" style={{flexDirection:'column', textAlign:'center', justifyContent:'center', alignItems:'center', padding:24, border:0, background:'transparent'}}
                onClick={() => setOpen(true)}>
          <span className="watch-add-icon" style={{width:36,height:36}}><Icon.Plus s={18}/></span>
          <span>Add to watchlist</span>
        </button>
      ) : (
        <div style={{width:'100%'}}>
          <div className="add-search">
            <Icon.Search/>
            <input autoFocus placeholder="Ticker or company" value={q} onChange={e => setQ(e.target.value)} />
            <button className="icon-btn" style={{width:24,height:24}} onClick={() => setOpen(false)}><Icon.Close s={10}/></button>
          </div>
          <div style={{maxHeight:120, overflowY:'auto'}}>
            {filtered.slice(0, 6).map(a => (
              <div key={a.sym} className="add-row" onClick={() => { onAdd(a.sym); setOpen(false); setQ(''); }}>
                <div className="watch-icon" style={{background:(a.color||'#888')+'22', color:a.color||'#aaa'}}>{a.sym.slice(0,2)}</div>
                <div className="grow"><div className="watch-symbol">{a.sym}</div><div className="watch-name">{a.name}</div></div>
                <Icon.Plus s={14}/>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Portfolio view ────────────────────────────────────────
function PortfolioView({ stocks, realPositions = null }) {
  const market = useMarket();
  // If FinPilot has live open positions, derive the donut from those. Match
  // each position to a stock for the brand color (fallback to a neutral hue).
  const usingReal = realPositions
    && Array.isArray(realPositions.open_positions)
    && realPositions.open_positions.length > 0;

  let positions;
  if (usingReal) {
    positions = realPositions.open_positions.slice(0, 8).map(p => {
      const bare = (p.symbol || '').replace(/\.(NS|BO|NSE|BSE)$/i, '');
      const stock = stocks.find(s => s.sym === bare);
      const last = stock ? stock.price : Number(p.avg_entry_price);
      return {
        sym: bare,
        color: stock?.color || '#5fa0ff',
        value: Number(p.quantity) * last,
      };
    });
  } else {
    const lotMult = market.code === 'IN' ? 80 : 12;
    positions = stocks.slice(0, 8).map((s, i) => ({
      sym: s.sym, color: s.color,
      value: s.price * (lotMult + s.sym.charCodeAt(0) % 8),
    }));
  }
  const total = positions.reduce((a, p) => a + p.value, 0);
  const sorted = [...positions].sort((a,b) => b.value - a.value);

  // Donut
  const R = 64, sw = 14;
  const C = 2 * Math.PI * R;
  let acc = 0;
  const segs = sorted.map(p => {
    const frac = p.value / total;
    const dash = frac * C;
    const seg = { ...p, dash, offset: -acc, frac };
    acc += dash;
    return seg;
  });

  return (
    <div className="view-enter">
      <PageHead title="Portfolio" subtitle="Allocation & performance"
        right={<button className="btn-secondary">Export CSV</button>}
      />
      <KpiRow stocks={stocks} />
      <div style={{height:16}}/>
      <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:16}}>
        <div className="card">
          <div className="card-head"><div className="card-title">Allocation</div></div>
          <div className="donut-wrap">
            <svg width="170" height="170" viewBox="-85 -85 170 170" style={{transform:'rotate(-90deg)'}}>
              <circle r={R} fill="none" stroke="var(--card-2)" strokeWidth={sw}/>
              {segs.map((s, i) => (
                <circle key={i} r={R} fill="none" stroke={s.color}
                        strokeWidth={sw}
                        strokeDasharray={`${s.dash} ${C - s.dash}`}
                        strokeDashoffset={s.offset}
                        style={{transition:'stroke-dasharray 0.6s ease'}} />
              ))}
              <g style={{transform:'rotate(90deg)'}}>
                <text textAnchor="middle" y={-4} fontSize="20" fontWeight="600" fill="var(--text)" fontFamily="Geist">{formatCompact(total, market.code)}</text>
                <text textAnchor="middle" y={14} fontSize="10" fill="var(--text-3)" letterSpacing="0.06em">TOTAL VALUE</text>
              </g>
            </svg>
            <div className="alloc-legend">
              {segs.slice(0, 6).map(s => (
                <div className="alloc-row" key={s.sym}>
                  <span className="swatch" style={{background:s.color}}></span>
                  <span className="sym">{s.sym}</span>
                  <span className="pct">{(s.frac * 100).toFixed(1)}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="card">
          <div className="card-head">
            <div className="card-title">Performance · 30 days</div>
            <div className="card-spacer"/>
            <span className="pill up"><Icon.ArrowUp/>12.4%</span>
          </div>
          {(() => {
            // Synthetic 30-day equity curve
            const n = 30;
            let v = total * 0.88;
            const pts = [];
            for (let i = 0; i < n; i++) {
              v += (total - v) * 0.06 + (Math.sin(i*0.7) + Math.cos(i*0.3)) * total * 0.005;
              pts.push(v);
            }
            pts[n-1] = total;
            return <Sparkline data={pts} color="var(--green)" width={420} height={170} fill />;
          })()}
        </div>
      </div>
      <div style={{height:16}}/>
      <Positions stocks={stocks} title="Holdings" limit={20} realPositions={realPositions} />
    </div>
  );
}

// ── Trades view ───────────────────────────────────────────
function TradesView({ stocks, realOrders = [] }) {
  const market = useMarket();
  const hasReal = Array.isArray(realOrders) && realOrders.length > 0;

  // Build the trade history from FinPilot's /api/portfolio/orders/ when it
  // has data, otherwise fall back to the deterministic synthetic feed so the
  // UI is never empty when the user is just browsing the prototype.
  const trades = vUseMemo(() => {
    if (hasReal) {
      return realOrders.map((o, i) => {
        const bare = (o.symbol || '').replace(/\.(NS|BO|NSE|BSE)$/i, '');
        const stock = stocks.find(s => s.sym === bare);
        const qty = Number(o.quantity ?? 0);
        const price = Number(o.price ?? 0);
        const statusMap = {
          COMPLETE: 'Filled', PENDING: 'Pending',
          REJECTED: 'Rejected', CANCELLED: 'Cancelled',
        };
        return {
          id: `FP-${o.id}`,
          sym: bare,
          name: stock?.name || bare,
          color: stock?.color || '#5fa0ff',
          side: (o.side || 'BUY').toUpperCase(),
          qty, price, total: qty * price,
          time: new Date(o.created_at).toLocaleString(undefined, {
            month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
          }),
          status: statusMap[o.status] || o.status,
          mode: o.is_paper ? 'paper' : 'LIVE',
        };
      });
    }
    // Synthetic fallback (unchanged from the original prototype).
    const out = [];
    const now = Date.now();
    for (let i = 0; i < 24; i++) {
      const s = stocks[(i * 3 + 1) % stocks.length];
      if (!s) continue;
      const dir = (i * 7) % 5 < 2 ? 'SELL' : 'BUY';
      const qty = 3 + (i * 11) % 24;
      const px = s.open * (0.95 + ((i * 13) % 100) / 1000);
      out.push({
        id: 'TR-' + (10248 - i),
        sym: s.sym, name: s.name, color: s.color,
        side: dir, qty, price: px, total: qty * px,
        time: new Date(now - i * 3600000 * (1 + (i%5))).toLocaleString(undefined, { month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' }),
        status: i === 0 ? 'Filled' : i < 3 ? 'Filled' : i === 5 ? 'Partial' : 'Filled',
      });
    }
    return out;
  }, [stocks.length, hasReal, realOrders]);

  return (
    <div className="view-enter">
      <PageHead title="Trades"
        subtitle={hasReal
          ? `${trades.length} order(s) from FinPilot · live`
          : 'Order history · last 90 days'}
        right={
          <div className="row gap-8">
            {hasReal && (
              <span className="pill" title="Live from FinPilot /api/portfolio/orders/">
                <span style={{width:6,height:6,background:'var(--violet)',borderRadius:'50%'}}/>FinPilot
              </span>
            )}
            <div className="seg">
              <button className="active">All</button>
              <button>Buys</button>
              <button>Sells</button>
              <button>Pending</button>
            </div>
            <button className="btn-primary">+ New order</button>
          </div>
        }
      />
      <div className="card tight">
        <table className="markets-table">
          <thead>
            <tr>
              <th>Order</th><th>Symbol</th><th>Side</th>
              <th style={{textAlign:'right'}}>Qty</th>
              <th style={{textAlign:'right'}}>Price</th>
              <th style={{textAlign:'right'}}>Total</th>
              <th>Status</th><th>Time</th>
            </tr>
          </thead>
          <tbody>
            {trades.map(t => (
              <tr key={t.id}>
                <td className="mono" style={{color:'var(--text-2)'}}>{t.id}</td>
                <td>
                  <div style={{display:'flex',alignItems:'center',gap:10}}>
                    <div className="watch-icon" style={{width:24,height:24,background:t.color+'22',color:t.color}}>{t.sym.slice(0,2)}</div>
                    <span style={{fontWeight:600}}>{t.sym}</span>
                  </div>
                </td>
                <td><span className={'tag ' + (t.side === 'BUY' ? 'buy' : 'sell')}>{t.side}</span></td>
                <td style={{textAlign:'right'}}>{t.qty}</td>
                <td style={{textAlign:'right'}}>{market.currency}{formatNum(t.price, market.code)}</td>
                <td style={{textAlign:'right'}}>{formatCompact(t.total, market.code)}</td>
                <td>
                  {(() => {
                    // Colour the status pill by outcome — green = filled,
                    // amber = pending/partial, red = rejected/cancelled.
                    const ok = t.status === 'Filled';
                    const bad = t.status === 'Rejected' || t.status === 'Cancelled';
                    const bg = ok ? 'var(--green-dim)'
                             : bad ? 'rgba(255,85,119,0.12)'
                             : 'rgba(246,185,75,0.12)';
                    const fg = ok ? 'var(--green)'
                             : bad ? 'var(--red)'
                             : 'var(--amber)';
                    return <span className="pill" style={{background: bg, color: fg, border: 0}}>{t.status}</span>;
                  })()}
                  {t.mode && (
                    <span className="muted" style={{fontSize:11, marginLeft:6, textTransform:'lowercase'}}>{t.mode}</span>
                  )}
                </td>
                <td style={{color:'var(--text-2)'}}>{t.time}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── News view ─────────────────────────────────────────────
function NewsView({ stocks }) {
  const sources = ['Bloomberg', 'Reuters', 'WSJ', 'CoinDesk', 'FT'];
  const headlines = [
    'beats Q2 earnings expectations; raises full-year guidance on AI demand',
    'announces share buyback program of $10B over 18 months',
    'gains analyst upgrade to overweight on margin expansion story',
    'volume spike detected as institutional inflows climb',
    'CEO comments on capital allocation strategy at investor day',
    'reports record quarter despite macro headwinds',
    'partners with major retailer on AI infrastructure deal',
  ];
  const items = vUseMemo(() => stocks.slice(0, 10).flatMap((s, i) => [{
    sym: s.sym, color: s.color, name: s.name,
    src: sources[(i * 3) % sources.length],
    time: `${(i * 7 + 4) % 60}m`,
    head: `${s.sym} ${headlines[(i*5) % headlines.length]}`,
  }]), [stocks.length]);

  return (
    <div className="view-enter">
      <PageHead title="News & Insights" subtitle="Filtered to your watchlist"
        right={
          <div className="seg">
            <button className="active">All</button>
            <button>Earnings</button>
            <button>Macro</button>
            <button>Crypto</button>
          </div>
        }
      />
      <div style={{display:'grid', gridTemplateColumns:'repeat(auto-fill, minmax(360px, 1fr))', gap:14}}>
        {items.map((n, i) => (
          <div key={i} className="card">
            <div style={{height:120, borderRadius:10, marginBottom:14, background:`linear-gradient(135deg, ${n.color}22, var(--card-2))`, border:'1px solid var(--line)', position:'relative', overflow:'hidden'}}>
              <div style={{position:'absolute', inset:0, display:'grid', placeItems:'center', fontFamily:'Geist Mono', fontSize:11, color:'var(--text-3)'}}>IMG · {n.sym} headline</div>
            </div>
            <div style={{fontSize:11, color:'var(--text-3)', textTransform:'uppercase', letterSpacing:'0.06em', marginBottom:6}}>
              {n.src} · {n.time} ago
            </div>
            <div style={{fontSize:15, fontWeight:500, lineHeight:1.35, textWrap:'pretty', marginBottom:10}}>{n.head}.</div>
            <div className="row gap-8">
              <div className="watch-icon" style={{width:22,height:22,background:n.color+'22',color:n.color, fontSize:10}}>{n.sym.slice(0,2)}</div>
              <span className="muted" style={{fontSize:12}}>{n.name}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Alerts view ───────────────────────────────────────────
function AlertsView() {
  const [alerts, setAlerts] = vUseState([
    { id:1, sym:'NVDA', name:'Nvidia Corp.', color:'#76e84c', rule:'Price crosses above $1,150', triggered:'2 minutes ago', on:true },
    { id:2, sym:'TSLA', name:'Tesla Inc.', color:'#ff5577', rule:'Down more than 3% in 1h', triggered:'14 minutes ago', on:true },
    { id:3, sym:'BTC',  name:'Bitcoin', color:'#f6b94b', rule:'Volume spike > 2× average', triggered:'38 minutes ago', on:true },
    { id:4, sym:'AAPL', name:'Apple Inc.', color:'#a5a5a5', rule:'Crosses below 50-day MA', triggered:'—', on:false },
    { id:5, sym:'COIN', name:'Coinbase', color:'#5b8def', rule:'Rallies > 5% in a day', triggered:'—', on:true },
    { id:6, sym:'META', name:'Meta Platforms', color:'#5fa0ff', rule:'Crosses above resistance at $530', triggered:'—', on:true },
  ]);
  function toggle(id) { setAlerts(prev => prev.map(a => a.id === id ? {...a, on:!a.on} : a)); }
  function remove(id) { setAlerts(prev => prev.filter(a => a.id !== id)); }

  return (
    <div className="view-enter">
      <PageHead title="Alerts" subtitle={`${alerts.filter(a=>a.on).length} active rules`}
        right={<button className="btn-primary">+ Create alert</button>}
      />
      <div className="card">
        {alerts.map(a => (
          <div className="alert-row" key={a.id}>
            <div className="watch-icon" style={{background:a.color+'22', color:a.color}}>{a.sym.slice(0,2)}</div>
            <div>
              <div style={{fontWeight:600, marginBottom:2}}>{a.sym} <span className="muted" style={{fontWeight:400, marginLeft:6, fontSize:12}}>{a.name}</span></div>
              <div style={{fontSize:12, color:'var(--text-2)'}}>{a.rule}</div>
              <div style={{fontSize:11, color:'var(--text-3)', marginTop:4}}>Last triggered: {a.triggered}</div>
            </div>
            <button className={'toggle ' + (a.on ? 'on' : '')} onClick={() => toggle(a.id)} aria-label="toggle"></button>
            <button className="icon-btn" onClick={() => remove(a.id)}><Icon.Close/></button>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Settings view ─────────────────────────────────────────
function SettingsView() {
  const [tab, setTab] = vUseState('Account');
  const tabs = ['Account', 'Trading', 'Notifications', 'API keys', 'Billing'];
  return (
    <div className="view-enter">
      <PageHead title="Settings" subtitle="Preferences & integrations" />
      <div className="card">
        <div className="settings-grid">
          <div className="settings-nav">
            {tabs.map(t => (
              <button key={t} className={tab===t?'active':''} onClick={() => setTab(t)}>{t}</button>
            ))}
          </div>
          <div>
            {tab === 'Account' && (
              <>
                <div className="field"><label>Display name</label><input defaultValue="Alex Rivera"/></div>
                <div className="field"><label>Email</label><input defaultValue="alex@cardinal.app"/></div>
                <div className="field"><label>Default currency</label>
                  <select defaultValue="USD"><option>USD</option><option>EUR</option><option>GBP</option><option>JPY</option></select>
                </div>
                <div className="field"><label>Time zone</label>
                  <select><option>America/New York (UTC-5)</option><option>Europe/London (UTC+0)</option></select>
                </div>
                <div className="row gap-8" style={{marginTop:8}}>
                  <button className="btn-primary">Save changes</button>
                  <button className="btn-secondary">Cancel</button>
                </div>
              </>
            )}
            {tab === 'Trading' && (
              <>
                <div className="field"><label>Default order type</label>
                  <select><option>Limit</option><option>Market</option><option>Stop</option></select>
                </div>
                <div className="field"><label>Default order size</label><input defaultValue="100" /></div>
                <div className="field"><label>Confirm orders above</label><input defaultValue="$10,000" /></div>
                <button className="btn-primary" style={{marginTop:8}}>Save changes</button>
              </>
            )}
            {tab === 'Notifications' && (
              <>
                <div className="alert-row" style={{gridTemplateColumns:'1fr auto'}}>
                  <div><div style={{fontWeight:500}}>Email alerts</div><div style={{fontSize:12, color:'var(--text-2)'}}>Daily summary + price triggers</div></div>
                  <div className="toggle on"/>
                </div>
                <div className="alert-row" style={{gridTemplateColumns:'1fr auto'}}>
                  <div><div style={{fontWeight:500}}>Push notifications</div><div style={{fontSize:12, color:'var(--text-2)'}}>Real-time triggers via app</div></div>
                  <div className="toggle on"/>
                </div>
                <div className="alert-row" style={{gridTemplateColumns:'1fr auto'}}>
                  <div><div style={{fontWeight:500}}>SMS alerts</div><div style={{fontSize:12, color:'var(--text-2)'}}>Critical alerts only</div></div>
                  <div className="toggle"/>
                </div>
              </>
            )}
            {tab === 'API keys' && (
              <>
                <div className="field"><label>Live trading key</label><input defaultValue="sk_live_•••••••••••••••a3f2" readOnly/></div>
                <div className="field"><label>Sandbox key</label><input defaultValue="sk_test_•••••••••••••••8b14" readOnly/></div>
                <div className="row gap-8"><button className="btn-primary">Generate new key</button><button className="btn-secondary">Revoke</button></div>
              </>
            )}
            {tab === 'Billing' && (
              <>
                <div className="field"><label>Current plan</label><div style={{padding:'9px 12px', background:'var(--card-2)', border:'1px solid var(--line)', borderRadius:8}}>Pro · <span className="muted">$29/month</span></div></div>
                <div className="field"><label>Next billing date</label><div style={{padding:'9px 12px', color:'var(--text-2)'}}>June 15, 2026</div></div>
                <button className="btn-secondary">Manage billing</button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, {
  MarketsView, WatchlistView, PortfolioView, TradesView,
  NewsView, AlertsView, SettingsView, PageHead, AddSymbolCard,
});
