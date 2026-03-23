"""
Módulo de utilidades - Exporta todas las funciones comunes del proyecto.

Autor: Sebastian Chirino
Versión: 3.0.0
"""

from .config import Config
from .logger import ProjectLogger, get_logger
from .text_processing import (
    normalizar_texto,
    limpiar_texto_excel,
    calcular_similitud,
    encontrar_similares,
    extraer_palabras_clave,
    contiene_palabras_clave,
    truncar_texto,
    limpiar_codigo_licitacion
)
from .file_ops import (
    validar_archivo_excel,
    crear_backup,
    encontrar_fila_encabezado,
    encontrar_columna,
    leer_excel_con_header_dinamico,
    guardar_excel_con_formato,
    obtener_timestamp,
    obtener_fecha_hoy,
    listar_archivos_output,
    limpiar_outputs_antiguos
)
from .analizador_incremental import AnalizadorIncremental

__all__ = [
    # Config
    'Config',
    
    # Logger
    'ProjectLogger',
    'get_logger',
    
    # Text Processing
    'normalizar_texto',
    'limpiar_texto_excel',
    'calcular_similitud',
    'encontrar_similares',
    'extraer_palabras_clave',
    'contiene_palabras_clave',
    'truncar_texto',
    'limpiar_codigo_licitacion',
    
    # File Operations
    'validar_archivo_excel',
    'crear_backup',
    'encontrar_fila_encabezado',
    'encontrar_columna',
    'leer_excel_con_header_dinamico',
    'guardar_excel_con_formato',
    'obtener_timestamp',
    'obtener_fecha_hoy',
    'listar_archivos_output',
    'limpiar_outputs_antiguos',
    
    # Incremental Analysis
    'AnalizadorIncremental',
]

__version__ = '3.0.0'
