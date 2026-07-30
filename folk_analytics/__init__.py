"""
Folk Analytics - Streaming Intelligence Agent
=============================================

Agente de analisis de datos que recupera, procesa y reporta metricas de
artistas musicales siguiendo el ciclo clasico de agente:

    percibir  ->  procesar  ->  actuar

Autor       : Armando Karin Molina Marrufo
Institucion : Universidad Politecnica de Yucatan (UPY)
Periodo     : Q2 2026
"""

__version__ = "2.5.0"
__author__ = "Armando Karin Molina Marrufo"

from folk_analytics.agent import FolkAnalyticsAgent

__all__ = ["FolkAnalyticsAgent", "__version__", "__author__"]
