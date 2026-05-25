"""FilterProfile: representación inmutable del conjunto de reglas de filtrado de un equipo.

Esta es la capa de datos pura, sin dependencias del PIVOT ni de pandas. Permite que
la lógica de filtrado (etapa2) trabaje contra una abstracción estable y testeable.

Diseño:
    - FilterProfile es inmutable (frozen=True) → seguro para pasar entre threads/etapas.
    - El mapeo de qué columnas se aplican a qué campos es DATO, no código.
    - Validación explícita en __post_init__ → fail fast si el equipo está mal configurado.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

# ---------------------------------------------------------------------------
# Constantes de dominio (NO hardcoding de equipos: estos son los CAMPOS del PIVOT)
# ---------------------------------------------------------------------------

#: Claves de los grupos de reglas de inclusión. Coinciden con las columnas del PIVOT.
INCLUIR_KEYS: tuple[str, ...] = ("nombre", "nivel1", "nivel2", "nivel3")

#: Claves de los grupos de reglas de exclusión.
EXCLUIR_KEYS: tuple[str, ...] = (
    "nombre", "nivel1", "nivel2", "nivel3",
    "generico", "componente", "organismo", "valor",
)


# ---------------------------------------------------------------------------
# Entidades de dominio
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IntencionGlobal:
    """Invariante de negocio MP: qué verbos indican servicio profesional vs. compra/insumo.

    Esta entidad es ÚNICA para toda la empresa (compartida por todos los equipos).
    Se carga de la hoja `01-Intencion_Global` del PIVOT_MAESTRO.

    Semántica:
        - `vetada`   : si alguna de estas palabras aparece en el nombre de la
                       licitación → se descarta (no negociable, no bypasseable).
                       Ej: 'adquisicion de', 'suministro de', 'mantencion'.
        - `requerida`: si alguna aparece en el nombre → confianza ALTA en que es
                       servicio profesional. Ej: 'ingenieria', 'consultoria', 'diseno'.
        - Si ambas listas están vacías → feature deshabilitado (backward compat).

    Una licitación que no matchea ni vetada ni requerida queda en ZONA GRIS
    (`Nivel Confianza = REVISAR`) — se mantiene en el reporte para que el humano
    decida, no se descarta automáticamente.
    """
    requerida: Sequence[str] = field(default_factory=tuple)
    vetada: Sequence[str] = field(default_factory=tuple)

    @property
    def habilitado(self) -> bool:
        """True si al menos una de las listas tiene contenido (= feature activado)."""
        return bool(self.requerida) or bool(self.vetada)


@dataclass(frozen=True)
class EquipoInfo:
    """Metadata de un equipo MP (Telecom, Arquitectura, Eléctrica, etc.).

    Esta entidad describe QUÉ equipos existen y dónde están sus reglas.
    Se carga desde la hoja 00-Equipos del PIVOT_MAESTRO.
    """
    codigo: str           # Identificador único: "TELECOM", "ARQ", "ELEC"
    nombre: str           # Nombre legible: "Telecomunicaciones, ITS & Seguridad"
    hoja_filtros: str     # Nombre de la hoja de Excel: "06-Telecom"
    descripcion: str = "" # Texto largo para mostrar al usuario
    activo: bool = True   # Si False, no se ofrece en el selector

    def __post_init__(self) -> None:
        if not self.codigo or not self.codigo.strip():
            raise ValueError("EquipoInfo.codigo no puede estar vacío")
        if not self.hoja_filtros or not self.hoja_filtros.strip():
            raise ValueError(f"EquipoInfo[{self.codigo}].hoja_filtros vacío")


@dataclass(frozen=True)
class FilterProfile:
    """Perfil de filtrado completo para un equipo: incluir, excluir, bypass, exclusión dura.

    Esta entidad es PURA — no sabe nada del PIVOT, pandas, ni archivos. Se construye
    desde un dict (vía ProfileLoader) y se consume desde la etapa2 (vía aplicar()).
    """
    equipo: EquipoInfo
    incluir: Mapping[str, Sequence[str]]      # {nombre: [...], nivel1: [...], ...}
    excluir: Mapping[str, Sequence[str]]      # idem
    bypass: Sequence[str] = field(default_factory=tuple)
    exclusion_dura: Sequence[str] = field(default_factory=tuple)
    intencion_global: IntencionGlobal = field(default_factory=IntencionGlobal)

    def __post_init__(self) -> None:
        # Validación: keys conocidas
        unknown_incl = set(self.incluir.keys()) - set(INCLUIR_KEYS)
        if unknown_incl:
            raise ValueError(
                f"FilterProfile[{self.equipo.codigo}].incluir contiene claves desconocidas: {unknown_incl}. "
                f"Permitidas: {INCLUIR_KEYS}"
            )
        unknown_excl = set(self.excluir.keys()) - set(EXCLUIR_KEYS)
        if unknown_excl:
            raise ValueError(
                f"FilterProfile[{self.equipo.codigo}].excluir contiene claves desconocidas: {unknown_excl}. "
                f"Permitidas: {EXCLUIR_KEYS}"
            )

    # -- Métricas de validación (usadas por el ProfileValidator y el GUI) ----

    @property
    def total_incluir(self) -> int:
        return sum(len(v) for v in self.incluir.values())

    @property
    def total_excluir(self) -> int:
        return sum(len(v) for v in self.excluir.values())

    def esta_vacio(self) -> bool:
        """True si no hay reglas de inclusión — el filtrado no producirá resultados."""
        return self.total_incluir == 0

    def resumen(self) -> dict[str, int]:
        """Diccionario con métricas resumidas, para mostrar en GUI o logs."""
        return {
            "total_incluir": self.total_incluir,
            "total_excluir": self.total_excluir,
            "bypass": len(self.bypass),
            "exclusion_dura": len(self.exclusion_dura),
            "intencion_requerida": len(self.intencion_global.requerida),
            "intencion_vetada": len(self.intencion_global.vetada),
        }
