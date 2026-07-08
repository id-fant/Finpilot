// news_panel.jsx — real market news (Yahoo Finance + Zerodha Pulse).
//
// Backed by /api/signals/news/ (week3's llm.news.news_items). No made-up
// headlines: "Market" shows the broad Pulse feed, a stock shows its Yahoo
// items + Pulse mentions. Server-cached 15 min, so switching scopes is snappy
// after the first fetch.
//
// Exported on window: NewsView

const { useState: nUseState, useEffect: nUseEffect } = React;

function NewsView() {
  const [stocks, setStocks] = nUseState([]);
  const [scope, setScope] = nUseState('market');   // 'market' | 'RELIANCE.NS' | …
  const [items, setItems] = nUseState(null);
  const [error, setError] = nUseState(null);
  const [loading, setLoading] = nUseState(false);

  // Scope options come from the real tracked universe.
  nUseEffect(() => {
    fetch(`${window.FINPILOT_API}/signals/stocks/`)
      .then(r => r.json())
      .then(d => setStocks((Array.isArray(d) ? d : (d.results || [])).map(s => s.symbol)))
      .catch(() => {});
  }, []);

  nUseEffect(() => {
    let cancelled = false;
    setLoading(true); setError(null); setItems(null);
    const q = scope === 'market' ? '' : `?symbol=${encodeURIComponent(scope)}`;
    fetch(`${window.FINPILOT_API}/signals/news/${q}`)
      .then(async r => {
        const body = await r.json().catch(() => null);
        if (!r.ok) throw new Error((body && body.error) || `HTTP ${r.status}`);
        return body;
      })
      .then(d => { if (!cancelled) { setItems(d.items || []); setLoading(false); } })
      .catch(e => { if (!cancelled) { setError(e.message); setLoading(false); } });
    return () => { cancelled = true; };
  }, [scope]);

  const sourceTone = (src) => src === 'Yahoo Finance' ? 'var(--violet)' : 'var(--accent)';

  return (
    <div className="view-enter">
      <PageHead title="News"
                subtitle="Live headlines from Yahoo Finance and Zerodha Pulse — no synthetic feeds." />

      <div className="card">
        <div className="row gap-8" style={{ flexWrap: 'wrap', marginBottom: 4 }}>
          <button className={'chip ' + (scope === 'market' ? 'chip-active' : '')}
                  onClick={() => setScope('market')}>Market</button>
          {stocks.map(s => (
            <button key={s} className={'chip ' + (scope === s ? 'chip-active' : '')}
                    onClick={() => setScope(s)}>{stripNS(s)}</button>
          ))}
        </div>
      </div>

      <div className="card">
        {loading && <div className="muted">loading headlines…</div>}
        {error && (
          <div className="muted" style={{ color: 'var(--red)' }}>
            error: {error}
            {/fetch|network/i.test(error) ? `. Is the Django API running on ${window.FINPILOT_API}?` : ''}
          </div>
        )}
        {items && items.length === 0 && !loading && (
          <div className="muted" style={{ fontSize: 13 }}>
            No headlines right now for {scope === 'market' ? 'the market feed' : stripNS(scope)}.
            News is best-effort — Yahoo/Pulse may be rate-limiting; try another scope
            or refresh in a minute.
          </div>
        )}
        {items && items.map((it, i) => {
          const Wrapper = it.link ? 'a' : 'div';
          const props = it.link ? { href: it.link, target: '_blank', rel: 'noopener noreferrer' } : {};
          return (
            <Wrapper key={i} {...props}
                     style={{ display: 'block', padding: '13px 0',
                              borderTop: i ? '1px solid var(--line)' : 0,
                              textDecoration: 'none', color: 'inherit', cursor: it.link ? 'pointer' : 'default' }}>
              <div style={{ fontSize: 14, fontWeight: 500, lineHeight: 1.4, textWrap: 'pretty' }}>
                {it.title}
              </div>
              <div className="row gap-8" style={{ marginTop: 6 }}>
                <span className="mono" style={{ fontSize: 11, color: sourceTone(it.source) }}>
                  {it.source}
                </span>
                {it.link && <span className="muted" style={{ fontSize: 11 }}>· open ↗</span>}
              </div>
            </Wrapper>
          );
        })}
      </div>
    </div>
  );
}

Object.assign(window, { NewsView });
