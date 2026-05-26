# FinPilot — Week 2: Django Backend

The Week 1 strategy logic, rebuilt as a service: a REST API plus a Celery job
that generates buy/sell/hold signals automatically every trading morning.

## What it does

- **`core/`** — the framework-free engine. `data.py` fetches OHLCV (yfinance
  wrapper); `strategy.py` computes RSI / MACD / Bollinger Bands and turns the
  latest bar into a signal. No Django imports — so it is testable and portable.
- **`signals/`** — `Stock` and `Signal` models, a read-only REST API, and the
  `generate_daily_signals` Celery task.
- **`portfolio/`** — `Position` and `Order` models + API (populated in Week 4).

## Architecture

```
Celery Beat (09:05 IST)  ──fires──►  generate_daily_signals task
                                          │
                       core.data.fetch_ohlcv ─► core.strategy.generate_signal
                                          │
                                  Signal rows in the DB
                                          │
                              DRF REST API  ──►  clients
```

The strategy **engine** (`core/`) is deliberately Django-free — "ports and
adapters". The Django app is just an adapter around it.

## Setup

```bash
cd week2
python -m venv .venv && .venv\Scripts\activate     # Windows
pip install -r requirements.txt
copy .env.example .env                              # then edit .env

python manage.py migrate
python manage.py seed_stocks                        # load a starter NIFTY universe
python manage.py createsuperuser                    # optional, for the admin
```

## Verify it works (smoke test — no Redis needed)

```bash
python smoke_test.py
```

This runs the full fetch → strategy → DB path synchronously and asserts that
signals were written.

## Run the API

```bash
python manage.py runserver
```

| Endpoint | Returns |
|----------|---------|
| `GET /api/signals/stocks/` | every stock under coverage |
| `GET /api/signals/latest/` | signals from the most recent run |
| `GET /api/signals/<symbol>/` | full signal history for one stock |
| `GET /api/portfolio/` | open positions + aggregate P&L |
| `GET /api/portfolio/orders/` | order history |
| `/admin/` | Django admin |

## Run the automation (needs Redis)

Three processes, three terminals:

```bash
redis-server                                        # the broker
celery -A finpilot worker --loglevel=info            # executes tasks
celery -A finpilot beat --loglevel=info              # schedules them
```

Then add a periodic task in the admin (`Periodic Tasks`) pointing at
`signals.generate_daily_signals`, or trigger it once from a shell:

```bash
python manage.py shell -c "from signals.tasks import generate_daily_signals; generate_daily_signals.delay()"
```

## Logs & debugging

Every layer logs to the console with a timestamp, level and exact source
(`logger:line function()`), so a runtime issue can be traced to its origin
without a debugger:

```
12:01:44 INFO     core.data:48 fetch_ohlcv() | fetch_ohlcv(TCS.NS): 124 rows, ...
12:01:44 DEBUG    core.strategy:148 generate_signal() | ... buy_votes=1 sell_votes=0 -> HOLD
12:01:44 INFO     signals.tasks:54 generate_daily_signals() | TCS.NS -> HOLD @ 3891.0 [created]
```

Two `.env` switches:

- `DJANGO_LOG_LEVEL=DEBUG` — turn on detailed step-by-step traces (every fetch,
  every indicator vote, per-stock task progress). Default `INFO`.
- `DJANGO_SQL_LOG=True` — log every SQL query (noisy; for chasing DB issues).

Failures in the daily task are logged at `ERROR` **with the full traceback**
(`exc_info`), and a run with any failure ends on a `WARNING` so it stands out.

## Concepts covered

Project vs app, thin views / fat models, the strategy engine kept framework-free,
DRF serializers & generic views, the N+1 query problem (`select_related`),
Celery worker vs beat, and task **idempotency** (`update_or_create` + a unique
constraint). Full notes: see `../LEARNINGS.md`.
