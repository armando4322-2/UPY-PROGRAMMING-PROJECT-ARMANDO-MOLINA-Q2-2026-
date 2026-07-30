# Folk Analytics — Streaming Intelligence Agent

**Author:** Armando Karin Molina Marrufo
**Institution:** Universidad Politécnica de Yucatán (UPY)
**Term:** Q2 2026

[![tests](https://github.com/armando4322-2/UPY-PROGRAMMING-PROJECT-ARMANDO-MOLINA-Q2-2026-/actions/workflows/tests.yml/badge.svg)](https://github.com/armando4322-2/UPY-PROGRAMMING-PROJECT-ARMANDO-MOLINA-Q2-2026-/actions/workflows/tests.yml)

📄 **[Reporte de estado del proyecto](REPORTE.md)** — resumen completo en español:
decisiones, limitaciones y resultados de la auditoría.

### ▶ [Run it in your browser](https://armando4322-2.github.io/UPY-PROGRAMMING-PROJECT-ARMANDO-MOLINA-Q2-2026-/)

No installation required. The live page runs the real Python package in your
browser via WebAssembly.

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

python run.py -a "Bad Bunny" --source deezer      # real data, no credentials
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

The project ships **two working sources** and they serve different purposes.
The simulated one can demonstrate trend detection today; the real one cannot,
because no public API returns the follower count an artist had thirty days ago.
Keeping both is the honest way to have real data *and* a demonstrable feature.

### Live stats — the real-data source

"Live stats" is not one API. Each metric comes from whichever source actually
publishes it, so no field is ever left empty:

| Metric | Source | Nature |
|---|---|---|
| Followers | Deezer | direct |
| Albums | Deezer | direct |
| Top 10 tracks + previews | Deezer | direct |
| Top-10 reach | Deezer | mean of real track ranks |
| **Popularity 0–100** | Deezer | **derived — see below** |
| Photo, canonical ID | Spotify | direct |
| Country, type, genres | MusicBrainz | direct |

**The popularity index is calculated, not official.** No platform publishes a
per-artist popularity figure any more — Spotify stopped exposing it to new
applications. It is derived from something that *is* real: the rank Deezer
assigns each track (0–1,000,000).

```
index = mean(rank of the top 10 tracks) / 10,000
```

The mean is used rather than the maximum on purpose: one viral hit would spike
the maximum and misdescribe an artist whose remaining catalogue is barely
played. This is labelled as calculated in the report, on the page and here —
it is **not** a platform metric and **not** a play count.

Metrics no source publishes are **removed from the interface** rather than shown
as "not published". A shorter report that is entirely true beats a longer one
with holes in it.

| | Simulated | Deezer | Spotify |
|---|---|---|---|
| Role | trend demonstration | **metrics** | **artist photos** |
| Real artists | no | **yes** | yes |
| Credentials | none | **none** | build time only |
| Works in the browser | yes | yes (JSONP) | n/a (baked in) |
| History available now | 30 days | accumulates | — |
| Followers | yes | **yes** | **blocked** |
| Monthly listeners | yes | not published anywhere — field removed | — |
| Popularity | yes | **derived index** | **blocked** |
| Albums | — | yes | — |

### Simulated source (default)

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

### Deezer — real artists, no credentials

```bash
python run.py -a "Natalia Lafourcade" --source deezer
python run.py -a "Sufjan Stevens" --source deezer
```

Deezer's public API needs no key, no registration and no account. It publishes
`nb_fan` (real followers) and `nb_album`.

**Disambiguation matters more than it looks.** Searching `AURORA` and taking the
first result returns a homonym with 2,486 followers instead of the Norwegian
artist, who has 551,254 and appears sixth. `select_best_match` scores candidates
by name match first and follower count only as a tiebreaker, so an exact match
always beats a bigger but unrelated artist.

**Two limitations, stated rather than hidden.** Deezer does not publish monthly
listeners or a popularity index. Those appear as *not published* instead of `0`,
because a zero would assert something false about the artist — each source
declares its unavailable metrics and the report honours that. And since no public
API offers retroactive history, the agent starts accumulating from its first run;
until there are enough points the trend reads *insufficient data*, which is the
correct answer rather than a failure.

### Real Spotify API (optional, terminal only)

Spotify is **not** an analysis source, and that is a finding rather than a choice.
Running it against the live API with valid credentials (2026-07-30) showed that
Spotify no longer exposes metrics to newly registered applications:

| Endpoint | Result |
|---|---|
| `GET /v1/search?type=artist` | `200` — simplified object: `id`, `name`, `images`, `uri`. No `followers`, `popularity` or `genres` |
| `GET /v1/artists/{id}` | `200` — **the same keys**. Still no metrics |
| `GET /v1/artists?ids={id}` | **`403 Forbidden`** |
| `GET /v1/artists/{id}/top-tracks` | **`403 Forbidden`** |
| `GET /v1/artists/{id}/albums` | `200` |

Authentication works and search works; the metrics simply do not arrive. Using
Spotify for analysis would report zero followers for every artist, which looks like
a bug in the project when it is a platform restriction.

So Spotify does the one thing it still does well: **official high-resolution artist
photos and canonical IDs**. It is used only by `tools/build_catalog.py`, never during
analysis, and the result is committed — so neither the terminal nor the web page
needs Spotify credentials to display artwork.

This was worth catching. The earlier version of `tests/test_spotify.py` asserted
against a response shape taken from the documentation, passed green, and was wrong.

It cannot be used from the public web page: a client secret cannot live in a
page anyone can read. Enabling it in the terminal requires registering an app at
[developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) and
copying `.env.example` to `.env`. Then: `python run.py --source spotify`

> **An honest note on the data:** Spotify's public API does **not** expose monthly
> listeners — that figure only appears in the artist's web page. With that source
> the analysis leans on `followers` and the `popularity` index (0–100), which are
> officially available. Documenting the limitation beats inventing the number.

## Collecting real history

No public API returns the follower count an artist had thirty days ago. This was
checked rather than assumed: the Wayback Machine holds no captures of `api.deezer.com`
and only empty redirects for artist pages; ListenBrainz aggregates listens per user
rather than over time; Spotify blocks metrics outright. **The past is not available
anywhere.**

The only honest way to obtain a real time series is to start measuring it. A GitHub
Action runs `tools/collect_snapshots.py` daily, appends one point per artist to
`folk_analytics/data/history.json`, and commits it. The repository becomes the
historical database, and its commit log is evidence that each figure was recorded on
its date rather than generated afterwards.

```bash
python tools/collect_snapshots.py              # collect now
python tools/collect_snapshots.py --dry-run    # preview, write nothing
```

This also fixes something conceptual. Until now the agent only perceived when someone
ran it by hand; an agent perceives recurrently and accumulates memory. Now it does.

Backfilling the past with estimates was rejected: presenting invented figures beside
measured ones is precisely what invalidates an analysis.

## Web interface

[**armando4322-2.github.io/UPY-PROGRAMMING-PROJECT-ARMANDO-MOLINA-Q2-2026-**](https://armando4322-2.github.io/UPY-PROGRAMMING-PROJECT-ARMANDO-MOLINA-Q2-2026-/)

The page is not a JavaScript reimplementation or a mockup. It loads
[Pyodide](https://pyodide.org) — CPython compiled to WebAssembly — writes the
actual package source into a virtual filesystem, imports it, and runs the same
`FolkAnalyticsAgent` the terminal uses. There is no server: all computation
happens in the visitor's browser.

It offers live agent execution with artist and metric selectors, a Chart.js
history plot, metric cards, a terminal showing the real colour-coded log output,
the author's GitHub profile fetched live, and documentation whose configuration
values are read at runtime from `config.py` by the page's own interpreter.

### Rebuilding the page

```bash
python tools/build_web.py
```

`tools/build_web.py` injects the package sources into `tools/web_template.html`
and writes `docs/index.html`. This exists to avoid two sources of truth: change
the package, rerun the script, and the page is current. It also counts the test
functions with `ast` so the figure shown in the header can never go stale.
Two modules are excluded: `__main__.py` (argparse does not apply in a browser)
and `spotify.py` (needs network and credentials).

## Featured artists

The project ships a catalog of 50 artists with identifiers already resolved, so they
can be analysed with one click. Selecting one also fetches its **top 10 tracks**, with
30-second previews. It is generated offline and committed:

```bash
python tools/build_catalog.py           # resume-safe; skips what it already has
python tools/build_catalog.py --force   # rebuild from scratch
```

Each source contributes what it is actually good at — Deezer the ID and live
metrics, Spotify the official photo, MusicBrainz the country, type and genres that
compose the description. **No description is hand-written**, so nothing false can be
asserted about an artist: when a field is missing it simply does not appear.

The catalog deliberately stores only slow-moving data. Follower counts and track
rankings are *not* cached — they would freeze at generation time and the project would
present stale figures as current. Both are fetched live on every analysis.

Disambiguation applies to MusicBrainz too, and it matters: searching `Mora` ranks
*Mora Träsk* (Swedish children's music, score 100) above the Puerto Rican reggaeton
artist (score 96). Taking the top result would have described a reggaeton artist as a
children's musician. An exact name match is required; when there is none, the genre
fields are simply left empty. **An empty description is correct — a wrong one asserts
something false about a real person.**

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
│   ├── popularity.py    # derived popularity index
│   ├── trends.py        # trend detection
│   └── alerts.py        # threshold-based alert engine
├── storage/
│   └── json_store.py    # history and watchlist persistence
└── reports/
    └── console.py       # report rendering
tests/                   # 205 pytest tests
tools/
├── build_web.py         # generates docs/index.html from the package
├── web_template.html    # page template
├── build_catalog.py     # generates the featured-artist catalog
└── collect_snapshots.py # daily real-metric collection
docs/
└── index.html           # generated — the live web interface
logs/
├── development.log      # engineering diary (versioned)
└── app.log              # runtime output (regenerated, not versioned)
```

## Tests

```bash
python -m pytest tests/ -v
```

205 tests. The suite covers input validation, trend mathematics, persistence, the alert
engine and the full agent flow, including edge cases: constant series, division by
zero, odd-length windows, corrupt history files, retry exhaustion, and — for the real
source — homonym disambiguation, API quota errors and malformed responses, all
against fixed payloads so the suite never touches the network.

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
- Scheduled collection so real history builds without manual runs

---

> Academic project — Universidad Politécnica de Yucatán, Q2 2026
