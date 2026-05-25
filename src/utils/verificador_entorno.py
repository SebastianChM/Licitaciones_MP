"""
Verificador de entorno para el sistema de Licitaciones Mercado Público.

Comprueba que los archivos y configuraciones requeridos estén presentes
antes de lanzar el pipeline, distinguiendo entre requisitos críticos
(que bloquean la ejecución) y advertencias (que no la bloquean).
"""
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResultadoCheck:
    """Resultado de una verificación individual de entorno."""

    nombre: str
    ok: bool
    mensaje: str
    critico: bool = True


class VerificadorEntorno:
    """
    Comprueba que los archivos y configuraciones requeridos estén presentes.

    Checks críticos (bloquean ejecución si fallan):
      - Entorno virtual .venv
      - PIVOT_MAESTRO.xlsx

    Checks no-críticos (advierten pero no bloquean):
      - Archivo .env con credenciales de API
      - Archivo de entrada Licitacion_Publicada.xlsx (Etapa 0 lo descarga)
    """

    def __init__(self, base_dir: Path) -> None:
        self._base = base_dir

    def verificar_todo(self) -> list[ResultadoCheck]:
        """Ejecuta todas las verificaciones y retorna la lista de resultados."""
        return [
            self._check_venv(),
            self._check_pivot(),
            self._check_env(),
            self._check_input(),
        ]

    def hay_errores_criticos(self, resultados: list[ResultadoCheck]) -> bool:
        """True si algún check crítico falló."""
        return any(not r.ok and r.critico for r in resultados)

    # ------------------------------------------------------------------
    # Checks individuales
    # ------------------------------------------------------------------

    def _check_venv(self) -> ResultadoCheck:
        ok = sys.prefix != sys.base_prefix
        return ResultadoCheck(
            nombre="Entorno virtual",
            ok=ok,
            mensaje="Activo" if ok else "No activo — abre con MP_Licitaciones.vbs",
            critico=True,
        )

    def _check_pivot(self) -> ResultadoCheck:
        pivot = self._base / "config_pivot" / "PIVOT_MAESTRO.xlsx"
        ok = pivot.is_file()
        return ResultadoCheck(
            nombre="PIVOT_MAESTRO.xlsx",
            ok=ok,
            mensaje="Encontrado" if ok else f"Faltante en {pivot.parent.name}/",
            critico=True,
        )

    def _check_env(self) -> ResultadoCheck:
        ok = (self._base / ".env").is_file()
        return ResultadoCheck(
            nombre="Credenciales (.env)",
            ok=ok,
            mensaje="Configurado" if ok else "No encontrado — copia .env.example → .env",
            critico=False,
        )

    def _check_input(self) -> ResultadoCheck:
        input_file = self._base / "data" / "1. INPUT" / "Licitacion_Publicada.xlsx"
        ok = input_file.is_file()
        return ResultadoCheck(
            nombre="Archivo de entrada",
            ok=ok,
            mensaje="Disponible" if ok else "Se descargará automáticamente en Etapa 0",
            critico=False,
        )
