"""Configuracion central del proyecto.

Todos los parametros ajustables viven aqui. Ningun otro modulo debe
definir constantes de negocio por su cuenta.
"""

from pathlib import Path

# --- Rutas -------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = PROJECT_ROOT / "logs"

SNAPSHOT_FILE = DATA_DIR / "snapshots.json"
WATCHLIST_FILE = DATA_DIR / "watchlist.json"
LOG_FILE = LOG_DIR / "app.log"

# --- Ventana de analisis -----------------------------------------------------
ANALYSIS_WINDOW_DAYS = 30       # dias hacia atras que considera el analisis
MIN_SNAPSHOTS_FOR_TREND = 4     # minimo de puntos para calcular una tendencia

# --- Umbrales de tendencia ---------------------------------------------------
# Un cambio dentro de +/- este porcentaje se considera ESTABLE.
TREND_THRESHOLD_PCT = 5.0

# --- Umbrales de alerta ------------------------------------------------------
ALERT_DROP_PCT = -15.0          # caida que dispara una alerta
ALERT_SPIKE_PCT = 25.0          # subida que dispara una alerta

# --- Validacion de entrada ---------------------------------------------------
MAX_ARTIST_NAME_LENGTH = 100
MIN_ARTIST_NAME_LENGTH = 1

# --- API ---------------------------------------------------------------------
API_MAX_RETRIES = 3
API_RETRY_BACKOFF_SECONDS = 0.5
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"
