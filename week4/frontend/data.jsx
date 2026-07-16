// data.jsx — FinPilot data layer.
//
// This is the ONLY source of truth for talking to the Django API. No more
// simulated markets, crypto, or fake tick engine — FinPilot is a NIFTY-50
// signal service, so the dashboard reads real signals/positions/orders/
// journal/system from :8000 and nothing else.
//
// Performance: one consolidated poll (Promise.allSettled over 5 endpoints)
// every 30s, plus an imperative refetch() so an action button can refresh
// immediately instead of waiting for the next tick.

const FINPILOT_API = 'http://127.0.0.1:8000/api';
const POLL_MS = 30_000;

// ── Formatting (Indian numbering: 12,34,567.89) ─────────────────────────────
function formatINR(n, { decimals = 2, sign = false } = {}) {
  if (n == null || !Number.isFinite(Number(n))) return '—';
  n = Number(n);
  const neg = n < 0;
  const [intp, dec = ''] = Math.abs(n).toFixed(decimals).split('.');
  const last3 = intp.slice(-3);
  const rest = intp.slice(0, -3);
  const grouped = rest ? rest.replace(/\B(?=(\d{2})+(?!\d))/g, ',') + ',' + last3 : last3;
  return (neg ? '−' : sign ? '+' : '') + '₹' + grouped + (decimals > 0 ? '.' + dec : '');
}

// Compact INR: ₹3.42 Cr / ₹15.4 L / ₹8,200
function formatCompactINR(n) {
  if (n == null || !Number.isFinite(Number(n))) return '—';
  n = Number(n);
  const abs = Math.abs(n), s = n < 0 ? '−' : '';
  if (abs >= 1e7) return s + '₹' + (abs / 1e7).toFixed(2) + ' Cr';
  if (abs >= 1e5) return s + '₹' + (abs / 1e5).toFixed(2) + ' L';
  return formatINR(abs, { decimals: 0 });
}

function stripNS(sym) { return (sym || '').replace(/\.(NS|BO|NSE|BSE)$/i, ''); }

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

// ── The one hook the whole app reads from ───────────────────────────────────
// Returns everything the Command view and shell need, refreshed together:
//   signals   — array from /signals/latest/ (each has ml_prob, reason, …)
//   signalMap — { RELIANCE: signalRow } for quick lookup by bare symbol
//   positions — /portfolio/ composite { open_positions, open_count, total_pnl }
//   orders    — /portfolio/orders/ rows
//   journal   — /portfolio/journal/ rows (recent decisions)
//   system    — /system/ config + gate state
//   online / lastUpdated / error / refetch
function useFinPilot() {
  const [state, setState] = React.useState({
    signals: [], signalMap: {}, positions: null, orders: [], journal: [],
    system: null, online: false, lastUpdated: null, error: null,
  });
  const tick = React.useRef(0);

  const poll = React.useCallback(async () => {
    const [sig, port, ord, jour, sys] = await Promise.allSettled([
      getJSON('/signals/latest/'),
      getJSON('/portfolio/'),
      getJSON('/portfolio/orders/'),
      getJSON('/portfolio/journal/'),
      getJSON('/system/'),
    ]);
    const val = (r) => (r.status === 'fulfilled' ? r.value : null);
    const signals = unwrapDRF(val(sig));
    const signalMap = {};
    for (const s of signals) signalMap[stripNS(s.symbol)] = s;
    const anyOk = [sig, port, ord, jour, sys].some(r => r.status === 'fulfilled');

    setState({
      signals, signalMap,
      positions: val(port),
      orders: unwrapDRF(val(ord)),
      journal: unwrapDRF(val(jour)),
      system: val(sys),
      online: anyOk,
      lastUpdated: anyOk ? new Date() : null,
      error: anyOk ? null : (sig.reason?.message || 'API unreachable'),
    });
  }, []);

  React.useEffect(() => {
    let alive = true;
    const run = () => { if (alive) poll(); };
    run();
    const id = setInterval(run, POLL_MS);
    return () => { alive = false; clearInterval(id); };
  }, [poll, tick.current]);

  // Imperative refresh — bump the ref so the effect re-subscribes and fires now.
  const refetch = React.useCallback(() => { poll(); }, [poll]);

  return { ...state, refetch };
}

// ── useApi — the one GET hook every panel shares ────────────────────────────
// Replaces six hand-rolled fetch/error/loading blocks. Covers the three
// shapes the panels need: fetch-on-mount, refetch when `path` changes
// (scope chips, symbol pickers), and interval polling. Errors keep the last
// good data so a blip doesn't blank a rendered panel.
function useApi(path, { poll = 0, enabled = true } = {}) {
  const [state, setState] = React.useState({ data: null, error: null, loading: true });

  const load = React.useCallback(async () => {
    try {
      const res = await fetch(`${FINPILOT_API}${path}`);
      const body = await res.json().catch(() => null);
      if (!res.ok) throw new Error((body && body.error) || `HTTP ${res.status}`);
      setState({ data: body, error: null, loading: false });
    } catch (e) {
      setState(s => ({ data: s.data, error: e.message, loading: false }));
    }
  }, [path]);

  React.useEffect(() => {
    if (!enabled) return;
    setState(s => ({ ...s, loading: true, error: null }));
    load();
    if (poll > 0) {
      const id = setInterval(load, poll);
      return () => clearInterval(id);
    }
  }, [load, poll, enabled]);

  return { ...state, refetch: load };
}

// POST an action (refresh-signals / execute-orders); returns the HTTP status.
async function postAction(path) {
  const res = await fetch(`${FINPILOT_API}${path}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
  });
  const body = await res.json().catch(() => ({}));
  return { status: res.status, body };
}

window.FINPILOT_API = FINPILOT_API;
window.useFinPilot = useFinPilot;
window.useApi = useApi;
window.postAction = postAction;
window.formatINR = formatINR;
window.formatCompactINR = formatCompactINR;
window.stripNS = stripNS;
window.unwrapDRF = unwrapDRF;
