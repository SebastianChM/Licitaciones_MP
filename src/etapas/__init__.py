"""Paquete de etapas del pipeline de licitaciones."""

from .etapa0 import Etapa0Descarga
from .etapa1 import AuditorTaxonomia
from .etapa2 import FiltradorLicitaciones
from .etapa3 import EnriquecedorAPI
from .etapa4 import GeneradorReporte
from .etapa5 import GeneradorReporteIncremental

__all__ = [
    'AuditorTaxonomia',
    'EnriquecedorAPI',
    'Etapa0Descarga',
    'FiltradorLicitaciones',
    'GeneradorReporte',
    'GeneradorReporteIncremental',
]
