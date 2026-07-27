# Folk Analytics — Streaming Intelligence Agent

**Author:** Armando Karin Molina Marrufo
**Institution:** Universidad Politécnica de Yucatán (UPY)
**Term:** Q2 2026

---

## What is Folk Analytics?

Folk Analytics is a console-based data analysis agent that retrieves music artist
metrics, accumulates them into a persistent history, and detects real growth or
decline trends. The user enters an artist name and the system handles the rest:
it queries the data source, stores the snapshot, analyses the time series, and
produces a structured report with alerts.

## Why it exists

Independent and emerging artists — especially those from underrepresented regions
or genres — rarely have access to the analytics tools major labels use. Folk
Analytics democratizes that access: no account, no subscription, no third-party
dashboard. Just an artist name and a report.

## Agent alignment

The system implements the classic agent loop **perceive → process → act**:

| Phase | What it does | Where it lives |
|-------|--------------|----------------|
| **Perceive** | Validates input and queries the data source | `agent.py`, `api/` |
| **Process** | Persists the snapshot and analyses accumulated history | `storage/`, `analytics/` |
| **Act** | Produces metrics, trends, alerts and the final report | `analytics/alerts.py`, `reports/` |

What separates this from a one-off lookup script is **memory**. Every run leaves a
trace on disk that later runs build on. Without history there is no trend to
detect — only noise.

## What it does

- Retrieves artist metrics: followers, monthly listeners and popularity
- Accumulates a persistent JSON history, deduplicated per calendar day
- Detects trends by combining **percentage change** between window halves with
  **least-squares linear regression**, reporting R² as a confidence measure
- Raises alerts against configurable thresholds: sharp drops, exceptional growth,
  and series too noisy to be statistically reliable
- Manages a *watchlist* of artists under continuous observation
- Validates all user input through numeric menus with full error handling
- Writes a complete audit trail to `logs/app.log`

## Installation

Requires **Python 3.10 or newer**. The core runs on the standard library alone;
external dependencies are optional.

```bash
git clone https://github.com/armando4322-2/UPY-PROGRAMMING-PROJECT-ARMANDO-MOLINA-Q2-2026-.git
cd UPY-PROGRAMMING-PROJECT-ARMANDO-MOLINA-Q2-2026-
pip install -r requirements.txt
```

## Usage

```bash
python run.py                    # interactive menu
python run.py --demo             # non-interactive demonstration
python run.py -a "Novo Amor"     # analyse a single artist and exit
python run.py --metric popularity --verbose
```

It also runs as a module: `python -m folk_analytics --demo`

### Sample output

```
══════════════════════════════════════════════════════════════
  FOLK ANALYTICS  |  SESION A3F91C02
══════════════════════════════════════════════════════════════
  IDENTIDAD
  Artista               : Novo Amor
  ID                    : ART-004
  Fuente de datos       : simulated
──────────────────────────────────────────────────────────────
  HISTORICO (followers)
  Instantaneas          : 30
  Media                 : 1,007,645
  Cambio neto           : +61,809 (+6.2%)
  Evolucion             : ▄▃▂▄▂▁▄▃▂▃▁▄▆▄▃▇▄▃▇▇▂▇█▄▇▆▅▄▅▆
──────────────────────────────────────────────────────────────
  TENDENCIA
  Direccion             : ↗ CRECIENDO
  Cambio en la ventana  : +6.2%
  Confianza             : media (R2=0.31)
══════════════════════════════════════════════════════════════
```

## The data source

The project programs against an interface (`StreamingClient`), never against a
concrete implementation. Swapping data sources touches one line.

### Simulated source (the project's data path)

Folk Analytics runs on a **simulated streaming API**. This is a deliberate scope
decision, not a shortcut: it keeps the project reproducible, offline, and free of
credential management, while still exercising the full agent pipeline.

The simulation is not `random.random()` sprinkled over a report. It generates
**deterministic, coherent time series** — for a given artist and date it always
returns the same value, following the model

```
value(day) = base × (1 + growth_rate) ^ days_from_today × noise(day)
```

where `noise(day)` is derived from the artist ID and the calendar date. Each
artist in the catalog carries its own growth rate and volatility, so the resulting
series behave like real ones: some climb, some decay, some are too noisy to read
confidently. **This determinism is what makes the detected trends mean anything.**

The simulated client also models real API behaviour: transient failures with
exponential-backoff retries, artists absent from the catalog, and artists with no
recorded activity.

### Real Spotify API (future work)

`api/spotify.py` implements the real Client Credentials Flow and is included as
documented future work. It is not the project's active data path — it exists to
demonstrate that the `StreamingClient` abstraction holds against a genuine
implementation, which is the architectural point the interface is there to prove.

Enabling it requires registering an app at
[developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) and
copying `.env.example` to `.env`. Then: `python run.py --source spotify`

> **An honest note on the data:** Spotify's public API does **not** expose monthly
> listeners — that figure only appears in the artist's web page. With that source
> the analysis leans on `followers` and the `popularity` index (0–100), which are
> officially available. Documenting the limitation beats inventing the number.

## Project structure

```
folk_analytics/
├── __main__.py          # entry point and command-line arguments
├── agent.py             # the perceive → process → act cycle
├── cli.py               # interactive menu and demonstration mode
├── config.py            # every tunable parameter
├── logging_setup.py     # file and console logging, with ASCII fallback
├── api/
│   ├── base.py          # StreamingClient interface and exception hierarchy
│   ├── models.py        # ArtistData
│   ├── simulated.py     # deterministic synthetic source
│   └── spotify.py       # real source (future work)
├── analytics/
│   ├── metrics.py       # descriptive statistics
│   ├── trends.py        # trend detection
│   └── alerts.py        # threshold-based alert engine
├── storage/
│   └── json_store.py    # history and watchlist persistence
└── reports/
    └── console.py       # report rendering
tests/                   # 85 pytest tests
logs/
├── development.log      # engineering diary (versioned)
└── app.log              # runtime output (regenerated, not versioned)
```

## Tests

```bash
python -m pytest tests/ -v
```

The suite covers input validation, trend mathematics, persistence, the alert
engine and the full agent flow, including edge cases: constant series, division by
zero, odd-length windows, corrupt history files and retry exhaustion.

## Configuration

Every tunable parameter lives in `folk_analytics/config.py`:

| Parameter | Default | Controls |
|-----------|---------|----------|
| `ANALYSIS_WINDOW_DAYS` | 30 | Days covered by the analysis |
| `MIN_SNAPSHOTS_FOR_TREND` | 4 | Minimum points before a trend is computed |
| `TREND_THRESHOLD_PCT` | 5.0 | Band treated as stable |
| `ALERT_DROP_PCT` | −15.0 | Drop that triggers a critical alert |
| `ALERT_SPIKE_PCT` | 25.0 | Rise that triggers an informational alert |

## Development history

`logs/development.log` is the project's engineering diary. It records every phase,
every defect found and fixed, and the reasoning behind each design decision —
including the audit that exposed the original trend-detection flaw.

## Future work

- CSV and HTML report export
- Scheduled monitoring with notifications
- Cross-artist comparison and genre ranking
- Migrating the store to SQLite if the history grows large
- Activating the real Spotify integration

---

> Academic project — Universidad Politécnica de Yucatán, Q2 2026
