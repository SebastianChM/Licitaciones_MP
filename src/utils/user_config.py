"""Configuración persistente del USUARIO (no del proyecto).

Guarda preferencias por usuario/máquina en %LOCALAPPDATA% (Windows),
fuera del repositorio y fuera de OneDrive — para evitar conflictos
entre máquinas y bloqueos de sincronización.

Ubicación: %LOCALAPPDATA%\\MP\\Licitaciones_MP\\config_usuario.json

Campos:
    equipo_seleccionado: código del equipo activo (ej: "TELECOM", "ARQ")
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


def _ruta_default() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "MP" / "Licitaciones_MP" / "config_usuario.json"


@dataclass
class UserConfig:
    """Preferencias persistentes por usuario."""
    equipo_seleccionado: str = ""

    # ---- Persistencia ----------------------------------------------------

    @classmethod
    def cargar(cls, ruta: Path | None = None) -> UserConfig:
        """Carga la configuración o devuelve defaults si no existe / es inválida."""
        ruta = ruta or _ruta_default()
        if not ruta.exists():
            return cls()
        try:
            data = json.loads(ruta.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return cls()
            return cls(
                equipo_seleccionado=str(data.get("equipo_seleccionado", "")).strip(),
            )
        except (json.JSONDecodeError, OSError):
            # Archivo corrupto → devolvemos defaults, no crasheamos
            return cls()

    def guardar(self, ruta: Path | None = None) -> Path:
        """Persiste la configuración. Crea el directorio si no existe."""
        ruta = ruta or _ruta_default()
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return ruta

    @staticmethod
    def ruta_default() -> Path:
        """Expone la ruta por defecto (útil para GUI y CLI)."""
        return _ruta_default()
