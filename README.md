# Folk Analytics — Streaming Intelligence Agent

**Autor:** Armando Karin Molina Marrufo
**Institución:** Universidad Politécnica de Yucatán (UPY)
**Período:** Q2 2026

---

## Qué es Folk Analytics

Folk Analytics es un agente de análisis de datos que recupera métricas de artistas
musicales, las acumula en un histórico persistente y detecta tendencias reales de
crecimiento o declive. El usuario introduce el nombre de un artista y el sistema
se encarga del resto: consulta la fuente, guarda la instantánea, analiza la serie
temporal y emite un reporte con alertas.

## Por qué existe

Los artistas independientes —sobre todo los de regiones o géneros poco
representados— rara vez tienen acceso a las herramientas de analítica que usan
los sellos grandes. Folk Analytics democratiza ese acceso: sin cuenta, sin
suscripción y sin dashboards de terceros. Solo un nombre y un reporte.

## El ciclo del agente

El sistema implementa el ciclo clásico **percibir → procesar → actuar**:

| Fase | Qué hace | Dónde vive |
|------|----------|------------|
| **Percibir** | Valida la entrada y consulta la fuente de datos | `agent.py`, `api/` |
| **Procesar** | Persiste la instantánea y analiza el histórico acumulado | `storage/`, `analytics/` |
| **Actuar** | Genera métricas, tendencias, alertas y el reporte final | `analytics/alerts.py`, `reports/` |

La diferencia con un script de consulta puntual es la **memoria**: cada ejecución
deja un rastro en disco que las siguientes aprovechan. Sin histórico no hay
tendencia posible, solo ruido.

## Qué hace

- Recupera métricas de artistas: seguidores, oyentes mensuales y popularidad
- Acumula un histórico persistente en JSON, sin duplicar instantáneas del mismo día
- Detecta tendencias combinando **cambio porcentual** entre mitades de la ventana
  y **regresión lineal** por mínimos cuadrados, reportando el R² como medida de confianza
- Emite alertas por umbrales configurables: caídas pronunciadas, crecimientos
  excepcionales y series demasiado ruidosas para ser fiables
- Gestiona una *watchlist* de artistas bajo vigilancia
- Valida toda entrada del usuario con menús numéricos y manejo de errores
- Registra un rastro de auditoría completo en `logs/app.log`

## Instalación

Requiere **Python 3.10 o superior**. El núcleo funciona solo con la librería
estándar; las dependencias externas son opcionales.

```bash
git clone https://github.com/armando4322-2/UPY-PROGRAMMING-PROJECT-ARMANDO-MOLINA-Q2-2026-.git
cd UPY-PROGRAMMING-PROJECT-ARMANDO-MOLINA-Q2-2026-
pip install -r requirements.txt
```

## Uso

```bash
python run.py                    # menú interactivo
python run.py --demo             # demostración no interactiva
python run.py -a "Novo Amor"     # análisis directo de un artista
python run.py --metric popularity --verbose
python run.py --source spotify   # usa la API real (requiere credenciales)
```

También funciona como módulo: `python -m folk_analytics --demo`

### Ejemplo de salida

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

## Fuentes de datos

El proyecto programa contra una interfaz (`StreamingClient`), no contra una
implementación concreta. Eso permite cambiar de fuente sin tocar el resto del código.

### Cliente simulado (por defecto)

Genera series temporales **deterministas y coherentes**: para un artista y una
fecha dados siempre devuelve el mismo valor, siguiendo el modelo

```
valor(día) = base × (1 + tasa_crecimiento) ^ días_desde_hoy × ruido(día)
```

donde `ruido(día)` se deriva del identificador del artista y de la fecha del
calendario. Esto es lo que hace que las tendencias detectadas signifiquen algo.
No requiere red ni credenciales.

### Cliente de Spotify

Usa el *Client Credentials Flow* de la API oficial. Para activarlo:

1. Entra a [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. **Create app** → Redirect URI: `http://localhost:8888/callback`
3. Copia `.env.example` a `.env` y rellena tus credenciales

> **Nota honesta sobre los datos:** la API pública de Spotify **no expone oyentes
> mensuales** —ese dato solo aparece en la interfaz web. Con esta fuente el
> análisis se apoya en `followers` y en el índice `popularity` (0–100), que sí
> están disponibles oficialmente. Documentarlo es preferible a inventar el número.

## Estructura del proyecto

```
folk_analytics/
├── __main__.py          # punto de entrada y argumentos de línea de comandos
├── agent.py             # el ciclo percibir → procesar → actuar
├── cli.py               # menú interactivo y modo demostración
├── config.py            # todos los parámetros ajustables
├── logging_setup.py     # logging a archivo y consola, con fallback ASCII
├── api/
│   ├── base.py          # interfaz StreamingClient y jerarquía de excepciones
│   ├── models.py        # ArtistData
│   ├── simulated.py     # fuente sintética determinista
│   └── spotify.py       # fuente real
├── analytics/
│   ├── metrics.py       # estadística descriptiva
│   ├── trends.py        # detección de tendencias
│   └── alerts.py        # motor de alertas por umbrales
├── storage/
│   └── json_store.py    # histórico y watchlist en JSON
└── reports/
    └── console.py       # renderizado del reporte
tests/                   # 85 tests con pytest
```

## Tests

```bash
python -m pytest tests/ -v
```

La suite cubre validación de entrada, matemática de tendencias, persistencia,
motor de alertas y flujo completo del agente, incluidos los casos límite:
series constantes, división entre cero, ventanas de longitud impar, archivos
de histórico corruptos y agotamiento de reintentos.

## Configuración

Todos los parámetros ajustables viven en `folk_analytics/config.py`:

| Parámetro | Por defecto | Qué controla |
|-----------|-------------|--------------|
| `ANALYSIS_WINDOW_DAYS` | 30 | Días que abarca el análisis |
| `MIN_SNAPSHOTS_FOR_TREND` | 4 | Puntos mínimos para calcular tendencia |
| `TREND_THRESHOLD_PCT` | 5.0 | Margen que se considera estable |
| `ALERT_DROP_PCT` | −15.0 | Caída que dispara alerta crítica |
| `ALERT_SPIKE_PCT` | 25.0 | Subida que dispara alerta informativa |

## Trabajo futuro

- Exportación de reportes a CSV y HTML
- Monitoreo programado con notificaciones
- Comparación entre artistas y ranking por género
- Migración del almacén a SQLite si el histórico crece

---

> Proyecto académico — Universidad Politécnica de Yucatán, Q2 2026
