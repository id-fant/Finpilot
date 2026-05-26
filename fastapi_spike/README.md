# FinPilot — FastAPI Spike: the Returns Assistant

A small, self-contained **FastAPI** service. Give it an NSE ticker; it returns
the headline return/risk metrics — total return, CAGR, annualised volatility,
Sharpe ratio, max drawdown. It is the FinPilot **week_1** analysis logic,
re-packaged as a clean JSON API.

## Why this exists

1. **It proves the logic ports.** The metric maths is pure Python — no Django,
   no ORM. Lifting it into FastAPI with zero rewrites is the ports-and-adapters
   principle paying off in practice.
2. **It is a focused portfolio piece.** A tight, reviewable FastAPI service is
   a better application artifact than a sprawling framework project — hence
   the name *spike* (a deliberately small, sharp prototype).

## Layout

```
fastapi_spike/
├── requirements.txt
└── app/
    ├── main.py      FastAPI app + the pure metric logic
    └── models.py    Pydantic request/response models
```

## Run it

```bash
cd fastapi_spike
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open **http://127.0.0.1:8000/docs** — FastAPI generates an interactive,
typed API explorer from the Pydantic models. No Postman needed.

## Endpoints

| Method | Path | What it does |
|--------|------|--------------|
| `GET` | `/healthz` | liveness check |
| `GET` | `/metrics/{symbol}?period=1y` | metrics for one stock |
| `POST` | `/compare` | rank several stocks by Sharpe ratio |

Examples:

```bash
curl "http://127.0.0.1:8000/metrics/RELIANCE.NS?period=2y"

curl -X POST http://127.0.0.1:8000/compare \
     -H "Content-Type: application/json" \
     -d '{"symbols": ["RELIANCE.NS", "TCS.NS", "INFY.NS"], "period": "1y"}'
```

## FastAPI vs the week_2 Django API

| | Django + DRF (week_2) | FastAPI (this spike) |
|--|--|--|
| Validation | DRF serializers | Pydantic models, off type hints |
| API docs | extra package | built in (`/docs`) |
| Async | bolt-on | native |
| Best for | batteries-included apps (admin, ORM, auth) | thin, fast, typed services |

Same metric logic underneath — the framework is just the adapter.

> Concept notes: see `../LEARNINGS.md`.
