"""Generacion de reportes."""

from folk_analytics.reports.console import (
    render_report,
    render_summary_table,
    render_sparkline,
)

__all__ = ["render_report", "render_summary_table", "render_sparkline"]
