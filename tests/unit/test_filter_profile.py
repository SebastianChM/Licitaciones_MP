"""Tests unitarios para core.filter_profile (entidades de dominio inmutables)."""
import pytest

from core.filter_profile import (
    EXCLUIR_KEYS,
    INCLUIR_KEYS,
    EquipoInfo,
    FilterProfile,
)

# ---------------------------------------------------------------------------
# EquipoInfo
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestEquipoInfo:

    def test_construccion_valida(self):
        e = EquipoInfo(codigo="TELECOM", nombre="Telecom", hoja_filtros="06-Telecom")
        assert e.codigo == "TELECOM"
        assert e.activo is True
        assert e.descripcion == ""

    def test_codigo_vacio_falla(self):
        with pytest.raises(ValueError, match="codigo"):
            EquipoInfo(codigo="", nombre="x", hoja_filtros="06-X")

    def test_codigo_solo_whitespace_falla(self):
        with pytest.raises(ValueError, match="codigo"):
            EquipoInfo(codigo="   ", nombre="x", hoja_filtros="06-X")

    def test_hoja_vacia_falla(self):
        with pytest.raises(ValueError, match="hoja_filtros"):
            EquipoInfo(codigo="ARQ", nombre="Arq", hoja_filtros="")

    def test_inmutable(self):
        e = EquipoInfo(codigo="X", nombre="x", hoja_filtros="06-X")
        with pytest.raises(Exception):  # FrozenInstanceError
            e.codigo = "Y"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# FilterProfile
# ---------------------------------------------------------------------------

def _equipo_fake() -> EquipoInfo:
    return EquipoInfo(codigo="TEST", nombre="Test", hoja_filtros="06-Test")


@pytest.mark.unit
class TestFilterProfile:

    def test_construccion_minima(self):
        p = FilterProfile(
            equipo=_equipo_fake(),
            incluir={"nombre": ["consultoria"]},
            excluir={},
        )
        assert p.total_incluir == 1
        assert p.total_excluir == 0
        assert not p.esta_vacio()

    def test_perfil_vacio_detectado(self):
        p = FilterProfile(equipo=_equipo_fake(), incluir={}, excluir={})
        assert p.esta_vacio()

    def test_keys_incluir_desconocidas_falla(self):
        with pytest.raises(ValueError, match="incluir.*desconocidas"):
            FilterProfile(
                equipo=_equipo_fake(),
                incluir={"clave_inventada": ["x"]},
                excluir={},
            )

    def test_keys_excluir_desconocidas_falla(self):
        with pytest.raises(ValueError, match="excluir.*desconocidas"):
            FilterProfile(
                equipo=_equipo_fake(),
                incluir={},
                excluir={"clave_inventada": ["x"]},
            )

    def test_todas_las_keys_validas_pasan(self):
        p = FilterProfile(
            equipo=_equipo_fake(),
            incluir={k: [] for k in INCLUIR_KEYS},
            excluir={k: [] for k in EXCLUIR_KEYS},
            bypass=("a", "b"),
            exclusion_dura=("x",),
        )
        assert p.resumen() == {
            "total_incluir": 0,
            "total_excluir": 0,
            "bypass": 2,
            "exclusion_dura": 1,
            "intencion_requerida": 0,
            "intencion_vetada": 0,
        }

    def test_inmutabilidad(self):
        p = FilterProfile(equipo=_equipo_fake(), incluir={}, excluir={})
        with pytest.raises(Exception):
            p.bypass = ("nuevo",)  # type: ignore[misc]

    def test_resumen_formato(self):
        p = FilterProfile(
            equipo=_equipo_fake(),
            incluir={"nombre": ["a", "b", "c"]},
            excluir={"nombre": ["x"]},
            bypass=("y",),
            exclusion_dura=(),
        )
        r = p.resumen()
        assert r["total_incluir"] == 3
        assert r["total_excluir"] == 1
        assert r["bypass"] == 1
        assert r["exclusion_dura"] == 0
