"""Tests para el entrypoint reporte_incremental.main().

El módulo define una función main() que:
  1. Parsea --standalone (default True)
  2. Crea Config + PipelineContext
  3. Delega en _Etapa5GeneradorReporte (alias de etapas.etapa5.GeneradorReporteIncremental)
  4. Retorna 0 en éxito, 1 en fallo

Estos tests verifican ese contrato sin ejecutar I/O real.
El alias interno se llama '_Etapa5GeneradorReporte' para no colisionar con la
clase legacy 'GeneradorReporteIncremental' definida más abajo en el mismo módulo.
"""
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

_PATCH_ETAPA5 = 'reporte_incremental._Etapa5GeneradorReporte'
_PATCH_CONFIG = 'reporte_incremental.Config'
_PATCH_CONTEXT = 'reporte_incremental.PipelineContext'


def _make_resultado(success: bool, detalles: dict | None = None, files: list | None = None):
    from core.contracts import StageResult
    return StageResult(
        success=success,
        stage_name="incremental",
        error_message=None if success else "error simulado",
        files_produced=files or [],
        custom_data={'detalles': detalles or {}},
    )


# ---------------------------------------------------------------------------
# main() — flujo exitoso y casos de error
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_argv(monkeypatch):
    """Evita que argparse en main() lea los argumentos de pytest."""
    monkeypatch.setattr(sys, 'argv', ['reporte_incremental.py'])


@pytest.mark.unit
class TestReporteIncrementalMain:

    def test_retorna_0_en_exito(self, config, context):
        from reporte_incremental import main

        detalles = {'tipo': 'incremental', 'licitaciones_nuevas': 3,
                    'licitaciones_existentes': 5, 'licitaciones_vencidas': 1}
        resultado_ok = _make_resultado(success=True, detalles=detalles)

        with patch(_PATCH_CONFIG, return_value=config), \
             patch(_PATCH_CONTEXT, return_value=context), \
             patch(_PATCH_ETAPA5) as MockEtapa5:
            MockEtapa5.return_value.run.return_value = resultado_ok
            codigo = main()

        assert codigo == 0

    def test_retorna_1_en_fallo_stage(self, config, context):
        from reporte_incremental import main

        resultado_ko = _make_resultado(success=False)

        with patch(_PATCH_CONFIG, return_value=config), \
             patch(_PATCH_CONTEXT, return_value=context), \
             patch(_PATCH_ETAPA5) as MockEtapa5:
            MockEtapa5.return_value.run.return_value = resultado_ko
            codigo = main()

        assert codigo == 1

    def test_retorna_1_en_excepcion(self, config, context):
        from reporte_incremental import main

        with patch(_PATCH_CONFIG, return_value=config), \
             patch(_PATCH_CONTEXT, return_value=context), \
             patch(_PATCH_ETAPA5) as MockEtapa5:
            MockEtapa5.return_value.run.side_effect = RuntimeError("fallo inesperado")
            codigo = main()

        assert codigo == 1

    def test_run_invocado_con_context(self, config, context):
        from reporte_incremental import main

        detalles = {'tipo': 'inicial', 'licitaciones_nuevas': 0,
                    'licitaciones_existentes': 0, 'licitaciones_vencidas': 0}
        resultado_ok = _make_resultado(success=True, detalles=detalles)

        with patch(_PATCH_CONFIG, return_value=config), \
             patch(_PATCH_CONTEXT, return_value=context), \
             patch(_PATCH_ETAPA5) as MockEtapa5:
            MockEtapa5.return_value.run.return_value = resultado_ok
            main()

        MockEtapa5.return_value.run.assert_called_once_with(context)

    def test_flag_allow_fallback_activado(self, config, context):
        """main() siempre activa allow_fallback en el contexto."""
        from reporte_incremental import main

        resultado_ok = _make_resultado(success=True, detalles={})

        with patch(_PATCH_CONFIG, return_value=config), \
             patch(_PATCH_CONTEXT, return_value=context), \
             patch(_PATCH_ETAPA5) as MockEtapa5:
            MockEtapa5.return_value.run.return_value = resultado_ok
            main()

        assert context.flags.get('allow_fallback') is True

    def test_archivo_producido_loggeado(self, config, context, tmp_path):
        from reporte_incremental import main

        archivo = tmp_path / "Reporte_Incremental_2025-01-01.xlsx"
        archivo.touch()
        detalles = {'tipo': 'incremental', 'licitaciones_nuevas': 1,
                    'licitaciones_existentes': 0, 'licitaciones_vencidas': 0}
        resultado_ok = _make_resultado(success=True, detalles=detalles, files=[archivo])

        with patch(_PATCH_CONFIG, return_value=config), \
             patch(_PATCH_CONTEXT, return_value=context), \
             patch(_PATCH_ETAPA5) as MockEtapa5:
            MockEtapa5.return_value.run.return_value = resultado_ok
            codigo = main()

        assert codigo == 0
