#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador de icono simple para MP Licitaciones
"""
import os
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

def crear_icono_mp():
    """Crear un icono simple para MP"""
    try:
        # Configuración
        tamaño = 256
        color_fondo = "#0066CC"  # Azul MP
        color_texto = "white"
        
        # Crear imagen
        img = Image.new('RGBA', (tamaño, tamaño), color_fondo)
        draw = ImageDraw.Draw(img)
        
        # Dibujar círculo de fondo
        margen = 20
        draw.ellipse([margen, margen, tamaño-margen, tamaño-margen], 
                    fill=color_fondo, outline="white", width=8)
        
        # Intentar cargar una fuente, si no usar la default
        try:
            font_grande = ImageFont.truetype("arial.ttf", 60)
            font_pequeña = ImageFont.truetype("arial.ttf", 28)
        except:
            font_grande = ImageFont.load_default()
            font_pequeña = ImageFont.load_default()
        
        # Dibujar texto "MP"
        texto_principal = "MP"
        bbox = draw.textbbox((0, 0), texto_principal, font=font_grande)
        texto_ancho = bbox[2] - bbox[0]
        texto_alto = bbox[3] - bbox[1]
        
        x = (tamaño - texto_ancho) // 2
        y = (tamaño - texto_alto) // 2 - 20
        
        draw.text((x, y), texto_principal, fill=color_texto, font=font_grande)
        
        # Dibujar subtexto "LIC"
        subtexto = "LIC"
        bbox2 = draw.textbbox((0, 0), subtexto, font=font_pequeña)
        subtexto_ancho = bbox2[2] - bbox2[0]
        
        x2 = (tamaño - subtexto_ancho) // 2
        y2 = y + texto_alto + 10
        
        draw.text((x2, y2), subtexto, fill=color_texto, font=font_pequeña)
        
        # Guardar como ICO
        ruta_icono = Path(__file__).parent / "icono_mp.ico"
        
        # Crear múltiples tamaños para el ICO
        tamaños = [16, 32, 48, 64, 128, 256]
        iconos = []
        
        for tam in tamaños:
            img_redimensionada = img.resize((tam, tam), Image.Resampling.LANCZOS)
            iconos.append(img_redimensionada)
        
        # Guardar como ICO con múltiples resoluciones
        iconos[0].save(ruta_icono, format='ICO', sizes=[(t, t) for t in tamaños])
        
        print(f"✅ Icono creado: {ruta_icono}")
        return True
        
    except ImportError:
        print("⚠️ PIL/Pillow no está instalado. Creando icono básico...")
        return crear_icono_basico()
    except Exception as e:
        print(f"❌ Error creando icono: {e}")
        return crear_icono_basico()

def crear_icono_basico():
    """Crear un icono básico usando recursos del sistema"""
    try:
        # Como alternativa, crear un archivo de texto que Windows pueda usar
        ruta_icon = Path(__file__).parent / "icono_mp.txt"
        with open(ruta_icon, 'w', encoding='utf-8') as f:
            f.write("🏛️ MP Licitaciones")
        
        print(f"✅ Archivo de referencia creado: {ruta_icon}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("🎨 Generando icono para MP Licitaciones...")
    crear_icono_mp()