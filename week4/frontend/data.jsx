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

const FINPILOT_API = (import.meta.env.VITE_API_BASE || '/api').replace(/\/$/, '');
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
  const res = await fetch(`${FINPILOT_API}${path}`, {
    credentials: 'same-origin',
  });
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
    signals: [], signalMap: {}, positions: null, orders: [], journal: [], quotes: [],
    system: null, online: false, lastUpdated: null, error: null,
    connection: {
      api: 'connecting', stream: 'connecting', market: 'unknown',
      dataAgeMs: null, lastEvent: null,
    },
  });
  const refreshTimer = React.useRef(null);
  const pollInFlight = React.useRef(null);

  const poll = React.useCallback(() => {
    if (pollInFlight.current) return pollInFlight.current;
    const request = (async () => {
      try {
        const snapshot = await getJSON('/dashboard/snapshot/');
        const quotes = snapshot.quotes || [];
        const quoteMap = Object.fromEntries(
          quotes.map(q => [stripNS(q.symbol), q])
        );
        const signals = (snapshot.signals || []).map(signal => {
          const quote = quoteMap[stripNS(signal.symbol)];
          return quote ? {...signal, price: quote.last_price} : signal;
        });
        const signalMap = {};
        for (const s of signals) signalMap[stripNS(s.symbol)] = s;
        const received = new Date(snapshot.snapshot_at || Date.now());
        setState(previous => ({
          ...previous,
          signals, signalMap, quotes,
          positions: snapshot.positions,
          orders: snapshot.orders || [],
          journal: snapshot.journal || [],
          system: snapshot.system,
          online: true,
          lastUpdated: received,
          error: null,
          connection: {
            ...previous.connection,
            api: 'connected',
            market: snapshot.system?.data?.latest_signal_date ? 'snapshot' : 'waiting',
            dataAgeMs: Math.max(0, Date.now() - received.getTime()),
          },
        }));
      } catch (error) {
        setState(previous => ({
          ...previous,
          online: false,
          error: error.message,
          connection: {...previous.connection, api: 'disconnected'},
        }));
      }
    })();
    pollInFlight.current = request.finally(() => {
      pollInFlight.current = null;
    });
    return pollInFlight.current;
  }, []);

  React.useEffect(() => {
    let alive = true;
    const run = () => { if (alive) poll(); };
    run();
    const id = setInterval(run, POLL_MS);
    return () => {
      alive = false;
      clearInterval(id);
      if (refreshTimer.current) clearTimeout(refreshTimer.current);
    };
  }, [poll]);

  React.useEffect(() => {
    let socket;
    let retryTimer;
    let closed = false;
    let attempts = 0;

    const connect = () => {
      const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
      socket = new WebSocket(`${protocol}//${location.host}/ws/dashboard/`);
      socket.onopen = () => {
        attempts = 0;
        setState(previous => ({
          ...previous,
          connection: {...previous.connection, stream: 'connected'},
        }));
      };
      socket.onmessage = event => {
        const message = JSON.parse(event.data);
        if (message.event === 'quote.updated' && message.payload?.symbol) {
          const symbol = stripNS(message.payload.symbol);
          setState(previous => {
            const signals = previous.signals.map(signal =>
              stripNS(signal.symbol) === symbol
                ? {...signal, price: message.payload.last_price}
                : signal
            );
            const signalMap = {...previous.signalMap};
            if (signalMap[symbol]) {
              signalMap[symbol] = {
                ...signalMap[symbol], price: message.payload.last_price,
              };
            }
            return {
              ...previous, signals, signalMap, lastUpdated: new Date(),
              connection: {
                ...previous.connection, stream: 'connected', market: 'live',
                dataAgeMs: 0, lastEvent: message.event,
              },
            };
          });
          return;
        }
        setState(previous => ({
          ...previous,
          connection: {
            ...previous.connection,
            stream: 'connected',
            lastEvent: message.event,
          },
        }));
        // Collapse event bursts (journal + action completion) into one snapshot.
        if (message.event !== 'connection.ready') {
          clearTimeout(refreshTimer.current);
          refreshTimer.current = setTimeout(poll, 120);
        }
      };
      socket.onclose = () => {
        if (closed) return;
        attempts += 1;
        setState(previous => ({
          ...previous,
          connection: {...previous.connection, stream: 'reconnecting'},
        }));
        retryTimer = setTimeout(connect, Math.min(30_000, 750 * 2 ** attempts));
      };
      socket.onerror = () => socket.close();
    };

    connect();
    return () => {
      closed = true;
      clearTimeout(retryTimer);
      if (socket) socket.close();
    };
  }, [poll]);

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
  const cookie = document.cookie.split('; ').find(row => row.startsWith('csrftoken='));
  const csrf = cookie ? decodeURIComponent(cookie.split('=').slice(1).join('=')) : '';
  const idempotencyKey = crypto.randomUUID
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const res = await fetch(`${FINPILOT_API}${path}`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrf,
      'Idempotency-Key': idempotencyKey,
    },
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
