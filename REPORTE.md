# Reporte de estado — Folk Analytics

**Autor:** Armando Karin Molina Marrufo
**Institución:** Universidad Politécnica de Yucatán
**Período:** Q2 2026
**Versión:** 2.5.0 · **Fecha del reporte:** 30 de julio de 2026

---

## 1. Qué es el proyecto

Folk Analytics es un agente de análisis de streaming musical. Recupera métricas
reales de artistas, las acumula en un histórico persistente y detecta tendencias
de crecimiento o declive.

Existe en dos formas, ambas ejecutando **el mismo código**:

- **Consola:** `python run.py`
- **Web:** [armando4322-2.github.io/UPY-PROGRAMMING-PROJECT-ARMANDO-MOLINA-Q2-2026-](https://armando4322-2.github.io/UPY-PROGRAMMING-PROJECT-ARMANDO-MOLINA-Q2-2026-/)
  — el paquete Python corre en el navegador mediante Pyodide (CPython compilado
  a WebAssembly). No es una reimplementación en JavaScript.

## 2. El ciclo del agente

| Fase | Qué hace | Dónde vive |
|------|----------|------------|
| **Percibir** | Valida la entrada, consulta la fuente, recupera el repertorio | `agent.py`, `api/` |
| **Procesar** | Persiste la instantánea y analiza el histórico acumulado | `storage/`, `analytics/` |
| **Actuar** | Genera métricas, tendencias, alertas y el reporte | `analytics/alerts.py`, `reports/` |

Lo que separa esto de un script de consulta es la **memoria**. Cada ejecución
deja un rastro que las siguientes aprovechan. Y desde la versión 2.4.0 el agente
percibe **por su cuenta**: un GitHub Action recolecta métricas cada día sin
intervención.

## 3. Estado actual

| Indicador | Valor |
|-----------|-------|
| Versión | 2.5.0 |
| Tests | **205**, todos en verde |
| Líneas de Python | ~4.800 (1.400 de tests) |
| Módulos del paquete | 23 |
| Artistas en catálogo | **50** — todos con foto e identificador |
| Instantáneas recolectadas | 50 · 1 día |
| Integración continua | Python 3.10, 3.11 y 3.12 |
| Recolección diaria | activa (cron 06:00 UTC) |

## 4. Fuentes de datos

Cada métrica procede de la fuente que **realmente la publica**. Ninguna aparece
vacía.

| Métrica | Fuente | Naturaleza |
|---------|--------|-----------|
| Seguidores | Deezer | directo |
| Álbumes | Deezer | directo |
| Top 10 canciones + preview | Deezer | directo |
| Alcance del top 10 | Deezer | media de rangos reales |
| **Popularidad 0–100** | Deezer | **derivado — ver §5** |
| Foto, ID canónico | Spotify | directo |
| País, tipo, géneros | MusicBrainz | directo |

Además existe una **fuente simulada** que conserva 30 días de histórico
determinista. Sirve para demostrar la detección de tendencias hoy, mientras la
fuente real acumula datos. Está etiquetada como simulada en todas partes.

## 5. Decisiones que conviene poder defender

### 5.1 Spotify no aporta métricas, y es una restricción suya

Con credenciales válidas se comprobó contra la API real el 30-07-2026:

| Endpoint | Resultado |
|----------|-----------|
| `GET /v1/search?type=artist` | `200` — objeto simplificado: `id`, `name`, `images`, `uri` |
| `GET /v1/artists/{id}` | `200` — **las mismas claves**, sin `followers`, `popularity` ni `genres` |
| `GET /v1/artists?ids={id}` | **`403 Forbidden`** |
| `GET /v1/artists/{id}/top-tracks` | **`403 Forbidden`** |
| `GET /v1/artists/{id}/albums` | `200` |

Spotify dejó de exponer métricas a las aplicaciones registradas recientemente.
Usarlo como fuente de análisis devolvería cero seguidores en todos los artistas,
con apariencia de fallo del proyecto. Se reconvirtió en **proveedor de imágenes**,
que es lo único que sigue haciendo bien.

> Los tests que existían antes de esta comprobación estaban escritos contra la
> forma documentada de la respuesta, pasaban en verde y **afirmaban algo falso**.
> Se reescribieron contra la forma observada, incluido un test que verifica que
> esos campos *no* existen: si Spotify los restituye, fallará y avisará.

### 5.2 El índice de popularidad es calculado, no oficial

Ninguna plataforma publica ya una popularidad por artista. Se deriva de un dato
que sí es real: el rango que Deezer asigna a cada canción (0–1.000.000).

```
índice = media(rango de las 10 canciones más populares) / 10.000
```

Se usa la **media y no el máximo** a propósito: un único éxito viral dispararía
el máximo y describiría mal a un artista cuyo repertorio restante apenas se
escucha.

Está etiquetado como **calculado** en el reporte, en la web y en el README. No es
una métrica de plataforma y **no es un número de reproducciones**.

### 5.3 El pasado no existe, así que se mide

Ninguna API pública devuelve los seguidores que un artista tenía hace treinta
días. Se comprobó, no se supuso:

- **Wayback Machine** — ninguna captura de `api.deezer.com`; las páginas de
  artista están archivadas solo como redirecciones vacías
- **ListenBrainz** — responde, pero agrega escuchas por usuario, no en el tiempo,
  y apenas cubre artistas latinos
- **Spotify** — métricas bloqueadas

La única vía honesta es empezar a medir. Un GitHub Action ejecuta
`tools/collect_snapshots.py` cada día y hace commit del punto nuevo. **El
repositorio es la base de datos histórica**, y su historial de commits es la
prueba de que cada cifra se recogió en su fecha y no se generó después.

> Se descartó rellenar el pasado con estimaciones. Presentar cifras inventadas
> junto a cifras medidas es exactamente lo que invalida un análisis.

### 5.4 Desambiguación de artistas

Buscar `AURORA` y quedarse con el primer resultado devuelve un homónimo con
2.486 seguidores en lugar de la artista noruega, que tiene 551.254 y aparece
sexta. Sin desambiguar, el agente habría analizado a la persona equivocada **sin
avisar** — el peor tipo de fallo, porque no lanza ninguna excepción.

`api/matching.py` puntúa por coincidencia de nombre primero y por popularidad
solo como desempate. El mismo criterio se aplica a MusicBrainz, donde `Mora`
resolvía a *Mora Träsk* (música infantil sueca) por delante del reggaetonero
puertorriqueño. Ahora se exige coincidencia exacta; sin ella los géneros se dejan
vacíos: **una descripción vacía es correcta, una equivocada afirma algo falso
sobre una persona real**.

### 5.5 Nada se muestra vacío

Las métricas que ninguna fuente publica se **retiran** de la interfaz en lugar de
imprimirse como «no publicado». Un reporte más corto y enteramente cierto es
mejor que uno más largo con agujeros.

## 6. Limitaciones conocidas

| Limitación | Estado |
|------------|--------|
| Solo 1 día de histórico real | Se resuelve solo: 4 días para las primeras tendencias, 30 para la ventana completa |
| Oyentes mensuales no disponibles | Ninguna API pública los expone. Campo retirado, no falseado |
| 11 de 50 artistas sin géneros | MusicBrainz no los tiene con coincidencia exacta. Se omite antes que arriesgar un dato falso |
| Spotify sin métricas | Restricción de la plataforma, no del proyecto |
| El cron se desactiva a los 60 días sin actividad | Política de GitHub. Se reactiva desde la pestaña Actions |

## 7. Auditoría del 30-07-2026

Revisión completa de código, datos y flujos. **Cuatro defectos encontrados y
corregidos:**

1. **`-a ""` colgaba el programa.** Al comprobarse por veracidad en lugar de
   contra `None`, una cadena vacía caía al menú interactivo y quedaba esperando
   teclado. En un script automatizado, colgado indefinidamente.
2. **Los apóstrofos rompían la coincidencia.** `normalize()` los convertía en
   espacio, así que «El De Las R's» y «El De Las Rs» no coincidían.
3. **Dos módulos sin tests propios.** `matching.py` y `logging_setup.py` tenían
   solo cobertura indirecta. El primero es justo del que depende analizar al
   artista correcto. **33 tests nuevos.**
4. **Imports muertos en seis módulos.** Los que eran reexportaciones
   intencionadas se declaran ahora en `__all__`.

**Verificado además:** sin secretos en el repositorio, `.env` fuera del control
de versiones, sin TODO ni código muerto, catálogo e histórico sin huérfanos ni
duplicados, y `docs/index.html` sincronizado con el paquete.

## 8. Cómo ejecutarlo

```bash
python run.py                              # menú interactivo
python run.py --demo                       # demostración con casos de error
python run.py -a "Caifanes" --source deezer   # datos reales
python -m pytest tests/ -v                 # 205 tests

python tools/build_catalog.py              # regenerar el catálogo
python tools/collect_snapshots.py          # recolectar métricas ahora
python tools/build_web.py                  # regenerar la página
```

## 9. Trabajo futuro

- Acumular los 30 días de histórico real (en curso, automático)
- Exportación de reportes a CSV y HTML
- Notificaciones cuando una alerta crítica se dispare
- Migrar el almacén a SQLite si el histórico crece

---

> El diario de ingeniería completo, con cada decisión y cada defecto fechado,
> está en [`logs/development.log`](logs/development.log).
