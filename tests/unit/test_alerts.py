"""Tests unitarios para utils/alerts.py.

Cubre AlertSeverity, Alert, ConsoleAlertSink, FileAlertSink, AlertManager.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, call
from io import StringIO


# ---------------------------------------------------------------------------
# AlertSeverity
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestAlertSeverity:

    def test_valores_string(self):
        from utils.alerts import AlertSeverity
        assert AlertSeverity.INFO.value == "INFO"
        assert AlertSeverity.WARNING.value == "WARNING"
        assert AlertSeverity.ERROR.value == "ERROR"
        assert AlertSeverity.CRITICAL.value == "CRITICAL"

    def test_enum_comparable(self):
        from utils.alerts import AlertSeverity
        assert AlertSeverity.CRITICAL != AlertSeverity.INFO


# ---------------------------------------------------------------------------
# Alert
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestAlert:

    def test_campos_requeridos(self):
        from utils.alerts import Alert, AlertSeverity
        a = Alert(rule_id="TEST", message="mensaje", severity=AlertSeverity.INFO)
        assert a.rule_id == "TEST"
        assert a.message == "mensaje"
        assert a.severity == AlertSeverity.INFO

    def test_stage_default_global(self):
        from utils.alerts import Alert, AlertSeverity
        a = Alert(rule_id="TEST", message="msg", severity=AlertSeverity.WARNING)
        assert a.stage == "GLOBAL"

    def test_timestamp_generado(self):
        from utils.alerts import Alert, AlertSeverity
        a = Alert(rule_id="TEST", message="msg", severity=AlertSeverity.INFO)
        assert a.timestamp  # no vacío

    def test_recommendation_opcional(self):
        from utils.alerts import Alert, AlertSeverity
        a = Alert(rule_id="X", message="m", severity=AlertSeverity.ERROR,
                  recommendation="Revisar config")
        assert a.recommendation == "Revisar config"


# ---------------------------------------------------------------------------
# ConsoleAlertSink
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestConsoleAlertSink:

    def test_imprime_severity_en_output(self, capsys):
        from utils.alerts import ConsoleAlertSink, Alert, AlertSeverity
        sink = ConsoleAlertSink()
        a = Alert(rule_id="R1", message="algo fallo", severity=AlertSeverity.ERROR,
                  stage="etapa1")
        sink.send(a)
        out = capsys.readouterr().out
        assert "ERROR" in out
        assert "algo fallo" in out

    def test_imprime_recomendacion_si_existe(self, capsys):
        from utils.alerts import ConsoleAlertSink, Alert, AlertSeverity
        sink = ConsoleAlertSink()
        a = Alert(rule_id="R2", message="aviso", severity=AlertSeverity.WARNING,
                  recommendation="Hacer X")
        sink.send(a)
        out = capsys.readouterr().out
        assert "Hacer X" in out

    def test_info_usa_prefijo_advertencia(self, capsys):
        from utils.alerts import ConsoleAlertSink, Alert, AlertSeverity
        sink = ConsoleAlertSink()
        a = Alert(rule_id="R3", message="info", severity=AlertSeverity.INFO)
        sink.send(a)
        out = capsys.readouterr().out
        assert "INFO" in out


# ---------------------------------------------------------------------------
# FileAlertSink
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFileAlertSink:

    def test_crea_archivo_en_primera_alerta(self, tmp_path):
        from utils.alerts import FileAlertSink, Alert, AlertSeverity
        ruta = tmp_path / "alerts.jsonl"
        sink = FileAlertSink(ruta)
        a = Alert(rule_id="R1", message="ok", severity=AlertSeverity.INFO)
        sink.send(a)
        assert ruta.exists()

    def test_json_valido_por_linea(self, tmp_path):
        from utils.alerts import FileAlertSink, Alert, AlertSeverity
        ruta = tmp_path / "alerts.jsonl"
        sink = FileAlertSink(ruta)
        a = Alert(rule_id="R1", message="texto", severity=AlertSeverity.WARNING,
                  stage="etapa2", recommendation="Revisar filtros")
        sink.send(a)
        linea = ruta.read_text(encoding='utf-8').strip()
        data = json.loads(linea)
        assert data['rule_id'] == "R1"
        assert data['severity'] == "WARNING"

    def test_multiples_alertas_multiples_lineas(self, tmp_path):
        from utils.alerts import FileAlertSink, Alert, AlertSeverity
        ruta = tmp_path / "alerts.jsonl"
        sink = FileAlertSink(ruta)
        for i in range(3):
            sink.send(Alert(rule_id=f"R{i}", message="m", severity=AlertSeverity.INFO))
        lineas = [l for l in ruta.read_text(encoding='utf-8').strip().split('\n') if l]
        assert len(lineas) == 3

    def test_crea_directorio_si_no_existe(self, tmp_path):
        from utils.alerts import FileAlertSink, Alert, AlertSeverity
        ruta = tmp_path / "subdir" / "alerts.jsonl"
        sink = FileAlertSink(ruta)
        sink.send(Alert(rule_id="X", message="m", severity=AlertSeverity.INFO))
        assert ruta.exists()


# ---------------------------------------------------------------------------
# AlertManager
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestAlertManager:

    def test_trigger_crea_alerta(self):
        from utils.alerts import AlertManager, AlertSeverity
        mgr = AlertManager()
        mgr.trigger("R1", "mensaje", AlertSeverity.WARNING)
        assert len(mgr.get_history()) == 1

    def test_get_history_retorna_lista(self):
        from utils.alerts import AlertManager, AlertSeverity
        mgr = AlertManager()
        assert mgr.get_history() == []
        mgr.trigger("R1", "m", AlertSeverity.INFO)
        assert len(mgr.get_history()) == 1

    def test_sink_recibe_alerta(self, tmp_path):
        from utils.alerts import AlertManager, FileAlertSink, AlertSeverity
        ruta = tmp_path / "log.jsonl"
        mgr = AlertManager()
        mgr.add_sink(FileAlertSink(ruta))
        mgr.trigger("R1", "prueba", AlertSeverity.ERROR)
        assert ruta.exists()

    def test_trigger_retorna_alerta(self):
        from utils.alerts import AlertManager, AlertSeverity
        mgr = AlertManager()
        a = mgr.trigger("R1", "m", AlertSeverity.INFO, stage="etapa0", recommendation="Hacer X")
        assert a.rule_id == "R1"
        assert a.stage == "etapa0"

    def test_fallo_en_sink_no_propaga_excepcion(self):
        from utils.alerts import AlertManager, AlertSeverity, AlertSink, Alert
        class SinkRoto:
            def send(self, alert: Alert):
                raise RuntimeError("fallo de red")

        mgr = AlertManager()
        mgr.add_sink(SinkRoto())
        # No debe lanzar
        mgr.trigger("R1", "test", AlertSeverity.CRITICAL)
        assert len(mgr.get_history()) == 1

    def test_multiples_sinks(self, tmp_path):
        from utils.alerts import AlertManager, FileAlertSink, AlertSeverity
        ruta1 = tmp_path / "a.jsonl"
        ruta2 = tmp_path / "b.jsonl"
        mgr = AlertManager()
        mgr.add_sink(FileAlertSink(ruta1))
        mgr.add_sink(FileAlertSink(ruta2))
        mgr.trigger("R1", "m", AlertSeverity.INFO)
        assert ruta1.exists() and ruta2.exists()
