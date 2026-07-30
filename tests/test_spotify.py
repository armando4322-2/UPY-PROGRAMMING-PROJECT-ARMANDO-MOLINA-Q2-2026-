"""Tests del cliente de Spotify.

ALCANCE DE ESTOS TESTS
----------------------
Validan **nuestra** logica de seleccion y conversion sobre la forma de
respuesta que documenta Spotify. No demuestran que esa forma sea correcta:
los payloads de aqui estan construidos a partir de la documentacion, no
capturados de una llamada real, porque el proyecto no dispone de
credenciales. Hasta que alguien ejecute el cliente contra la API de verdad,
esa suposicion sigue sin confirmar.

Se documenta asi a proposito: un test que pasa sobre una suposicion
equivocada da una falsa sensacion de cobertura.
"""

import pytest

from folk_analytics.api.base import ArtistNotFoundError, StreamingAPIError
from folk_analytics.api.spotify import parse_search_payload, to_artist_data


def artist(name, followers, popularity=50, artist_id="id0"):
    """Objeto artista con la forma que documenta Spotify."""
    return {
        "id": artist_id,
        "name": name,
        "followers": {"href": None, "total": followers},
        "popularity": popularity,
        "genres": [],
    }


def payload(*artists):
    return {"artists": {"href": "...", "items": list(artists), "total": len(artists)}}


class TestToArtistData:
    def test_convierte_los_campos(self):
        data = to_artist_data(artist("AURORA", 4_200_000, 74, "0X2BHQ16UqDKA80USdJSFZ"))
        assert data.artist_id == "0X2BHQ16UqDKA80USdJSFZ"
        assert data.name == "AURORA"
        assert data.followers == 4_200_000
        assert data.popularity == 74
        assert data.source == "spotify"

    def test_declara_que_no_publica_oyentes_mensuales(self):
        """Spotify solo expone esa cifra en la web del artista, no en la API.
        Debe constar como no disponible, no como cero."""
        data = to_artist_data(artist("AURORA", 100))
        assert not data.is_available("monthly_listeners")
        assert data.is_available("followers")
        assert data.is_available("popularity")

    def test_tolera_followers_ausente(self):
        record = {"id": "x", "name": "Sin Datos", "popularity": 10}
        assert to_artist_data(record).followers == 0

    def test_tolera_followers_nulo(self):
        record = {"id": "x", "name": "Sin Datos", "followers": None}
        assert to_artist_data(record).followers == 0


class TestParseSearchPayload:
    def test_caso_simple(self):
        data = parse_search_payload(payload(artist("Novo Amor", 480_000)), "Novo Amor")
        assert data.name == "Novo Amor"
        assert data.followers == 480_000

    def test_desambigua_homonimos(self):
        """El mismo fallo que se corrigio en Deezer: quedarse con el primer
        resultado puede devolver un artista distinto del buscado."""
        data = parse_search_payload(
            payload(
                artist("Aurora Band", 1_200, artist_id="a"),
                artist("Aurora Project", 800, artist_id="b"),
                artist("AURORA", 4_200_000, artist_id="c"),
            ),
            "AURORA",
        )
        assert data.artist_id == "c"

    def test_coincidencia_exacta_gana_a_mas_seguidores(self):
        data = parse_search_payload(
            payload(
                artist("Novo Amor Tribute Band", 90_000_000, artist_id="grande"),
                artist("Novo Amor", 480_000, artist_id="correcto"),
            ),
            "Novo Amor",
        )
        assert data.artist_id == "correcto"

    def test_equipara_ampersand_y_and(self):
        data = parse_search_payload(payload(artist("Iron & Wine", 900_000)), "Iron and Wine")
        assert data.name == "Iron & Wine"

    def test_sin_resultados(self):
        with pytest.raises(ArtistNotFoundError):
            parse_search_payload(payload(), "Artista Inexistente")

    def test_ningun_candidato_relacionado(self):
        with pytest.raises(ArtistNotFoundError):
            parse_search_payload(payload(artist("Bad Bunny", 100)), "Sufjan Stevens")

    def test_error_de_la_api_se_propaga(self):
        error = {"error": {"status": 401, "message": "Invalid access token"}}
        with pytest.raises(StreamingAPIError, match="Invalid access token"):
            parse_search_payload(error, "AURORA")

    def test_formato_inesperado(self):
        with pytest.raises(StreamingAPIError):
            parse_search_payload("esto no es un diccionario", "AURORA")

    def test_respuesta_sin_la_clave_artists(self):
        with pytest.raises(ArtistNotFoundError):
            parse_search_payload({}, "AURORA")


class TestSpotifyClientSinCredenciales:
    def test_falla_con_un_mensaje_accionable(self, monkeypatch):
        """Sin credenciales debe explicar como conseguirlas, no reventar."""
        from folk_analytics.api.spotify import SpotifyClient

        monkeypatch.setenv("SPOTIFY_CLIENT_ID", "")
        monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "")
        monkeypatch.setattr(
            "folk_analytics.api.spotify._load_dotenv_if_present", lambda: None
        )

        with pytest.raises(StreamingAPIError, match="developer.spotify.com"):
            SpotifyClient()
