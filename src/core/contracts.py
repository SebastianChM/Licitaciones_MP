"""Contratos base: BaseStage (interfaz de etapas) y StageResult (salida estándar)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from core.context import PipelineContext

if TYPE_CHECKING:
    from utils.config import Config
    from utils.logger import ProjectLogger

@dataclass
class StageResult:
    """Salida estandarizada de cada etapa. success=False indica fallo no fatal."""
    success: bool
    stage_name: str
    error_message: str | None = None
    files_produced: list[Path] = field(default_factory=list)
    metrics_produced: dict[str, Any] = field(default_factory=dict)
    custom_data: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.success and self.error_message:
            raise ValueError(
                f"StageResult inconsistente en '{self.stage_name}': "
                f"success=True no puede coexistir con error_message='{self.error_message}'."
            )

class BaseStage(ABC):
    """Clase base abstracta para todas las etapas del pipeline."""

    def __init__(self) -> None:
        self._context: PipelineContext | None = None
        self._logger: ProjectLogger | None = None

    def bind(self, context: PipelineContext) -> None:
        """Enlaza la etapa al contexto e inicializa su logger. Llamado automáticamente por run()."""
        from utils.logger import ProjectLogger
        self._context = context
        self._logger = ProjectLogger(self.name, context.config.LOG_DIR)

    @property
    def config(self) -> 'Config':
        """Acceso rápido a la configuración global. Requiere bind() previo."""
        if self._context is None:
            raise RuntimeError("Stage not bound to a context.")
        return self._context.config

    @property
    def logger(self) -> 'ProjectLogger':
        """Logger de la etapa. Requiere bind() previo."""
        if self._logger is None:
            raise RuntimeError("Stage not bound to a context.")
        return self._logger

    @property
    def context(self) -> PipelineContext:
        """Contexto global del pipeline. Requiere bind() previo."""
        if self._context is None:
            raise RuntimeError("Stage not bound to a context.")
        return self._context

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre canónico de la etapa (clave en logs y stage_results)."""
        pass

    def validate_inputs(self, context: PipelineContext) -> bool:
        """Verifica pre-condiciones antes de _execute(). Sobreescribir en subclases si se necesita."""
        return True

    def run(self, context: PipelineContext) -> StageResult:
        """Template Method: bind → validate_inputs → _execute → _cleanup. No sobreescribir."""
        try:
            self.bind(context)
            if self.validate_inputs(context) is False:
                return StageResult(
                    success=False,
                    stage_name=self.name,
                    error_message=f"Etapa '{self.name}': validate_inputs() rechazó las entradas.",
                )
            return self._execute(context)
        except Exception as e:
            return StageResult(success=False, stage_name=self.name, error_message=str(e))
        finally:
            self._cleanup()
            if self._logger:
                self._logger.finalize()

    @abstractmethod
    def _execute(self, context: PipelineContext) -> StageResult:
        """Lógica de negocio de la etapa. Puede lanzar excepciones; run() las captura."""
        pass

    def _cleanup(self) -> None:  # noqa: B027 — optional hook, not required to override
        """Hook de liberación de recursos. Sobreescribir para cerrar HTTP clients, etc."""
        pass
