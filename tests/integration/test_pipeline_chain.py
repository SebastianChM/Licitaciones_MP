"""Tests de integración: encadenamiento de etapas y orquestador.

Verifica que las etapas se pasen artefactos correctamente a través
del contexto y que el orquestador refactorizado funcione.

Ejecutar con:  pytest tests/integration/test_pipeline_chain.py -v -m integration
"""

from unittest.mock import patch

import pandas as pd
import pytest

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Test: Cadena Etapa1 → Etapa2 vía artefactos
# ---------------------------------------------------------------------------

class TestCadenaEtapa1Etapa2:
    """Verifica que la salida de etapa1 alimenta correctamente a etapa2."""

    def test_artefacto_etapa0_fluye_a_etapa2(self, context, tmp_path, excel_licitaciones):
        """El archivo de entrada registrado como artefacto es accesible por etapa2."""
        from core.filter_profile import EquipoInfo, FilterProfile
        from etapas.etapa2 import FiltradorLicitaciones

        # Simular que etapa0 registró el archivo
        context.add_artifact("etapa0_output", excel_licitaciones)
        context.config.FILTRADO_DIR = tmp_path

        perfil = FilterProfile(
            equipo=EquipoInfo(codigo="TEST", nombre="Test", hoja_filtros="06-Test"),
            incluir={"nombre": ["consultoria"], "nivel1": [], "nivel2": [], "nivel3": []},
            excluir={k: [] for k in ("nombre", "nivel1", "nivel2", "nivel3",
                                      "generico", "componente", "organismo", "valor")},
            bypass=(),
            exclusion_dura=(),
        )

        with patch.object(FiltradorLicitaciones, '_validar_prerequisitos'), \
             patch.object(FiltradorLicitaciones, '_cargar_perfil', return_value=perfil):
            result = FiltradorLicitaciones().run(context)

        assert result.success is True
        # El artefacto de salida debe existir en disco
        archivo_filtrado = context.get_artifact("etapa2_output")
        assert archivo_filtrado is not None
        assert archivo_filtrado.exists()
        # El contenido debe ser un Excel legible con al menos 1 fila
        df = pd.read_excel(archivo_filtrado)
        assert len(df) >= 1

    def test_etapa2_sin_artefacto_previo_falla_limpiamente(self, context, tmp_path):
        """Etapa2 sin input registrado y sin fallback retorna success=False (no crash)."""
        from etapas.etapa2 import FiltradorLicitaciones

        context.flags["allow_fallback"] = False
        context.config.FILTRADO_DIR = tmp_path
        # Apuntar INPUT_DIR a carpeta vacía para que no encuentre archivo por disco
        context.config.INPUT_DIR = tmp_path / "vacio"
        context.config.INPUT_DIR.mkdir()
        result = FiltradorLicitaciones().run(context)
        assert result.success is False
        assert result.error_message is not None


# ---------------------------------------------------------------------------
# Test: Registro de etapas del orquestador
# ---------------------------------------------------------------------------

class TestOrquestadorRegistro:
    """Verifica que el registro de etapas del orquestador sea coherente."""

    def test_registry_tiene_5_etapas(self):
        from run_pipeline import PipelineLicitaciones
        assert len(PipelineLicitaciones._STAGE_REGISTRY) == 5

    def test_registry_numeros_consecutivos(self):
        from run_pipeline import PipelineLicitaciones
        numeros = [num for num, _, _, _ in PipelineLicitaciones._STAGE_REGISTRY]
        assert numeros == [1, 2, 3, 4, 5]

    def test_registry_clases_son_basestage(self):
        from core.contracts import BaseStage
        from run_pipeline import PipelineLicitaciones
        for _, cls, _, _ in PipelineLicitaciones._STAGE_REGISTRY:
            assert issubclass(cls, BaseStage), f"{cls.__name__} no hereda de BaseStage"

    def test_etapa5_no_es_fatal(self):
        """Etapa 5 (incremental) no debe ser fatal si falla."""
        from run_pipeline import PipelineLicitaciones
        for num, _, _, es_fatal in PipelineLicitaciones._STAGE_REGISTRY:
            if num == 5:
                assert es_fatal is False


# ---------------------------------------------------------------------------
# Test: StageResult invariantes
# ---------------------------------------------------------------------------

class TestStageResultInvariantes:
    def test_success_true_sin_error(self):
        from core.contracts import StageResult
        r = StageResult(success=True, stage_name="x", files_produced=[], metrics_produced={})
        assert r.error_message is None

    def test_success_false_requiere_error(self):
        from core.contracts import StageResult
        r = StageResult(success=False, stage_name="x", error_message="fallo",
                        files_produced=[], metrics_produced={})
        assert r.error_message == "fallo"

    def test_success_true_con_error_invalido(self):
        """No se puede tener success=True con error_message."""
        from core.contracts import StageResult
        with pytest.raises(Exception):
            StageResult(success=True, stage_name="x", error_message="no debería",
                        files_produced=[], metrics_produced={})
