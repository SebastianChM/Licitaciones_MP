"""Tests para el Intent Gate (invariante de negocio MP).

Cubre:
    - IntencionGlobal habilitado/deshabilitado.
    - Carga de la hoja 01-Intencion_Global desde el PIVOT (presente y ausente).
    - _aplicar_intencion con las 4 ramas semánticas:
        1) Sin intent global → todas REVISAR (legacy).
        2) Vetada matchea → fila descartada.
        3) Requerida matchea → fila marcada ALTA.
        4) Ni vetada ni requerida → fila marcada REVISAR.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import openpyxl
import pandas as pd
import pytest

from core.filter_profile import EquipoInfo, FilterProfile, IntencionGlobal
from core.profile_loader import HOJA_INTENCION_GLOBAL, ProfileLoader
from etapas.etapa2 import FiltradorLicitaciones

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def equipo() -> EquipoInfo:
    return EquipoInfo(codigo="TEST", nombre="Test", hoja_filtros="06-Test")


def _profile(equipo: EquipoInfo, *, requerida=(), vetada=()) -> FilterProfile:
    return FilterProfile(
        equipo=equipo,
        incluir={"nombre": (), "nivel1": (), "nivel2": (), "nivel3": ()},
        excluir=dict.fromkeys(("nombre", "nivel1", "nivel2", "nivel3", "generico", "componente", "organismo", "valor"), ()),
        intencion_global=IntencionGlobal(requerida=tuple(requerida), vetada=tuple(vetada)),
    )


def _df(*nombres: str) -> pd.DataFrame:
    return pd.DataFrame({
        "Nombre Adquisición (norm)": list(nombres),
        "Descripción (norm)": [""] * len(nombres),
    })


# ---------------------------------------------------------------------------
# IntencionGlobal entity
# ---------------------------------------------------------------------------

class TestIntencionGlobal:
    def test_default_deshabilitado(self):
        ig = IntencionGlobal()
        assert ig.habilitado is False
        assert ig.requerida == ()
        assert ig.vetada == ()

    def test_habilitado_si_alguna_lista_no_vacia(self):
        assert IntencionGlobal(requerida=("INGENIERIA",)).habilitado is True
        assert IntencionGlobal(vetada=("ADQUISICION",)).habilitado is True

    def test_inmutable(self):
        ig = IntencionGlobal(requerida=("INGENIERIA",))
        with pytest.raises((AttributeError, TypeError)):
            ig.requerida = ("OTRA",)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ProfileLoader.cargar_intencion_global
# ---------------------------------------------------------------------------

class TestCargarIntencionGlobal:
    def test_hoja_ausente_devuelve_vacio(self, tmp_path: Path):
        pivot = tmp_path / "pivot_sin_intent.xlsx"
        wb = openpyxl.Workbook()
        wb.active.title = "00-Equipos"
        wb.save(pivot)

        loader = ProfileLoader(pivot)
        ig = loader.cargar_intencion_global()
        assert ig.habilitado is False

    def test_hoja_presente_se_carga(self, tmp_path: Path):
        pivot = tmp_path / "pivot_con_intent.xlsx"
        wb = openpyxl.Workbook()
        wb.active.title = "00-Equipos"
        ws = wb.create_sheet(HOJA_INTENCION_GLOBAL)
        ws["A1"] = "INTENCION_REQUERIDA"
        ws["B1"] = "INTENCION_VETADA"
        ws["A2"] = "INGENIERIA"
        ws["A3"] = "CONSULTORIA"
        ws["B2"] = "ADQUISICION DE"
        ws["B3"] = "MANTENCION"
        wb.save(pivot)

        loader = ProfileLoader(pivot)
        ig = loader.cargar_intencion_global()
        assert ig.habilitado is True
        assert "INGENIERIA" in ig.requerida
        assert "CONSULTORIA" in ig.requerida
        assert "ADQUISICION DE" in ig.vetada
        assert "MANTENCION" in ig.vetada

    def test_cache_no_relee_pivot(self, tmp_path: Path):
        pivot = tmp_path / "pivot.xlsx"
        wb = openpyxl.Workbook()
        wb.active.title = "00-Equipos"
        wb.save(pivot)
        loader = ProfileLoader(pivot)
        ig1 = loader.cargar_intencion_global()
        ig2 = loader.cargar_intencion_global()
        assert ig1 is ig2  # mismo objeto = cached


# ---------------------------------------------------------------------------
# _aplicar_intencion (lógica del intent gate)
# ---------------------------------------------------------------------------

class TestAplicarIntencion:
    @pytest.fixture
    def filtrador(self) -> FiltradorLicitaciones:
        f = FiltradorLicitaciones()
        # Inyectamos logger mock — no necesitamos pipeline completo en estos tests.
        f._logger = MagicMock()
        return f

    def test_deshabilitado_marca_todas_NA(self, filtrador, equipo):
        filtrador.profile = _profile(equipo)  # intent global vacío
        df = _df("CUALQUIER COSA", "OTRA")
        out = filtrador._aplicar_intencion(df)
        assert len(out) == 2
        assert all(out["Nivel Confianza"] == "N/A")

    def test_vetada_descarta_fila(self, filtrador, equipo):
        filtrador.profile = _profile(equipo, vetada=("ADQUISICION DE",))
        df = _df("ADQUISICION DE COMPUTADORES", "CONSULTORIA TECNICA")
        out = filtrador._aplicar_intencion(df)
        assert len(out) == 1
        assert "CONSULTORIA" in out["Nombre Adquisición (norm)"].iloc[0]

    def test_requerida_marca_ALTA(self, filtrador, equipo):
        filtrador.profile = _profile(
            equipo,
            requerida=("INGENIERIA", "CONSULTORIA"),
        )
        df = _df("INGENIERIA CONCEPTUAL DE RED", "ALGO AMBIGUO")
        out = filtrador._aplicar_intencion(df)
        assert out["Nivel Confianza"].tolist() == ["ALTA", "REVISAR"]

    def test_combinado_veta_y_etiqueta(self, filtrador, equipo):
        filtrador.profile = _profile(
            equipo,
            requerida=("DISENO",),
            vetada=("MANTENCION",),
        )
        df = _df(
            "MANTENCION DE EQUIPOS",          # vetada → descartada
            "DISENO DE PUENTE",                # requerida → ALTA
            "SERVICIO DE INTERNET",            # ni una ni otra → REVISAR
        )
        out = filtrador._aplicar_intencion(df)
        assert len(out) == 2
        assert out["Nivel Confianza"].tolist() == ["ALTA", "REVISAR"]

    def test_word_boundary_evita_falso_positivo_en_vetada(self, filtrador, equipo):
        """'COMPRA DE' no debe matchear dentro de 'INCOMPRABLE' o similares."""
        filtrador.profile = _profile(
            equipo,
            vetada=("COMPRA DE",),
            requerida=("INGENIERIA",),
        )
        df = _df("INGENIERIA DE OBRAS", "COMPRA DE EQUIPOS")
        out = filtrador._aplicar_intencion(df)
        assert len(out) == 1
        assert out["Nivel Confianza"].iloc[0] == "ALTA"

    def test_intencion_evalua_descripcion_no_solo_nombre(self, filtrador, equipo):
        filtrador.profile = _profile(equipo, vetada=("MANTENCION",))
        df = pd.DataFrame({
            "Nombre Adquisición (norm)": ["SERVICIO ABC"],
            "Descripción (norm)": ["INCLUYE MANTENCION DE EQUIPOS"],
        })
        out = filtrador._aplicar_intencion(df)
        assert len(out) == 0  # vetada matcheó en descripción

    def test_df_vacio_no_falla(self, filtrador, equipo):
        filtrador.profile = _profile(equipo, requerida=("INGENIERIA",))
        out = filtrador._aplicar_intencion(_df())
        assert len(out) == 0

    def test_stats_se_actualizan(self, filtrador, equipo):
        filtrador.profile = _profile(
            equipo,
            requerida=("INGENIERIA",),
            vetada=("ADQUISICION",),
        )
        df = _df(
            "ADQUISICION X",
            "INGENIERIA Y",
            "ALGO Z",
        )
        filtrador._aplicar_intencion(df)
        assert filtrador.stats["intencion_vetadas"] == 1
        assert filtrador.stats["confianza_alta"] == 1
        assert filtrador.stats["confianza_revisar"] == 1
