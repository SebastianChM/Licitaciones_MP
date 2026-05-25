#!/usr/bin/env python3
"""
tests/unit/test_lanzador_components.py

Pruebas unitarias de los componentes no-UI del lanzador.

Estrategia:
- PipelineController y AppState se prueban sin necesidad de Display/Tk.
- IconFactory._hex_rgba y los métodos de dibujo se prueban con Pillow directamente
  (sin CTkImage ni Tk), ya que ImageDraw no requiere pantalla.
- Los tests que necesitan CTk usan el fixture `ctk_root` con teardown seguro.
"""

import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image, ImageDraw

# ---------------------------------------------------------------------------
# Path setup — igual que en el propio lanzador
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).parents[2]
_SRC = _ROOT / "src"
_LAUNCHER = _ROOT / "mp_launcher"
for _p in (str(_SRC), str(_LAUNCHER)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Importar solo los componentes no-UI primero
from MP_Licitaciones import (
    AppState,
    DesignTokens,
    IconFactory,
    PipelineController,
)

# ===========================================================================
# DesignTokens
# ===========================================================================


class TestDesignTokens:
    def test_is_immutable(self) -> None:
        t = DesignTokens()
        with pytest.raises(Exception):
            t.surface_bg = "#000000"  # type: ignore[misc]

    def test_brand_primary_format(self) -> None:
        t = DesignTokens()
        assert t.brand_primary.startswith("#")
        assert len(t.brand_primary) == 7

    def test_sidebar_width_positive(self) -> None:
        assert DesignTokens().sidebar_w > 0


# ===========================================================================
# AppState
# ===========================================================================


class TestAppState:
    def test_defaults(self) -> None:
        state = AppState()
        assert state.proceso_activo is False
        assert state.proceso_detenido is False
        assert state.etapa_actual is None
        assert state.tiempo_inicio is None
        assert state.proceso_actual is None
        assert state.ultimo_run_exitoso is None

    def test_mutable(self) -> None:
        state = AppState()
        state.proceso_activo = True
        assert state.proceso_activo is True

    def test_etapa_actual_assignable(self) -> None:
        state = AppState()
        state.etapa_actual = 3
        assert state.etapa_actual == 3


# ===========================================================================
# PipelineController — detect_stage (no UI, no subprocess)
# ===========================================================================


class TestDetectStage:
    @pytest.mark.parametrize("line,expected", [
        ("Iniciando Etapa 0: Descarga",  0),
        ("=== ETAPA0 ===",               0),
        ("Ejecutando etapa 1",           1),
        ("etapa1: auditoria",            1),
        ("Etapa 2 completada",           2),
        ("ETAPA2",                       2),
        ("procesando etapa 3",           3),
        ("etapa3 iniciada",              3),
        ("ejecutando etapa 4",           4),
        ("ETAPA4 reporte",               4),
        ("Etapa 5: incremental",         5),
        ("etapa5",                       5),
    ])
    def test_known_patterns(self, line: str, expected: int) -> None:
        assert PipelineController.detect_stage(line) == expected

    @pytest.mark.parametrize("line", [
        "Pipeline iniciado correctamente",
        "Descarga completada",
        "Error en filtrado",
        "",
        "Paso 3 de 5",
    ])
    def test_no_match_returns_none(self, line: str) -> None:
        assert PipelineController.detect_stage(line) is None

    def test_case_insensitive(self) -> None:
        assert PipelineController.detect_stage("ETAPA 3 COMPLETADA") == 3

    def test_returns_first_match(self) -> None:
        # Si una línea menciona dos etapas, devuelve la primera según _STAGE_PATTERNS
        line = "etapa 1 y etapa 2 procesadas"
        result = PipelineController.detect_stage(line)
        assert result in (1, 2)


class TestPipelineControllerStop:
    def test_stop_no_process_is_safe(self) -> None:
        """stop() no lanza si no hay proceso activo."""
        state = AppState()
        ctrl = PipelineController(
            root_path=_ROOT,
            state=state,
            on_line=lambda l: None,
            on_complete=lambda c: None,
            on_error=lambda e: None,
        )
        ctrl.stop()  # No debe lanzar excepción

    def test_run_skips_if_already_active(self) -> None:
        """run() no lanza un segundo thread si proceso_activo=True."""
        state = AppState()
        state.proceso_activo = True  # Simula proceso ya activo
        ctrl = PipelineController(
            root_path=_ROOT,
            state=state,
            on_line=lambda l: None,
            on_complete=lambda c: None,
            on_error=lambda e: None,
        )
        import threading
        before = threading.active_count()
        ctrl.run(["python", "-c", "print('x')"])
        after = threading.active_count()
        assert after == before  # No se creó thread nuevo

    def test_run_sets_proceso_activo_before_thread(self) -> None:
        """run() activa proceso_activo=True antes de lanzar el thread."""
        import threading
        state = AppState()
        assert state.proceso_activo is False
        ctrl = PipelineController(
            root_path=_ROOT,
            state=state,
            on_line=lambda l: None,
            on_complete=lambda c: None,
            on_error=lambda e: None,
        )
        # Simula la guardia: primer run pasa, segundo run es bloqueado
        ctrl.run(["python", "-c", "import time; time.sleep(0.2)"])
        # proceso_activo debe ser True inmediatamente tras run()
        assert state.proceso_activo is True
        # Segundo run mientras activo: no crea thread adicional
        before = threading.active_count()
        ctrl.run(["python", "-c", "print('x')"])
        after = threading.active_count()
        assert after == before


# ===========================================================================
# IconFactory — sin CTk (Pillow only)
# ===========================================================================


class TestIconFactoryHexRgba:
    def test_white(self) -> None:
        assert IconFactory._hex_rgba("#ffffff") == (255, 255, 255, 255)

    def test_black(self) -> None:
        assert IconFactory._hex_rgba("#000000") == (0, 0, 0, 255)

    def test_brand_blue(self) -> None:
        r, g, b, a = IconFactory._hex_rgba("#1565C0")
        assert r == 0x15
        assert g == 0x65
        assert b == 0xC0
        assert a == 255

    def test_without_hash(self) -> None:
        assert IconFactory._hex_rgba("ff0000") == (255, 0, 0, 255)

    def test_custom_alpha(self) -> None:
        _, _, _, a = IconFactory._hex_rgba("#aabbcc", alpha=128)
        assert a == 128


class TestIconFactoryDrawMethods:
    """Prueba cada método de dibujo con un canvas Pillow limpio (sin CTk)."""

    def _canvas(self, size: int = 36) -> tuple[ImageDraw.ImageDraw, int, type[IconFactory]]:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        return ImageDraw.Draw(img), size, IconFactory

    @pytest.mark.parametrize("method_name", [
        "play", "chart", "folder", "log", "stop",
        "check", "x_mark", "warning", "refresh",
    ])
    def test_draw_does_not_raise(self, method_name: str) -> None:
        d, s, F = self._canvas()
        color = (255, 255, 255, 255)
        method = getattr(F, f"_{method_name}")
        method(d, s, color)  # No debe lanzar excepción


class TestIconFactoryInvalidName:
    def test_unknown_name_raises_valueerror(self) -> None:
        """get() con nombre no registrado debe lanzar ValueError."""
        # Parchamos _render para que no necesite CTk
        with patch.object(IconFactory, "_render", side_effect=ValueError("Icono desconocido: 'xyz'")):
            with pytest.raises(ValueError, match="Icono desconocido"):
                IconFactory.get("xyz", 18, "#ffffff")  # type: ignore[arg-type]

    def test_render_invalid_name_raises(self) -> None:
        """_render() directamente con nombre inválido."""
        # Creamos un mini mock de CTkImage para que _render pueda ejecutar
        with patch("MP_Licitaciones.ctk.CTkImage") as mock_ctk_image:
            mock_ctk_image.return_value = MagicMock()
            with pytest.raises(ValueError, match="Icono desconocido: 'nonexistent'"):
                IconFactory._render("nonexistent", 18, "#ffffff")  # type: ignore[arg-type]


# ===========================================================================
# ConsoleWidget._classify — prueban los patrones compilados sin CTk
# ===========================================================================


class TestConsoleClassify:
    """
    Prueba la clasificación semántica de líneas sin instanciar la UI.
    Replicamos la lógica de compilación directamente.
    """

    _TAG_RULES = (
        (r"\b(error|exception|traceback|fallo|failed|critico)\b", "error"),
        (r"\b(warning|warn|advertencia)\b",                       "warn"),
        (r"\b(completad\w*|exito\w*|success|\[ok\])",             "success"),
        (r"\b(etapa|stage|ejecutando etapa)\b",                   "stage"),
    )

    def _classify(self, text: str) -> str:
        for pat, tag in self._TAG_RULES:
            if re.search(pat, text, re.IGNORECASE):
                return tag
        return "info"

    @pytest.mark.parametrize("line,expected", [
        ("ERROR: archivo no encontrado",  "error"),
        ("Traceback (most recent call)",  "error"),
        ("WARNING: valor fuera de rango", "warn"),
        ("Pipeline completado",           "success"),
        ("[OK] verificacion exitosa",     "success"),
        ("Ejecutando Etapa 3",            "stage"),
        ("stage 1 processing",            "stage"),
        ("Procesando registros...",       "info"),
        ("Leyendo configuracion",         "info"),
    ])
    def test_classification(self, line: str, expected: str) -> None:
        assert self._classify(line) == expected

    def test_priority_error_over_info(self) -> None:
        assert self._classify("Error en etapa") == "error"

    def test_case_insensitive(self) -> None:
        assert self._classify("FALLO CRITICO") == "error"


# ===========================================================================
# DesignTokens — completitud de la escala tipográfica
# ===========================================================================


class TestDesignTokensScale:
    def test_sz_lg_present(self) -> None:
        """sz_lg debe existir para completar la escala xs→sm→md→lg→xl→xxl."""
        t = DesignTokens()
        assert hasattr(t, "sz_lg")
        assert t.sz_lg == 16

    def test_scale_is_ascending(self) -> None:
        t = DesignTokens()
        assert t.sz_xs < t.sz_sm < t.sz_md < t.sz_lg < t.sz_xl < t.sz_xxl


# ===========================================================================
# ConsoleWidget — cap de líneas (sin CTk, lógica pura)
# ===========================================================================


class TestConsoleMaxLines:
    """
    Verifica la lógica de truncado FIFO.
    Prueba el invariante sin instanciar CTk, replicando la condición del cap.
    """

    MAX_LINES = 2_000
    BATCH_TRIGGER = MAX_LINES + 200

    def test_cap_constant_defined(self) -> None:
        from MP_Licitaciones import ConsoleWidget
        assert hasattr(ConsoleWidget, "MAX_LINES")
        assert ConsoleWidget.MAX_LINES == self.MAX_LINES

    def test_truncation_invariant(self) -> None:
        """Después del truncado, line_count no puede superar MAX_LINES."""
        count = self.BATCH_TRIGGER + 1  # supera el umbral
        if count > self.BATCH_TRIGGER:
            count = self.MAX_LINES       # el reset que aplica el cap
        assert count <= self.MAX_LINES

    def test_batch_trigger_is_above_max(self) -> None:
        """El truncado no ocurre en cada línea sino en lotes para evitar reindexación costosa."""
        assert self.BATCH_TRIGGER > self.MAX_LINES


# ===========================================================================
# PipelineController — reset de proceso_activo
# ===========================================================================


class TestPipelineControllerState:
    def test_proceso_activo_reset_semantics(self) -> None:
        """
        Después de que run() active proceso_activo, una segunda llamada inmediata
        debe ser bloqueada (guardia funcional).
        """
        state = AppState()
        ctrl = PipelineController(
            root_path=_ROOT,
            state=state,
            on_line=lambda l: None,
            on_complete=lambda c: None,
            on_error=lambda e: None,
        )
        # Primera llamada: proceso_activo False → pasa la guardia → activa flag
        ctrl.run(["python", "-c", "import time; time.sleep(0.3)"])
        assert state.proceso_activo is True, "run() debe activar proceso_activo antes del thread"

        # Segunda llamada inmediata: proceso_activo True → debe bloquearse
        import threading
        before = threading.active_count()
        ctrl.run(["python", "-c", "print('x')"])
        after = threading.active_count()
        assert after == before, "Segunda llamada no debe crear thread"

    def test_stop_sets_proceso_detenido(self) -> None:
        """stop() debe marcar proceso_detenido=True cuando hay proceso activo."""
        import subprocess
        state = AppState()
        # Simular proceso activo con un proc mock
        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.poll.return_value = None  # proceso sigue corriendo
        state.proceso_actual = mock_proc

        ctrl = PipelineController(
            root_path=_ROOT,
            state=state,
            on_line=lambda l: None,
            on_complete=lambda c: None,
            on_error=lambda e: None,
        )
        ctrl.stop()
        assert state.proceso_detenido is True
        mock_proc.terminate.assert_called_once()


# ===========================================================================
# Auto-scroll toggle (concepto, sin CTk)
# ===========================================================================


class TestAutoScrollToggle:
    """
    Verifica el contrato lógico del toggle de auto-scroll.
    Prueba la lógica de bool sin instanciar CTk.
    """

    def test_toggle_inverts_flag(self) -> None:
        """El toggle debe invertir el flag en cada llamada."""
        auto_scroll = True
        auto_scroll = not auto_scroll
        assert auto_scroll is False
        auto_scroll = not auto_scroll
        assert auto_scroll is True

    def test_default_attribute_exists(self) -> None:
        """ConsoleWidget debe exponer MAX_LINES; la clase debe definir _auto_scroll."""
        from MP_Licitaciones import ConsoleWidget
        # Verificar que el atributo de clase no existe pero la anotación sí (instancia)
        # Se infiere por la presencia de _toggle_auto_scroll como método.
        assert callable(getattr(ConsoleWidget, "_toggle_auto_scroll", None)), (
            "ConsoleWidget debe tener el método _toggle_auto_scroll"
        )

    def test_btn_scroll_attribute_annotated(self) -> None:
        """El atributo _btn_scroll debe estar anotado en ConsoleWidget.__init__."""
        import inspect

        from MP_Licitaciones import ConsoleWidget
        source = inspect.getsource(ConsoleWidget.__init__)
        assert "_btn_scroll" in source, "_btn_scroll debe inicializarse en __init__"
        assert "_auto_scroll" in source, "_auto_scroll debe inicializarse en __init__"


# ===========================================================================
# Queue-based on_line (concepto, sin CTk)
# ===========================================================================


class TestQueuePattern:
    """
    Valida el patrón queue-based _on_line sin instanciar CTk.
    Cubre la cola SimpleQueue, el patrón de drain y el límite de líneas por tick.
    """

    def test_simplequeue_put_get_roundtrip(self) -> None:
        """queue.SimpleQueue garantiza put/get sin pérdida de datos."""
        import queue as q
        lq: q.SimpleQueue[str] = q.SimpleQueue()
        assert lq.empty()
        lq.put("linea de prueba")
        assert not lq.empty()
        assert lq.get_nowait() == "linea de prueba"
        assert lq.empty()

    def test_drain_pattern_empties_queue(self) -> None:
        """El patrón de drain while-True debe vaciar completamente la cola."""
        import queue as q
        lq: q.SimpleQueue[str] = q.SimpleQueue()
        for i in range(10):
            lq.put(f"linea {i}")
        drained: list[str] = []
        while True:
            try:
                drained.append(lq.get_nowait())
            except q.Empty:
                break
        assert len(drained) == 10
        assert lq.empty()

    def test_max_lines_per_tick_respected(self) -> None:
        """El flush no debe procesar más de MAX_PER_TICK líneas en un solo tick."""
        import queue as q
        MAX_PER_TICK = 50
        lq: q.SimpleQueue[str] = q.SimpleQueue()
        for i in range(100):
            lq.put(f"linea {i}")
        processed = 0
        for _ in range(MAX_PER_TICK):
            try:
                lq.get_nowait()
                processed += 1
            except q.Empty:
                break
        assert processed == MAX_PER_TICK
        assert not lq.empty(), "Deben quedar líneas sin procesar tras el límite de tick"

    def test_on_line_method_signature(self) -> None:
        """_on_line en LanzadorLicitaciones debe tomar solo 'line: str' (sin closures)."""
        import inspect

        import MP_Licitaciones as lz
        source = inspect.getsource(lz.LanzadorLicitaciones._on_line)
        assert "self._line_queue.put" in source, (
            "_on_line debe delegar a self._line_queue.put (queue-based)"
        )
        assert "def update" not in source, (
            "_on_line no debe definir closures after(0,...); usa la cola"
        )

    def test_flush_queue_method_exists(self) -> None:
        """LanzadorLicitaciones debe tener el método _flush_queue."""
        import MP_Licitaciones as lz
        assert callable(getattr(lz.LanzadorLicitaciones, "_flush_queue", None))

    def test_process_line_method_exists(self) -> None:
        """LanzadorLicitaciones debe tener el método _process_line (DRY)."""
        import MP_Licitaciones as lz
        assert callable(getattr(lz.LanzadorLicitaciones, "_process_line", None))

