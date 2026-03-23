from dataclasses import dataclass, field
from enum import Enum
from typing import List, Protocol
from datetime import datetime
import json
from pathlib import Path

class AlertSeverity(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

@dataclass
class Alert:
    rule_id: str
    message: str
    severity: AlertSeverity
    stage: str = "GLOBAL"
    recommendation: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

class AlertSink(Protocol):
    def send(self, alert: Alert) -> None:
        """Destino de la alerta (log, db, api, etc)"""
        ...

class ConsoleAlertSink:
    def send(self, alert: Alert) -> None:
        prefix = f"🚨 [{alert.severity.value}]" if alert.severity in (AlertSeverity.ERROR, AlertSeverity.CRITICAL) else f"⚠️ [{alert.severity.value}]"
        print(f"{prefix} {alert.stage} ({alert.rule_id}): {alert.message}")
        if alert.recommendation:
            print(f"   -> Recomendación: {alert.recommendation}")

class FileAlertSink:
    def __init__(self, output_path: Path):
        self.output_path = output_path
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        
    def send(self, alert: Alert) -> None:
        alert_data = {
            "timestamp": alert.timestamp,
            "severity": alert.severity.value,
            "rule_id": alert.rule_id,
            "stage": alert.stage,
            "message": alert.message,
            "recommendation": alert.recommendation
        }
        with open(self.output_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(alert_data, ensure_ascii=False) + "\n")

class AlertManager:
    """Sistema centralizado de alertas (desacoplado del pipeline base)"""
    def __init__(self):
        self._sinks: List[AlertSink] = []
        self._history: List[Alert] = []

    def add_sink(self, sink: AlertSink):
        self._sinks.append(sink)

    def trigger(self, rule_id: str, message: str, severity: AlertSeverity, stage: str = "GLOBAL", recommendation: str = "") -> Alert:
        alert = Alert(rule_id=rule_id, message=message, severity=severity, stage=stage, recommendation=recommendation)
        self._history.append(alert)
        for sink in self._sinks:
            try:
                sink.send(alert)
            except Exception:
                pass # Un fallo en sink externo no tumba el pipeline
        return alert
        
    def get_history(self) -> List[Alert]:
        return self._history
