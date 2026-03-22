"""
Configuración centralizada del proyecto Licitaciones Mercado Público
Todas las rutas, parámetros y constantes del sistema gestionadas mediante Pydantic Settings.

Autor: Sebastian Chirino
Versión: 3.1.0 (Refactorizado)
"""

from pathlib import Path
from typing import Optional, Dict
import logging
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_PATH = Path(__file__).parent.parent.parent
DATA_PATH = BASE_PATH / "data"
OUTPUT_PATH = DATA_PATH / "2. OUTPUT"

class Config(BaseSettings):
    """Configuración global del sistema de licitaciones usando 12-factor"""
    model_config = SettingsConfigDict(
        env_prefix="LICIT_", 
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

    # ==================== SECRETOS Y VARIABLES DE ENTORNO ====================
    cmf_api_key: str = ""
    mercado_publico_ticket: str = ""
    fx_provider_url: str = "https://api.exchangerate.host/latest"
    env: str = "production"

    # ==================== RUTAS BASE ====================
    BASE_DIR: Path = BASE_PATH
    PIVOT_DIR: Path = BASE_PATH / "config_pivot"
    DATA_DIR: Path = DATA_PATH
    INPUT_DIR: Path = DATA_PATH / "1. INPUT"
    OUTPUT_DIR: Path = OUTPUT_PATH
    LOG_DIR: Path = OUTPUT_PATH / "1. LOGS"
    HALLAZGOS_DIR: Path = OUTPUT_PATH / "2. HALLAZGOS"
    HISTORICO_DIR: Path = OUTPUT_PATH / "2. HISTORICO"
    FILTRADO_DIR: Path = OUTPUT_PATH / "3. FILTRADO"
    ENRIQUECIDO_DIR: Path = OUTPUT_PATH / "4. ENRIQUECIDO"
    PRESENTACION_DIR: Path = OUTPUT_PATH / "5. PRESENTACION"
    PRESENTACION_ORIGINAL_DIR: Path = OUTPUT_PATH / "5. PRESENTACION" / "ORIGINALES"
    PRESENTACION_INCREMENTAL_DIR: Path = OUTPUT_PATH / "5. PRESENTACION" / "INCREMENTALES"
    
    # Archivos Maestros
    @property
    def PIVOT_MAESTRO(self) -> Path:
        return self.PIVOT_DIR / "PIVOT_MAESTRO.xlsx"
        
    @property
    def LICITACIONES_MP(self) -> Path:
        return self.INPUT_DIR / "Licitacion_Publicada.xlsx"

    # ==================== PARÁMETROS ETAPA 1 - AUDITORÍA ====================
    ETAPA1_UMBRAL_ALERTA: int = 3
    ETAPA1_DETECTAR_SIMILARES: bool = True
    ETAPA1_SIMILITUD_THRESHOLD: float = 0.85
    ETAPA1_MAX_FILAS_BUSQUEDA: int = 50
    
    # ==================== PARÁMETROS ETAPA 2 - FILTRADO ====================
    ETAPA2_SCORE_BASE: float = 50.0
    ETAPA2_SCORE_INCLUSION: float = 30.0
    ETAPA2_SCORE_EXCLUSION: float = -40.0
    ETAPA2_MIN_SCORE: float = 30.0
    
    ETAPA2_MIN_AMOUNT: int = 1_000_000
    ETAPA2_MAX_AMOUNT: int = 50_000_000_000
    ETAPA2_MIN_DAYS: int = 7
    ETAPA2_MAX_DAYS: int = 365
    
    # ==================== PARÁMETROS ETAPA 3 - API ====================
    ETAPA3_API_BASE_URL: str = "https://api.mercadopublico.cl/servicios/v1/publico"
    ETAPA3_RATE_LIMIT: int = 2
    ETAPA3_DELAY_SEGUNDOS: float = 1.5
    ETAPA3_MAX_REINTENTOS: int = 3
    ETAPA3_TIMEOUT: int = 40
    
    # ==================== PARÁMETROS ETAPA 4 - REPORTE ====================
    ETAPA4_VALOR_UTM: int = 65000
    ETAPA4_VALOR_USD_CLP: int = 900
    ETAPA4_DIAS_GRACIA_HISTORICO: int = 30
    
    ETAPA4_COLUMNAS_FINALES: list[str] = [
        'Código Licitación', 'Nombre', 'Organismo', 'Monto CLP',
        'Días para Cierre', 'Fecha Cierre', 'Estado', 'Región',
        'Tipo', 'Categoría', 'Descripción'
    ]
    
    # ==================== CONFIGURACIÓN GENERAL ====================
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
    LOG_DATE_FORMAT: str = '%Y-%m-%d %H:%M:%S'
    LOG_ENCODING: str = 'utf-8'
    EXCEL_ENGINE: str = 'openpyxl'
    EXCEL_ENCODING: str = 'utf-8'
    
    TEST_MODE: bool = False
    TEST_LIMIT: int = 100
    
    def validar_estructura(self) -> bool:
        """Valida que existan los directorios críticos"""
        directorios_criticos = [
            self.INPUT_DIR, self.OUTPUT_DIR, self.LOG_DIR, self.PIVOT_DIR,
            self.PRESENTACION_ORIGINAL_DIR, self.PRESENTACION_INCREMENTAL_DIR
        ]
        
        for directorio in directorios_criticos:
            directorio.mkdir(parents=True, exist_ok=True)
            
        if not self.PIVOT_MAESTRO.exists():
            logging.warning(f"⚠️ Archivo maestro faltante: {self.PIVOT_MAESTRO}")
            return False
        return True
    
    def cargar_desde_pivot(self, ruta_pivot: Optional[Path] = None) -> Dict[str, str]:
        """Carga parámetros dinámicos (filtros de analistas) desde PIVOT_MAESTRO."""
        import openpyxl
        ruta = ruta_pivot or self.PIVOT_MAESTRO
        
        try:
            wb = openpyxl.load_workbook(ruta, data_only=True)
            if '02-CONFIG' not in wb.sheetnames:
                return {}
            ws = wb['02-CONFIG']
            
            config_dict = {}
            for row in ws.iter_rows(min_row=5, max_row=50, values_only=True):
                if not row or len(row) < 5:
                    continue
                nombre, valor = row[1], row[4]
                if nombre and valor:
                    config_dict[str(nombre).strip()] = str(valor).strip()
            return config_dict
        except Exception as e:
            logging.error(f"Error cargando configuración desde PIVOT: {e}")
            return {}
    
    def info(self) -> str:
        return f"""
╔══════════════════════════════════════════════════════════════╗
║          CONFIGURACIÓN - LICITACIONES MERCADO PÚBLICO        ║
╚══════════════════════════════════════════════════════════════╝

📁 BASE_DIR: {self.BASE_DIR}
📋 PIVOT_MAESTRO: {self.PIVOT_MAESTRO}
📥 INPUT: {self.INPUT_DIR}
📤 OUTPUT: {self.OUTPUT_DIR}
🔐 CMF API KEY: {'✅ Configurada' if self.cmf_api_key else '❌ Faltante'}

🔧 ETAPA 1 - Umbral Alerta: {self.ETAPA1_UMBRAL_ALERTA}
🔧 ETAPA 2 - Score Mínimo: {self.ETAPA2_MIN_SCORE}
🔧 ETAPA 4 - Valor UTM: ${self.ETAPA4_VALOR_UTM:,}

🧪 Modo TEST: {'✅ Activado' if self.TEST_MODE else '❌ Desactivado'}
"""
