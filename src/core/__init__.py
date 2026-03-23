"""
Módulo core — Contratos y contexto de ejecución del pipeline.
"""
from .context import PipelineContext
from .contracts import BaseStage, StageResult

__all__ = ['PipelineContext', 'BaseStage', 'StageResult']
