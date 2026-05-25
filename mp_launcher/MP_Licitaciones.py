#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MP_Licitaciones.py — Panel de control profesional MP.

Arquitectura MVC con separación estricta de responsabilidades:
    DesignTokens         Sistema de diseño centralizado e inmutable.
    IconFactory          Generador de iconos vectoriales via Pillow (sin emojis, sin archivos).
    AppState             Estado encapsulado de la aplicación (modelo).
    PipelineController   Lógica de proceso completamente aislada de la UI (controlador).
    SidebarNav           Navegación lateral con branding corporativo.
    HealthCheckPanel     Panel de verificación del entorno.
    StepperWidget        Indicador de progreso por etapas con animación de pulso.
    ConsoleWidget        Consola de log estilo terminal dark con clasificación semántica.
    StatusBar            Barra de estado con cronómetro en vivo.
    LanzadorLicitaciones Ventana principal — orquestador (vista).
"""

from __future__ import annotations

__version__ = "6.0.0"

import math
import os
import queue
import re
import subprocess
import sys
import threading
import time
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Literal, Optional

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from tkinter import simpledialog
from PIL import Image, ImageDraw

#: Raíz del proyecto (dos niveles sobre este archivo: mp_launcher/ → raíz).
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
_SRC: Path = _PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from utils.verificador_entorno import VerificadorEntorno  # noqa: E402
from utils.user_config import UserConfig  # noqa: E402
from utils.config import Config as _LicitConfig  # noqa: E402
from core.profile_loader import ProfileRegistry, ProfileLoader, ProfileValidator, ProfileCopier, PivotConfigError  # noqa: E402
from core.filter_profile import EquipoInfo  # noqa: E402

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

IconName = Literal["play", "chart", "folder", "log", "stop", "check", "x_mark", "warning", "refresh"]
RGBA = tuple[int, int, int, int]

# ---------------------------------------------------------------------------
# Design Tokens — single source of truth for all visual constants
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DesignTokens:
    """
    Sistema de diseño inmutable.

    Todos los valores visuales (colores, tipografía, espaciado) se definen aquí.
    Ningún componente de UI hardcodea valores en su interior.
    """

    # Superficies — dark mode
    surface_bg:      str = "#161618"
    surface_sidebar: str = "#1C1C1E"
    surface_card:    str = "#2C2C2E"
    surface_raised:  str = "#3A3A3C"

    # Marca MP
    brand_primary: str = "#1565C0"
    brand_hover:   str = "#1E88E5"

    # Semántica
    success: str = "#30D158"
    warning: str = "#FF9F0A"
    error:   str = "#FF453A"

    # Texto
    on_surface:     str = "#F5F5F7"
    on_surface_sub: str = "#8E8E93"
    on_surface_dim: str = "#48484A"
    on_brand:       str = "#FFFFFF"

    # Terminal
    term_bg:      str = "#0D1117"
    term_fg:      str = "#E6EDF3"
    term_ts:      str = "#6A9955"
    term_error:   str = "#FF7B72"
    term_warn:    str = "#CBA6C3"
    term_success: str = "#7EE787"
    term_stage:   str = "#79C0FF"

    # Tipografía
    font:      str = "Segoe UI"
    font_mono: str = "Consolas"
    sz_xs:  int = 10
    sz_sm:  int = 11
    sz_md:  int = 13
    sz_xl:  int = 20
    sz_xxl: int = 26

    # Geometría
    radius_sm: int = 6
    radius_md: int = 10
    radius_lg: int = 14
    pad_sm:    int = 8
    pad_md:    int = 16
    pad_lg:    int = 24
    sidebar_w: int = 220
    header_h:  int = 70
    sz_lg:     int = 16   # escala completa: xs→sm→md→lg→xl→xxl


# ---------------------------------------------------------------------------
# Icon Factory — programmatic vector icons via Pillow (no emojis, no files)
# ---------------------------------------------------------------------------


class IconFactory:
    """
    Genera iconos PNG programáticamente con Pillow y los envuelve en CTkImage.

    Características:
    - Renderizado a 2x para soporte HiDPI/Retina, downsampled con LANCZOS.
    - Cache en memoria: (nombre, tamaño, color) -> CTkImage.
    - Sin archivos externos ni recursos embebidos.

    Raises:
        ValueError: Si se solicita un nombre de icono no registrado.
    """

    _cache: dict[tuple[str, int, str], ctk.CTkImage] = {}

    @classmethod
    def get(cls, name: IconName, size: int = 18, color: str = "#F5F5F7") -> ctk.CTkImage:
        """
        Devuelve un CTkImage desde cache o lo genera si no existe.

        Args:
            name:  Identificador del icono (IconName).
            size:  Lado del cuadrado en píxeles lógicos.
            color: Color del icono en formato hexadecimal (#RRGGBB).

        Returns:
            CTkImage lista para asignar a image= en cualquier widget CTk.
        """
        key = (name, size, color)
        if key not in cls._cache:
            cls._cache[key] = cls._render(name, size, color)
        return cls._cache[key]

    @classmethod
    def _render(cls, name: IconName, size: int, color: str) -> ctk.CTkImage:
        scale = 2
        s = size * scale
        img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        c = cls._hex_rgba(color)

        renderers: dict[str, Callable[[ImageDraw.ImageDraw, int, RGBA], None]] = {
            "play":    cls._play,
            "chart":   cls._chart,
            "folder":  cls._folder,
            "log":     cls._log,
            "stop":    cls._stop,
            "check":   cls._check,
            "x_mark":  cls._x_mark,
            "warning": cls._warning,
            "refresh": cls._refresh,
        }

        renderer = renderers.get(name)
        if renderer is None:
            raise ValueError(f"Icono desconocido: '{name}'")

        renderer(draw, s, c)
        img = img.resize((size, size), Image.Resampling.LANCZOS)
        return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))

    @staticmethod
    def _hex_rgba(h: str, alpha: int = 255) -> RGBA:
        h = h.lstrip("#")
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)

    @staticmethod
    def _play(d: ImageDraw.ImageDraw, s: int, c: RGBA) -> None:
        p = s // 5
        d.polygon([(p, p), (p, s - p), (s - p, s // 2)], fill=c)

    @staticmethod
    def _chart(d: ImageDraw.ImageDraw, s: int, c: RGBA) -> None:
        pad, n_bars = s // 7, 4
        heights = [0.40, 0.65, 0.85, 1.00]
        bar_w = (s - 2 * pad) // (n_bars * 2 - 1)
        gap, base = bar_w, s - pad
        for i, h in enumerate(heights):
            x0 = pad + i * (bar_w + gap)
            y0 = base - int((s - 2 * pad) * h)
            d.rounded_rectangle([x0, y0, x0 + bar_w, base], radius=max(1, bar_w // 4), fill=c)

    @staticmethod
    def _folder(d: ImageDraw.ImageDraw, s: int, c: RGBA) -> None:
        p, tab_w, tab_h = s // 8, s // 3, s // 7
        d.rounded_rectangle([p, s // 3 - tab_h, p + tab_w, s // 3], radius=2, fill=c)
        d.rounded_rectangle([p, s // 3, s - p, s - p], radius=max(2, s // 12), fill=c)

    @staticmethod
    def _log(d: ImageDraw.ImageDraw, s: int, c: RGBA) -> None:
        p, lw = s // 6, max(2, s // 14)
        d.rounded_rectangle([p, p // 2, s - p, s - p // 2], radius=max(2, s // 16), outline=c, width=lw)
        for i in range(3):
            y = s // 3 + i * (s // 7)
            d.line([(p + p // 2, y), (s - p - p // 2, y)], fill=c, width=max(1, lw - 1))

    @staticmethod
    def _stop(d: ImageDraw.ImageDraw, s: int, c: RGBA) -> None:
        p = s // 4
        d.rounded_rectangle([p, p, s - p, s - p], radius=max(2, s // 10), fill=c)

    @staticmethod
    def _check(d: ImageDraw.ImageDraw, s: int, c: RGBA) -> None:
        lw, p = max(2, s // 8), s // 6
        d.line([(p, s // 2), (s // 2 - p // 4, s - p - p // 4), (s - p, p)],
               fill=c, width=lw, joint="curve")

    @staticmethod
    def _x_mark(d: ImageDraw.ImageDraw, s: int, c: RGBA) -> None:
        lw, p = max(2, s // 8), s // 5
        d.line([(p, p), (s - p, s - p)], fill=c, width=lw)
        d.line([(s - p, p), (p, s - p)], fill=c, width=lw)

    @staticmethod
    def _warning(d: ImageDraw.ImageDraw, s: int, c: RGBA) -> None:
        p = s // 8
        d.polygon([(s // 2, p), (s - p, s - p), (p, s - p)], fill=c)
        bar_c: RGBA = (0, 0, 0, 200)
        mx, r = s // 2, s // 16
        d.line([(mx, s // 3 + p), (mx, s - s // 3)], fill=bar_c, width=max(2, s // 10))
        d.ellipse([mx - r, s - s // 4, mx + r, s - s // 4 + s // 8], fill=bar_c)

    @staticmethod
    def _refresh(d: ImageDraw.ImageDraw, s: int, c: RGBA) -> None:
        p, lw = s // 6, max(2, s // 10)
        d.arc([p, p, s - p, s - p], start=60, end=360, fill=c, width=lw)
        mid, arr = s // 2, s // 5
        d.polygon([(mid + arr, p + arr), (mid, p - arr // 2 + p),
                   (mid - arr // 2, p + arr + arr // 2)], fill=c)


# ---------------------------------------------------------------------------
# App State — single mutable model for the application
# ---------------------------------------------------------------------------


@dataclass
class AppState:
    """
    Estado mutable de la aplicación.

    Se inyecta por referencia a todos los componentes que necesitan leerlo.
    No es una variable global; su ciclo de vida lo gestiona LanzadorLicitaciones.
    """

    proceso_activo:     bool = False
    proceso_detenido:   bool = False
    etapa_actual:       Optional[int] = None
    tiempo_inicio:      Optional[datetime] = None
    proceso_actual:     Optional[subprocess.Popen] = None
    ultimo_run_exitoso: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Pipeline Controller — all process logic, zero UI dependency
# ---------------------------------------------------------------------------


class PipelineController:
    """
    Controlador del subproceso del pipeline.

    Lanza el proceso en un hilo daemon y notifica a la UI mediante callbacks.
    No importa ningún módulo de UI. Patrón: Command + Observer.

    Args:
        root_path:   Directorio raíz del proyecto.
        state:       Estado compartido de la aplicación (inyectado).
        on_line:     Callback(línea: str) invocado por cada línea de stdout/stderr.
        on_complete: Callback(returncode: int) invocado al terminar el proceso.
        on_error:    Callback(exc: Exception) invocado ante errores del controlador.
    """

    _STAGE_PATTERNS: tuple[tuple[str, int], ...] = (
        ("etapa 0", 0), ("etapa0", 0),
        ("etapa 1", 1), ("etapa1", 1),
        ("etapa 2", 2), ("etapa2", 2),
        ("etapa 3", 3), ("etapa3", 3),
        ("etapa 4", 4), ("etapa4", 4),
        ("etapa 5", 5), ("etapa5", 5),
    )

    def __init__(
        self,
        root_path: Path,
        state: AppState,
        on_line: Callable[[str], None],
        on_complete: Callable[[int], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        self._root_path = root_path
        self._state = state
        self._on_line = on_line
        self._on_complete = on_complete
        self._on_error = on_error

    def run(self, cmd: list[str]) -> None:
        """Lanza el proceso en un thread daemon. No bloquea el hilo principal."""
        if self._state.proceso_activo:
            return
        # La bandera se activa aquí, antes del thread, para que cualquier llamada
        # concurrente (rara pero posible) también sea bloqueada por la guardia.
        self._state.proceso_activo = True
        threading.Thread(target=self._execute, args=(cmd,), daemon=True).start()

    def stop(self) -> None:
        """Envía SIGTERM al proceso activo de forma segura."""
        proc = self._state.proceso_actual
        if proc is not None and proc.poll() is None:
            self._state.proceso_detenido = True
            try:
                proc.terminate()
            except OSError:
                pass

    def _execute(self, cmd: list[str]) -> None:
        """Núcleo de ejecución: lanza el proceso y consume stdout línea a línea."""
        returncode: Optional[int] = None
        try:
            env = {
                **os.environ,
                "PYTHONUNBUFFERED":  "1",
                "PYTHONUTF8":        "1",
                "PYTHONIOENCODING":  "utf-8",
            }
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="replace",
                env=env,
                cwd=self._root_path,
            )
            self._state.proceso_actual = proc

            if proc.stdout is None:
                raise RuntimeError("No se pudo capturar stdout del subproceso")

            for line in iter(proc.stdout.readline, ""):
                stripped = line.rstrip()
                if stripped:
                    self._on_line(stripped)

            proc.stdout.close()
            proc.wait()
            # proc.returncode está garantizado como int tras wait(), pero
            # Pylance lo tipifica como Optional[int]; el fallback -1 es seguro.
            returncode: int = proc.returncode if proc.returncode is not None else -1

        except Exception as exc:
            self._on_error(exc)
            return
        finally:
            self._state.proceso_actual  = None
            # Reset síncrono: garantiza estado correcto aunque after() no procese
            # el callback (p.ej. si la ventana se destruye antes del próximo tick).
            self._state.proceso_activo  = False

        # Fuera del try para que una excepción en el callback no se confunda
        # con un error del controlador y no oculte el código de retorno real.
        self._on_complete(returncode)

    @classmethod
    def detect_stage(cls, line: str) -> Optional[int]:
        """
        Detecta el número de etapa (0-5) en una línea de log.

        Args:
            line: Línea de texto del stdout del pipeline.

        Returns:
            Número de etapa si se detecta, None en caso contrario.
        """
        lower = line.lower()
        for pattern, stage_num in cls._STAGE_PATTERNS:
            if pattern in lower:
                return stage_num
        return None


# ---------------------------------------------------------------------------
# UI Components
# ---------------------------------------------------------------------------


class SidebarNav(ctk.CTkFrame):
    """
    Panel de navegación lateral fijo con branding corporativo MP.

    Expone set_running() y set_running_allowed() para control externo del estado
    de los botones de acción según el estado del proceso y del entorno.
    """

    def __init__(
        self,
        parent: tk.Misc,
        tokens: DesignTokens,
        on_run_full: Callable[[], None],
        on_run_incremental: Callable[[], None],
        on_open_results: Callable[[], None],
        on_open_log: Callable[[], None],
        on_stop: Callable[[], None],
    ) -> None:
        super().__init__(
            parent,
            width=tokens.sidebar_w,
            fg_color=tokens.surface_sidebar,
            corner_radius=0,
        )
        self._t = tokens
        self._actions_allowed = True
        self._process_running = False
        self._btn_run_full: Optional[ctk.CTkButton] = None
        self._btn_run_incr: Optional[ctk.CTkButton] = None
        self._btn_stop:     Optional[ctk.CTkButton] = None
        self._equipo_selector: Optional["EquipoSelector"] = None
        self.pack_propagate(False)
        self._build(on_run_full, on_run_incremental, on_open_results, on_open_log, on_stop)

    @property
    def equipo_selector(self) -> Optional["EquipoSelector"]:
        """Acceso al selector de equipo para que el lanzador consulte el código activo."""
        return self._equipo_selector

    def _build(
        self,
        on_run_full: Callable,
        on_run_incremental: Callable,
        on_open_results: Callable,
        on_open_log: Callable,
        on_stop: Callable,
    ) -> None:
        t = self._t
        self._build_brand()
        self._build_divider(top=t.pad_lg)

        # Sección EQUIPO ACTIVO — antes de ACCIONES porque define qué se va a procesar
        self._build_section("EQUIPO ACTIVO")
        self._equipo_selector = EquipoSelector(self, t)
        self._equipo_selector.pack(fill="x")
        self._build_divider()

        self._build_section("ACCIONES")
        self._btn_run_full = self._add_button(
            "Pipeline Completo", "play", t.brand_primary, t.brand_hover, on_run_full,
        )
        self._btn_run_incr = self._add_button(
            "Solo Incremental", "chart", t.surface_raised, t.brand_primary, on_run_incremental,
        )
        self._btn_stop = self._add_button(
            "Detener Proceso", "stop", t.surface_raised, "#3A1A1A", on_stop,
            text_color=t.error,
        )
        self._btn_stop.configure(state="disabled")

        self._build_divider()
        self._build_section("UTILIDADES")
        self._add_button("Abrir Resultados", "folder", t.surface_raised, t.brand_primary, on_open_results)
        self._add_button("Ultimo Log",        "log",    t.surface_raised, t.brand_primary, on_open_log)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=t.pad_md, pady=t.pad_md)
        ctk.CTkLabel(
            footer,
            text=f"Licitaciones MP  v{__version__}",
            font=(t.font, t.sz_xs),
            text_color=t.on_surface_dim,
        ).pack(anchor="w")

    def _build_brand(self) -> None:
        t = self._t
        brand = ctk.CTkFrame(self, fg_color=t.brand_primary, height=t.header_h, corner_radius=0)
        brand.pack(fill="x")
        brand.pack_propagate(False)
        ctk.CTkLabel(brand, text="MP",
                     font=(t.font, t.sz_xxl, "bold"), text_color=t.on_brand,
                     ).place(relx=0.5, rely=0.38, anchor="center")
        ctk.CTkLabel(brand, text="CONSULTING",
                     font=(t.font, t.sz_xs, "normal"), text_color="#BBDEFB",
                     ).place(relx=0.5, rely=0.72, anchor="center")

    def _build_section(self, label: str) -> None:
        t = self._t
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=t.pad_sm, pady=(t.pad_sm, 4))
        ctk.CTkLabel(frame, text=label,
                     font=(t.font, t.sz_xs, "bold"), text_color=t.on_surface_sub,
                     ).pack(anchor="w", padx=t.pad_sm)

    def _build_divider(self, top: int = 0) -> None:
        t = self._t
        ctk.CTkFrame(self, fg_color=t.surface_raised, height=1).pack(
            fill="x", padx=t.pad_md, pady=(top, t.pad_md),
        )

    def _add_button(
        self,
        label: str,
        icon_name: IconName,
        fg_color: str,
        hover_color: str,
        command: Callable,
        text_color: Optional[str] = None,
    ) -> ctk.CTkButton:
        t = self._t
        resolved = text_color or t.on_surface
        btn = ctk.CTkButton(
            self,
            text=f"   {label}",
            image=IconFactory.get(icon_name, 16, resolved),
            anchor="w",
            font=(t.font, t.sz_sm),
            fg_color=fg_color,
            hover_color=hover_color,
            text_color=resolved,
            corner_radius=t.radius_md,
            height=36,
            command=command,
        )
        btn.pack(fill="x", padx=t.pad_sm, pady=2)
        return btn

    def set_running(self, running: bool) -> None:
        """Bloquea/desbloquea botones de acción durante la ejecución de un proceso."""
        self._process_running = running
        run_state  = "disabled" if running else ("normal" if self._actions_allowed else "disabled")
        stop_state = "normal"   if running else "disabled"
        for btn in (self._btn_run_full, self._btn_run_incr):
            if btn is not None:
                btn.configure(state=run_state)
        if self._btn_stop is not None:
            self._btn_stop.configure(state=stop_state)

    def set_running_allowed(self, allowed: bool) -> None:
        """Habilita/inhabilita acciones según el estado de verificación del entorno."""
        self._actions_allowed = allowed
        if not self._process_running:
            state = "normal" if allowed else "disabled"
            for btn in (self._btn_run_full, self._btn_run_incr):
                if btn is not None:
                    btn.configure(state=state)


class EquipoSelector(ctk.CTkFrame):
    """Selector de equipo MP activo.

    Lee el catálogo desde la hoja 00-Equipos del PIVOT_MAESTRO, permite cambiarlo,
    persiste la elección en %LOCALAPPDATA%\\MP\\Licitaciones_MP\\config_usuario.json
    y ofrece dos atajos: editar las reglas (abre Excel en el archivo) y validar
    el perfil (muestra advertencias del ProfileValidator).

    Diseño: el widget es la ÚNICA fuente para `get_codigo_equipo()`, lo que
    desacopla la elección del usuario del subprocess del pipeline.
    """

    def __init__(
        self,
        parent: tk.Misc,
        tokens: "DesignTokens",
        on_change: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self._t = tokens
        self._on_change = on_change
        self._user_cfg = UserConfig.cargar()
        self._equipos: list[EquipoInfo] = []
        self._codigo_actual: str = ""
        self._combo: Optional[ctk.CTkComboBox] = None
        self._lbl_error: Optional[ctk.CTkLabel] = None
        self._build()
        self._cargar_equipos()

    # ── Public API ────────────────────────────────────────────────────────

    def get_codigo_equipo(self) -> str:
        """Código del equipo actualmente seleccionado (mayúsculas)."""
        return self._codigo_actual

    def refrescar(self) -> None:
        """Re-lee la lista de equipos desde el PIVOT (tras editar el Excel)."""
        self._cargar_equipos()

    # ── UI build ──────────────────────────────────────────────────────────

    def _build(self) -> None:
        t = self._t
        # Nota: el header "EQUIPO ACTIVO" lo provee SidebarNav vía _build_section
        # para mantener consistencia tipográfica con las otras secciones.

        self._combo = ctk.CTkComboBox(
            self,
            values=["(cargando...)"],
            command=self._on_combo_change,
            font=(t.font, t.sz_sm),
            dropdown_font=(t.font, t.sz_sm),
            state="readonly",
            height=32,
            corner_radius=t.radius_md,
            fg_color=t.surface_raised,
            border_color=t.surface_raised,
            button_color=t.brand_primary,
            button_hover_color=t.brand_hover,
        )
        self._combo.pack(fill="x", padx=t.pad_sm, pady=(2, 4))

        # Botones contextuales
        btn_editar = ctk.CTkButton(
            self,
            text="   Editar mis filtros",
            anchor="w",
            font=(t.font, t.sz_sm),
            fg_color=t.surface_raised,
            hover_color=t.brand_primary,
            text_color=t.on_surface,
            corner_radius=t.radius_md,
            height=32,
            command=self._cmd_editar,
        )
        btn_editar.pack(fill="x", padx=t.pad_sm, pady=2)

        btn_validar = ctk.CTkButton(
            self,
            text="   Validar filtros",
            anchor="w",
            font=(t.font, t.sz_sm),
            fg_color=t.surface_raised,
            hover_color=t.brand_primary,
            text_color=t.on_surface,
            corner_radius=t.radius_md,
            height=32,
            command=self._cmd_validar,
        )
        btn_validar.pack(fill="x", padx=t.pad_sm, pady=(2, 4))

        btn_init = ctk.CTkButton(
            self,
            text="   Inicializar desde otro equipo",
            anchor="w",
            font=(t.font, t.sz_sm),
            fg_color=t.surface_raised,
            hover_color=t.brand_primary,
            text_color=t.on_surface,
            corner_radius=t.radius_md,
            height=32,
            command=self._cmd_inicializar,
        )
        btn_init.pack(fill="x", padx=t.pad_sm, pady=(2, 4))

        # Label opcional para errores
        self._lbl_error = ctk.CTkLabel(
            self, text="", font=(t.font, t.sz_xs),
            text_color=t.error, anchor="w", justify="left", wraplength=180,
        )
        # se mostrará solo si hay error
        self._lbl_error.pack(fill="x", padx=t.pad_sm)
        self._lbl_error.pack_forget()

    # ── Carga del catálogo de equipos ─────────────────────────────────────

    def _pivot_path(self) -> Path:
        return _LicitConfig().PIVOT_MAESTRO

    def _cargar_equipos(self) -> None:
        try:
            registry = ProfileRegistry(self._pivot_path())
            self._equipos = registry.equipos_activos()
        except PivotConfigError as e:
            self._equipos = []
            self._mostrar_error(f"PIVOT mal configurado: {e}")
            if self._combo is not None:
                self._combo.configure(values=["(error)"])
                self._combo.set("(error)")
            return

        if not self._equipos:
            self._mostrar_error("No hay equipos activos en 00-Equipos.")
            if self._combo is not None:
                self._combo.configure(values=["(vacío)"])
                self._combo.set("(vacío)")
            return

        self._ocultar_error()
        valores = [self._label(e) for e in self._equipos]
        if self._combo is not None:
            self._combo.configure(values=valores)

        # Resolver selección inicial: UserConfig.equipo_seleccionado → primer activo
        codigo_pref = (self._user_cfg.equipo_seleccionado or "").strip().upper()
        equipo = next((e for e in self._equipos if e.codigo == codigo_pref), None)
        if equipo is None:
            equipo = self._equipos[0]
        self._set_seleccion(equipo, persistir=False)

    def _label(self, e: EquipoInfo) -> str:
        return f"{e.codigo} — {e.nombre}"

    def _equipo_de_label(self, label: str) -> Optional[EquipoInfo]:
        # El código va antes del primer espacio o " — "
        codigo = label.split(" ", 1)[0].strip().upper()
        return next((e for e in self._equipos if e.codigo == codigo), None)

    def _set_seleccion(self, equipo: EquipoInfo, *, persistir: bool) -> None:
        self._codigo_actual = equipo.codigo
        if self._combo is not None:
            self._combo.set(self._label(equipo))
        if persistir and self._user_cfg.equipo_seleccionado != equipo.codigo:
            self._user_cfg.equipo_seleccionado = equipo.codigo
            try:
                self._user_cfg.guardar()
            except OSError:
                # No bloquear la UI por un fallo de persistencia
                pass
        if self._on_change is not None:
            try:
                self._on_change(equipo.codigo)
            except Exception:
                pass

    def _on_combo_change(self, value: str) -> None:
        equipo = self._equipo_de_label(value)
        if equipo is not None:
            self._set_seleccion(equipo, persistir=True)

    # ── Acciones ──────────────────────────────────────────────────────────

    def _cmd_editar(self) -> None:
        """Abre PIVOT_MAESTRO.xlsx en Excel para que el usuario edite sus reglas."""
        pivot = self._pivot_path()
        if not pivot.exists():
            messagebox.showerror(
                "PIVOT no encontrado",
                f"No se encontró el archivo:\n{pivot}",
            )
            return
        try:
            os.startfile(str(pivot))
        except OSError as e:
            messagebox.showerror("Error al abrir Excel", str(e))
            return
        equipo = next((e for e in self._equipos if e.codigo == self._codigo_actual), None)
        hoja = equipo.hoja_filtros if equipo else "06-Telecom"
        messagebox.showinfo(
            "Editar filtros",
            f"Se abrió PIVOT_MAESTRO.xlsx.\n\n"
            f"Edita la hoja:  {hoja}\n\n"
            f"Cuando guardes y cierres, los cambios estarán activos en la próxima ejecución.",
        )

    def _cmd_validar(self) -> None:
        """Carga el FilterProfile del equipo y muestra advertencias del validador."""
        if not self._codigo_actual:
            messagebox.showwarning("Sin equipo", "No hay un equipo seleccionado.")
            return
        try:
            registry = ProfileRegistry(self._pivot_path())
            equipo = registry.buscar(self._codigo_actual)
            profile = ProfileLoader(self._pivot_path()).cargar(equipo)
        except PivotConfigError as e:
            messagebox.showerror("Error de configuración", str(e))
            return

        problemas = ProfileValidator.validar(profile)
        r = profile.resumen()
        resumen = (
            f"Equipo: {equipo.codigo} — {equipo.nombre}\n"
            f"Hoja: {equipo.hoja_filtros}\n\n"
            f"Reglas cargadas:\n"
            f"  - Inclusión:       {r['total_incluir']}\n"
            f"  - Exclusión:       {r['total_excluir']}\n"
            f"  - Bypass:          {r['bypass']}\n"
            f"  - Exclusión dura:  {r['exclusion_dura']}\n"
        )
        if not problemas:
            messagebox.showinfo("Filtros válidos", resumen + "\nSin problemas detectados.")
        else:
            detalle = "\n".join(f"• {p}" for p in problemas)
            messagebox.showwarning(
                "Advertencias del perfil",
                resumen + "\nProblemas detectados:\n" + detalle,
            )

    def _cmd_inicializar(self) -> None:
        """Copia las reglas de otro equipo a la hoja del equipo actual.

        Flujo:
          1) Pregunta el código del equipo ORIGEN.
          2) Verifica que origen y destino existan.
          3) Si el destino ya tiene datos, pide confirmación de sobrescritura.
          4) Llama a ProfileCopier.copiar() y refresca el selector.
        """
        if not self._codigo_actual:
            messagebox.showwarning("Sin equipo", "No hay un equipo seleccionado.")
            return
        equipo_destino = next((e for e in self._equipos if e.codigo == self._codigo_actual), None)
        if equipo_destino is None:
            messagebox.showerror("Equipo inválido", "No se encontró el equipo activo.")
            return

        candidatos = [e for e in self._equipos if e.codigo != self._codigo_actual]
        if not candidatos:
            messagebox.showinfo(
                "Sin equipos disponibles",
                "No hay otros equipos en el catálogo para usar como plantilla.",
            )
            return

        lista = "\n".join(f"  • {e.codigo} ({e.nombre})" for e in candidatos)
        codigo_origen = simpledialog.askstring(
            "Inicializar filtros",
            (
                f"Equipo destino: {equipo_destino.codigo} ({equipo_destino.nombre})\n\n"
                f"Equipos disponibles como plantilla:\n{lista}\n\n"
                f"Ingresa el CÓDIGO del equipo origen:"
            ),
            parent=self.winfo_toplevel(),
        )
        if not codigo_origen:
            return
        codigo_origen = codigo_origen.strip().upper()
        equipo_origen = next((e for e in candidatos if e.codigo == codigo_origen), None)
        if equipo_origen is None:
            messagebox.showerror(
                "Código inválido",
                f"'{codigo_origen}' no corresponde a ningún equipo en el catálogo.",
            )
            return

        copier = ProfileCopier(self._pivot_path())

        # Primer intento sin sobrescribir
        try:
            filas = copier.copiar(equipo_origen.hoja_filtros, equipo_destino.hoja_filtros)
        except PivotConfigError as e:
            # Caso típico: destino tiene datos. Pedir confirmación.
            if "ya contiene reglas" not in str(e):
                messagebox.showerror("Error", str(e))
                return
            if not messagebox.askyesno(
                "Sobrescribir reglas",
                (
                    f"La hoja '{equipo_destino.hoja_filtros}' ya tiene reglas.\n\n"
                    f"¿Deseas REEMPLAZARLAS con las de '{equipo_origen.codigo}'?\n"
                    f"(Se recomienda hacer respaldo del PIVOT antes.)"
                ),
            ):
                return
            try:
                filas = copier.copiar(
                    equipo_origen.hoja_filtros,
                    equipo_destino.hoja_filtros,
                    sobrescribir=True,
                )
            except PivotConfigError as e2:
                messagebox.showerror("Error al copiar", str(e2))
                return

        messagebox.showinfo(
            "Filtros inicializados",
            (
                f"Se copiaron {filas} filas de reglas desde "
                f"'{equipo_origen.codigo}' hacia '{equipo_destino.codigo}'.\n\n"
                f"Recomendación: pulsa 'Editar mis filtros' y ajusta las palabras "
                f"clave a la realidad de tu equipo."
            ),
        )
        # Refrescar el selector por si las reglas afectan algo visible.
        self.refrescar()

    # ── Errores inline ────────────────────────────────────────────────────

    def _mostrar_error(self, msg: str) -> None:
        if self._lbl_error is not None:
            self._lbl_error.configure(text=msg)
            self._lbl_error.pack(fill="x", padx=self._t.pad_sm, pady=(0, 4))

    def _ocultar_error(self) -> None:
        if self._lbl_error is not None:
            self._lbl_error.pack_forget()


class HealthCheckPanel(ctk.CTkFrame):
    """
    Panel compacto de verificación del entorno de ejecución.

    Muestra un badge por cada resultado y ofrece re-verificación
    sin reiniciar la aplicación.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        tokens: DesignTokens,
        verificador: VerificadorEntorno,
        on_state_change: Callable[[bool], None],
    ) -> None:
        super().__init__(parent, fg_color=tokens.surface_card, corner_radius=tokens.radius_lg)
        self._t = tokens
        self._verificador = verificador
        self._on_state_change = on_state_change
        self._badges_frame: Optional[ctk.CTkFrame] = None
        self._build()
        # Diferir la primera verificación para que la ventana se renderice
        # completamente antes de bloquear con I/O de disco.
        self.after(50, self.refresh)

    def _build(self) -> None:
        t = self._t
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=t.pad_md, pady=(t.pad_md, t.pad_sm))
        ctk.CTkLabel(header, text="ESTADO DEL ENTORNO",
                     font=(t.font, t.sz_xs, "bold"), text_color=t.on_surface_sub,
                     ).pack(side="left")
        ctk.CTkButton(
            header, text="Re-verificar",
            image=IconFactory.get("refresh", 12, t.on_surface_sub),
            font=(t.font, t.sz_xs),
            fg_color="transparent", hover_color=t.surface_raised,
            text_color=t.on_surface_sub,
            height=24, width=95, corner_radius=t.radius_sm,
            command=self.refresh,
        ).pack(side="right")
        self._badges_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._badges_frame.pack(fill="x", padx=t.pad_md, pady=(0, t.pad_md))

    def refresh(self) -> None:
        """Re-ejecuta la verificación y actualiza los badges de estado."""
        if self._badges_frame is None:
            return
        for widget in self._badges_frame.winfo_children():
            widget.destroy()
        resultados = self._verificador.verificar_todo()
        hay_errores = self._verificador.hay_errores_criticos(resultados)
        for r in resultados:
            self._add_badge(r.nombre, r.ok, r.critico)
        self._on_state_change(hay_errores)

    def _add_badge(self, nombre: str, ok: bool, critico: bool) -> None:
        t = self._t
        if ok:
            color, icon = t.success, "check"
        elif critico:
            color, icon = t.error, "x_mark"
        else:
            color, icon = t.warning, "warning"
        badge = ctk.CTkFrame(self._badges_frame, fg_color=t.surface_raised, corner_radius=t.radius_md)
        badge.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(badge, text="", image=IconFactory.get(icon, 13, color),
                     ).pack(side="left", padx=(t.pad_sm, 4), pady=t.pad_sm)
        ctk.CTkLabel(badge, text=nombre,
                     font=(t.font, t.sz_sm, "bold"), text_color=color,
                     ).pack(side="left", padx=(0, t.pad_sm), pady=t.pad_sm)


class StepperWidget(ctk.CTkFrame):
    """
    Indicador visual de progreso por etapas del pipeline.

    Renderizado con tk.Canvas para animaciones precisas.
    Soporta cuatro estados por nodo: pending | running | done | error.
    La etapa en estado 'running' muestra un halo animado de pulso.
    """

    STAGES: tuple[tuple[str, str], ...] = (
        ("0", "Descarga"),
        ("1", "Auditoria"),
        ("2", "Filtrado"),
        ("3", "Enriquec."),
        ("4", "Reporte"),
        ("5", "Incremental"),
    )

    _STATE_STYLE: dict[str, tuple[str, str]] = {
        "pending": ("#48484A", "#636366"),
        "running": ("#1565C0", "#1E88E5"),
        "done":    ("#1A3A2A", "#30D158"),
        "error":   ("#3A1A1A", "#FF453A"),
    }

    def __init__(self, parent: ctk.CTkFrame, tokens: DesignTokens) -> None:
        super().__init__(parent, fg_color=tokens.surface_card, corner_radius=tokens.radius_lg)
        self._t = tokens
        self._stage_states: list[str] = ["pending"] * len(self.STAGES)
        self._anim_id:    Optional[str] = None
        self._anim_phase: float = 0.0
        self._anim_stage: Optional[int] = None
        self._canvas:     Optional[tk.Canvas] = None
        self._build()

    def _build(self) -> None:
        t = self._t
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=t.pad_md, pady=(t.pad_md, 0))
        ctk.CTkLabel(header, text="PROGRESO DEL PIPELINE",
                     font=(t.font, t.sz_xs, "bold"), text_color=t.on_surface_sub,
                     ).pack(side="left")
        self._canvas = tk.Canvas(self, height=80, bg=t.surface_card, highlightthickness=0)
        self._canvas.pack(fill="x", padx=t.pad_lg, pady=(t.pad_sm, t.pad_md))
        self._canvas.bind("<Configure>", lambda _: self._redraw())

    def set_stage(self, index: int, state: str) -> None:
        """
        Actualiza el estado visual de una etapa específica.

        Args:
            index: Índice de la etapa (0-5).
            state: Nuevo estado: 'pending' | 'running' | 'done' | 'error'.

        Raises:
            ValueError: Si el índice está fuera de rango o el estado es inválido.
        """
        if not 0 <= index < len(self.STAGES):
            raise ValueError(f"Indice de etapa fuera de rango: {index}")
        if state not in self._STATE_STYLE:
            raise ValueError(f"Estado invalido: '{state}'")
        self._stage_states[index] = state
        if state == "running":
            self._start_pulse(index)
        else:
            if self._anim_stage == index:
                self._stop_pulse()
            self._redraw()

    def reset(self) -> None:
        """Resetea todas las etapas a 'pending' y detiene animaciones activas."""
        self._stop_pulse()
        self._stage_states = ["pending"] * len(self.STAGES)
        self._redraw()

    def _start_pulse(self, index: int) -> None:
        self._stop_pulse()
        self._anim_stage = index
        self._anim_phase = 0.0
        self._animate()

    def _stop_pulse(self) -> None:
        if self._anim_id is not None and self._canvas is not None:
            self._canvas.after_cancel(self._anim_id)
            self._anim_id = None
        self._anim_stage = None

    def _animate(self) -> None:
        self._anim_phase = (self._anim_phase + 0.10) % (2 * math.pi)
        self._redraw(pulse_stage=self._anim_stage, phase=self._anim_phase)
        if self._canvas is not None:
            self._anim_id = self._canvas.after(50, self._animate)

    def _redraw(self, pulse_stage: Optional[int] = None, phase: float = 0.0) -> None:
        if self._canvas is None:
            return
        c = self._canvas
        c.delete("all")
        w = c.winfo_width()
        if w <= 1:
            return
        t, n = self._t, len(self.STAGES)
        step, cy, r = w / n, 36, 16
        for i, (num, name) in enumerate(self.STAGES):
            cx = int(step * i + step / 2)
            fill_c, border_c = self._STATE_STYLE[self._stage_states[i]]
            if i < n - 1:
                next_cx = int(step * (i + 1) + step / 2)
                line_c = self._STATE_STYLE[self._stage_states[i + 1]][1] \
                    if self._stage_states[i + 1] == "done" else "#3A3A3C"
                c.create_line(cx + r, cy, next_cx - r, cy, fill=line_c, width=2)
            if i == pulse_stage:
                pr = r + 5 + int(4 * math.sin(phase))
                c.create_oval(cx - pr, cy - pr, cx + pr, cy + pr, outline=border_c, width=1, fill="")
            c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=fill_c, outline=border_c, width=2)
            lc = t.on_surface if self._stage_states[i] != "pending" else t.on_surface_sub
            c.create_text(cx, cy,        text=num,  fill=lc, font=(t.font, 10, "bold"))
            c.create_text(cx, cy + r + 12, text=name, fill=lc, font=(t.font, 9))


class ConsoleWidget(ctk.CTkFrame):
    """
    Consola de log estilo terminal dark con clasificación semántica.

    Cada línea recibe:
    - Un timestamp HH:MM:SS en columna fija (coloreado en verde suave).
    - Un tag de color según la categoría: error, warn, success, stage, info.

    Expone append(message) y clear() como API pública.
    """

    #: Número máximo de líneas visibles en la consola.
    #: Líneas antiguas se eliminan en bloques (FIFO) al superarlo.
    MAX_LINES = 2_000

    _TAG_RULES: tuple[tuple[str, str], ...] = (
        (r"\b(error|exception|traceback|fallo|failed|critico)\b", "error"),
        (r"\b(warning|warn|advertencia)\b",                       "warn"),
        (r"\b(completad\w*|exito\w*|success|\[ok\])",             "success"),
        (r"\b(etapa|stage|ejecutando etapa)\b",                   "stage"),
    )

    def __init__(self, parent: ctk.CTkFrame, tokens: DesignTokens) -> None:
        super().__init__(parent, fg_color=tokens.surface_card, corner_radius=tokens.radius_lg)
        self._t = tokens
        self._line_count = 0
        self._compiled: list[tuple[re.Pattern, str]] = [
            (re.compile(pat, re.IGNORECASE), tag) for pat, tag in self._TAG_RULES
        ]
        self._lbl_count:   Optional[ctk.CTkLabel]   = None
        self._textbox:    Optional[ctk.CTkTextbox] = None
        self._btn_scroll: Optional[ctk.CTkButton]  = None
        self._auto_scroll: bool = True
        self._build()

    def _build(self) -> None:
        t = self._t
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=t.pad_md, pady=(t.pad_md, 0))
        ctk.CTkLabel(header, text="CONSOLA DE EJECUCION",
                     font=(t.font, t.sz_xs, "bold"), text_color=t.on_surface_sub,
                     ).pack(side="left")
        self._lbl_count = ctk.CTkLabel(header, text="0 lineas",
                                        font=(t.font, t.sz_xs), text_color=t.on_surface_dim)
        self._lbl_count.pack(side="right")
        ctk.CTkButton(
            header, text="Limpiar",
            image=IconFactory.get("x_mark", 11, t.on_surface_sub),
            font=(t.font, t.sz_xs),
            fg_color="transparent", hover_color=t.surface_raised,
            text_color=t.on_surface_sub,
            height=22, width=68, corner_radius=t.radius_sm,
            command=self.clear,
        ).pack(side="right", padx=(0, t.pad_sm))
        self._btn_scroll = ctk.CTkButton(
            header, text="En vivo",
            font=(t.font, t.sz_xs),
            fg_color="transparent", hover_color=t.surface_raised,
            text_color=t.success,
            height=22, width=72, corner_radius=t.radius_sm,
            command=self._toggle_auto_scroll,
        )
        self._btn_scroll.pack(side="right", padx=(0, 4))
        self._textbox = ctk.CTkTextbox(
            self,
            font=(t.font_mono, t.sz_sm),
            fg_color=t.term_bg,
            text_color=t.term_fg,
            corner_radius=t.radius_md,
            state="disabled",
            wrap="word",
        )
        self._textbox.pack(fill="both", expand=True, padx=t.pad_sm, pady=t.pad_sm)
        inner: tk.Text = self._textbox._textbox  # type: ignore[attr-defined]
        inner.tag_config("ts",      foreground=t.term_ts)
        inner.tag_config("info",    foreground=t.term_fg)
        inner.tag_config("warn",    foreground=t.term_warn)
        inner.tag_config("error",   foreground=t.term_error,   font=(t.font_mono, t.sz_sm, "bold"))
        inner.tag_config("success", foreground=t.term_success)
        inner.tag_config("stage",   foreground=t.term_stage,   font=(t.font_mono, t.sz_sm, "bold"))

    def append(self, message: str) -> None:
        """
        Agrega una línea al log con timestamp y coloración semántica.

        Debe llamarse desde el hilo principal de la UI (o a través de after()).
        """
        if self._textbox is None or self._lbl_count is None:
            return
        ts = time.strftime("%H:%M:%S")
        tag = self._classify(message)
        inner: tk.Text = self._textbox._textbox  # type: ignore[attr-defined]
        inner.configure(state="normal")
        ts_start = inner.index("end-1c")
        inner.insert("end", f"{ts}  ")
        inner.tag_add("ts", ts_start, f"{ts_start}+{len(ts) + 2}c")
        msg_start = inner.index("end-1c")
        inner.insert("end", f"{message}\n")
        inner.tag_add(tag, msg_start, inner.index("end-1c"))
        inner.configure(state="disabled")
        if self._auto_scroll:
            inner.see("end")
        self._line_count += 1
        self._lbl_count.configure(text=f"{self._line_count} lineas")
        # Truncar bloque de 200 líneas cuando se supera el cap para amortiguar
        # el coste de reindexación del tk.Text (no truncar línea a línea).
        if self._line_count > self.MAX_LINES + 200:
            inner.configure(state="normal")
            inner.delete("1.0", f"{self._line_count - self.MAX_LINES}.0")
            inner.configure(state="disabled")
            self._line_count = self.MAX_LINES

    def clear(self) -> None:
        """Limpia todo el contenido de la consola y resetea el contador."""
        if self._textbox is None or self._lbl_count is None:
            return
        self._textbox.configure(state="normal")
        self._textbox.delete("1.0", "end")
        self._textbox.configure(state="disabled")
        self._line_count = 0
        self._lbl_count.configure(text="0 lineas")

    def _toggle_auto_scroll(self) -> None:
        """Alterna entre scroll automático (En vivo) y scroll manual libre (Pausado)."""
        t = self._t
        self._auto_scroll = not self._auto_scroll
        if self._btn_scroll is not None:
            if self._auto_scroll:
                self._btn_scroll.configure(text="En vivo", text_color=t.success)
            else:
                self._btn_scroll.configure(text="Pausado", text_color=t.warning)

    def _classify(self, text: str) -> str:
        """Clasifica una línea de texto en una categoría de color."""
        for pattern, tag in self._compiled:
            if pattern.search(text):
                return tag
        return "info"


class StatusBar(ctk.CTkFrame):
    """Barra de estado inferior con mensaje descriptivo y cronómetro en vivo."""

    def __init__(self, parent: ctk.CTkFrame, tokens: DesignTokens) -> None:
        super().__init__(parent, fg_color=tokens.surface_sidebar, corner_radius=0, height=34)
        self._t = tokens
        self._timer_running = False
        self._start_time: Optional[datetime] = None
        self._after_id:   Optional[str]      = None
        self.pack_propagate(False)
        self._build()

    def _build(self) -> None:
        t = self._t
        self._lbl_status = ctk.CTkLabel(
            self, text="Listo",
            font=(t.font, t.sz_sm), text_color=t.on_surface_sub,
        )
        self._lbl_status.pack(side="left", padx=t.pad_md)
        self._lbl_timer = ctk.CTkLabel(
            self, text="",
            font=(t.font_mono, t.sz_sm), text_color=t.on_surface_dim,
        )
        self._lbl_timer.pack(side="right", padx=t.pad_md)

    def set_status(self, text: str, color: Optional[str] = None) -> None:
        self._lbl_status.configure(text=text, text_color=color or self._t.on_surface_sub)

    def start_timer(self) -> None:
        self._start_time = datetime.now()
        self._timer_running = True
        self._tick()

    def stop_timer(self) -> None:
        self._timer_running = False
        if self._after_id is not None:
            self._lbl_timer.after_cancel(self._after_id)
            self._after_id = None

    def _tick(self) -> None:
        if not self._timer_running or self._start_time is None:
            return
        elapsed = int((datetime.now() - self._start_time).total_seconds())
        h, rem = divmod(elapsed, 3600)
        m, s   = divmod(rem, 60)
        self._lbl_timer.configure(text=f"{h:02d}:{m:02d}:{s:02d}")
        self._after_id = self._lbl_timer.after(1000, self._tick)


# ---------------------------------------------------------------------------
# Main Application Window
# ---------------------------------------------------------------------------


class LanzadorLicitaciones(ctk.CTk):
    """
    Ventana principal del Panel de Control MP.

    Orquesta los componentes UI y el controlador de pipeline.
    Patrón MVC: esta clase es la Vista, PipelineController el Controlador,
    AppState el Modelo. No contiene lógica de negocio.
    """

    def __init__(self) -> None:
        super().__init__()
        self._t = DesignTokens()
        self._state = AppState()
        self._verificador = VerificadorEntorno(_PROJECT_ROOT)
        self._controller = PipelineController(
            root_path=_PROJECT_ROOT,
            state=self._state,
            on_line=self._on_line,
            on_complete=self._on_complete,
            on_error=self._on_error,
        )
        self._sidebar:    Optional[SidebarNav]       = None
        self._health:     Optional[HealthCheckPanel] = None
        self._stepper:    Optional[StepperWidget]    = None
        self._console:    Optional[ConsoleWidget]    = None
        self._status_bar: Optional[StatusBar]        = None
        # Cola thread-safe para líneas de stdout.
        # El hilo worker escribe; el bucle _flush_queue lee en el hilo UI.
        self._line_queue: queue.SimpleQueue[str] = queue.SimpleQueue()
        self._configure_window()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _configure_window(self) -> None:
        t = self._t
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title("MP — Sistema de Licitaciones Mercado Publico")
        self.geometry("900x660")
        self.minsize(800, 580)
        self.configure(fg_color=t.surface_bg)
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - 900) // 2
        y = (self.winfo_screenheight() - 660) // 2
        self.geometry(f"900x660+{x}+{y}")

    def _build_ui(self) -> None:
        t = self._t
        self._sidebar = SidebarNav(
            self, t,
            on_run_full=self._cmd_run_full,
            on_run_incremental=self._cmd_run_incremental,
            on_open_results=self._cmd_open_results,
            on_open_log=self._cmd_open_last_log,
            on_stop=self._cmd_stop,
        )
        self._sidebar.pack(side="left", fill="y")
        main = ctk.CTkFrame(self, fg_color=t.surface_bg, corner_radius=0)
        main.pack(side="left", fill="both", expand=True)
        content = ctk.CTkFrame(main, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=t.pad_lg, pady=t.pad_lg)
        self._health = HealthCheckPanel(
            content, t, self._verificador, on_state_change=self._on_env_state_change,
        )
        self._health.pack(fill="x", pady=(0, t.pad_md))
        self._stepper = StepperWidget(content, t)
        self._stepper.pack(fill="x", pady=(0, t.pad_md))
        self._console = ConsoleWidget(content, t)
        self._console.pack(fill="both", expand=True)
        self._status_bar = StatusBar(main, t)
        self._status_bar.pack(side="bottom", fill="x")
        if self._console is not None:
            self._console.append("Panel de Control MP iniciado  selecciona una accion para comenzar")
        # Bucle permanente de vaciado del buffer de stdout (20Hz).
        # Se inicia aquí una sola vez y se auto-programa mientras la ventana exista.
        self.after(50, self._flush_queue)

    # ── Command Handlers ──────────────────────────────────────────────────────

    def _equipo_args(self) -> list[str]:
        """Args adicionales para CLI según el equipo activo en el selector."""
        if self._sidebar is None or self._sidebar.equipo_selector is None:
            return []
        codigo = self._sidebar.equipo_selector.get_codigo_equipo()
        return ["--equipo", codigo] if codigo else []

    def _cmd_run_full(self) -> None:
        script = str(_PROJECT_ROOT / "run_pipeline.py")
        self._launch(cmd=[sys.executable, "-u", script, *self._equipo_args()],
                     message="Ejecutando pipeline completo (etapas 0 a 5)")

    def _cmd_run_incremental(self) -> None:
        script = str(_PROJECT_ROOT / "run_pipeline.py")
        self._launch(
            cmd=[sys.executable, "-u", script, "--etapas", "5", "--standalone", "--no-descargar",
                 *self._equipo_args()],
            message="Ejecutando analisis incremental (etapa 5)",
        )

    def _cmd_stop(self) -> None:
        self._controller.stop()
        if self._console is not None:
            self._console.append("Solicitud de detencion enviada al proceso")
        if self._status_bar is not None:
            self._status_bar.set_status("Deteniendo proceso...", self._t.warning)

    def _cmd_open_results(self) -> None:
        carpeta = _PROJECT_ROOT / "data" / "2. OUTPUT" / "5. PRESENTACION"
        carpeta.mkdir(parents=True, exist_ok=True)
        os.startfile(str(carpeta))

    def _cmd_open_last_log(self) -> None:
        log_dir = _PROJECT_ROOT / "data" / "2. OUTPUT" / "1. LOGS"
        logs = sorted(log_dir.glob("*.log"), key=lambda f: f.stat().st_mtime, reverse=True)
        if logs:
            os.startfile(str(logs[0]))
        else:
            messagebox.showinfo("Sin logs", "No se encontraron archivos de log todavia.")

    # ── Internal Orchestration ────────────────────────────────────────────────

    def _launch(self, cmd: list[str], message: str) -> None:
        """Prepara el estado de la UI y delega la ejecución al controlador."""
        self._state.proceso_detenido = False
        self._state.etapa_actual     = None
        if self._sidebar is not None:
            self._sidebar.set_running(True)
        if self._stepper is not None:
            self._stepper.reset()
        if self._status_bar is not None:
            self._status_bar.set_status(message, self._t.brand_primary)
            self._status_bar.start_timer()
        if self._console is not None:
            self._console.append(f"Iniciando: {message}")
        self._controller.run(cmd)

    def _on_env_state_change(self, hay_errores: bool) -> None:
        if self._sidebar is not None:
            self._sidebar.set_running_allowed(not hay_errores)
        if self._status_bar is not None:
            if hay_errores:
                self._status_bar.set_status("Configuracion incompleta  revisa el entorno", self._t.error)
            else:
                self._status_bar.set_status("Listo para ejecutar")

    # ── Process Callbacks (worker thread -> UI thread via after()) ────────────

    def _on_line(self, line: str) -> None:
        """Thread-safe: encola la línea de stdout para procesamiento en lotes en el hilo UI."""
        self._line_queue.put(line)

    def _flush_queue(self) -> None:
        """
        Bucle de vaciado del buffer de stdout (20Hz).

        Procesa hasta 50 líneas por tick para no bloquear el event loop bajo
        carga alta. Se auto-programa mientras la ventana exista.
        """
        try:
            for _ in range(50):
                try:
                    self._process_line(self._line_queue.get_nowait())
                except queue.Empty:
                    break
            self.after(50, self._flush_queue)
        except tk.TclError:
            pass  # La ventana fue destruida; el bucle termina limpiamente.

    def _process_line(self, line: str) -> None:
        """
        Aplica una línea de stdout a la consola y al stepper (hilo UI).

        Compartido por _flush_queue y el drain síncrono de _on_complete/_on_error
        para garantizar que la lógica de detección de etapas sea DRY.
        """
        if self._console is not None:
            self._console.append(line)
        stage = PipelineController.detect_stage(line)
        if stage is None:
            return
        prev = self._state.etapa_actual
        if prev is not None and prev != stage and self._stepper is not None:
            self._stepper.set_stage(prev, "done")
        self._state.etapa_actual = stage
        if self._stepper is not None:
            self._stepper.set_stage(stage, "running")

    def _on_complete(self, returncode: int) -> None:
        """Recibe código de retorno desde hilo de proceso y despacha al hilo UI."""
        def update() -> None:
            # Vaciar el buffer antes del banner de finalización para que todas
            # las líneas de stdout aparezcan ANTES del estado final.
            while True:
                try:
                    self._process_line(self._line_queue.get_nowait())
                except queue.Empty:
                    break
            self._state.proceso_activo = False
            if self._status_bar is not None:
                self._status_bar.stop_timer()
            if self._sidebar is not None:
                self._sidebar.set_running(False)
            stage = self._state.etapa_actual
            if stage is not None and self._stepper is not None:
                final = "done" if returncode == 0 and not self._state.proceso_detenido else "error"
                self._stepper.set_stage(stage, final)
            if self._state.proceso_detenido:
                msg, color, log_msg = "Proceso detenido por el usuario", self._t.warning, "Proceso detenido"
            elif returncode == 0:
                self._state.ultimo_run_exitoso = datetime.now()
                msg, color, log_msg = "Pipeline completado exitosamente", self._t.success, "Pipeline completado exitosamente"
            else:
                msg, color, log_msg = (
                    f"Pipeline finalizado con errores (codigo {returncode})",
                    self._t.error,
                    f"Finalizado con codigo {returncode}",
                )
            if self._status_bar is not None:
                self._status_bar.set_status(msg, color)
            if self._console is not None:
                self._console.append(f"-- {log_msg} --")
            # Resumen ejecutivo solo para ejecuciones exitosas (no detenidas, no fallidas).
            if returncode == 0 and not self._state.proceso_detenido:
                self._volcar_resumen_ejecutivo()
        self.after(0, update)

    def _on_error(self, exc: Exception) -> None:
        """Recibe excepción del controlador desde hilo de proceso."""
        def update() -> None:
            while True:
                try:
                    self._process_line(self._line_queue.get_nowait())
                except queue.Empty:
                    break
            self._state.proceso_activo = False
            if self._status_bar is not None:
                self._status_bar.stop_timer()
                self._status_bar.set_status("Error critico en el controlador", self._t.error)
            if self._sidebar is not None:
                self._sidebar.set_running(False)
            if self._console is not None:
                self._console.append(f"Error critico: {exc}")
        self.after(0, update)

    def _volcar_resumen_ejecutivo(self) -> None:
        """Lee el JSON del último run y vuelca un resumen amigable a la consola.

        Estructura esperada: logs/runs/run_<uuid>.json con `etapas_detalle[*].metrics_produced`.
        Se enfoca en métricas de calidad de la etapa "filtrado": volumen total → filtradas,
        recuperadas por bypass y top 10 keywords de exclusión.
        Falla silenciosamente si el archivo no existe o está corrupto: no debe romper la UI.
        """
        if self._console is None:
            return
        try:
            runs_dir = _PROJECT_ROOT / "logs" / "runs"
            if not runs_dir.exists():
                return
            archivos = sorted(runs_dir.glob("run_*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
            if not archivos:
                return
            with open(archivos[0], "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return

        etapas = data.get("etapas_detalle", []) or []
        filtrado = next((e for e in etapas if e.get("nombre_etapa") == "filtrado"), None)
        if not filtrado:
            return
        m = filtrado.get("metrics_produced", {}) or {}
        original   = m.get("original", 0)
        incluidas  = m.get("incluidas", 0)
        excluidas  = m.get("excluidas", 0)
        bypass     = m.get("bypass", 0)
        excl_dura  = m.get("exclusion_dura", 0)
        final      = m.get("final", 0)
        equipo     = m.get("equipo", "?")
        top_kw     = m.get("top_keywords_exclusion") or []
        pct        = (final / original * 100) if original else 0.0

        c = self._console
        c.append("")
        c.append("============== RESUMEN DE LA EJECUCION ==============")
        c.append(f"Equipo activo:           {equipo}")
        c.append(f"Licitaciones procesadas: {original:,}")
        c.append(f"  - Incluidas:           {incluidas:,}")
        c.append(f"  - Excluidas:           {excluidas:,}")
        c.append(f"  - Recuperadas bypass:  {bypass:,}")
        c.append(f"  - Bloqueadas (dura):   {excl_dura:,}")
        c.append(f"Resultado final:         {final:,}   ({pct:.2f}% retencion)")
        if top_kw:
            c.append("")
            c.append("Top 10 keywords de exclusion (ajusta filtros si alguna no aplica a tu equipo):")
            for i, item in enumerate(top_kw[:10], start=1):
                # item puede ser [kw, count] (JSON serializado desde tupla)
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    kw, n = item
                    c.append(f"  {i:>2}. {str(kw):<28} {int(n):>5} exclusiones")
        toxicas = m.get("exclusiones_toxicas") or []
        if toxicas:
            c.append("")
            c.append("[!] EXCLUSIONES TOXICAS (keywords excluyen >10% del subconjunto post-inclusion):")
            for item in toxicas:
                # cada item es [kw, n, pct] (tupla serializada como lista en JSON)
                if isinstance(item, (list, tuple)) and len(item) >= 3:
                    kw, n, pct_tox = item[0], int(item[1]), float(item[2])
                    c.append(f"  - '{kw}' -> {n:,} exclusiones ({pct_tox:.1f}%)")
            c.append("  Recomendacion: edita tu hoja del PIVOT y quita/refina estas keywords.")
        c.append("=====================================================")
        c.append("")
        c.append("Tip: si ves que el filtrado dejo fuera algo importante, revisa Excluidas_*.xlsx")
        c.append("     (columna 'Motivo Exclusion') y edita tu hoja con el boton 'Editar mis filtros'.")

    def _on_close(self) -> None:
        if self._state.proceso_activo:
            if messagebox.askyesno("Confirmar", "Hay un proceso en ejecucion.\nDeseas salir igualmente?"):
                self._controller.stop()
                if self._stepper is not None:
                    self._stepper.reset()
                self.destroy()
        else:
            if self._stepper is not None:
                self._stepper.reset()
            self.destroy()

    def run(self) -> None:
        """Inicia el bucle principal de eventos de la aplicación."""
        try:
            self.mainloop()
        except KeyboardInterrupt:
            pass


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------


def main() -> None:
    """Punto de entrada. Inicializa y ejecuta el panel de control MP."""
    try:
        app = LanzadorLicitaciones()
        app.run()
    except Exception as exc:
        print(f"Error critico al iniciar la aplicacion: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

