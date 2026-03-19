"""
Configuración centralizada del proyecto Licitaciones Mercado Público
Todas las rutas, parámetros y constantes del sistema.

Autor: Sebastian Chirino
Versión: 3.0.0
"""

import os
from pathlib import Path
from typing import Optional
import logging

class Config:
    """Configuración global del sistema de licitaciones"""
    
    # ==================== RUTAS BASE ====================
    BASE_DIR = Path(__file__).parent.parent.parent
    
    # Directorios principales
    PIVOT_DIR = BASE_DIR / "config_pivot"
    DATA_DIR = BASE_DIR / "data"
    
    # Subdirectorios de DATA
    INPUT_DIR = DATA_DIR / "1. INPUT"
    OUTPUT_DIR = DATA_DIR / "2. OUTPUT"
    
    # Subdirectorios de OUTPUT
    LOG_DIR = OUTPUT_DIR / "1. LOGS"
    HALLAZGOS_DIR = OUTPUT_DIR / "2. HALLAZGOS"
    HISTORICO_DIR = OUTPUT_DIR / "2. HISTORICO"
    FILTRADO_DIR = OUTPUT_DIR / "3. FILTRADO"
    ENRIQUECIDO_DIR = OUTPUT_DIR / "4. ENRIQUECIDO"
    PRESENTACION_DIR = OUTPUT_DIR / "5. PRESENTACION"
    
    # Subdirectorios de PRESENTACION para separar reportes
    PRESENTACION_ORIGINAL_DIR = PRESENTACION_DIR / "ORIGINALES"
    PRESENTACION_INCREMENTAL_DIR = PRESENTACION_DIR / "INCREMENTALES"
    
    # ==================== ARCHIVOS MAESTROS ====================
    PIVOT_MAESTRO = PIVOT_DIR / "PIVOT_MAESTRO.xlsx"
    LICITACIONES_MP = INPUT_DIR / "Licitacion_Publicada.xlsx"
    
    # ==================== PARÁMETROS ETAPA 1 - AUDITORÍA ====================
    ETAPA1_UMBRAL_ALERTA = 3  # Número de ocurrencias para alertar
    ETAPA1_DETECTAR_SIMILARES = True  # Activar detección de valores similares
    ETAPA1_SIMILITUD_THRESHOLD = 0.85  # Umbral de similitud (0-1)
    ETAPA1_MAX_FILAS_BUSQUEDA = 50  # Filas máximas para buscar header
    
    # ==================== PARÁMETROS ETAPA 2 - FILTRADO ====================
    ETAPA2_SCORE_BASE = 50.0
    ETAPA2_SCORE_INCLUSION = 30.0
    ETAPA2_SCORE_EXCLUSION = -40.0
    ETAPA2_MIN_SCORE = 30.0
    
    # Umbrales de anomalías
    ETAPA2_MIN_AMOUNT = 1_000_000       # 1M CLP
    ETAPA2_MAX_AMOUNT = 50_000_000_000  # 50B CLP
    ETAPA2_MIN_DAYS = 7
    ETAPA2_MAX_DAYS = 365
    
    # ==================== PARÁMETROS ETAPA 3 - API ====================
    ETAPA3_API_BASE_URL = "https://api.mercadopublico.cl/servicios/v1/publico"
    ETAPA3_RATE_LIMIT = 2  # Llamadas por segundo
    ETAPA3_DELAY_SEGUNDOS = 1.5  # Delay entre llamadas (la API rechaza peticiones muy rápidas)
    ETAPA3_MAX_REINTENTOS = 3
    ETAPA3_TIMEOUT = 40  # Segundos (la API puede tardar, usar timeout largo)
    
    # ==================== PARÁMETROS ETAPA 4 - REPORTE ====================
    ETAPA4_VALOR_UTM = 65000  # Valor UTM por defecto (actualizar mensualmente)
    ETAPA4_VALOR_USD_CLP = 900  # Tipo de cambio por defecto
    ETAPA4_DIAS_GRACIA_HISTORICO = 30  # Días de gracia para considerar histórico
    
    # Columnas del reporte final
    ETAPA4_COLUMNAS_FINALES = [
        'Código Licitación',
        'Nombre',
        'Organismo',
        'Monto CLP',
        'Días para Cierre',
        'Fecha Cierre',
        'Estado',
        'Región',
        'Tipo',
        'Categoría',
        'Descripción'
    ]
    
    # ==================== CONFIGURACIÓN DE LOGGING ====================
    LOG_LEVEL = logging.INFO
    LOG_FORMAT = '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
    LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
    LOG_ENCODING = 'utf-8'
    
    # ==================== CONFIGURACIÓN DE EXCEL ====================
    EXCEL_ENGINE = 'openpyxl'
    EXCEL_ENCODING = 'utf-8'
    
    # ==================== MODO TEST ====================
    TEST_MODE = False  # Activar para usar datos de prueba
    TEST_LIMIT = 100   # Límite de registros en modo test
    
    @classmethod
    def validar_estructura(cls) -> bool:
        """Valida que existan los directorios y archivos críticos"""
        directorios_criticos = [
            cls.INPUT_DIR,
            cls.OUTPUT_DIR,
            cls.LOG_DIR,
            cls.PIVOT_DIR,
            cls.PRESENTACION_ORIGINAL_DIR,
            cls.PRESENTACION_INCREMENTAL_DIR
        ]
        
        archivos_criticos = [
            cls.PIVOT_MAESTRO
        ]
        
        # Crear directorios si no existen
        for directorio in directorios_criticos:
            directorio.mkdir(parents=True, exist_ok=True)
        
        # Validar archivos críticos
        archivos_faltantes = []
        for archivo in archivos_criticos:
            if not archivo.exists():
                archivos_faltantes.append(str(archivo))
        
        if archivos_faltantes:
            logging.warning(f"⚠️ Archivos faltantes: {archivos_faltantes}")
            return False
        
        return True
    
    @classmethod
    def cargar_desde_pivot(cls, ruta_pivot: Optional[Path] = None) -> dict:
        """
        Carga parámetros dinámicos desde la hoja 02-CONFIG del PIVOT_MAESTRO
        
        Estructura esperada:
        - Columna A: SCRIPT (ej: 'Etapa 3')
        - Columna B: NOMBRE (ej: 'API Key')
        - Columna C: DESCRIPCIÓN
        - Columna D: (vacío o instrucciones)
        - Columna E: VALOR (el dato real)
        
        Returns:
            dict: Diccionario con parámetros cargados {nombre: valor}
        """
        import openpyxl
        
        if ruta_pivot is None:
            ruta_pivot = cls.PIVOT_MAESTRO
        
        try:
            wb = openpyxl.load_workbook(ruta_pivot, data_only=True)
            ws = wb['02-CONFIG']
            
            config_dict = {}
            
            # Leer desde fila 5 (después del header en fila 4)
            for row in ws.iter_rows(min_row=5, max_row=50, values_only=True):
                if not row or len(row) < 5:
                    continue
                
                # Columna B (índice 1): Nombre del parámetro
                # Columna E (índice 4): Valor
                nombre = row[1]  # Columna B
                valor = row[4]   # Columna E
                
                if nombre and valor:
                    nombre_str = str(nombre).strip()
                    valor_str = str(valor).strip()
                    
                    if nombre_str and valor_str:
                        config_dict[nombre_str] = valor_str
            
            return config_dict
            
        except Exception as e:
            logging.error(f"Error cargando configuración desde PIVOT: {e}")
            return {}
    
    @classmethod
    def info(cls) -> str:
        """Retorna información de configuración para debugging"""
        return f"""
╔══════════════════════════════════════════════════════════════╗
║          CONFIGURACIÓN - LICITACIONES MERCADO PÚBLICO        ║
╚══════════════════════════════════════════════════════════════╝

📁 BASE_DIR: {cls.BASE_DIR}
📋 PIVOT_MAESTRO: {cls.PIVOT_MAESTRO}
📥 INPUT: {cls.INPUT_DIR}
📤 OUTPUT: {cls.OUTPUT_DIR}

🔧 ETAPA 1 - Umbral Alerta: {cls.ETAPA1_UMBRAL_ALERTA}
🔧 ETAPA 2 - Score Mínimo: {cls.ETAPA2_MIN_SCORE}
🔧 ETAPA 3 - Rate Limit: {cls.ETAPA3_RATE_LIMIT} req/s
🔧 ETAPA 4 - Valor UTM: ${cls.ETAPA4_VALOR_UTM:,}

🧪 Modo TEST: {'✅ Activado' if cls.TEST_MODE else '❌ Desactivado'}
"""

# Validar estructura al importar
Config.validar_estructura()
