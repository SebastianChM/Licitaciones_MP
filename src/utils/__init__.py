"""Paquete de utilidades: exporta todas las funciones comunes del proyecto."""

from .analizador_incremental import AnalizadorIncremental
from .config import Config
from .excel_formatter import guardar_formateado_reporte
from .file_ops import (
    crear_backup,
    encontrar_columna,
    encontrar_fila_encabezado,
    guardar_excel_con_formato,
    leer_excel_con_header_dinamico,
    limpiar_outputs_antiguos,
    listar_archivos_output,
    obtener_fecha_hoy,
    obtener_timestamp,
    validar_archivo_excel,
)
from .logger import ProjectLogger, get_logger
from .text_processing import (
    calcular_similitud,
    contiene_palabras_clave,
    encontrar_similares,
    extraer_palabras_clave,
    limpiar_codigo_licitacion,
    limpiar_texto_excel,
    normalizar_texto,
    truncar_texto,
)

__all__ = [
    # Incremental Analysis
    'AnalizadorIncremental',
    # Config
    'Config',
    # Logger
    'ProjectLogger',
    'calcular_similitud',
    'contiene_palabras_clave',
    'crear_backup',
    'encontrar_columna',
    'encontrar_fila_encabezado',
    'encontrar_similares',
    'extraer_palabras_clave',
    'get_logger',
    'guardar_excel_con_formato',
    # Excel Formatter
    'guardar_formateado_reporte',
    'leer_excel_con_header_dinamico',
    'limpiar_codigo_licitacion',
    'limpiar_outputs_antiguos',
    'limpiar_texto_excel',
    'listar_archivos_output',
    # Text Processing
    'normalizar_texto',
    'obtener_fecha_hoy',
    'obtener_timestamp',
    'truncar_texto',
    # File Operations
    'validar_archivo_excel',
]

