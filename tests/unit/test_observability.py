"""Tests unitarios para utils/observability.py.

Cubre ObservabilityRules (6 reglas de negocio) y RunSummaryReporter.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stage_result(success=True, metrics=None, files=None, warnings=None):
    from core.contracts import StageResult
    return StageResult(
        success=success,
        stage_name="test",
        metrics_produced=metrics or {},
        files_produced=files or [],
        warnings=warnings or [],
    )


@pytest.fixture
def alerts():
    from utils.alerts import AlertManager
    return AlertManager()


@pytest.fixture
def obs(context, alerts):
    from utils.observability import ObservabilityRules
    return ObservabilityRules(context, alerts)


# ---------------------------------------------------------------------------
# ObservabilityRules — etapa0
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCheckEtapa0:

    def test_tamano_cero_genera_alerta_critical(self, obs, context, alerts):
        context.stage_results['etapa0'] = _make_stage_result(
            metrics={'tamano_mb': 0}
        )
        obs._check_etapa0()
        assert any(a.rule_id == "E0_DESC_VACIA" for a in alerts.get_history())

    def test_tamano_positivo_no_genera_alerta(self, obs, context, alerts):
        context.stage_results['etapa0'] = _make_stage_result(
            metrics={'tamano_mb': 5.3}
        )
        obs._check_etapa0()
        assert alerts.get_history() == []

    def test_sin_resultado_no_genera_alerta(self, obs, alerts):
        obs._check_etapa0()
        assert alerts.get_history() == []

    def test_result_fallido_no_genera_alerta(self, obs, context, alerts):
        context.stage_results['etapa0'] = _make_stage_result(
            success=False, metrics={'tamano_mb': 0}
        )
        obs._check_etapa0()
        assert alerts.get_history() == []


# ---------------------------------------------------------------------------
# ObservabilityRules — etapa2
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCheckEtapa2:

    def test_filtradas_cero_genera_warning(self, obs, context, alerts):
        context.stage_results['etapa2'] = _make_stage_result(
            metrics={'total_analizadas': 100, 'total_filtradas': 0}
        )
        obs._check_etapa2()
        assert any(a.rule_id == "E2_FILTRO_VACIO" for a in alerts.get_history())

    def test_tasa_alta_genera_warning(self, obs, context, alerts):
        context.stage_results['etapa2'] = _make_stage_result(
            metrics={'total_analizadas': 1000, 'total_filtradas': 100}  # 10%
        )
        obs._check_etapa2()
        assert any(a.rule_id == "E2_TASA_FILTRADO_ALTA" for a in alerts.get_history())

    def test_tasa_normal_sin_alertas(self, obs, context, alerts):
        context.stage_results['etapa2'] = _make_stage_result(
            metrics={'total_analizadas': 10000, 'total_filtradas': 200}  # 2%
        )
        obs._check_etapa2()
        assert alerts.get_history() == []

    def test_sin_resultado_no_falla(self, obs, alerts):
        obs._check_etapa2()
        assert alerts.get_history() == []


# ---------------------------------------------------------------------------
# ObservabilityRules — etapa3
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCheckEtapa3:

    def test_tasa_error_alta_genera_critical(self, obs, context, alerts):
        context.stage_results['etapa3'] = _make_stage_result(
            metrics={'total_registros': 10, 'errores_registro': 3}  # 30%
        )
        obs._check_etapa3()
        assert any(a.rule_id == "E3_TASA_ERROR_ALTA" for a in alerts.get_history())

    def test_tasa_error_baja_sin_alerta(self, obs, context, alerts):
        context.stage_results['etapa3'] = _make_stage_result(
            metrics={'total_registros': 100, 'errores_registro': 5}  # 5%
        )
        obs._check_etapa3()
        assert alerts.get_history() == []

    def test_total_cero_sin_alerta(self, obs, context, alerts):
        context.stage_results['etapa3'] = _make_stage_result(
            metrics={'total_registros': 0, 'errores_registro': 0}
        )
        obs._check_etapa3()
        assert alerts.get_history() == []


# ---------------------------------------------------------------------------
# ObservabilityRules — etapa4
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCheckEtapa4:

    def test_exito_sin_archivos_genera_error(self, obs, context, alerts):
        context.stage_results['etapa4'] = _make_stage_result(
            success=True, files=[]
        )
        obs._check_etapa4()
        assert any(a.rule_id == "E4_SIN_OUTPUT" for a in alerts.get_history())

    def test_exito_con_archivos_sin_alerta(self, obs, context, alerts, tmp_path):
        context.stage_results['etapa4'] = _make_stage_result(
            success=True, files=[tmp_path / "reporte.xlsx"]
        )
        obs._check_etapa4()
        assert alerts.get_history() == []

    def test_sin_resultado_no_falla(self, obs, alerts):
        obs._check_etapa4()
        assert alerts.get_history() == []


# ---------------------------------------------------------------------------
# ObservabilityRules — fallback_modes
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCheckFallbackModes:

    def test_modo_standalone_genera_info(self, obs, context, alerts):
        context.flags['allow_fallback'] = True
        obs._check_fallback_modes()
        assert any(a.rule_id == "MODO_STANDALONE" for a in alerts.get_history())

    def test_modo_pipeline_sin_alerta(self, obs, context, alerts):
        context.flags['allow_fallback'] = False
        obs._check_fallback_modes()
        assert alerts.get_history() == []


# ---------------------------------------------------------------------------
# ObservabilityRules — evaluate_all
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestEvaluateAll:

    def test_invoca_todas_las_checks(self, context, alerts):
        from utils.observability import ObservabilityRules
        obs = ObservabilityRules(context, alerts)

        called = []
        obs._check_etapa0 = lambda: called.append('etapa0')
        obs._check_etapa2 = lambda: called.append('etapa2')
        obs._check_etapa3 = lambda: called.append('etapa3')
        obs._check_etapa4 = lambda: called.append('etapa4')
        obs._check_fallback_modes = lambda: called.append('fallback')

        obs.evaluate_all()

        assert set(called) == {'etapa0', 'etapa2', 'etapa3', 'etapa4', 'fallback'}


# ---------------------------------------------------------------------------
# RunSummaryReporter
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRunSummaryReporter:

    def test_genera_archivo_json(self, context, alerts, tmp_path):
        from utils.observability import RunSummaryReporter
        context.config.BASE_DIR = tmp_path
        reporter = RunSummaryReporter(context, alerts)
        path = reporter.generate_and_save()
        assert path.exists()
        assert path.suffix == ".json"

    def test_json_contiene_metadata(self, context, alerts, tmp_path):
        from utils.observability import RunSummaryReporter
        context.config.BASE_DIR = tmp_path
        reporter = RunSummaryReporter(context, alerts)
        path = reporter.generate_and_save()
        data = json.loads(path.read_text(encoding='utf-8'))
        assert 'metadata' in data
        assert data['metadata']['run_id'] == context.run_id

    def test_json_contiene_metricas(self, context, alerts, tmp_path):
        from utils.observability import RunSummaryReporter
        context.stage_results['etapa2'] = _make_stage_result(success=True)
        context.config.BASE_DIR = tmp_path
        reporter = RunSummaryReporter(context, alerts)
        path = reporter.generate_and_save()
        data = json.loads(path.read_text(encoding='utf-8'))
        assert data['metricas']['etapas_ejecutadas'] == 1
        assert data['metricas']['etapas_exitosas'] == 1

    def test_estado_error_cuando_hay_fallos(self, context, alerts, tmp_path):
        from utils.observability import RunSummaryReporter
        context.stage_results['etapa2'] = _make_stage_result(success=False)
        context.config.BASE_DIR = tmp_path
        reporter = RunSummaryReporter(context, alerts)
        path = reporter.generate_and_save()
        data = json.loads(path.read_text(encoding='utf-8'))
        assert data['metadata']['estado_general'] == "ERROR"

    def test_alerts_incluidas_en_json(self, context, alerts, tmp_path):
        from utils.observability import RunSummaryReporter
        from utils.alerts import AlertSeverity
        alerts.trigger("TEST_RULE", "Test message", AlertSeverity.WARNING)
        context.config.BASE_DIR = tmp_path
        reporter = RunSummaryReporter(context, alerts)
        path = reporter.generate_and_save()
        data = json.loads(path.read_text(encoding='utf-8'))
        assert any(a['rule_id'] == "TEST_RULE" for a in data['alerts_disparadas'])
