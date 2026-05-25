#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generar_icono.py — Genera icono_mp.ico para el acceso directo de escritorio.

Ejecutar una sola vez:
    python generar_icono.py

Requiere Pillow (incluido en requirements.txt).
El icono generado se usa automáticamente al crear el acceso directo
con scripts/crear_acceso_directo.ps1.
"""
from pathlib import Path

from PIL import Image, ImageDraw

# ── Paleta MP ───────────────────────────────────────────────────────────────
_AZUL   = (21, 101, 192)    # #1565C0
_BLANCO = (255, 255, 255)

# Tamaños estándar de ICO para Windows (256 px cubre la vista grande de Explorer)
_SIZES = [256, 128, 64, 48, 32, 16]


def _dibujar_frame(size: int) -> Image.Image:
    """Dibuja un frame del icono para el tamaño indicado."""
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    # Fondo con esquinas redondeadas en azul MP
    radio = max(3, size // 7)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radio, fill=_AZUL)

    # Gráfico de barras ascendente (símbolo de análisis/reporting)
    pad    = max(2, size // 7)
    ancho  = size - 2 * pad
    alto   = size - 2 * pad
    n      = 4                            # número de barras
    gap    = max(1, ancho // (n * 4))     # separación entre barras
    bar_w  = max(2, (ancho - gap * (n - 1)) // n)
    base_y = size - pad

    # Alturas relativas de cada barra (izq → der, ascendente)
    proporciones = [0.30, 0.52, 0.72, 1.00]

    for i, prop in enumerate(proporciones):
        x0    = pad + i * (bar_w + gap)
        x1    = x0 + bar_w - 1
        bar_h = max(2, int(alto * prop * 0.88))
        y0    = base_y - bar_h
        draw.rectangle([x0, y0, x1, base_y], fill=_BLANCO)

    return img


def main() -> None:
    # Siempre escribe en la raíz del proyecto (un nivel arriba de scripts/)
    salida = Path(__file__).resolve().parent.parent / "icono_mp.ico"

    # Generamos solo el frame más grande; Pillow reescala automáticamente
    # a cada tamaño solicitado en 'sizes'.
    base = _dibujar_frame(256)
    base.save(
        salida,
        format="ICO",
        sizes=[(s, s) for s in _SIZES],
    )
    kb = salida.stat().st_size / 1024
    print(f"Icono generado: {salida}  ({kb:.1f} KB, {len(_SIZES)} tamaños)")


if __name__ == "__main__":
    main()
