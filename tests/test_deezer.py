"""Tests del cliente de Deezer.

Ninguno toca la red: se usan respuestas fijas capturadas de la API real,
de modo que la suite sigue siendo rapida, reproducible y ejecutable sin
conexion.
"""

import pytest

from folk_analytics.api.base import ArtistNotFoundError, StreamingAPIError
from folk_analytics.api.deezer import (
    PrefetchedDeezerClient,
    match_score,
    normalize,
    parse_search_payload,
    select_best_match,
    to_artist_data,
)


def artist(name, fans, albums=10, artist_id=1):
    """Construye un registro con la forma que devuelve Deezer."""
    return {"id": artist_id, "name": name, "nb_fan": fans, "nb_album": albums}


# Respuesta real de la API al buscar "AURORA": la artista que el usuario
# busca aparece la ultima, y la primera es un homonimo marginal.
AURORA_PAYLOAD = {
    "data": [
        artist("Aurora", 2_486, 13, 7068105),
        artist("Aurora", 9, 6, 79445042),
        artist("Aurora", 9_381, 28, 9028),
        artist("Aurora", 10, 1, 79445052),
        artist("Au Rora", 6, 7, 95257542),
        artist("AURORA", 551_254, 88, 7699874),
    ]
}


class TestNormalize:
    def test_quita_acentos(self):
        assert normalize("Natalia Lafourcáde") == normalize("Natalia Lafourcade")

    def test_ignora_mayusculas(self):
        assert normalize("AURORA") == normalize("aurora")

    def test_colapsa_espacios(self):
        assert normalize("  Iron    Wine  ") == "iron wine"

    def test_equipara_ampersand_y_and(self):
        assert normalize("Iron & Wine") == normalize("Iron and Wine")


class TestMatchScore:
    def test_coincidencia_exacta_puntua_maximo(self):
        assert match_score("AURORA", "aurora") == 3

    def test_ampersand_cuenta_como_exacta(self):
        assert match_score("Iron & Wine", "Iron and Wine") == 3

    def test_prefijo_puntua_dos(self):
        assert match_score("Novo Amor Trio", "Novo Amor") == 2

    def test_contenido_puntua_uno(self):
        assert match_score("The Great Novo Amor Band", "novo amor") == 1

    def test_sin_relacion_puntua_cero(self):
        assert match_score("Bad Bunny", "Sufjan Stevens") == 0


class TestSelectBestMatch:
    def test_elige_la_aurora_correcta_y_no_la_primera(self):
        """El caso que motivo esta logica: con limit=1 Deezer devuelve un
        homonimo de 2.486 seguidores en lugar de la artista buscada."""
        best = select_best_match(AURORA_PAYLOAD["data"], "AURORA")
        assert best["nb_fan"] == 551_254
        assert best["id"] == 7699874

    def test_a_igual_coincidencia_gana_el_mas_seguido(self):
        candidatos = [artist("Aurora", 100, artist_id=1), artist("Aurora", 900, artist_id=2)]
        assert select_best_match(candidatos, "Aurora")["id"] == 2

    def test_la_coincidencia_exacta_gana_a_mas_seguidores(self):
        """Un artista con muchisimos mas fans no debe secuestrar la busqueda
        si su nombre solo contiene parcialmente la consulta."""
        candidatos = [
            artist("Novo Amor Tributo Banda", 5_000_000, artist_id=1),
            artist("Novo Amor", 68_101, artist_id=2),
        ]
        assert select_best_match(candidatos, "Novo Amor")["id"] == 2

    def test_lista_vacia_lanza_no_encontrado(self):
        with pytest.raises(ArtistNotFoundError):
            select_best_match([], "Quien Sea")

    def test_ningun_candidato_relacionado_lanza_no_encontrado(self):
        with pytest.raises(ArtistNotFoundError):
            select_best_match([artist("Bad Bunny", 900)], "Sufjan Stevens")


class TestToArtistData:
    def test_convierte_los_campos(self):
        data = to_artist_data(artist("Novo Amor", 68_101, 23, 5549375))
        assert data.artist_id == "DZ-5549375"
        assert data.name == "Novo Amor"
        assert data.followers == 68_101
        assert data.albums == 23
        assert data.source == "deezer"

    def test_declara_lo_que_deezer_no_publica(self):
        """Un 0 en oyentes mensuales significaria que el artista no tiene
        ninguno, que es falso. Debe constar como no disponible."""
        data = to_artist_data(artist("Novo Amor", 68_101))
        assert not data.is_available("monthly_listeners")
        assert not data.is_available("popularity")
        assert data.is_available("followers")


class TestParseSearchPayload:
    def test_caso_completo(self):
        data = parse_search_payload(AURORA_PAYLOAD, "AURORA")
        assert data.name == "AURORA"
        assert data.followers == 551_254

    def test_error_de_la_api_se_propaga(self):
        payload = {"error": {"type": "Exception", "message": "Quota limit exceeded"}}
        with pytest.raises(StreamingAPIError, match="Quota"):
            parse_search_payload(payload, "AURORA")

    def test_respuesta_sin_datos(self):
        with pytest.raises(ArtistNotFoundError):
            parse_search_payload({"data": []}, "Artista Inexistente")

    def test_respuesta_con_formato_inesperado(self):
        with pytest.raises(StreamingAPIError):
            parse_search_payload("esto no es un diccionario", "AURORA")


class TestPrefetchedClient:
    def test_usa_la_misma_logica_que_la_version_de_consola(self):
        """El cliente que alimenta la web comparte el parseo con el de
        consola; si divergieran, la pagina mostraria otra cosa."""
        client = PrefetchedDeezerClient(AURORA_PAYLOAD)
        data = client.fetch_artist("AURORA")
        assert data.followers == 551_254
        assert data.artist_id == "DZ-7699874"

    def test_no_permite_enumerar_catalogo(self):
        assert PrefetchedDeezerClient({"data": []}).available_artists() == []
