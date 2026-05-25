"""Sistema de alertas desacoplado: reglas de negocio → AlertManager → sinks (consola, JSONL)."""
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Protocol


class AlertSeverity(Enum):
    """Nivel de severidad: INFO < WARNING < ERROR < CRITICAL."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

@dataclass
class Alert:
    """Alerta de negocio disparada durante la ejecución del pipeline."""
    rule_id: str
    message: str
    severity: AlertSeverity
    stage: str = "GLOBAL"
    recommendation: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(tz=UTC).isoformat())

class AlertSink(Protocol):
    """Protocolo para cualquier destino de alertas (consola, archivo, Slack, etc.)."""
    def send(self, alert: Alert) -> None:
        """Envía una alerta al destino concreto."""
        ...


class ConsoleAlertSink:
    """Imprime alertas en stdout (🚨 para ERROR/CRITICAL, ⚠️ para WARNING, ℹ️ para INFO)."""
    def send(self, alert: Alert) -> None:
        if alert.severity in (AlertSeverity.ERROR, AlertSeverity.CRITICAL):
            prefix = f"🚨 [{alert.severity.value}]"
        elif alert.severity == AlertSeverity.WARNING:
            prefix = f"⚠️ [{alert.severity.value}]"
        else:
            prefix = f"ℹ️ [{alert.severity.value}]"
        print(f"{prefix} {alert.stage} ({alert.rule_id}): {alert.message}")
        if alert.recommendation:
            print(f"   -> Recomendación: {alert.recommendation}")


class FileAlertSink:
    """Persiste alertas en un archivo JSONL (append, una línea por alerta)."""
    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def send(self, alert: Alert) -> None:
        """Serializa la alerta como JSON y la añade al archivo de salida."""
        alert_data = {
            "timestamp": alert.timestamp,
            "severity": alert.severity.value,
            "rule_id": alert.rule_id,
            "stage": alert.stage,
            "message": alert.message,
            "recommendation": alert.recommendation
        }
        with self.output_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(alert_data, ensure_ascii=False) + "\n")

class AlertManager:
    """Gestor centralizado: distribuye alertas a todos los sinks registrados."""
    def __init__(self) -> None:
        self._sinks: list[AlertSink] = []
        self._history: list[Alert] = []

    def add_sink(self, sink: AlertSink) -> None:
        """Registra un destino de alertas."""
        self._sinks.append(sink)

    def trigger(
        self,
        rule_id: str,
        message: str,
        severity: AlertSeverity,
        stage: str = "GLOBAL",
        recommendation: str = ""
    ) -> Alert:
        """Crea y distribuye una alerta a todos los sinks registrados."""
        alert = Alert(rule_id=rule_id, message=message, severity=severity, stage=stage, recommendation=recommendation)
        self._history.append(alert)
        for sink in self._sinks:
            try:
                sink.send(alert)
            except Exception as e:
                # Un fallo en sink externo no tumba el pipeline; se reporta a stderr como fallback
                print(f"[AlertManager] sink {type(sink).__name__} falló: {e}", file=sys.stderr)
        return alert

    def get_history(self) -> list[Alert]:
        """Retorna todas las alertas disparadas durante la ejecución."""
        return self._history
