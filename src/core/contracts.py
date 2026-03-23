from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from abc import ABC, abstractmethod
from core.context import PipelineContext

if TYPE_CHECKING:
    from utils.config import Config
    from utils.logger import ProjectLogger

@dataclass
class StageResult:
    """Contrato de salida estricta para cualquier etapa del pipeline."""
    success: bool
    stage_name: str
    error_message: Optional[str] = None
    files_produced: List[Path] = field(default_factory=list)
    metrics_produced: Dict[str, Any] = field(default_factory=dict)
    custom_data: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

class BaseStage(ABC):
    """Contrato base que todas las etapas deben cumplir (Fase 2B)."""
    
    def __init__(self):
        self._context: Optional[PipelineContext] = None
        self._logger: Optional['ProjectLogger'] = None

    def bind(self, context: PipelineContext) -> None:
        """Enlaza explícitamente el stage a su run time con bindings definidos."""
        from utils.logger import ProjectLogger
        self._context = context
        self._logger = ProjectLogger(self.name, context.config.LOG_DIR)

    @property
    def config(self) -> 'Config':
        if self._context is None:
            raise RuntimeError("Stage not bound to a context.")
        return self._context.config

    @property
    def logger(self) -> 'ProjectLogger':
        if self._logger is None:
            raise RuntimeError("Stage not bound to a context.")
        return self._logger

    @property
    def context(self) -> PipelineContext:
        if self._context is None:
            raise RuntimeError("Stage not bound to a context.")
        return self._context

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre formal de la etapa (ej. 'descarga', 'auditoria')"""
        pass

    def validate_inputs(self, context: PipelineContext) -> bool:
        """
        Valida explícitamente si el contexto tiene lo necesario para esta etapa.
        Debe levantar excepciones detalladas (ValueError, FileNotFoundError) si falla.
        Retorna True si es válido.
        """
        return True

    @abstractmethod
    def run(self, context: PipelineContext) -> StageResult:
        """Ejecuta la etapa recibiendo y modificando el Contexto, devolviendo StageResult."""
        pass
