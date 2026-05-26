# FinPilot — Week 4: Broker Integration + Cloud Deploy

The last mile. Weeks 1-3 produced *signals* and served them; week 4 turns a
signal into an *order* and puts the whole thing online.

## Layout

```
week4/
├── broker/
│   ├── paper_trade.py     PaperBroker — simulated money, the safe default
│   ├── kite_client.py     KiteClient — live Zerodha Kite Connect broker
│   └── order_manager.py   sizing + risk checks + routing (signal -> order)
├── frontend/
│   ├── index.html         static signal dashboard
│   ├── dashboard.js        fetches the week2 REST API
│   └── styles.css
├── Dockerfile             deploy image for the week2 backend
├── docker-compose.yml     local stack (web + worker + redis)
└── railway.toml           one-command cloud deploy (Railway PaaS)
```

## The broker layer

The design idea: **`PaperBroker` and `KiteClient` expose the same interface**
— `get_ltp`, `place_order`, `get_positions`. `OrderManager` is handed one of
them and cannot tell which. Going from simulation to live trading swaps a
single object; nothing else changes.

```python
from broker import PaperBroker, OrderManager

broker = PaperBroker(starting_cash=300_000)        # simulated — safe
manager = OrderManager(broker, max_trade_value=80_000, max_positions=3)

signals = [{"symbol": "RELIANCE.NS", "action": "BUY"},
           {"symbol": "TCS.NS", "action": "SELL"}]
for result in manager.run(signals):
    print(result)
```

To trade live, build a `KiteClient` instead and hand *that* to `OrderManager`:

```python
from broker import KiteClient
broker = KiteClient.from_env()    # reads KITE_API_KEY / KITE_ACCESS_TOKEN
```

`OrderManager` is the only place that sizes orders and enforces risk — a fixed
rupee budget per trade, a cap on open positions, a daily order limit, and no
naked shorting. The broker clients stay "dumb" on purpose.

### Run the demos
```bash
pip install yfinance              # PaperBroker needs only this
pip install kiteconnect           # only if you intend to trade live

python broker/paper_trade.py      # buy/sell against simulated cash
python broker/order_manager.py    # a day of signals through the risk gate
```

> Paper trading is the default and it is deliberate. Wire up `KiteClient` only
> after the paper results convince you — and start with tiny size.

## The frontend

A build-step-free dashboard: open `frontend/index.html` directly, or serve it
with `python -m http.server 5500` from inside `frontend/`. Set `API_BASE` at
the top of `dashboard.js` to your running backend, then start the week2 API
so it has something to show.

## Deploy

| Target | How |
|--------|-----|
| Local stack | `docker compose -f week4/docker-compose.yml up --build` |
| Cloud (Railway) | install the Railway CLI, then `railway up` from the repo root |

The `Dockerfile` builds the **week2** Django backend (build context is the
repo root so it can reach `week2/`). `railway.toml` points Railway at that
Dockerfile and runs gunicorn on Railway's `$PORT`, using `/api/signals/stocks/`
as the health check (it confirms both the web process and the DB are up).

Set these as environment variables on the host — never in code:
`DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, and (for live trading)
`KITE_API_KEY`, `KITE_API_SECRET`, `KITE_ACCESS_TOKEN`.

## Notes
- The dashboard reads from the week2 API. A live *positions* view would need a
  small endpoint that exposes `OrderManager`/broker state — not built yet.
- The archived `_archive/week_3/` held a heavier self-hosted stack (Postgres,
  nginx, CI). Week 4 favours a Railway PaaS deploy instead — fewer moving parts.

> Concepts and interview notes: see `../LEARNINGS.md`.
