"""Configuración centralizada del sistema: rutas, parámetros y secretos vía pydantic-settings."""

import logging
from pathlib import Path

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
    fx_provider_url: str = "https://api.frankfurter.app/latest"
    # URL directa de descarga del portal Mercado Público. Override con LICIT_MP_DOWNLOAD_URL.
    mp_download_url: str = "https://www.mercadopublico.cl/Portal/att.ashx?id=5"
    cmf_utm_url: str = "https://api.cmfchile.cl/api-sbifv3/recursos_api/utm"
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
    # (El filtrado es basado en palabras clave; configuración en PIVOT_MAESTRO hoja 06-FILTROS)

    # ==================== PARÁMETROS ETAPA 3 - API ====================
    ETAPA3_API_BASE_URL: str = "https://api.mercadopublico.cl/servicios/v1/publico"
    ETAPA3_DELAY_SEGUNDOS: float = 7.0  # API pública MP ≈ 8-10 req/min → 7s de margen seguro
    ETAPA3_MAX_REINTENTOS: int = 3
    ETAPA3_TIMEOUT: int = 40
    ETAPA3_CHECKPOINT_RETENTION_DAYS: int = 7
    
    # ==================== PARÁMETROS ETAPA 4 - REPORTE ====================
    ETAPA4_VALOR_UTM: int = 65000
    ETAPA4_VALOR_USD_CLP: int = 900
    ETAPA4_DIAS_GRACIA_HISTORICO: int = 30

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
    
    def cargar_desde_pivot(self, ruta_pivot: Path | None = None) -> dict[str, str]:
        """Carga parámetros dinámicos de la hoja 02-CONFIG del PIVOT_MAESTRO. Detecta columnas nombre/valor automáticamente."""
        import openpyxl
        ruta = ruta_pivot or self.PIVOT_MAESTRO

        _HEADERS_NOMBRE = {'nombre', 'campo', 'clave', 'key'}
        _HEADERS_VALOR  = {'parámetro', 'parametro', 'valor', 'value'}

        try:
            wb = openpyxl.load_workbook(ruta, data_only=True)
            if '02-CONFIG' not in wb.sheetnames:
                logging.warning("Hoja '02-CONFIG' no encontrada en PIVOT_MAESTRO")
                return {}
            ws = wb['02-CONFIG']

            col_nombre: int | None = None
            col_valor: int | None = None
            header_row: int | None = None

            for row in ws.iter_rows(max_row=10):
                for cell in row:
                    if cell.value is None:
                        continue
                    normalizado = str(cell.value).strip().lower()
                    if normalizado in _HEADERS_NOMBRE and col_nombre is None:
                        col_nombre = cell.column
                        header_row = cell.row
                    elif normalizado in _HEADERS_VALOR and col_valor is None:
                        col_valor = cell.column
                        header_row = cell.row
                if col_nombre and col_valor:
                    break

            if col_nombre is None or col_valor is None:
                logging.warning(
                    "No se encontraron columnas nombre/valor en 02-CONFIG. "
                    "Cabeceras esperadas: NOMBRE + PARÁMETRO (o equivalentes)."
                )
                return {}

            config_dict: dict[str, str] = {}
            for row in ws.iter_rows(min_row=(header_row or 0) + 1, max_row=100):
                nombre_cell = next((c for c in row if c.column == col_nombre), None)
                valor_cell  = next((c for c in row if c.column == col_valor), None)
                if nombre_cell and valor_cell:
                    nombre = nombre_cell.value
                    valor  = valor_cell.value
                    if nombre and valor is not None:
                        config_dict[str(nombre).strip()] = str(valor).strip()

            wb.close()
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
🔧 ETAPA 2 - Filtrado por palabras clave (configuración en PIVOT_MAESTRO)
🔧 ETAPA 4 - Valor UTM: ${self.ETAPA4_VALOR_UTM:,}

🧪 Modo TEST: {'✅ Activado' if self.TEST_MODE else '❌ Desactivado'}
"""
