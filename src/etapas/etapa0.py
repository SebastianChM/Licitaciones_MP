"""
ETAPA 0 - DESCARGA AUTOMÁTICA DE LICITACIONES
Descarga el archivo más reciente desde Mercado Público

Autor: Sebastian Chirino
Versión: 3.0.0
"""

import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import shutil

from src.utils.config import Config
from src.utils.logger import ProjectLogger

__version__ = "3.0.0"

class Etapa0Descarga:
    """Descarga automática del archivo de licitaciones desde Mercado Público"""
    
    # URL directa de descarga del portal (PUEDE CAMBIAR - verificar en el portal)
    URL_DESCARGA = "https://www.mercadopublico.cl/Portal/att.ashx?id=5"
    
    # URL alternativa: API de Mercado Público
    API_URL = "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"
    
    def __init__(self, usar_api: bool = False):
        self.logger = ProjectLogger("etapa0", Config.LOG_DIR)
        self.config = Config
        self.usar_api = usar_api  # Si True, usa API en lugar de descarga directa
        self.stats = {
            'inicio': datetime.now(),
            'archivo_descargado': False,
            'tamano_mb': 0,
            'tiempo': None,
            'total_licitaciones': 0
        }
    
    def ejecutar(self) -> Dict[str, Any]:
        """Ejecuta la descarga del archivo de licitaciones"""
        self.logger.section("ETAPA 0 - DESCARGA AUTOMÁTICA", 80)
        self.logger.info(f"[>>] Iniciando descarga - v{__version__}")
        self.logger.info(f"[DATE] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            # Paso 1: Validar conexión
            self._validar_conexion()
            
            # Paso 2: Descargar archivo
            ruta_descarga = self._descargar_archivo()
            
            # Paso 3: Mover a INPUT
            ruta_final = self._mover_a_input(ruta_descarga)
            
            # Paso 4: Validar archivo
            self._validar_archivo(ruta_final)
            
            self.stats['archivo_descargado'] = True
            self.stats['tiempo'] = datetime.now() - self.stats['inicio']
            
            self.logger.section("RESUMEN", 80)
            self._imprimir_resumen()
            
            return {
                'exito': True,
                'stats': {
                    'archivo': ruta_final.name,
                    'tamano_mb': self.stats['tamano_mb'],
                    'tiempo_descarga': str(self.stats['tiempo'])
                },
                'ruta_archivo': str(ruta_final)
            }
            
        except Exception as e:
            self.logger.error(f"Error en descarga: {e}")
            return {
                'exito': False,
                'error': str(e),
                'stats': self.stats
            }
    
    def _validar_conexion(self):
        """Valida la conexión con el servidor de Mercado Público"""
        self.logger.subsection("Validando conexión")
        
        try:
            # Headers para simular navegador
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'es-CL,es;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            # Hacer HEAD request con headers de navegador
            response = requests.head(self.URL_DESCARGA, headers=headers, timeout=10, allow_redirects=True)
            
            # Aceptar 200 o 302 (redirect)
            if response.status_code in [200, 302]:
                self.logger.info("[OK] Servidor disponible")
                
                # Obtener tamaño del archivo si está disponible
                if 'Content-Length' in response.headers:
                    tamano_bytes = int(response.headers['Content-Length'])
                    tamano_mb = tamano_bytes / (1024 * 1024)
                    self.logger.info(f"[INFO] Tamaño archivo: {tamano_mb:.2f} MB")
            else:
                self.logger.warning(f"[!] Servidor respondió con código {response.status_code}, intentando descarga directa...")
                
        except requests.exceptions.Timeout:
            raise Exception("Timeout al conectar con Mercado Público")
        except requests.exceptions.ConnectionError:
            raise Exception("No se pudo conectar con Mercado Público. Verifica tu conexión a internet.")
    
    def _descargar_archivo(self) -> Path:
        """Descarga el archivo de licitaciones"""
        self.logger.subsection("Descargando archivo")
        
        # Crear directorio temporal si no existe
        temp_dir = self.config.BASE_DIR / "temp"
        temp_dir.mkdir(exist_ok=True)
        
        # Nombre temporal con timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ruta_temp = temp_dir / f"Licitacion_Descarga_{timestamp}.xlsx"
        
        try:
            self.logger.info(f"[>>] Descargando desde: {self.URL_DESCARGA}")
            
            # Headers para simular navegador
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,application/octet-stream,*/*',
                'Accept-Language': 'es-CL,es;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://www.mercadopublico.cl/Home',
                'Connection': 'keep-alive'
            }
            
            # Descargar con stream para mostrar progreso
            response = requests.get(self.URL_DESCARGA, headers=headers, stream=True, timeout=60, allow_redirects=True)
            response.raise_for_status()
            
            # Obtener tamaño total
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            chunk_size = 8192
            
            with open(ruta_temp, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Mostrar progreso cada 10%
                        if total_size > 0:
                            progreso = (downloaded / total_size) * 100
                            if progreso % 10 < 1:  # Aproximadamente cada 10%
                                self.logger.info(f"[...] Progreso: {progreso:.0f}%")
            
            # Calcular tamaño final
            self.stats['tamano_mb'] = ruta_temp.stat().st_size / (1024 * 1024)
            self.logger.info(f"[OK] Descargado: {self.stats['tamano_mb']:.2f} MB")
            
            return ruta_temp
            
        except requests.exceptions.RequestException as e:
            if ruta_temp.exists():
                ruta_temp.unlink()
            raise Exception(f"Error al descargar archivo: {e}")
    
    def _mover_a_input(self, ruta_origen: Path) -> Path:
        """Mueve el archivo descargado a la carpeta INPUT y gestiona histórico"""
        self.logger.subsection("Moviendo a INPUT")
        
        # Verificar si es un ZIP (el portal a veces comprime el Excel)
        import zipfile
        
        ruta_final_excel = None
        
        if zipfile.is_zipfile(ruta_origen):
            self.logger.info("[INFO] Archivo comprimido detectado, extrayendo...")
            
            with zipfile.ZipFile(ruta_origen, 'r') as zip_ref:
                # Buscar el archivo Excel dentro del ZIP
                archivos_excel = [f for f in zip_ref.namelist() if f.endswith(('.xlsx', '.xls'))]
                
                if not archivos_excel:
                    raise Exception("No se encontró archivo Excel en el ZIP descargado")
                
                # Usar el primer Excel encontrado
                archivo_excel = archivos_excel[0]
                self.logger.info(f"[INFO] Extrayendo: {archivo_excel}")
                
                # Extraer a directorio temporal
                temp_dir = ruta_origen.parent
                zip_ref.extract(archivo_excel, temp_dir)
                
                ruta_final_excel = temp_dir / archivo_excel
        else:
            ruta_final_excel = ruta_origen
        
        # Ruta de destino principal
        ruta_destino = self.config.LICITACIONES_MP
        
        # Crear carpeta de histórico
        historico_dir = self.config.INPUT_DIR / "HISTORICO"
        historico_dir.mkdir(exist_ok=True)
        
        # Guardar archivo actual en histórico antes de reemplazar
        if ruta_destino.exists():
            fecha_hoy = datetime.now().strftime("%Y%m%d")
            ruta_historico = historico_dir / f"Licitacion_{fecha_hoy}.xlsx"
            
            # Solo guardar si no existe ya uno de hoy
            if not ruta_historico.exists():
                self.logger.info(f"[HISTORICO] Guardando versión anterior: {ruta_historico.name}")
                shutil.copy2(ruta_destino, ruta_historico)
            else:
                self.logger.info(f"[HISTORICO] Ya existe versión de hoy, omitiendo backup")
        
        # Limpiar históricos antiguos (mayores a 30 días)
        self._limpiar_historico(historico_dir, dias_max=30)
        
        # Mover archivo nuevo como principal
        shutil.move(str(ruta_final_excel), str(ruta_destino))
        self.logger.info(f"[OK] Archivo principal actualizado: {ruta_destino.name}")
        
        # Limpiar archivo temporal ZIP si existía
        if ruta_origen != ruta_final_excel and ruta_origen.exists():
            ruta_origen.unlink()
        
        return ruta_destino
    
    def _limpiar_historico(self, historico_dir: Path, dias_max: int = 30):
        """Elimina archivos históricos mayores a N días"""
        from datetime import timedelta
        
        fecha_limite = datetime.now() - timedelta(days=dias_max)
        archivos_eliminados = 0
        
        for archivo in historico_dir.glob("Licitacion_*.xlsx"):
            # Obtener fecha de modificación del archivo
            fecha_archivo = datetime.fromtimestamp(archivo.stat().st_mtime)
            
            if fecha_archivo < fecha_limite:
                archivo.unlink()
                archivos_eliminados += 1
        
        if archivos_eliminados > 0:
            self.logger.info(f"[LIMPIEZA] Eliminados {archivos_eliminados} archivos históricos (>{dias_max} días)")
        
        # Contar archivos restantes
        total_historicos = len(list(historico_dir.glob("Licitacion_*.xlsx")))
        self.logger.info(f"[HISTORICO] Total archivos mantenidos: {total_historicos}")
    
    def _validar_archivo(self, ruta: Path):
        """Valida que el archivo descargado sea correcto"""
        self.logger.subsection("Validando archivo")
        
        try:
            import openpyxl
            
            # Intentar abrir el archivo
            wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
            
            # Obtener la primera hoja
            ws = wb.active
            
            # Contar filas aproximadas (sin cargar todo)
            filas = ws.max_row or 0
            columnas = ws.max_column or 0
            
            self.logger.info("[OK] Archivo válido")
            self.logger.info(f"[INFO] Filas: ~{filas:,}")
            self.logger.info(f"[INFO] Columnas: {columnas}")
            
            wb.close()
            
            # Validaciones mínimas
            if filas < 100:
                self.logger.warning(f"[!] Archivo sospechosamente pequeño ({filas} filas)")
            
            if columnas < 10:
                self.logger.warning(f"[!] Pocas columnas ({columnas})")
                
        except Exception as e:
            raise Exception(f"Archivo descargado no es válido: {e}")
    
    def _imprimir_resumen(self):
        """Imprime resumen de la descarga"""
        # Contar archivos en histórico
        historico_dir = self.config.INPUT_DIR / "HISTORICO"
        total_historicos = len(list(historico_dir.glob("Licitacion_*.xlsx"))) if historico_dir.exists() else 0
        
        resumen = f"""
╔══════════════════════════════════════════════════════════════╗
║         ESTADÍSTICAS DE DESCARGA                             ║
╚══════════════════════════════════════════════════════════════╝

📥 Descarga:
   - Archivo:        Licitacion_Publicada.xlsx
   - Tamaño:         {self.stats['tamano_mb']:.2f} MB
   - Estado:         {'✅ Exitosa' if self.stats['archivo_descargado'] else '❌ Fallida'}

📂 Histórico:
   - Archivos:       {total_historicos} versiones guardadas
   - Retención:      30 días automático

⏱️  Rendimiento:
   - Tiempo:         {self.stats['tiempo']}

🔗 Origen:
   - URL:            {self.URL_DESCARGA}
   - Portal:         Mercado Público de Chile
"""
        self.logger.info(resumen)


def main():
    """Función principal para ejecutar Etapa 0 de forma independiente"""
    etapa = Etapa0Descarga()
    resultado = etapa.ejecutar()
    
    if resultado['exito']:
        print("\n✅ ETAPA 0 COMPLETADA")
        print(f"   * Archivo descargado: {resultado['stats']['archivo']}")
        print(f"   * Tamaño: {resultado['stats']['tamano_mb']:.2f} MB")
    else:
        print("\n❌ ETAPA 0 FALLÓ")
        print(f"   * Error: {resultado.get('error', 'Desconocido')}")
        exit(1)


if __name__ == "__main__":
    main()
