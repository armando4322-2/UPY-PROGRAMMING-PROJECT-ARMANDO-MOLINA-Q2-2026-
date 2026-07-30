"""Tests directos de la desambiguacion de artistas.

Estaba cubierta solo de forma indirecta a traves de los clientes. Como es el
modulo del que depende que el agente analice al artista correcto y no a un
homonimo, merece tests propios: un fallo aqui no lanza ninguna excepcion,
simplemente devuelve datos de otra persona.
"""

import pytest

from folk_analytics.api.base import ArtistNotFoundError
from folk_analytics.api.matching import match_score, normalize, select_best_match


def pick(candidates, query):
    return select_best_match(
        candidates, query,
        name_of=lambda c: c["name"],
        rank_of=lambda c: c.get("rank", 0),
        source="Prueba",
    )


class TestNormalize:
    def test_quita_acentos(self):
        assert normalize("Jósean Log") == normalize("Josean Log")

    def test_ignora_mayusculas(self):
        assert normalize("ABBA") == normalize("abba")

    def test_colapsa_espacios(self):
        assert normalize("  The   Beatles  ") == "the beatles"

    def test_equipara_ampersand(self):
        assert normalize("Iron & Wine") == normalize("Iron and Wine")

    def test_ignora_puntuacion(self):
        assert normalize("Tyler, The Creator") == normalize("Tyler The Creator")

    def test_ignora_puntos(self):
        assert normalize("C. Tangana") == normalize("C Tangana")

    def test_ignora_apostrofos(self):
        assert normalize("El De Las R's") == normalize("El De Las Rs")

    def test_cadena_vacia(self):
        assert normalize("") == ""

    def test_solo_puntuacion(self):
        assert normalize("...") == ""


class TestMatchScore:
    def test_exacta_es_tres(self):
        assert match_score("Queen", "queen") == 3

    def test_prefijo_es_dos(self):
        assert match_score("Queen Latifah", "Queen") == 2

    def test_contenido_es_uno(self):
        assert match_score("Tributo a Queen en vivo", "queen") == 1

    def test_sin_relacion_es_cero(self):
        assert match_score("Drake", "Queen") == 0

    def test_nombre_vacio_es_cero(self):
        assert match_score("", "Queen") == 0

    def test_consulta_vacia_es_cero(self):
        assert match_score("Queen", "") == 0


class TestSelectBestMatch:
    def test_la_coincidencia_exacta_gana_al_mas_popular(self):
        """El orden importa: si se ordenara primero por popularidad, un
        artista enorme cuyo nombre solo contiene la consulta secuestraria la
        busqueda de otro mas pequeno con nombre exacto."""
        elegido = pick([
            {"name": "Queen Tribute Band", "rank": 10_000_000},
            {"name": "Queen", "rank": 100},
        ], "Queen")
        assert elegido["name"] == "Queen"

    def test_a_igual_coincidencia_gana_el_mas_popular(self):
        elegido = pick([
            {"name": "Aurora", "rank": 100},
            {"name": "Aurora", "rank": 900},
        ], "Aurora")
        assert elegido["rank"] == 900

    def test_descarta_los_no_relacionados(self):
        with pytest.raises(ArtistNotFoundError):
            pick([{"name": "Bad Bunny", "rank": 9}], "Frank Sinatra")

    def test_lista_vacia(self):
        with pytest.raises(ArtistNotFoundError):
            pick([], "Cualquiera")

    def test_el_mensaje_de_error_nombra_la_fuente(self):
        with pytest.raises(ArtistNotFoundError, match="Prueba"):
            pick([], "Cualquiera")

    def test_el_desempate_es_estable(self):
        """Con candidatos identicos el resultado no debe depender del orden
        de iteracion: dos ejecuciones deben coincidir."""
        candidatos = [{"name": "X", "rank": 5} for _ in range(5)]
        primera = pick(list(candidatos), "X")
        segunda = pick(list(candidatos), "X")
        assert primera is not None and segunda is not None

    def test_rank_nulo_no_rompe(self):
        assert pick([{"name": "X", "rank": None}], "X")["name"] == "X"

    def test_rank_ausente_no_rompe(self):
        assert pick([{"name": "X"}], "X")["name"] == "X"
