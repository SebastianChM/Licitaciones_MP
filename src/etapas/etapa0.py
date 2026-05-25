"""Etapa 0 — descarga automática del archivo de licitaciones desde Mercado Público."""

import shutil
import zipfile
from datetime import datetime, timedelta
from importlib.metadata import version as _pkg_version
from pathlib import Path

import openpyxl

from core.context import PipelineContext
from core.contracts import BaseStage, StageResult
from utils.config import Config
from utils.http import HTTPClient

__version__ = _pkg_version("licitaciones-mp")

class Etapa0Descarga(BaseStage):
    """Descarga automática del archivo de licitaciones desde Mercado Público.

    La URL de descarga se obtiene de `Config.mp_download_url` (override con
    LICIT_MP_DOWNLOAD_URL) y se expone vía la propiedad `URL_DESCARGA` para
    mantener compatibilidad con código y logs existentes.
    """

    @property
    def URL_DESCARGA(self) -> str:
        return self.config.mp_download_url
    
    def __init__(self) -> None:
        super().__init__()
        self.stats = {
            'inicio': datetime.now(),
            'archivo_descargado': False,
            'tamano_mb': 0,
            'tiempo': None,
            'total_licitaciones': 0
        }

    @property
    def name(self) -> str:
        return "descarga"

    def validate_inputs(self, context: PipelineContext) -> bool:
        return True # Etapa 0 no tiene inputs mandatorios del pipeline
    
    def _execute(self, context: PipelineContext) -> StageResult:
        """Ejecuta la descarga del archivo de licitaciones"""
        self.http = HTTPClient(self.logger, timeout=60)
        
        self.logger.section("ETAPA 0 - DESCARGA AUTOMÁTICA", 80)
        self.logger.info(f"[>>] Iniciando descarga - v{__version__} | RunID: {context.run_id}")
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
            
            # Paso 5: Registrar artefacto
            context.add_artifact('etapa0_output', ruta_final)
            context.set_metric('etapa0_tamano_mb', self.stats['tamano_mb'])
            
            return StageResult(
                success=True,
                stage_name=self.name,
                files_produced=[ruta_final],
                metrics_produced={'tamano_mb': self.stats['tamano_mb'], 'tiempo_descarga': str(self.stats['tiempo'])},
                custom_data={
                    'stats': {
                        'archivo': ruta_final.name,
                        'tamano_mb': self.stats['tamano_mb'],
                        'tiempo_descarga': str(self.stats['tiempo'])
                    },
                    'ruta_archivo': str(ruta_final)
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error en descarga: {e}")
            return StageResult(
                success=False,
                stage_name=self.name,
                error_message=str(e),
                custom_data={'stats': self.stats}
            )

    def _cleanup(self) -> None:
        """Cierra el cliente HTTP al finalizar la etapa."""
        if hasattr(self, 'http') and self.http:
            self.http.close()
    
    def _validar_conexion(self) -> None:
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
            response = self.http.head(self.URL_DESCARGA, headers=headers, timeout=10, allow_redirects=True)
            
            # Aceptar 200 o 3xx (redirects); 4xx/5xx indican problema real en el portal
            if response.status_code >= 400:
                raise ConnectionError(f"Servidor respondió HTTP {response.status_code}. Portal puede estar caído.")
            self.logger.info(f"[OK] Servidor disponible (HTTP {response.status_code})")
            
            # Obtener tamaño del archivo si está disponible
            if 'Content-Length' in response.headers:
                tamano_bytes = int(response.headers['Content-Length'])
                tamano_mb = tamano_bytes / (1024 * 1024)
                self.logger.info(f"[INFO] Tamaño archivo: {tamano_mb:.2f} MB")
                
        except Exception as e:
            raise ConnectionError(f"No se pudo conectar o timeout con Mercado Público. Error: {e!s}") from e
    
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
            
            # Descargar con stream para mostrar progreso (usando HTTPClient encapsulado)
            response = self.http.get(self.URL_DESCARGA, headers=headers, stream=True, timeout=60, allow_redirects=True)
            
            # Obtener tamaño total
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            chunk_size = 8192
            
            with ruta_temp.open('wb') as f:
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
            
        except Exception as e:
            if ruta_temp.exists():
                ruta_temp.unlink()
            raise ConnectionError(f"Error al descargar archivo HTTP: {e}") from e
    
    def _mover_a_input(self, ruta_origen: Path) -> Path:
        """Mueve el archivo descargado a la carpeta INPUT y gestiona histórico"""
        self.logger.subsection("Moviendo a INPUT")
        
        ruta_final_excel = None
        
        if zipfile.is_zipfile(ruta_origen):
            self.logger.info("[INFO] Archivo comprimido detectado, extrayendo...")
            
            with zipfile.ZipFile(ruta_origen, 'r') as zip_ref:
                archivos_excel = [f for f in zip_ref.namelist() if f.endswith(('.xlsx', '.xls'))]
                
                if not archivos_excel:
                    raise ValueError("No se encontró archivo Excel en el ZIP descargado")
                
                archivo_excel = archivos_excel[0]
                # Zip Slip guard: usar solo el nombre base, nunca rutas con directorios intermedios.
                # Path("../../etc/passwd").name == "passwd" — elimina cualquier path traversal.
                nombre_seguro = Path(archivo_excel).name
                if not nombre_seguro:
                    raise ValueError(f"Nombre de archivo ZIP inseguro o vacío: '{archivo_excel}'")
                
                self.logger.info(f"[INFO] Extrayendo: {nombre_seguro}")
                
                # Extracción segura: copiar bytes directamente en lugar de zip_ref.extract()
                temp_dir = ruta_origen.parent
                ruta_final_excel = temp_dir / nombre_seguro
                with zip_ref.open(archivo_excel) as source, ruta_final_excel.open('wb') as target:
                    shutil.copyfileobj(source, target)
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
                self.logger.info("[HISTORICO] Ya existe versión de hoy, omitiendo backup")
        
        # Limpiar históricos antiguos (mayores a 30 días)
        self._limpiar_historico(historico_dir, dias_max=30)
        
        # Mover archivo nuevo como principal
        shutil.move(str(ruta_final_excel), str(ruta_destino))
        self.logger.info(f"[OK] Archivo principal actualizado: {ruta_destino.name}")
        
        # Limpiar archivo temporal ZIP si existía
        if ruta_origen != ruta_final_excel and ruta_origen.exists():
            ruta_origen.unlink()
        
        return ruta_destino
    
    def _limpiar_historico(self, historico_dir: Path, dias_max: int = 30) -> None:
        """Elimina archivos históricos mayores a N días"""
        fecha_limite = datetime.now() - timedelta(days=dias_max)
        archivos_eliminados = 0
        
        for archivo in historico_dir.glob("Licitacion_*.xlsx"):
            # Obtener fecha de modificación del archivo
            fecha_archivo = datetime.fromtimestamp(archivo.stat().st_mtime, tz=None)  # noqa: DTZ006 — local filesystem timestamp
            
            if fecha_archivo < fecha_limite:
                archivo.unlink()
                archivos_eliminados += 1
        
        if archivos_eliminados > 0:
            self.logger.info(f"[LIMPIEZA] Eliminados {archivos_eliminados} archivos históricos (>{dias_max} días)")
        
        # Contar archivos restantes
        total_historicos = len(list(historico_dir.glob("Licitacion_*.xlsx")))
        self.logger.info(f"[HISTORICO] Total archivos mantenidos: {total_historicos}")
    
    def _validar_archivo(self, ruta: Path) -> None:
        """Valida que el archivo descargado sea correcto"""
        self.logger.subsection("Validando archivo")

        try:
            # openpyxl en modo read_only puede devolver max_row=None en archivos grandes
            # con el campo <dimension> en el XML de Excel ausente. Usamos pandas que es
            # más robusto para este tipo de archivos.
            import pandas as pd
            df_muestra = pd.read_excel(ruta, nrows=5, engine='openpyxl')
            # Contar filas reales sin cargar todo el archivo
            wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
            ws = wb.active
            filas = ws.max_row or 0 if ws is not None else 0
            columnas = len(df_muestra.columns) if df_muestra is not None else 0
            wb.close()

            # Si openpyxl no pudo contar filas pero pandas sí leyó columnas, el archivo es válido
            if filas == 0 and columnas > 0:
                self.logger.info("[OK] Archivo válido")
                self.logger.info(f"[INFO] Columnas detectadas: {columnas}")
                return  # Archivo OK aunque max_row no sea confiable
        except Exception as e:
            raise ValueError(f"Archivo descargado no es válido: {e}") from e

        self.logger.info("[OK] Archivo válido")
        self.logger.info(f"[INFO] Filas: ~{filas:,}")
        self.logger.info(f"[INFO] Columnas: {columnas}")

        if filas < 100:
            self.logger.warning(f"[!] Archivo sospechosamente pequeño ({filas} filas)")

        if columnas < 10:
            self.logger.warning(f"[!] Pocas columnas ({columnas})")
    
    def _imprimir_resumen(self) -> None:
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


def main() -> None:
    """Función principal para ejecutar Etapa 0 de forma independiente"""
    from utils.logger import configurar_consola_utf8
    configurar_consola_utf8()
    context = PipelineContext(config=Config())
    etapa = Etapa0Descarga()
    resultado = etapa.run(context)
    
    if resultado.success:
        print("\n✅ ETAPA 0 COMPLETADA")
        print(f"   * Archivo descargado: {resultado.custom_data['stats']['archivo']}")
        print(f"   * Tamaño: {resultado.custom_data['stats']['tamano_mb']:.2f} MB")
    else:
        print("\n❌ ETAPA 0 FALLÓ")
        print(f"   * Error: {resultado.error_message}")
        exit(1)


if __name__ == "__main__":
    main()
