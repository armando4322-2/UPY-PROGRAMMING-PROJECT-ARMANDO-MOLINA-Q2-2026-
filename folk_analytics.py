"""
Folk Analytics — Streaming Intelligence Agent
Simulates retrieval and analysis of music artist statistics from a streaming platform.
"""

import logging
import os
import random
import uuid
from datetime import datetime, timedelta

# ── Logging setup ─────────────────────────────────────────────────────────────
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "app.log")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s — [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("folk_analytics")

# ── Simulated artist database ──────────────────────────────────────────────────
ARTIST_DB = {
    "aurora":         {"id": "ART-001", "followers": 2_400_000, "monthly_listeners": 1_800_000},
    "iron & wine":    {"id": "ART-002", "followers": 890_000,   "monthly_listeners": 620_000},
    "sufjan stevens": {"id": "ART-003", "followers": 3_100_000, "monthly_listeners": 2_250_000},
    "novo amor":      {"id": "ART-004", "followers": 1_050_000, "monthly_listeners": 780_000},
    "unknown artist": {"id": "ART-999", "followers": 0,         "monthly_listeners": 0},
}

HISTORY_DAYS = 30  # configurable analysis window


def simulate_api_call(artist_name: str) -> dict | None:
    """Simulate a streaming platform API call for artist metrics."""
    logger.info(f'API query initiated for artist: "{artist_name}"')

    # Simulate occasional network hiccup
    if random.random() < 0.12:
        logger.warning(f'API response delayed for "{artist_name}" — retrying...')

    data = ARTIST_DB.get(artist_name.lower())
    if data is None:
        logger.error(f'Artist "{artist_name}" not found in streaming database')
        return None

    if data["followers"] == 0:
        logger.warning(f'Artist "{artist_name}" has no streaming activity on record')

    logger.info(
        f'API response received for "{artist_name}" '
        f'(ID: {data["id"]}, followers: {data["followers"]:,})'
    )
    return data


def generate_play_history(monthly_listeners: int) -> list[int]:
    """Generate simulated daily play counts for the past HISTORY_DAYS days."""
    base = monthly_listeners // HISTORY_DAYS
    history = [max(0, int(base * random.uniform(0.6, 1.4))) for _ in range(HISTORY_DAYS)]
    logger.debug(f"Play history generated: {HISTORY_DAYS} days, base ~{base:,} plays/day")
    return history


def calculate_metrics(history: list[int]) -> dict:
    """Compute average plays and detect trend."""
    avg = sum(history) / len(history)
    first_half = sum(history[: HISTORY_DAYS // 2]) / (HISTORY_DAYS // 2)
    second_half = sum(history[HISTORY_DAYS // 2 :]) / (HISTORY_DAYS // 2)

    change_pct = ((second_half - first_half) / first_half * 100) if first_half else 0

    if change_pct > 5:
        trend = "📈 GROWING"
        logger.info(f"Trend detected: GROWTH ({change_pct:+.1f}% over period)")
    elif change_pct < -5:
        trend = "📉 DECLINING"
        logger.warning(f"Trend detected: DECLINE ({change_pct:+.1f}% over period)")
    else:
        trend = "➡️  STABLE"
        logger.info(f"Trend detected: STABLE ({change_pct:+.1f}% over period)")

    return {"avg_daily": avg, "trend": trend, "change_pct": change_pct}


def validate_artist_input(raw: str) -> str | None:
    """Validate and clean artist input."""
    cleaned = raw.strip()
    if not cleaned:
        logger.warning("Empty artist name received — input rejected")
        return None
    if len(cleaned) > 100:
        logger.warning(f"Artist name too long ({len(cleaned)} chars) — input rejected")
        return None
    logger.debug(f'Input validated: "{cleaned}"')
    return cleaned


def generate_report(session_id: str, artist: str, api_data: dict, metrics: dict) -> None:
    """Print a structured analytics report to the console."""
    logger.info(f"Generating report for session {session_id}")
    print("\n" + "═" * 56)
    print(f"  FOLK ANALYTICS — SESSION {session_id}")
    print("═" * 56)
    print(f"  Artist          : {artist.title()}")
    print(f"  Artist ID       : {api_data['id']}")
    print(f"  Followers       : {api_data['followers']:,}")
    print(f"  Monthly Listeners: {api_data['monthly_listeners']:,}")
    print(f"  Avg Daily Plays : {metrics['avg_daily']:,.0f}")
    print(f"  Trend ({HISTORY_DAYS}d)   : {metrics['trend']} ({metrics['change_pct']:+.1f}%)")
    print(f"  Analysis Window : {HISTORY_DAYS} days")
    print("═" * 56 + "\n")
    logger.info(f"Report output complete for session {session_id}")


def run_agent(artist_queries: list[str]) -> None:
    """Main agent loop: perceive → process → act."""
    logger.info("═" * 50)
    logger.info("Folk Analytics Agent — session started")
    logger.info(f"Analysis window: {HISTORY_DAYS} days | Queries: {len(artist_queries)}")

    for raw_input in artist_queries:
        session_id = str(uuid.uuid4())[:8].upper()
        logger.info(f"--- New query | session={session_id} | input='{raw_input}'")

        # Perceive
        artist = validate_artist_input(raw_input)
        if artist is None:
            continue

        api_data = simulate_api_call(artist)
        if api_data is None:
            logger.error(f"Session {session_id} aborted — artist not found")
            continue

        # Process
        try:
            history = generate_play_history(api_data["monthly_listeners"])
            metrics = calculate_metrics(history)
        except Exception as exc:
            logger.error(f"Processing failed for session {session_id}: {exc}")
            continue

        # Act
        generate_report(session_id, artist, api_data, metrics)

    logger.info("Folk Analytics Agent — session ended")
    logger.info("═" * 50)


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Demo queries (replaces interactive menu for prototype)
    queries = [
        "Aurora",
        "Sufjan Stevens",
        "novo amor",
        "",                 # invalid — empty input
        "Iron & Wine",
        "UNKNOWN ARTIST",   # artist with no activity
        "Bibio",            # artist not in DB → ERROR
    ]
    run_agent(queries)
