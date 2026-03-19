"""
ETAPA 3 - Enriquecimiento vía API de Mercado Público
Versión: 3.0.0
"""

__version__ = "3.0.0"

import requests
import time
import pandas as pd
from pathlib import Path
from typing import Dict, Optional, Any, Tuple
from datetime import datetime
import sys

sys.path.append(str(Path(__file__).parent.parent.parent))
from src.utils import Config, ProjectLogger, guardar_excel_con_formato, obtener_timestamp


class EnriquecedorAPI:
    """Enriquecedor de licitaciones mediante API de Mercado Público"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.logger = ProjectLogger('etapa3', self.config.LOG_DIR)
        
        self.api_base_url = self.config.ETAPA3_API_BASE_URL
        self.delay_segundos = self.config.ETAPA3_DELAY_SEGUNDOS
        self.max_reintentos = self.config.ETAPA3_MAX_REINTENTOS
        self.timeout = self.config.ETAPA3_TIMEOUT
        
        self.api_key = self._cargar_api_key()
        self.estadisticas = {
            'total_procesar': 0,
            'exitosas': 0,
            'errores': 0,
            'tiempo_inicio': datetime.now(),
            'llamadas_api': 0
        }
        self.cache = {}
        self.session = requests.Session()
    
    def _cargar_api_key(self) -> str:
        try:
            params = self.config.cargar_desde_pivot()
            api_key = params.get('API Key', '')
            if api_key:
                self.logger.info("[OK] API Key cargada desde PIVOT")
            return api_key
        except Exception as e:
            self.logger.warning(f"[!] Error cargando API Key: {e}")
            return ""
    
    def ejecutar(self, archivo_entrada: Optional[Path] = None) -> Dict[str, Any]:
        self.logger.section("ETAPA 3 - ENRIQUECIMIENTO VÍA API", 80)
        self.logger.info(f"🚀 Iniciando enriquecimiento - Versión {__version__}")
        self.logger.info(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            archivo_entrada = archivo_entrada or self._obtener_archivo_entrada()
            df_filtradas = self._cargar_licitaciones(archivo_entrada)
            self.estadisticas['total_procesar'] = len(df_filtradas)
            
            df_enriquecidas = self._enriquecer_licitaciones(df_filtradas)
            self._generar_outputs(df_enriquecidas)
            
            self.estadisticas['tiempo_total'] = datetime.now() - self.estadisticas['tiempo_inicio']
            self.logger.section("RESUMEN DE ENRIQUECIMIENTO", 80)
            self._imprimir_resumen()
            
            return {
                'exito': True,
                'stats': {
                    'total_enriquecidas': len(df_enriquecidas),
                    'exitosas': self.estadisticas['exitosas'],
                    'errores': self.estadisticas['errores']
                },
                'total_enriquecidas': len(df_enriquecidas)
            }
        except Exception as e:
            self.logger.error(f"❌ Error crítico: {e}", exc_info=True)
            raise
        finally:
            self.session.close()
            self.logger.finalize()
    
    def _obtener_archivo_entrada(self) -> Path:
        archivos = list(self.config.FILTRADO_DIR.glob("Licitaciones_Filtradas_*.xlsx"))
        if not archivos:
            raise FileNotFoundError(f"No se encontró archivo filtrado en {self.config.FILTRADO_DIR}")
        # Ordenar por fecha de modificación (más reciente primero)
        archivos = sorted(archivos, key=lambda f: f.stat().st_mtime, reverse=True)
        self.logger.info(f"📥 Usando archivo: {archivos[0].name}")
        return archivos[0]
    
    def _cargar_licitaciones(self, ruta: Path) -> pd.DataFrame:
        self.logger.subsection("Cargando licitaciones filtradas")
        df = pd.read_excel(ruta, engine='openpyxl')
        self.logger.info(f"[OK] {len(df):,} licitaciones cargadas")
        
        col_codigo = next((c for c in ["Numero Adquisición", "Código", "Codigo", "CodigoExterno"] if c in df.columns), None)
        if not col_codigo:
            raise ValueError("No se encontró columna con código de licitación")
        self.logger.info(f"📋 Columna de código: {col_codigo}")
        return df
    
    def _enriquecer_licitaciones(self, df: pd.DataFrame) -> pd.DataFrame:
        self.logger.subsection("Enriqueciendo licitaciones vía API")
        
        col_codigo = next((c for c in ["Numero Adquisición", "Código", "Codigo", "CodigoExterno"] if c in df.columns), None)
        resultados = []
        total = len(df)
        
        for idx, row in df.iterrows():
            if (idx + 1) % 10 == 0 or idx == 0 or idx == total - 1:
                self.logger.progress(idx + 1, total, prefix="Enriqueciendo")
            
            datos_api = self._consultar_api(row[col_codigo])
            resultados.append({**row.to_dict(), **datos_api})
            
            if datos_api.get('_api_disponible', True):
                self.estadisticas['exitosas'] += 1
            else:
                self.estadisticas['errores'] += 1
            
            time.sleep(self.delay_segundos)
        
        df_enriquecidas = pd.DataFrame(resultados)
        self.logger.info("\n[OK] Enriquecimiento completado:")
        self.logger.info(f"   • Total procesadas: {len(df_enriquecidas):,}")
        self.logger.info(f"   • Con datos API: {self.estadisticas['exitosas']:,}")
        self.logger.info(f"   • Sin datos API: {self.estadisticas['errores']:,}")
        
        return df_enriquecidas
    
    def _consultar_api(self, codigo: str) -> Dict[str, Any]:
        if codigo in self.cache:
            return self.cache[codigo]
        
        url = f"{self.api_base_url}/licitaciones.json"
        params = {'codigo': codigo}
        if self.api_key:
            params['ticket'] = self.api_key
        
        for intento in range(self.max_reintentos):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
                self.estadisticas['llamadas_api'] += 1
                
                if response.status_code != 200:
                    raise requests.exceptions.HTTPError(f"HTTP {response.status_code}", response=response)
                
                data = response.json()
                if 'Listado' in data and data['Listado']:
                    datos_procesados = self._procesar_respuesta_api(data['Listado'][0])
                    self.cache[codigo] = datos_procesados
                    return datos_procesados
                return {'_api_error': 'Listado vacío', '_api_disponible': False}
            
            except requests.exceptions.Timeout:
                if intento < self.max_reintentos - 1:
                    time.sleep(2 ** intento)
                    continue
                return {'_api_error': 'Timeout', '_api_disponible': False}
            
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    time.sleep(5)
                    continue
                elif e.response.status_code == 500:
                    if intento == 0:
                        time.sleep(0.5)
                        continue
                    self.estadisticas['errores_http_500'] = self.estadisticas.get('errores_http_500', 0) + 1
                    return {'_api_error': 'HTTP 500', '_api_disponible': False}
                return {'_api_error': f'HTTP {e.response.status_code}', '_api_disponible': False}
            
            except Exception as e:
                return {'_api_error': str(e), '_api_disponible': False}
        
        return {'_api_error': 'Max reintentos excedidos', '_api_disponible': False}
    
    def _procesar_respuesta_api(self, datos_raw: Dict) -> Dict[str, Any]:
        """Extrae y procesa datos de la respuesta de la API, incluyendo objetos anidados"""
        datos = {}
        
        # Campos simples del primer nivel
        datos['API_Nombre'] = datos_raw.get('Nombre', '')
        datos['API_Descripcion'] = datos_raw.get('Descripcion', '')
        datos['API_Estado'] = datos_raw.get('Estado', '')
        datos['API_CodigoEstado'] = datos_raw.get('CodigoEstado', '')
        datos['API_Moneda'] = datos_raw.get('Moneda', '')
        datos['API_Monto'] = datos_raw.get('MontoEstimado', '')
        datos['API_UnidadTiempo'] = datos_raw.get('UnidadTiempo', '')
        datos['API_DuracionContrato'] = datos_raw.get('TiempoDuracionContrato', '')
        
        # Extraer objeto anidado "Fechas"
        fechas = datos_raw.get('Fechas', {}) or {}
        datos['API_FechaPublicacion'] = fechas.get('FechaPublicacion', '')
        datos['API_FechaCierre'] = fechas.get('FechaCierre', '')
        datos['API_FechaInicio'] = fechas.get('FechaInicio', '')
        datos['API_FechaFinal'] = fechas.get('FechaFinal', '')
        datos['API_FechaPubRespuestas'] = fechas.get('FechaPubRespuestas', '')
        datos['API_FechaActoAperturaTecnica'] = fechas.get('FechaActoAperturaTecnica', '')
        datos['API_FechaActoAperturaEconomica'] = fechas.get('FechaActoAperturaEconomica', '')
        datos['API_FechaAdjudicacion'] = fechas.get('FechaAdjudicacion', '')
        
        # Extraer objeto anidado "Comprador"
        comprador = datos_raw.get('Comprador', {}) or {}
        datos['API_RegionUnidad'] = comprador.get('RegionUnidad', '')
        datos['API_ComunaUnidad'] = comprador.get('ComunaUnidad', '')
        datos['API_NombreUnidad'] = comprador.get('NombreUnidad', '')
        
        # Items y Adjuntos
        items = datos_raw.get('Items', {})
        datos['API_TotalItems'] = len(items.get('Listado', [])) if items else 0
        
        adjuntos = datos_raw.get('Adjuntos', {})
        datos['API_TotalAdjuntos'] = len(adjuntos.get('Listado', [])) if adjuntos else 0
        
        return datos
    
    def _generar_outputs(self, df_enriquecidas: pd.DataFrame):
        self.logger.subsection("Generando archivos de salida")
        timestamp = obtener_timestamp()
        
        if len(df_enriquecidas) > 0:
            ruta_enriquecidas = self.config.ENRIQUECIDO_DIR / f"Licitaciones_Enriquecidas_{timestamp}.xlsx"
            self.logger.info("[>>] Guardando licitaciones enriquecidas...")
            guardar_excel_con_formato(df_enriquecidas, ruta_enriquecidas, nombre_hoja="Licitaciones Enriquecidas")
            self.logger.info(f"   [OK] {ruta_enriquecidas.name}")
    
    def _imprimir_resumen(self):
        stats = self.estadisticas
        porcentaje = (stats['exitosas'] / stats['total_procesar'] * 100) if stats['total_procesar'] > 0 else 0
        errores_500 = stats.get('errores_http_500', 0)
        tiempo_promedio = (stats.get('tiempo_total', 0).total_seconds() / stats['total_procesar']) if stats['total_procesar'] > 0 else 0
        
        self.logger.info(f"""
+==============================================================+
|           ESTADISTICAS DE ENRIQUECIMIENTO                    |
+==============================================================+

[*] Procesamiento:
   - Total a procesar:      {stats['total_procesar']:,}
   - Exitosas:              {stats['exitosas']:,}
   - Errores:               {stats['errores']:,}

[API] API:
   - Llamadas totales:      {stats['llamadas_api']:,}
   - Errores HTTP 500:      {errores_500:,} (servidor MP inestable)
   - Rate limit:            2 req/segundo
   - Reintentos max:        {self.max_reintentos}

[+] Resultados:
   - % Éxito:               {porcentaje:.1f}%
   - Tiempo total:          {stats.get('tiempo_total', 'N/A')}
   - Tiempo promedio/lic:   {tiempo_promedio:.2f}s
""")


def main():
    try:
        enriquecedor = EnriquecedorAPI()
        resultados = enriquecedor.ejecutar()
        
        if resultados['exito']:
            print("\n[OK] ETAPA 3 COMPLETADA EXITOSAMENTE")
            print(f"[*] {resultados['total_enriquecidas']:,} licitaciones enriquecidas")
            return 0
        return 1
    except Exception as e:
        print(f"\n❌ ERROR CRÍTICO: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
