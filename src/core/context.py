from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, TYPE_CHECKING
import uuid
import datetime
from utils.config import Config

if TYPE_CHECKING:
    from core.contracts import StageResult

@dataclass
class PipelineContext:
    """
    Contexto global que fluye a través de todas las etapas del pipeline.
    Reemplaza la heurística de buscar archivos en el sistema operativo.
    """
    config: Config
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    start_time: datetime.datetime = field(default_factory=datetime.datetime.now)
    
    # Inventario centralizado de artefactos producidos y consumidos (claves fijas, valores: rutas)
    artifacts: Dict[str, Path] = field(default_factory=dict)
    
    # Métricas globales del run
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    # Resultados estandarizados por etapa
    stage_results: Dict[str, 'StageResult'] = field(default_factory=dict)
    
    # Flags de ejecución o estado
    flags: Dict[str, bool] = field(default_factory=dict)

    def add_artifact(self, key: str, path: Path) -> None:
        """Registra un artefacto generado explícitamente."""
        self.artifacts[key] = path

    def get_artifact(self, key: str) -> Path | None:
        """Obtiene de manera estricta un artefacto registrado o None."""
        return self.artifacts.get(key)

    def set_metric(self, key: str, value: Any) -> None:
        """Almacena una métrica de negocio trans-etapas."""
        self.metrics[key] = value
