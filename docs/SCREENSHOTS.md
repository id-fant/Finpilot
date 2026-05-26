# Capturing dashboard screenshots for the README

Goal: a 60-second clone-to-screenshot path. Drop the output PNGs into
`docs/screenshots/` and link them from the top of `README.md`.

## One-time setup

```bash
git clone <repo>
cd finance_project
python run.py --demo
```

This bootstraps the venv, applies migrations, seeds the demo dataset, and
opens the dashboard at <http://127.0.0.1:5500>. Wait ~3 seconds for the API
to bind.

## What to capture (5 panels, ordered by hireability impact)

The order matters — capture them in this sequence; the first three are the
ones that go in the README hero section.

### 1. The hero: full dashboard with real data flowing
- **Browser:** Chrome 120%+ zoom, no devtools open, light mode.
- **Crop:** the entire viewport — leave the top status pill ("live · updated
  HH:MM:SS") visible. This is the *proof* that real backend data is loading,
  not a static mock.
- **Filename:** `dashboard-hero.png`
- **Why it's first:** a recruiter who only opens one image opens this one.

### 2. The signal side-panel with LLM explanation
- **Action:** click a BUY pill (RELIANCE or HDFCBANK in the demo seed) to
  pop the side panel. The `Signal.reason` text — populated by `week3`'s
  Gemini explainer when `GEMINI_API_KEY` is set — appears in the body.
- **Crop:** the side panel + the row that triggered it. The reason text
  should be readable.
- **Filename:** `signal-explanation.png`
- **Why:** this is the *only* screenshot that demonstrates the LLM layer.
  Without it, the AI claim in the README is just a claim.

### 3. The trades view — coloured-pill variety
- **Action:** click "Trades" in the nav.
- **Crop:** the table showing one COMPLETE BUY, one PENDING BUY, one
  COMPLETE SELL, one REJECTED — the seed dataset gives all four colours.
- **Filename:** `trades-table.png`
- **Why:** shows you've thought about *state*, not just happy-path.

### 4. The open-positions donut
- **Action:** scroll to "Positions". The TCS open position (8 shares, ~₹824
  profit) is the only one in the demo seed.
- **Crop:** the donut + the row beneath it. The P&L colour should match the
  positive return.
- **Filename:** `positions-donut.png`

### 5. (Optional) Django admin showing the order rows
- **Open:** <http://127.0.0.1:8000/admin/> (create a superuser first:
  `python manage.py createsuperuser` in `week2/`).
- **Navigate:** `portfolio > orders`.
- **Crop:** the list view with the 4 demo orders. Demonstrates the admin
  surface — useful as a credibility signal for the Django side.
- **Filename:** `admin-orders.png`

## After capturing

1. Drop all PNGs into `docs/screenshots/`.
2. Open `README.md`, find the `🎬 **Demo:**` line near the top, and replace
   the Loom placeholder with the hero image as an interim:
   ```markdown
   ![FinPilot dashboard](docs/screenshots/dashboard-hero.png)
   ```
3. The other four go further down the README under a `## Screenshots` heading.
4. Once you record the Loom, swap the hero image for the Loom embed.

## Recording the 90-second Loom

The same sequence as the screenshots, on tape:

1. (0:00) `python run.py --demo` — show the launcher output.
2. (0:15) Browser opens to the dashboard — point at the live status pill.
3. (0:25) Click a BUY pill — side panel opens, read the LLM explanation.
4. (0:40) Click "Trades" — show the 4 statuses.
5. (0:55) Click "Positions" — show TCS open with P&L.
6. (1:10) Switch to Django admin — show the underlying Order rows.
7. (1:25) End on the README's results table with the honest numbers.

Keep it under 90 seconds — recruiters skip past 2 minutes. Mute the
microphone if you don't have a script ready; the visual flow tells the
story.
