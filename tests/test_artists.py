"""Tests del catalogo de artistas destacados."""

import json

import pytest

from folk_analytics.api.artists import CatalogArtist, suggest


class TestDescription:
    """La descripcion se compone solo con datos reales de MusicBrainz.

    Nada esta escrito a mano sobre ningun artista, de modo que no puede
    afirmarse nada falso: si un dato falta, simplemente no aparece.
    """

    def test_persona_con_pais_y_generos(self):
        artist = CatalogArtist(
            name="Peso Pluma", country="MX", kind="Person",
            genres=("regional mexicano", "corrido tumbado"), began="1999-06-15",
        )
        assert artist.description == (
            "Artista mexicano · regional mexicano, corrido tumbado · n. 1999"
        )

    def test_grupo_dice_grupo_y_activo_desde(self):
        artist = CatalogArtist(
            name="NewJeans", country="KR", kind="Group",
            genres=("k-pop",), began="2022-07-22",
        )
        assert artist.description == "Grupo surcoreano · k-pop · activo desde 2022"

    def test_concuerda_el_genero_gramatical(self):
        artist = CatalogArtist(name="Mon Laferte", country="MX", kind="Person", gender="female")
        assert "mexicana" in artist.description

    def test_sin_datos_no_inventa_nada(self):
        assert CatalogArtist(name="Desconocido").description == "Artista"

    def test_pais_no_mapeado_se_omite_en_lugar_de_mostrar_el_codigo(self):
        artist = CatalogArtist(name="X", country="ZZ", kind="Person")
        assert "ZZ" not in artist.description

    def test_limita_a_tres_generos(self):
        artist = CatalogArtist(name="X", genres=("a", "b", "c", "d", "e"))
        assert "d" not in artist.description

    def test_ano_truncado_a_cuatro_cifras(self):
        artist = CatalogArtist(name="X", kind="Person", began="1985-10-08")
        assert "n. 1985" in artist.description


class TestSuggest:
    @pytest.fixture(autouse=True)
    def catalogo_de_prueba(self, monkeypatch, tmp_path):
        from folk_analytics.api import artists as module

        data = {"artists": [
            {"name": "Bad Bunny"}, {"name": "Bruno Mars"},
            {"name": "Peso Pluma"}, {"name": "Black Eyed Peas"},
        ]}
        path = tmp_path / "catalog.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        monkeypatch.setattr(module, "CATALOG_FILE", path)
        module.load_catalog.cache_clear()
        yield
        module.load_catalog.cache_clear()

    def test_sugiere_por_prefijo(self):
        assert suggest("bad") == ["Bad Bunny"]

    def test_los_prefijos_van_antes_que_las_coincidencias_internas(self):
        """Al teclear 'b' el usuario espera primero lo que empieza por 'b'."""
        result = suggest("b")
        assert result[0].lower().startswith("b")

    def test_ignora_mayusculas_y_acentos(self):
        assert "Peso Pluma" in suggest("PESO")

    def test_prefijo_vacio_no_sugiere_nada(self):
        assert suggest("") == []
        assert suggest("   ") == []

    def test_respeta_el_limite(self):
        assert len(suggest("b", limit=1)) == 1

    def test_sin_coincidencias(self):
        assert suggest("zzzzz") == []


class TestCatalogoReal:
    def test_el_catalogo_del_repositorio_esta_completo(self):
        """Comprueba el archivo versionado: 26 artistas, todos con foto."""
        from folk_analytics.api.artists import load_catalog

        catalog = load_catalog()
        assert len(catalog) == 26
        assert all(a.image for a in catalog), "hay artistas sin foto"
        assert all(a.deezer_id for a in catalog), "hay artistas sin id de Deezer"

    def test_no_hay_nombres_repetidos(self):
        from folk_analytics.api.artists import catalog_names

        names = catalog_names()
        assert len(names) == len(set(names))
