#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mp_launcher/generar_icono.py

Genera mp_launcher/MP.ico usando únicamente Pillow (sin dependencias extras).
El ícono representa un gráfico de barras ascendente sobre fondo oscuro, alineado
con la paleta de DesignTokens de la aplicación.

Uso:
    python mp_launcher/generar_icono.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

# ---------------------------------------------------------------------------
# Paleta — alineada con DesignTokens del launcher
# ---------------------------------------------------------------------------
_BG      = (28, 28, 30)    # #1C1C1E  surface_bg
_BLUE    = (10, 132, 255)  # #0A84FF  brand_primary
_BLUE_LT = (74, 173, 255)  # #4AADFF  acento más claro (barra más alta)

_ICO_SIZES = [256, 128, 64, 48, 32, 24, 16]


def _draw_frame(size: int) -> Image.Image:
    """Dibuja un frame del ícono en el tamaño dado."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)

    # Fondo redondeado (esquinas ~15 % del tamaño)
    radius = max(2, size * 15 // 100)
    d.rounded_rectangle(
        [0, 0, size - 1, size - 1],
        radius=radius,
        fill=(*_BG, 255),
    )

    # Tres barras de tendencia ascendente izq→der
    pad_h   = max(2, size * 18 // 100)   # margen horizontal
    pad_bot = max(2, size * 14 // 100)   # margen inferior
    pad_top = max(2, size * 20 // 100)   # espacio libre arriba

    available_w = size - 2 * pad_h
    bar_w = max(2, available_w * 22 // 100)
    gap   = max(1, (available_w - 3 * bar_w) // 2)

    max_bar_h  = size - pad_top - pad_bot
    baseline_y = size - pad_bot
    bar_r      = max(1, bar_w // 4)

    heights   = [int(max_bar_h * f) for f in (0.42, 0.63, 0.86)]
    bar_color = [(*_BLUE, 255), (*_BLUE, 255), (*_BLUE_LT, 255)]

    for i, (h, color) in enumerate(zip(heights, bar_color)):
        x0 = pad_h + i * (bar_w + gap)
        y0 = baseline_y - h
        d.rounded_rectangle([x0, y0, x0 + bar_w, baseline_y], radius=bar_r, fill=color)

    return img


def generate(output_path: Path) -> None:
    """Genera el archivo .ico con todos los tamaños embebidos."""
    base = _draw_frame(256)
    base.save(
        str(output_path),
        format="ICO",
        sizes=[(s, s) for s in _ICO_SIZES],
    )
    print(f"Ícono generado: {output_path}")


if __name__ == "__main__":
    out = Path(__file__).parent / "MP.ico"
    generate(out)
