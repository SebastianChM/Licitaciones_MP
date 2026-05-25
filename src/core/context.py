"""Contexto único que fluye entre etapas: artefactos, métricas y resultados."""
import datetime
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from utils.config import Config

if TYPE_CHECKING:
    from core.contracts import StageResult

@dataclass
class PipelineContext:
    """Contenedor compartido por todas las etapas: config, artefactos, métricas y flags."""
    config: Config
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    start_time: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(tz=datetime.UTC))
    artifacts: dict[str, Path] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    stage_results: dict[str, 'StageResult'] = field(default_factory=dict)
    flags: dict[str, Any] = field(default_factory=dict)

    def add_artifact(self, key: str, path: Path) -> None:
        """Registra la ruta de un archivo producido por la etapa actual."""
        if path is None:
            raise ValueError(f"Artifact '{key}' recibió path=None — la etapa no generó el archivo esperado.")
        self.artifacts[key] = path

    def get_artifact(self, key: str) -> Path | None:
        """Devuelve la ruta de un artefacto registrado, o None si no existe."""
        return self.artifacts.get(key)

    def set_metric(self, key: str, value: Any) -> None:
        """Registra una métrica de negocio trans-etapas."""
        self.metrics[key] = value

    def get_metric(self, key: str, default: Any = None) -> Any:
        """Devuelve una métrica registrada, o default si no existe."""
        return self.metrics.get(key, default)
