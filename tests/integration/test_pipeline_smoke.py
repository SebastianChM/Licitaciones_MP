"""Tests de integración del pipeline de Licitaciones.

Estos tests inyectan datos sintéticos y verifican que las etapas
encadenen artefactos, produzcan archivos y devuelvan StageResult.success.

No requieren archivos reales (Excel de Mercado Público ni API key):
- etapa0 y etapa3 son mockeadas porque dependen de red externa.
- El resto opera sobre DataFrames sintéticos escritos en tmp_path.

Ejecutar con:  pytest tests/integration/ -v -m integration
"""

import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import patch, MagicMock


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

COLS_BASICAS = [
    "Numero Adquisición", "Nombre Adquisición", "Descripción",
    "Nivel 1", "Nivel 2", "Nivel 3", "Genérico",
    "Organismo", "Tipo Adquisición", "Descripción del producto/servicio",
]


def _crear_excel_licitaciones(path: Path, n: int = 5) -> Path:
    filas = [
        [f"2025-{100+i}-L1",
         f"Consultoría TI servicio {i}",
         f"Servicios de tecnología número {i}",
         "Servicios", "Tecnología", "Consultoría", "Software",
         "Ministerio de Obras Públicas", "Licitación Pública",
         f"Asesoría técnica {i}"]
        for i in range(n)
    ]
    df = pd.DataFrame(filas, columns=COLS_BASICAS)
    df.to_excel(path, index=False)
    return path


# ---------------------------------------------------------------------------
# Test: PipelineContext ↔ artefactos
# ---------------------------------------------------------------------------

class TestPipelineContext:
    def test_artefacto_persistido_entre_etapas(self, context, tmp_path):
        """Un artefacto añadido por una etapa está disponible para la siguiente."""
        archivo = tmp_path / "output_etapa0.xlsx"
        archivo.touch()
        context.add_artifact("etapa0_output", archivo)
        assert context.get_artifact("etapa0_output") == archivo

    def test_run_id_unico_por_contexto(self, config):
        from core.context import PipelineContext
        ctx1 = PipelineContext(config=config)
        ctx2 = PipelineContext(config=config)
        assert ctx1.run_id != ctx2.run_id

    def test_flags_allow_fallback(self, context):
        assert context.flags.get("allow_fallback") is True


# ---------------------------------------------------------------------------
# Test: Etapa 1 — Auditoría
# ---------------------------------------------------------------------------

class TestEtapa1Integracion:
    def test_etapa1_falla_sin_pivot(self, context, tmp_path, excel_licitaciones):
        """Etapa 1 retorna success=False si PIVOT_MAESTRO no existe."""
        from etapas.etapa1 import AuditorTaxonomia
        context.add_artifact("etapa0_output", excel_licitaciones)
        # Apuntamos PIVOT_DIR a un directorio vacío
        context.config.PIVOT_DIR = tmp_path / "pivot_vacio"
        context.config.PIVOT_DIR.mkdir()
        etapa = AuditorTaxonomia()
        result = etapa.run(context)
        assert result.success is False

    def test_etapa1_stageresult_tiene_stage_name(self, context, tmp_path, excel_licitaciones):
        """Verifica que StageResult tenga el nombre correcto aunque falle."""
        from etapas.etapa1 import AuditorTaxonomia
        context.add_artifact("etapa0_output", excel_licitaciones)
        context.config.PIVOT_DIR = tmp_path
        etapa = AuditorTaxonomia()
        result = etapa.run(context)
        assert result.stage_name == "auditoria"


# ---------------------------------------------------------------------------
# Test: Etapa 2 — Filtrado (con PIVOT mockeado)
# ---------------------------------------------------------------------------

class TestEtapa2Integracion:
    def test_etapa2_filtra_y_registra_artefacto(self, context, tmp_path, excel_licitaciones):
        """Etapa 2 produce archivo filtrado y lo registra como artefacto."""
        from etapas.etapa2 import FiltradorLicitaciones

        context.add_artifact("etapa0_output", excel_licitaciones)
        context.config.FILTRADO_DIR = tmp_path

        filtros_mock = {
            "incluir": {"nombre": ["consultoria", "ti"], "nivel1": [], "nivel2": [], "nivel3": []},
            "excluir": {k: [] for k in ["nombre","nivel1","nivel2","nivel3","generico","componente","organismo","valor"]},
            "bypass": [],
        }

        with patch.object(FiltradorLicitaciones, '_validar_prerequisitos'), \
             patch.object(FiltradorLicitaciones, '_cargar_filtros', return_value=filtros_mock):
            etapa = FiltradorLicitaciones()
            result = etapa.run(context)

        assert result.success is True
        assert context.get_artifact("etapa2_output") is not None
        assert context.get_artifact("etapa2_output").exists()

    def test_etapa2_stats_coherentes(self, context, tmp_path, excel_licitaciones):
        """Stats de filtrado son numéricamente coherentes."""
        from etapas.etapa2 import FiltradorLicitaciones

        context.add_artifact("etapa0_output", excel_licitaciones)
        context.config.FILTRADO_DIR = tmp_path

        filtros_mock = {
            "incluir": {"nombre": ["consultoria"], "nivel1": [], "nivel2": [], "nivel3": []},
            "excluir": {k: [] for k in ["nombre","nivel1","nivel2","nivel3","generico","componente","organismo","valor"]},
            "bypass": [],
        }

        with patch.object(FiltradorLicitaciones, '_validar_prerequisitos'), \
             patch.object(FiltradorLicitaciones, '_cargar_filtros', return_value=filtros_mock):
            etapa = FiltradorLicitaciones()
            result = etapa.run(context)

        stats = result.metrics_produced
        assert stats["original"] >= stats["final"]
        assert stats["final"] >= 0


# ---------------------------------------------------------------------------
# Test: Contratos de etapas (BaseStage)
# ---------------------------------------------------------------------------

class TestContratosBaseStage:
    @pytest.mark.parametrize("clase_path,nombre_etapa", [
        ("etapas.etapa1.AuditorTaxonomia", "auditoria"),
        ("etapas.etapa2.FiltradorLicitaciones", "filtrado"),
        ("etapas.etapa3.EnriquecedorAPI", "enriquecimiento"),
    ])
    def test_name_property_definido(self, clase_path, nombre_etapa):
        """Cada etapa expone su nombre correctamente."""
        modulo, clase = clase_path.rsplit(".", 1)
        import importlib
        mod = importlib.import_module(modulo)
        EtapaClass = getattr(mod, clase)
        assert EtapaClass().name == nombre_etapa

    def test_stageresult_exitoso_tiene_campos_requeridos(self):
        from core.contracts import StageResult
        result = StageResult(
            success=True,
            stage_name="test",
            files_produced=[],
            metrics_produced={"total": 5},
        )
        assert result.success is True
        assert result.stage_name == "test"
        assert result.error_message is None

    def test_stageresult_fallido_tiene_mensaje(self):
        from core.contracts import StageResult
        result = StageResult(
            success=False,
            stage_name="test",
            error_message="Error de prueba",
        )
        assert result.success is False
        assert result.error_message is not None
        assert "prueba" in result.error_message
