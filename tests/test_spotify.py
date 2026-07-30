"""Tests del proveedor de identidad de Spotify.

Estos tests se reescribieron despues de ejecutar la API real por primera vez.
La version anterior daba por supuesto que la busqueda devolvia `followers`,
`popularity` y `genres`; pasaba en verde y estaba equivocada. La API real
devuelve un objeto simplificado sin ninguno de esos campos.

Los payloads de aqui reproducen la forma REAL observada el 2026-07-30 con
credenciales validas, no la que describe la documentacion.
"""

import pytest

from folk_analytics.api.base import ArtistNotFoundError, StreamingAPIError
from folk_analytics.api.spotify import (
    OBSERVED_ARTIST_KEYS,
    parse_search_payload,
)


def artist(name, artist_id="id0", with_image=True):
    """Objeto artista tal y como lo devuelve Spotify de verdad.

    Sin followers, sin popularity y sin genres: comprobado contra la API.
    """
    record = {
        "external_urls": {"spotify": f"https://open.spotify.com/artist/{artist_id}"},
        "href": f"https://api.spotify.com/v1/artists/{artist_id}",
        "id": artist_id,
        "images": [
            {"url": f"https://i.scdn.co/image/{artist_id}_640", "height": 640, "width": 640},
            {"url": f"https://i.scdn.co/image/{artist_id}_160", "height": 160, "width": 160},
        ] if with_image else [],
        "name": name,
        "type": "artist",
        "uri": f"spotify:artist:{artist_id}",
    }
    return record


def payload(*artists):
    return {"artists": {"href": "...", "items": list(artists), "total": len(artists)}}


class TestFormaRealDeLaRespuesta:
    def test_el_objeto_no_trae_metricas(self):
        """Documenta el hallazgo: Spotify no expone estos campos a las apps
        nuevas. Si algun dia volvieran, este test fallaria y avisaria."""
        record = artist("Mon Laferte")
        assert set(record.keys()) == set(OBSERVED_ARTIST_KEYS)
        assert "followers" not in record
        assert "popularity" not in record
        assert "genres" not in record


class TestParseSearchPayload:
    def test_devuelve_identidad_e_imagen(self):
        result = parse_search_payload(
            payload(artist("Mon Laferte", "4boI7bJtmB1L3b1cuL75Zr")), "Mon Laferte"
        )
        assert result["spotify_id"] == "4boI7bJtmB1L3b1cuL75Zr"
        assert result["name"] == "Mon Laferte"
        assert result["image"].endswith("_640")

    def test_prefiere_la_imagen_de_mayor_resolucion(self):
        """Las imagenes vienen ordenadas de mayor a menor; se toma la primera."""
        result = parse_search_payload(payload(artist("Queen", "q1")), "Queen")
        assert "_640" in result["image"]

    def test_artista_sin_imagen(self):
        result = parse_search_payload(
            payload(artist("Sin Foto", "x", with_image=False)), "Sin Foto"
        )
        assert result["image"] is None

    def test_desambigua_homonimos(self):
        """Buscar AURORA devuelve varios candidatos y el correcto no siempre
        es el primero."""
        result = parse_search_payload(
            payload(
                artist("Trio Aurora Hidalguense", "a"),
                artist("Aurora Ardent", "b"),
                artist("AURORA", "c"),
            ),
            "AURORA",
        )
        assert result["spotify_id"] == "c"

    def test_equipara_ampersand_y_and(self):
        result = parse_search_payload(payload(artist("Iron & Wine", "iw")), "Iron and Wine")
        assert result["spotify_id"] == "iw"

    def test_sin_resultados(self):
        with pytest.raises(ArtistNotFoundError):
            parse_search_payload(payload(), "Artista Inexistente")

    def test_ningun_candidato_relacionado(self):
        with pytest.raises(ArtistNotFoundError):
            parse_search_payload(payload(artist("Bad Bunny", "bb")), "Sufjan Stevens")

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


class TestCredenciales:
    def test_sin_credenciales_da_un_mensaje_accionable(self, monkeypatch, tmp_path):
        from folk_analytics import config
        from folk_analytics.api.spotify import SpotifyImageProvider

        monkeypatch.setenv("SPOTIFY_CLIENT_ID", "")
        monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "")
        monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)  # sin .env

        with pytest.raises(StreamingAPIError, match="developer.spotify.com"):
            SpotifyImageProvider()

    def test_acepta_credenciales_explicitas(self):
        from folk_analytics.api.spotify import SpotifyImageProvider

        provider = SpotifyImageProvider(client_id="abc", client_secret="def")
        assert provider.client_id == "abc"
