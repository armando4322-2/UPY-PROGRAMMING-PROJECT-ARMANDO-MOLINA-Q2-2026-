"""Tests de la configuracion de logging.

El proyecto se apoya en el log como rastro de auditoria, asi que conviene
comprobar que se inicializa bien y que la degradacion a ASCII —el fallo que
reventaba la salida en cmd.exe de Windows— sigue en su sitio.
"""

import logging

from folk_analytics.logging_setup import (
    _SafeConsoleFormatter,
    _console_supports_unicode,
    get_logger,
    setup_logging,
)


class TestSetup:
    def test_es_idempotente(self):
        """Llamarlo dos veces no debe duplicar manejadores, o cada linea se
        escribiria repetida en el archivo."""
        primero = setup_logging()
        cuantos = len(primero.handlers)
        segundo = setup_logging()
        assert segundo is primero
        assert len(segundo.handlers) == cuantos

    def test_devuelve_el_logger_del_proyecto(self):
        assert setup_logging().name == "folk_analytics"

    def test_no_propaga_al_logger_raiz(self):
        """Si propagara, la configuracion de logging de otro programa que
        importe el paquete duplicaria toda la salida."""
        assert setup_logging().propagate is False


class TestGetLogger:
    def test_crea_hijos_del_logger_del_proyecto(self):
        assert get_logger("api.deezer").name == "folk_analytics.api.deezer"

    def test_el_hijo_hereda_la_configuracion(self):
        setup_logging()
        assert get_logger("prueba").getEffectiveLevel() <= logging.WARNING


class TestSafeConsoleFormatter:
    def _record(self, message):
        return logging.LogRecord("t", logging.INFO, "f", 1, message, None, None)

    def test_deja_pasar_el_texto_normal(self):
        salida = _SafeConsoleFormatter("%(message)s").format(self._record("hola"))
        assert "hola" in salida

    def test_no_lanza_con_caracteres_no_ascii(self):
        """Es el fallo original: una flecha o un emoji reventaban la consola
        de Windows con UnicodeEncodeError."""
        salida = _SafeConsoleFormatter("%(message)s").format(
            self._record("tendencia ↗ CRECIENDO")
        )
        assert "CRECIENDO" in salida

    def test_la_deteccion_de_unicode_devuelve_un_booleano(self):
        assert isinstance(_console_supports_unicode(), bool)
