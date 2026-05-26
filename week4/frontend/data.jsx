// data.jsx — mock market data + live tick simulation
//   Supports two markets: 'IN' (NSE/BSE, ₹) and 'GLOBAL' (NASDAQ/NYSE/crypto, $)

// ── GLOBAL (US + crypto) ─────────────────────────────────────────────
const GLOBAL_SEED = [
  { sym: 'NVDA', name: 'Nvidia Corp.',     price: 1142.85, color: '#76e84c', exchange: 'NASDAQ' },
  { sym: 'AAPL', name: 'Apple Inc.',       price: 218.47,  color: '#a5a5a5', exchange: 'NASDAQ' },
  { sym: 'TSLA', name: 'Tesla Inc.',       price: 264.12,  color: '#ff5577', exchange: 'NASDAQ' },
  { sym: 'MSFT', name: 'Microsoft Corp.',  price: 467.30,  color: '#5dbcff', exchange: 'NASDAQ' },
  { sym: 'GOOG', name: 'Alphabet Inc.',    price: 178.92,  color: '#f6b94b', exchange: 'NASDAQ' },
  { sym: 'AMZN', name: 'Amazon.com',       price: 195.64,  color: '#ffb74a', exchange: 'NASDAQ' },
  { sym: 'META', name: 'Meta Platforms',   price: 528.10,  color: '#5fa0ff', exchange: 'NASDAQ' },
  { sym: 'AMD',  name: 'AMD',              price: 162.74,  color: '#ff7c4a', exchange: 'NASDAQ' },
  { sym: 'NFLX', name: 'Netflix Inc.',     price: 712.30,  color: '#e2444a', exchange: 'NASDAQ' },
  { sym: 'COIN', name: 'Coinbase',         price: 248.16,  color: '#5b8def', exchange: 'NASDAQ' },
  { sym: 'BTC',  name: 'Bitcoin',          price: 71430.0, color: '#f6b94b', exchange: 'CRYPTO' },
  { sym: 'ETH',  name: 'Ethereum',         price: 3852.7,  color: '#a78bfa', exchange: 'CRYPTO' },
];

const GLOBAL_EXTRA = [
  { sym: 'CRM',  name: 'Salesforce',       price: 274.50,  color: '#5fa0ff', exchange: 'NYSE' },
  { sym: 'INTC', name: 'Intel Corp.',      price: 24.18,   color: '#5dbcff', exchange: 'NASDAQ' },
  { sym: 'BABA', name: 'Alibaba Group',    price: 88.42,   color: '#ff7c4a', exchange: 'NYSE' },
  { sym: 'UBER', name: 'Uber Technologies',price: 72.10,   color: '#a5a5a5', exchange: 'NYSE' },
  { sym: 'PYPL', name: 'PayPal Holdings',  price: 67.83,   color: '#5fa0ff', exchange: 'NASDAQ' },
  { sym: 'SHOP', name: 'Shopify Inc.',     price: 78.95,   color: '#76e84c', exchange: 'NYSE' },
  { sym: 'SQ',   name: 'Block Inc.',       price: 71.20,   color: '#a78bfa', exchange: 'NYSE' },
  { sym: 'DIS',  name: 'Walt Disney Co.',  price: 102.34,  color: '#5b8def', exchange: 'NYSE' },
];

// ── INDIA (NSE) ──────────────────────────────────────────────────────
// Prices reflect approximate 2025 NSE levels for Nifty-heavy names.
const IN_SEED = [
  { sym: 'RELIANCE',   name: 'Reliance Industries', price: 2945.30,  color: '#5fa0ff', exchange: 'NSE' },
  { sym: 'TCS',        name: 'Tata Consultancy',    price: 3892.50,  color: '#5dbcff', exchange: 'NSE' },
  { sym: 'HDFCBANK',   name: 'HDFC Bank',           price: 1689.20,  color: '#76e84c', exchange: 'NSE' },
  { sym: 'INFY',       name: 'Infosys',             price: 1856.40,  color: '#5dbcff', exchange: 'NSE' },
  { sym: 'ICICIBANK',  name: 'ICICI Bank',          price: 1204.85,  color: '#ff7c4a', exchange: 'NSE' },
  { sym: 'BHARTIARTL', name: 'Bharti Airtel',       price: 1584.60,  color: '#e2444a', exchange: 'NSE' },
  { sym: 'ITC',        name: 'ITC Limited',         price: 458.30,   color: '#f6b94b', exchange: 'NSE' },
  { sym: 'SBIN',       name: 'State Bank of India', price: 819.45,   color: '#5b8def', exchange: 'NSE' },
  { sym: 'LT',         name: 'Larsen & Toubro',     price: 3648.90,  color: '#a5a5a5', exchange: 'NSE' },
  { sym: 'BAJFINANCE', name: 'Bajaj Finance',       price: 7184.20,  color: '#76e84c', exchange: 'NSE' },
  { sym: 'NIFTY50',    name: 'Nifty 50 Index',      price: 24812.65, color: '#a78bfa', exchange: 'NSE-IDX' },
  { sym: 'SENSEX',     name: 'BSE Sensex',          price: 81392.40, color: '#ffb74a', exchange: 'BSE-IDX' },
];

const IN_EXTRA = [
  { sym: 'HINDUNILVR', name: 'Hindustan Unilever',  price: 2451.30,  color: '#5dbcff', exchange: 'NSE' },
  { sym: 'KOTAKBANK',  name: 'Kotak Mahindra Bank', price: 1748.10,  color: '#5fa0ff', exchange: 'NSE' },
  { sym: 'AXISBANK',   name: 'Axis Bank',           price: 1182.50,  color: '#ff5577', exchange: 'NSE' },
  { sym: 'MARUTI',     name: 'Maruti Suzuki',       price: 12815.30, color: '#76e84c', exchange: 'NSE' },
  { sym: 'ASIANPAINT', name: 'Asian Paints',        price: 2814.40,  color: '#a78bfa', exchange: 'NSE' },
  { sym: 'TITAN',      name: 'Titan Company',       price: 3398.65,  color: '#f6b94b', exchange: 'NSE' },
  { sym: 'TATAMOTORS', name: 'Tata Motors',         price: 982.70,   color: '#5dbcff', exchange: 'NSE' },
  { sym: 'ADANIENT',   name: 'Adani Enterprises',   price: 2786.50,  color: '#ff7c4a', exchange: 'NSE' },
  { sym: 'WIPRO',      name: 'Wipro',               price: 562.80,   color: '#a5a5a5', exchange: 'NSE' },
  { sym: 'HCLTECH',    name: 'HCL Technologies',    price: 1721.40,  color: '#5fa0ff', exchange: 'NSE' },
  { sym: 'SUNPHARMA',  name: 'Sun Pharmaceutical',  price: 1815.20,  color: '#76e84c', exchange: 'NSE' },
  { sym: 'NIFTYBANK',  name: 'Nifty Bank Index',    price: 52384.10, color: '#a78bfa', exchange: 'NSE-IDX' },
];

// ── Currency formatting ─────────────────────────────────────────────
// Indian numbering: 12,34,567.89 — last 3 digits then groups of 2
function formatINR(n, opts = {}) {
  const { showSign = false, decimals = 2 } = opts;
  const neg = n < 0;
  const abs = Math.abs(n);
  const [intPart, decPart = ''] = abs.toFixed(decimals).split('.');
  const last3 = intPart.slice(-3);
  const rest = intPart.slice(0, -3);
  const formatted = rest
    ? rest.replace(/\B(?=(\d{2})+(?!\d))/g, ',') + ',' + last3
    : last3;
  const sign = neg ? '−' : showSign ? '+' : '';
  return sign + '₹' + formatted + (decimals > 0 ? '.' + decPart : '');
}

function formatUSD(n, opts = {}) {
  const { showSign = false, decimals = 2 } = opts;
  const neg = n < 0;
  const abs = Math.abs(n);
  const sign = neg ? '−' : showSign ? '+' : '';
  return sign + '$' + abs.toLocaleString(undefined, {
    minimumFractionDigits: decimals, maximumFractionDigits: decimals
  });
}

// Compact: ₹3.42 Cr / ₹15.4 L / $1.2M / $4.8K  (with Indian grouping for big crores)
function formatCompact(n, market) {
  const abs = Math.abs(n);
  const sign = n < 0 ? '−' : '';
  if (market === 'IN') {
    if (abs >= 1e7) return sign + '₹' + formatNum(abs / 1e7, 'IN', 2) + ' Cr';
    if (abs >= 1e5) return sign + '₹' + (abs / 1e5).toFixed(2) + ' L';
    return sign + formatINR(abs, { decimals: 0 });
  } else {
    if (abs >= 1e9) return sign + '$' + (abs / 1e9).toFixed(2) + 'B';
    if (abs >= 1e6) return sign + '$' + (abs / 1e6).toFixed(2) + 'M';
    if (abs >= 1e3) return sign + '$' + (abs / 1e3).toFixed(1) + 'K';
    return sign + '$' + abs.toFixed(0);
  }
}

// Plain number (no currency) with locale-appropriate digit grouping
function formatNum(n, market, decimals = 2) {
  if (market === 'IN') {
    const abs = Math.abs(n);
    const [intPart, decPart = ''] = abs.toFixed(decimals).split('.');
    const last3 = intPart.slice(-3);
    const rest = intPart.slice(0, -3);
    const out = rest ? rest.replace(/\B(?=(\d{2})+(?!\d))/g, ',') + ',' + last3 : last3;
    return (n < 0 ? '−' : '') + out + (decimals > 0 ? '.' + decPart : '');
  }
  return n.toLocaleString(undefined, {
    minimumFractionDigits: decimals, maximumFractionDigits: decimals
  });
}

// ── Market registry ─────────────────────────────────────────────────
const MARKETS = {
  IN: {
    code: 'IN',
    label: 'India',
    flag: '🇮🇳',
    currency: '₹',
    currencyCode: 'INR',
    exchange: 'NSE',
    primaryIndex: 'NIFTY50',
    indexLabel: 'NIFTY 50',
    hours: 'NSE closes at 3:30 PM IST',
    seed: IN_SEED,
    catalog: [...IN_SEED, ...IN_EXTRA],
    fmt: formatINR,
  },
  GLOBAL: {
    code: 'GLOBAL',
    label: 'Global',
    flag: '🌐',
    currency: '$',
    currencyCode: 'USD',
    exchange: 'NASDAQ',
    primaryIndex: 'NVDA',
    indexLabel: 'S&P 500',
    hours: 'NYSE closes in 2h 14m',
    seed: GLOBAL_SEED,
    catalog: [...GLOBAL_SEED, ...GLOBAL_EXTRA],
    fmt: formatUSD,
  },
};

// ── Seeded PRNG + candle generator ──────────────────────────────────
function mulberry32(seed) {
  return function () {
    let t = (seed += 0x6D2B79F5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function makeCandles(sym, end, n = 60) {
  let seed = 0;
  for (let i = 0; i < sym.length; i++) seed = seed * 31 + sym.charCodeAt(i);
  const rand = mulberry32(seed);
  const candles = [];
  let price = end * (0.85 + rand() * 0.15);
  const vol = end * 0.012;
  for (let i = 0; i < n; i++) {
    const drift = (end - price) * 0.015;
    const o = price;
    const change = drift + (rand() - 0.5) * vol;
    const c = Math.max(0.1, o + change);
    const range = vol * (0.6 + rand() * 1.0);
    const h = Math.max(o, c) + rand() * range * 0.6;
    const l = Math.min(o, c) - rand() * range * 0.6;
    const v = 0.4 + rand() * 1.0;
    candles.push({ o, h, l, c, v });
    price = c;
  }
  const last = candles[candles.length - 1];
  last.c = end;
  last.h = Math.max(last.h, end);
  last.l = Math.min(last.l, end);
  return candles;
}

function makeSparkline(sym, end, n = 24) {
  let seed = 0;
  for (let i = 0; i < sym.length; i++) seed = seed * 17 + sym.charCodeAt(i);
  const rand = mulberry32(seed + 1);
  const pts = [];
  let p = end * 0.92;
  for (let i = 0; i < n; i++) {
    p += (rand() - 0.45) * end * 0.015 + (end - p) * 0.04;
    pts.push(p);
  }
  pts[pts.length - 1] = end;
  return pts;
}

function makeStock(s) {
  const candles = makeCandles(s.sym, s.price, 60);
  const open = candles[candles.length - 24].o;
  const change = s.price - open;
  const changePct = (change / open) * 100;
  // Volume + market cap scale with price magnitude
  const shares = (Math.abs(s.sym.charCodeAt(0) * 1.7) + 20);
  return {
    ...s,
    open,
    change,
    changePct,
    high: Math.max(...candles.slice(-24).map(c => c.h)),
    low: Math.min(...candles.slice(-24).map(c => c.l)),
    vol: shares.toFixed(1) + 'M',
    mcap: s.price * (50 + s.sym.charCodeAt(0) % 30) * 1e7, // raw number; format at render
    candles,
    spark: makeSparkline(s.sym, s.price),
  };
}

// Pre-build for both markets
const BUILT = {
  IN: {
    seed: MARKETS.IN.seed.map(makeStock),
    catalog: MARKETS.IN.catalog.map(makeStock),
  },
  GLOBAL: {
    seed: MARKETS.GLOBAL.seed.map(makeStock),
    catalog: MARKETS.GLOBAL.catalog.map(makeStock),
  },
};

// ── React hook: live ticks ──────────────────────────────────────────
function useLiveMarket(initial) {
  const [stocks, setStocks] = React.useState(initial);

  // Reset when initial array identity changes (e.g. market switch)
  React.useEffect(() => { setStocks(initial); }, [initial]);

  React.useEffect(() => {
    const id = setInterval(() => {
      setStocks(prev => prev.map(s => {
        const vol = s.price * 0.0012;
        const delta = (Math.random() - 0.5) * vol * 2;
        const newPrice = Math.max(0.1, s.price + delta);
        const candles = s.candles.slice();
        const last = { ...candles[candles.length - 1] };
        last.c = newPrice;
        last.h = Math.max(last.h, newPrice);
        last.l = Math.min(last.l, newPrice);
        candles[candles.length - 1] = last;
        const spark = s.spark.slice(1).concat(newPrice);
        const change = newPrice - s.open;
        return {
          ...s, price: newPrice, change, changePct: (change / s.open) * 100,
          candles, spark,
        };
      }));
    }, 1400);
    return () => clearInterval(id);
  }, []);

  React.useEffect(() => {
    const id = setInterval(() => {
      setStocks(prev => prev.map(s => {
        const last = s.candles[s.candles.length - 1];
        const next = { o: last.c, h: last.c, l: last.c, c: last.c, v: 0.4 + Math.random() };
        const candles = s.candles.slice(1).concat(next);
        return { ...s, candles };
      }));
    }, 6000);
    return () => clearInterval(id);
  }, []);

  return stocks;
}

// ── React context for market selection ──────────────────────────────
const MarketContext = React.createContext(MARKETS.IN);

function useMarket() { return React.useContext(MarketContext); }

// Currency-aware formatters bound to the active market
function fmtPrice(n, market) {
  return market.code === 'IN' ? formatINR(n) : formatUSD(n);
}

// ── FinPilot backend bridge ─────────────────────────────────────────
// The IN market is wired to FinPilot's Django REST API for real signals,
// positions, and orders. The GLOBAL market keeps the synthetic simulation.
//
// The integration is deliberately additive: we POLL three endpoints, return
// the data as state, and let App merge it into the existing stock objects.
// Components that don't need FinPilot data ignore it; components that do
// receive it as optional props. If the API is unreachable, the dashboard
// keeps rendering the simulated baseline — no blank screens.

const FINPILOT_API = 'http://127.0.0.1:8000/api';
const FINPILOT_POLL_MS = 30_000;  // 30s — daily-signal app, no need to spam

// Strip the NSE suffix FinPilot stores ("RELIANCE.NS") so it matches the bare
// Cardinal symbol ("RELIANCE"). Idempotent — passing a bare symbol returns it.
function stripNS(sym) {
  return (sym || '').replace(/\.(NS|BO|NSE|BSE)$/i, '');
}

// Unwrap DRF list responses: a paginated payload is {count, results}; a bare
// array is returned as-is. Returns [] for null/undefined so callers don't have
// to null-check before mapping.
function unwrapDRF(data) {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results;
  return [];
}

async function getJSON(path) {
  const res = await fetch(`${FINPILOT_API}${path}`);
  if (!res.ok) throw new Error(`${path} → HTTP ${res.status}`);
  return res.json();
}

// React hook — single source of truth for FinPilot data.
//
// Returns { signalMap, positions, orders, online, lastUpdated, error }.
//   signalMap   — { 'RELIANCE': { signal_type, price, rsi, macd, reason, date } }
//   positions   — composite object: { open_positions, open_count, total_pnl }
//   orders      — array of order rows (newest first; DRF default ordering)
//   online      — true once any endpoint responds, false on hard fetch failure
//   lastUpdated — Date of the most recent successful poll
//
// The `enabled` flag lets callers skip polling entirely (e.g. when on GLOBAL
// market we don't want the network chatter — FinPilot only knows NSE stocks).
function useFinPilotData(enabled = true) {
  const [state, setState] = React.useState({
    signalMap: {}, positions: null, orders: [],
    online: false, lastUpdated: null, error: null,
  });

  React.useEffect(() => {
    if (!enabled) return;
    let cancelled = false;

    async function poll() {
      // Promise.allSettled — a missing /orders/ endpoint mustn't blank the
      // signals panel. We keep whatever succeeded.
      const [signalsR, portfolioR, ordersR] = await Promise.allSettled([
        getJSON('/signals/latest/'),
        getJSON('/portfolio/'),
        getJSON('/portfolio/orders/'),
      ]);
      if (cancelled) return;

      // Build a symbol → signal lookup once per poll (vs filtering inside
      // every render). Index by the bare Cardinal symbol.
      const signalMap = {};
      if (signalsR.status === 'fulfilled') {
        for (const s of unwrapDRF(signalsR.value)) {
          signalMap[stripNS(s.symbol)] = s;
        }
      }
      const positions = portfolioR.status === 'fulfilled' ? portfolioR.value : null;
      const orders = ordersR.status === 'fulfilled' ? unwrapDRF(ordersR.value) : [];

      const anyOk = (signalsR.status === 'fulfilled'
                     || portfolioR.status === 'fulfilled'
                     || ordersR.status === 'fulfilled');

      setState({
        signalMap, positions, orders,
        online: anyOk,
        lastUpdated: anyOk ? new Date() : null,
        error: anyOk ? null : (signalsR.reason?.message || 'API unreachable'),
      });
    }

    poll();                                            // fire immediately
    const id = setInterval(poll, FINPILOT_POLL_MS);    // then on a cadence
    return () => { cancelled = true; clearInterval(id); };
  }, [enabled]);

  return state;
}

// Patch FinPilot's real prices into Cardinal's stock array. Called by App.
//
// For each stock whose bare symbol has a matching FinPilot signal, we:
//   • override `price` with the real value
//   • recompute `change` / `changePct` against the (still simulated) `open`
//   • push the real price into the last candle so the chart's "now" matches
//   • slide the sparkline to end on the real price
//
// Stocks without a matching signal pass through unchanged. The simulated
// candle/sparkline history is preserved — FinPilot only stores daily bars,
// so the simulation provides the intraday "live feel" around the real anchor.
function mergeFinPilotPrices(stocks, signalMap) {
  if (!signalMap || Object.keys(signalMap).length === 0) return stocks;
  return stocks.map(s => {
    const sig = signalMap[s.sym];
    if (!sig || sig.price == null) return s;
    const realPrice = Number(sig.price);
    if (!Number.isFinite(realPrice)) return s;

    const change = realPrice - s.open;
    const candles = s.candles.slice();
    const last = { ...candles[candles.length - 1] };
    last.c = realPrice;
    last.h = Math.max(last.h, realPrice);
    last.l = Math.min(last.l, realPrice);
    candles[candles.length - 1] = last;
    const spark = s.spark.slice(0, -1).concat(realPrice);

    return {
      ...s,
      price: realPrice,
      change,
      changePct: (change / s.open) * 100,
      candles,
      spark,
      // Stash the signal so downstream components can show BUY/SELL badges
      // off the same object — saves passing signalMap through every layer.
      finpilotSignal: sig.signal_type,
    };
  });
}

window.MARKETS = MARKETS;
window.BUILT_MARKETS = BUILT;
window.useLiveMarket = useLiveMarket;
window.makeStock = makeStock;
window.MarketContext = MarketContext;
window.useMarket = useMarket;
window.fmtPrice = fmtPrice;
window.formatINR = formatINR;
window.formatUSD = formatUSD;
window.formatCompact = formatCompact;
window.formatNum = formatNum;
window.useFinPilotData = useFinPilotData;
window.mergeFinPilotPrices = mergeFinPilotPrices;
window.stripNS = stripNS;
// Exported so other panels (e.g. the Monte Carlo simulation) can build their
// own fetch URLs without re-declaring the constant.
window.FINPILOT_API = FINPILOT_API;
