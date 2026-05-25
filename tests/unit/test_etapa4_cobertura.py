"""
Tests adicionales de cobertura para etapas/etapa4.py.

Cubre las ramas no alcanzadas por test_etapa4_run.py y test_etapa4_convertir_monto.py:
- _actualizar_tasas: success UTM + USD / error en cada uno
- _obtener_utm / _obtener_usd: llamadas HTTP con mocks
- _obtener_archivo: fallback desde ENRIQUECIDO_DIR
- run(): rama rutas_generadas vacías → ValueError
- run(): historico artifact registrado cuando hay vencidas
- _imprimir_resumen
- main()
"""
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from core.context import PipelineContext
from etapas.etapa4 import GeneradorReporte
from utils.config import Config

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_FECHA_FUTURO = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d 00:00:00")
_FECHA_PASADA = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d 00:00:00")


def _ctx(tmp_path: Path, *, allow_fallback: bool = False) -> PipelineContext:
    config = Config()
    config.PRESENTACION_ORIGINAL_DIR = tmp_path / "PRES" / "ORIG"
    config.HISTORICO_DIR = tmp_path / "HIST"
    config.ENRIQUECIDO_DIR = tmp_path / "ENRIQ"
    config.PRESENTACION_ORIGINAL_DIR.mkdir(parents=True)
    config.HISTORICO_DIR.mkdir(parents=True)
    config.ENRIQUECIDO_DIR.mkdir(parents=True)
    ctx = PipelineContext(config)  # type: ignore[call-arg]
    ctx.flags['allow_fallback'] = allow_fallback
    return ctx


def _stage_bound(tmp_path: Path) -> GeneradorReporte:
    """Stage enlazado con contexto temporal y logger silenciado."""
    stage = GeneradorReporte()
    ctx = _ctx(tmp_path)
    stage.bind(ctx)
    stage._logger = MagicMock()
    return stage


def _make_xlsx(path: Path, fecha_cierre: str | None = None) -> Path:
    """Excel mínimo compatible con salida de Etapa 3."""
    fd = fecha_cierre or _FECHA_FUTURO
    pd.DataFrame([{
        "Numero Adquisición": "2025-001-L1",
        "Nombre Adquisición": "Consultoría TI",
        "Descripción": "Desc",
        "Región Compradora": "Metropolitana",
        "Organismo": "Min TI",
        "Fecha Publicación": "2025-01-01",
        "FechaCierre": fd,
        "Monto": "5000000",
        "Moneda": "CLP",
        "Tipo Adquisición": "Licitación Pública",
        "Nivel 1": "Servicios",
        "Nivel 2": "Tecnología",
        "Nivel 3": "Consultoría",
        "Genérico": "Software",
        "Trazabilidad Filtro": "Directo",
    }]).to_excel(path, index=False, engine="openpyxl")
    return path


# ---------------------------------------------------------------------------
# _actualizar_tasas
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestActualizarTasas:

    def test_utm_exitosa_actualiza_valor(self, tmp_path):
        stage = _stage_bound(tmp_path)
        with patch.object(stage, '_obtener_utm', return_value=70000.0), \
             patch.object(stage, '_obtener_usd', return_value=950.0):
            stage._actualizar_tasas()
        assert stage.valor_utm == 70000.0
        assert stage.valor_usd == 950.0

    def test_utm_retorna_cero_no_actualiza(self, tmp_path):
        """Si _obtener_utm retorna 0, no sobreescribe el valor por defecto."""
        stage = _stage_bound(tmp_path)
        valor_original = stage.valor_utm
        with patch.object(stage, '_obtener_utm', return_value=0.0), \
             patch.object(stage, '_obtener_usd', return_value=900.0):
            stage._actualizar_tasas()
        assert stage.valor_utm == valor_original

    def test_utm_error_no_propaga(self, tmp_path):
        """Excepción en _obtener_utm no debe matar el pipeline."""
        stage = _stage_bound(tmp_path)
        with patch.object(stage, '_obtener_utm', side_effect=ValueError("CMF down")), \
             patch.object(stage, '_obtener_usd', return_value=900.0):
            stage._actualizar_tasas()   # no debe lanzar

    def test_usd_error_no_propaga(self, tmp_path):
        """Excepción en _obtener_usd no debe matar el pipeline."""
        stage = _stage_bound(tmp_path)
        with patch.object(stage, '_obtener_utm', return_value=65000.0), \
             patch.object(stage, '_obtener_usd', side_effect=RuntimeError("timeout")):
            stage._actualizar_tasas()   # no debe lanzar


# ---------------------------------------------------------------------------
# _obtener_utm
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestObtenerUtm:

    def test_sin_api_key_lanza_valor_error(self, tmp_path):
        stage = _stage_bound(tmp_path)
        stage.config.cmf_api_key = ""
        with pytest.raises(ValueError, match="CMF API key"):
            stage._obtener_utm()

    def test_con_api_key_retorna_float(self, tmp_path):
        stage = _stage_bound(tmp_path)
        stage.config.cmf_api_key = "FAKE_KEY"
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"Valor": 65234.56}
        stage.http = MagicMock()
        stage.http.get.return_value = mock_resp
        utm = stage._obtener_utm()
        assert utm == 65234.56


# ---------------------------------------------------------------------------
# _obtener_usd
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestObtenerUsd:

    def test_retorna_float_del_exchange(self, tmp_path):
        stage = _stage_bound(tmp_path)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"rates": {"CLP": 935.12}}
        stage.http = MagicMock()
        stage.http.get.return_value = mock_resp
        usd = stage._obtener_usd()
        assert usd == 935.12


# ---------------------------------------------------------------------------
# _obtener_archivo (fallback desde ENRIQUECIDO_DIR)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestObtenerArchivo:

    def test_retorna_mas_reciente(self, tmp_path):
        stage = _stage_bound(tmp_path)
        enriq = stage.config.ENRIQUECIDO_DIR
        f1 = enriq / "Licitaciones_Enriquecidas_20250101_000000.xlsx"
        f2 = enriq / "Licitaciones_Enriquecidas_20250201_000000.xlsx"
        f1.touch()
        f2.touch()
        import os
        import time as t
        os.utime(f1, (t.time() - 100, t.time() - 100))
        os.utime(f2, (t.time(), t.time()))

        ctx = PipelineContext(stage.config)  # type: ignore[call-arg]
        resultado = stage._obtener_archivo(ctx)
        assert resultado == f2

    def test_sin_archivos_lanza_not_found(self, tmp_path):
        stage = _stage_bound(tmp_path)
        ctx = PipelineContext(stage.config)  # type: ignore[call-arg]
        with pytest.raises(FileNotFoundError, match="fallback"):
            stage._obtener_archivo(ctx)


# ---------------------------------------------------------------------------
# run() — rama rutas_generadas vacías
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRunRutas:

    def test_run_falla_si_generar_excel_retorna_vacio(self, tmp_path):
        """Si _generar_excel devuelve [], run() debe retornar success=False."""
        ctx = _ctx(tmp_path)
        entrada = tmp_path / "entrada.xlsx"
        _make_xlsx(entrada)
        ctx.add_artifact("etapa3_output", entrada)

        stage = GeneradorReporte()

        with patch.object(stage, '_actualizar_tasas'), \
             patch.object(stage, '_generar_excel', return_value=[]):
            result = stage.run(ctx)

        assert result.success is False
        assert result.error_message and "No se generó" in result.error_message

    def test_historico_artifact_registrado_con_dos_archivos(self, tmp_path):
        """Cuando _generar_excel devuelve 2 rutas, etapa4_historico se registra."""
        ctx = _ctx(tmp_path)
        entrada = tmp_path / "entrada.xlsx"
        pd.DataFrame([{
            "Numero Adquisición": "A",
            "Nombre Adquisición": "T",
            "Descripción": "D",
            "Región Compradora": "R",
            "Organismo": "O",
            "Fecha Publicación": "2025-01-01",
            "FechaCierre": _FECHA_FUTURO,
            "Monto": "1000000",
            "Moneda": "CLP",
            "Tipo Adquisición": "Licitación",
            "Nivel 1": "S",
            "Nivel 2": "T",
            "Nivel 3": "C",
            "Genérico": "G",
            "Trazabilidad Filtro": "Directo",
        }]).to_excel(entrada, index=False)
        ctx.add_artifact("etapa3_output", entrada)

        ruta1 = tmp_path / "PRES" / "ORIG" / "Reporte.xlsx"
        ruta2 = tmp_path / "HIST" / "Historico.xlsx"
        ruta1.parent.mkdir(parents=True, exist_ok=True)
        ruta2.parent.mkdir(parents=True, exist_ok=True)
        ruta1.touch()
        ruta2.touch()

        stage = GeneradorReporte()
        with patch.object(stage, '_actualizar_tasas'), \
             patch.object(stage, '_generar_excel', return_value=[ruta1, ruta2]):
            result = stage.run(ctx)

        assert result.success is True
        assert ctx.get_artifact('etapa4_historico') == ruta2


# ---------------------------------------------------------------------------
# _imprimir_resumen
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestImprimirResumen:

    def test_no_crash_con_stats_completos(self, tmp_path):
        stage = _stage_bound(tmp_path)
        stage.stats.update({
            'total': 100, 'vigentes': 80, 'vencidas': 20,
            'utm': 5, 'usd': 3, 'errores': 1,
        })
        stage.valor_utm = 65000.0
        stage.valor_usd = 950.0
        stage._imprimir_resumen()  # no debe lanzar


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestMain:

    def test_main_retorna_0_en_exito(self):
        from etapas.etapa4 import main
        res_ok = MagicMock(success=True, custom_data={'vigentes': 5, 'vencidas': 2})
        with patch('etapas.etapa4.GeneradorReporte') as MockStage:
            MockStage.return_value.run.return_value = res_ok
            rc = main()
        assert rc == 0

    def test_main_retorna_1_si_falla(self):
        from etapas.etapa4 import main
        res_fail = MagicMock(success=False, error_message="Error fatal")
        with patch('etapas.etapa4.GeneradorReporte') as MockStage:
            MockStage.return_value.run.return_value = res_fail
            rc = main()
        assert rc == 1

    def test_main_retorna_1_en_excepcion(self):
        from etapas.etapa4 import main
        with patch('etapas.etapa4.GeneradorReporte') as MockStage:
            MockStage.return_value.run.side_effect = RuntimeError("crash")
            rc = main()
        assert rc == 1
