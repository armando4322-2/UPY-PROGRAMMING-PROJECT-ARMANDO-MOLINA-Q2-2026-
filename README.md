# Folk Analytics — Streaming Intelligence Agent

**Autor:** Armando Molina  
**Institución:** Universidad Politécnica de Yucatán (UPY)  
**Período:** Q2 2026

---

## What is Folk Analytics?

Folk Analytics is a console-based data analysis agent that simulates the retrieval of music artist statistics from a streaming platform API. The user enters an artist name or ID, and the system autonomously handles the full pipeline: API query, data processing, and formatted report generation.

## What it does

- Retrieves artist metrics: total plays, followers, monthly listeners, and recent activity
- Calculates daily play averages over a configurable time period
- Detects growth or decline trends based on historical data
- Assigns unique IDs to each query session for traceability
- Validates all user inputs with numeric menus and error handling
- Outputs a clean, structured report directly in the console

## Why it exists

Independent and emerging artists — especially those from underrepresented regions or genres rarely have access to the analytics tools major labels use. Folk Analytics democratizes that access: no account, no subscription, no third-party dashboard. Just an artist name and a report.

## Agent alignment

The system follows a classic agent loop: **perceive → process → act**. It perceives streaming data via simulated API calls, processes it autonomously (averages, trend detection, ranking), and acts by producing structured analytical output. Future versions can extend this to continuous monitoring with threshold-based alerts.

## Tech

Built in **PSeInt** (pseudocode) as an academic prototype. Designed to be ported to Python with real Spotify API integration.

---

> Proyecto académico — UPY Q2 2026
