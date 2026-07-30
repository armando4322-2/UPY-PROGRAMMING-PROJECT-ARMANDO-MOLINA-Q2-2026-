"""Tests de validacion de entrada."""

import pytest

from folk_analytics.agent import InvalidInputError, validate_artist_name


class TestValidateArtistName:
    def test_acepta_un_nombre_normal(self):
        assert validate_artist_name("AURORA") == "AURORA"

    def test_recorta_espacios_sobrantes(self):
        assert validate_artist_name("  Novo Amor  ") == "Novo Amor"

    def test_colapsa_espacios_internos(self):
        assert validate_artist_name("Iron   &    Wine") == "Iron & Wine"

    def test_rechaza_cadena_vacia(self):
        with pytest.raises(InvalidInputError):
            validate_artist_name("")

    def test_rechaza_solo_espacios(self):
        with pytest.raises(InvalidInputError):
            validate_artist_name("      ")

    def test_rechaza_none(self):
        with pytest.raises(InvalidInputError):
            validate_artist_name(None)

    def test_rechaza_nombre_demasiado_largo(self):
        with pytest.raises(InvalidInputError):
            validate_artist_name("x" * 101)

    def test_acepta_el_maximo_exacto(self):
        assert len(validate_artist_name("x" * 100)) == 100


class TestEntradaPorLineaDeComandos:
    """El punto de entrada tambien valida, no solo el nucleo."""

    def test_artista_vacio_no_cae_al_menu_interactivo(self):
        """`-a ""` es una entrada invalida. Antes se colaba al menu y el
        programa se quedaba esperando teclado, que en un script automatizado
        significa colgarse."""
        from folk_analytics.__main__ import main

        assert main(["-a", "", "--quiet"]) == 2

    def test_artista_solo_espacios(self):
        from folk_analytics.__main__ import main

        assert main(["-a", "   ", "--quiet"]) == 2

    def test_artista_demasiado_largo(self):
        from folk_analytics.__main__ import main

        assert main(["-a", "x" * 150, "--quiet"]) == 2
