"""
ETAPA 3 - Enriquecimiento vía API de Mercado Público
Versión: 3.0.0
"""

__version__ = "3.0.0"

import time
import pandas as pd
from pathlib import Path
from datetime import datetime
import json
import hashlib
from utils import Config, guardar_excel_con_formato, obtener_timestamp
from utils.http import HTTPClient
from core.contracts import BaseStage, StageResult
from core.context import PipelineContext


class EnriquecedorAPI(BaseStage):
    """Enriquecedor de licitaciones mediante API de Mercado Público"""
    
    def __init__(self):
        super().__init__()
        self.estadisticas = {
            'total_registros': 0,
            'enriquecidos_ok': 0,
            'omitidos': 0,
            'errores_registro': 0,
            'errores_fatales_etapa': 0,
            'tiempo_inicio': datetime.now(),
            'llamadas_api': 0,
            'errores_http_500': 0
        }
        self.cache = {}
        self.http = None

    @property
    def name(self) -> str:
        return "enriquecimiento"

    def validate_inputs(self, context: PipelineContext) -> bool:
        permite_fallback = context.flags.get('allow_fallback', False)
        archivo_entrada = context.get_artifact('etapa2_output')
        
        if not archivo_entrada:
            if not permite_fallback:
                raise ValueError("Modo pipeline: Fallo al iniciar Etapa 3. Falta artefacto 'etapa2_output'.")
            archivo_entrada = self._obtener_archivo_fallback(context)
            
        if not archivo_entrada or not archivo_entrada.exists():
            raise FileNotFoundError(f"El archivo filtrado no existe físicamente: {archivo_entrada}")
            
        return True
    
    def _cargar_api_key(self) -> str:
        """Carga API Key priorizando variable de entorno, con fallback a PIVOT_MAESTRO."""
        if self.config.mercado_publico_ticket:
            self.logger.info("[OK] API Key cargada desde variable de entorno (LICIT_MERCADO_PUBLICO_TICKET)")
            return self.config.mercado_publico_ticket
        try:
            params = self.config.cargar_desde_pivot()
            api_key = params.get('API Key', '')
            if api_key:
                self.logger.info("[!] API Key cargada desde PIVOT (migrar a LICIT_MERCADO_PUBLICO_TICKET en .env)")
            return api_key
        except Exception as e:
            self.logger.warning(f"[!] No se pudo cargar API Key del PIVOT: {e}")
            return ""
    
    def run(self, context: PipelineContext) -> StageResult:
        self.bind(context)
        self.logger.section("ETAPA 3 - ENRIQUECIMIENTO VÍA API", 80)
        self.logger.info(f"🚀 Iniciando enriquecimiento - Versión {__version__} | RunID: {context.run_id}")
        self.logger.info(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            self.api_base_url = self.config.ETAPA3_API_BASE_URL
            self.delay_segundos = self.config.ETAPA3_DELAY_SEGUNDOS
            self.max_reintentos = self.config.ETAPA3_MAX_REINTENTOS
            self.timeout = self.config.ETAPA3_TIMEOUT
            # HTTPClient se inicializa DESPUÉS de leer el config para usar ETAPA3_TIMEOUT (40s) y ETAPA3_MAX_REINTENTOS
            self.http = HTTPClient(self.logger,
                                   max_retries=self.max_reintentos,
                                   timeout=self.timeout,
                                   backoff_factor=1.5)
            self.api_key = self._cargar_api_key()
            
            self.validate_inputs(context)
            archivo_entrada = context.get_artifact('etapa2_output') or self._obtener_archivo_fallback(context)

            # ── Health check: verificar que la API responde ANTES de procesar N registros ──
            api_disponible = self._health_check_api()
            if not api_disponible:
                self.logger.warning(
                    "⚠️ La API de Mercado Público no está respondiendo ahora mismo.\n"
                    "   El pipeline continuará SIN datos adicionales de la API.\n"
                    "   Puedes volver a ejecutar solo la Etapa 3 cuando la API esté disponible."
                )

            df_filtradas = self._cargar_licitaciones(archivo_entrada)
            self.estadisticas['total_registros'] = len(df_filtradas)

            df_enriquecidas = self._enriquecer_licitaciones(df_filtradas, api_disponible=api_disponible)
            rutas_generadas = self._generar_outputs(df_enriquecidas)
            
            if not rutas_generadas:
                raise ValueError("La etapa no generó ningún artefacto de salida. Proceso abortado.")
            
            context.add_artifact('etapa3_output', rutas_generadas[0])
            
            self.estadisticas['tiempo_total'] = str(datetime.now() - self.estadisticas['tiempo_inicio'])
            self.logger.section("RESUMEN DE ENRIQUECIMIENTO", 80)
            self._imprimir_resumen()
            
            warnings = []
            if self.estadisticas['errores_registro'] > 0:
                warnings.append(f"Hubo {self.estadisticas['errores_registro']} errores parciales por registro.")
            
            return StageResult(
                success=True,
                stage_name=self.name,
                files_produced=rutas_generadas,
                metrics_produced=self.estadisticas,
                custom_data={'stats': self.estadisticas},
                warnings=warnings
            )

        except Exception as e:
            self.estadisticas['errores_fatales_etapa'] += 1
            self.logger.error(f"❌ Error crítico en etapa 3: {e}", exc_info=True)
            return StageResult(success=False, stage_name=self.name, error_message=str(e), metrics_produced=self.estadisticas)
        finally:
            if hasattr(self, 'http') and self.http:
                self.http.close()
            self.logger.finalize()
    
    def _obtener_archivo_fallback(self, context: PipelineContext) -> Path:
        archivos = list(context.config.FILTRADO_DIR.glob("Licitaciones_Filtradas_*.xlsx"))
        if not archivos:
            raise FileNotFoundError(f"No se encontró archivo filtrado de fallback en {context.config.FILTRADO_DIR}")
        archivos = sorted(archivos, key=lambda f: f.stat().st_mtime, reverse=True)
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
    
    def _get_dataset_hash(self, df: pd.DataFrame, col_codigo: str) -> str:
        concatenado = "".join(df[col_codigo].astype(str).tolist())
        return hashlib.sha256(concatenado.encode('utf-8')).hexdigest()

    def _limpiar_checkpoints_antiguos(self, checkpoint_dir: Path) -> None:
        """Elimina checkpoints más antiguos que ETAPA3_CHECKPOINT_RETENTION_DAYS días."""
        retention = self.config.ETAPA3_CHECKPOINT_RETENTION_DAYS
        ahora = time.time()
        cutoff = ahora - retention * 86400
        eliminados = 0
        for cp in checkpoint_dir.glob("e3_checkpoint_*.jsonl"):
            try:
                if cp.stat().st_mtime < cutoff:
                    cp.unlink()
                    eliminados += 1
            except OSError:
                pass
        if eliminados:
            self.logger.info(f"[♻️] {eliminados} checkpoint(s) antiguo(s) eliminado(s) (>{retention}d)")

    def _health_check_api(self) -> bool:
        """Hace UNA llamada rápida para saber si la API está respondiendo."""
        url = f"{self.api_base_url}/licitaciones.json"
        params = {"ticket": self.api_key, "estado": "publicada"}
        self.logger.info("[>>] Verificando disponibilidad de la API de Mercado Público...")
        try:
            resp = self.http.session.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                self.logger.info("[OK] API de Mercado Público disponible.")
                return True
            self.logger.warning(f"⚠️ API respondió con HTTP {resp.status_code} — puede estar degradada.")
            return resp.status_code < 500   # 2xx/3xx/4xx = está up; 5xx = servidor caído
        except Exception:
            self.logger.warning("⚠️ API de Mercado Público no respondió al health check (timeout o sin conexión).")
            return False

    def _enriquecer_licitaciones(self, df: pd.DataFrame, api_disponible: bool = True) -> pd.DataFrame:
        self.logger.subsection("Enriqueciendo licitaciones vía API")
        
        col_codigo = next((c for c in ["Numero Adquisición", "Código", "Codigo", "CodigoExterno"] if c in df.columns), None)
        total = len(df)
        dataset_hash = self._get_dataset_hash(df, col_codigo)
        
        checkpoint_dir = self.config.BASE_DIR / 'temp' / 'checkpoints'
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._limpiar_checkpoints_antiguos(checkpoint_dir)
        checkpoint_file = checkpoint_dir / f"e3_checkpoint_{dataset_hash}.jsonl"
        
        resultados_cache = {}
        if checkpoint_file.exists():
            self.logger.info(f"[ℹ️] Archivo de checkpoint encontrado: {checkpoint_file.name}")
            try:
                with open(checkpoint_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        try:
                            record = json.loads(line)
                            # Solo reutilizar registros exitosos del checkpoint.
                            # Los 'api_disponible_false' pueden ser de cuando el ticket
                            # estaba caducado o la API caída — se deben reintentar.
                            if record.get('status') == 'success':
                                resultados_cache[record['codigo']] = record['data']
                        except json.JSONDecodeError:
                            continue
                self.logger.info(f"[>>] {len(resultados_cache)} registros recuperados del checkpoint.")
            except Exception as e:
                self.logger.warning(f"[!] Checkpoint corrupto o inaccesible, se ignorará: {e}")
                resultados_cache = {}
                
        # Si la API está caída, marcar todo directamente sin llamadas HTTP
        if not api_disponible:
            self.logger.info("[>>] API no disponible — generando resultado sin datos adicionales para todas las licitaciones.")
            resultados = [{**row.to_dict(), '_api_disponible': False, '_api_error': 'API no disponible al inicio del proceso'}
                          for _, row in df.iterrows()]
            self.estadisticas['errores_registro'] = len(resultados)
            return pd.DataFrame(resultados)

        resultados = []
        okcount = 0
        failcount = 0
        # Circuit breaker: si N fallos consecutivos, pausar para dejar recuperar la API
        _CB_UMBRAL = 5       # fallos seguidos antes de activar
        _CB_PAUSA  = 60      # segundos de espera cuando se activa
        fallos_consecutivos = 0

        with open(checkpoint_file, 'a', encoding='utf-8') as cp_file:
            for idx, row in df.iterrows():
                mostrar_progreso = (idx + 1) % 10 == 0 or idx == 0 or idx == total - 1
                if mostrar_progreso:
                    self.logger.progress(
                        idx + 1, total,
                        prefix=f"Enriqueciendo [✓ {okcount} datos | ⚠ {failcount} sin respuesta]"
                    )
                
                codigo = str(row[col_codigo])
                if codigo in resultados_cache:
                    datos_api = resultados_cache[codigo]
                else:
                    datos_api = self._consultar_api(codigo)
                    
                    status = 'api_disponible_false' if not datos_api.get('_api_disponible', True) else 'success'
                    record_to_save = {
                        'codigo': codigo,
                        'status': status,
                        'data': datos_api,
                        'timestamp': datetime.now().isoformat()
                    }
                    cp_file.write(json.dumps(record_to_save, ensure_ascii=False) + '\n')
                    cp_file.flush()
                    
                    time.sleep(self.delay_segundos)
                
                resultados.append({**row.to_dict(), **datos_api})

                if datos_api.get('_api_disponible', True):
                    self.estadisticas['enriquecidos_ok'] += 1
                    okcount += 1
                    fallos_consecutivos = 0   # reset circuit breaker en éxito
                else:
                    self.estadisticas['errores_registro'] += 1
                    failcount += 1
                    # Solo activar circuit breaker en fallos reales de red/servidor
                    # "Listado vacío" (HTTP 200 sin datos) es normal y NO debe contar
                    if datos_api.get('_fallo_red', False):
                        fallos_consecutivos += 1
                        self.logger.info(
                            f"   ↪️ Licitación {codigo} incluida sin datos adicionales "
                            f"(fallo de red, el proceso continúa)"
                        )
                        # Circuit breaker: N fallos de red seguidos → pausar
                        if fallos_consecutivos >= _CB_UMBRAL:
                            self.logger.warning(
                                f"⏸ {fallos_consecutivos} fallos de red consecutivos. "
                                f"Pausando {_CB_PAUSA}s para que el servidor se recupere..."
                            )
                            time.sleep(_CB_PAUSA)
                            self.http._renovar_sesion()
                            fallos_consecutivos = 0
                    else:
                        # Listado vacío: licitación no indexada en la API — es normal
                        fallos_consecutivos = 0

        try:
            if checkpoint_file.exists():
                checkpoint_file.unlink()
        except OSError:
            pass

        df_enriquecidas = pd.DataFrame(resultados)
        self.logger.info("\n[OK] Enriquecimiento completado:")
        self.logger.info(f"   • Total procesadas: {len(df_enriquecidas):,}")
        self.logger.info(f"   • Con datos API: {self.estadisticas['enriquecidos_ok']:,}")
        self.logger.info(f"   • Errores por registro: {self.estadisticas['errores_registro']:,}")
        
        return df_enriquecidas
    
    def _consultar_api(self, codigo: str) -> dict:
        if codigo in self.cache:
            return self.cache[codigo]
        
        url = f"{self.api_base_url}/licitaciones.json"
        params = {'codigo': codigo}
        if self.api_key:
            params['ticket'] = self.api_key
        
        try:
            self.estadisticas['llamadas_api'] += 1
            response = self.http.get(url, params=params)

            data = response.json()
            if 'Listado' in data and data['Listado']:
                datos_procesados = self._procesar_respuesta_api(data['Listado'][0])
                self.cache[codigo] = datos_procesados
                return datos_procesados
            # HTTP 200 pero sin datos — licitación no indexada en la API (normal, no es fallo de red)
            return {'_api_error': 'Listado vacío', '_api_disponible': False, '_fallo_red': False}

        except Exception as e:
            # Fallo real de red/servidor — éstos sí deben activar el circuit breaker
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code >= 500:
                    self.estadisticas['errores_http_500'] += 1
                return {'_api_error': f'HTTP Error {e.response.status_code}',
                        '_api_disponible': False, '_fallo_red': True}
            return {'_api_error': str(e), '_api_disponible': False, '_fallo_red': True}
    
    def _procesar_respuesta_api(self, datos_raw: dict) -> dict:
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
    
    def _generar_outputs(self, df_enriquecidas: pd.DataFrame) -> list[Path]:
        self.logger.subsection("Generando archivos de salida")
        timestamp = obtener_timestamp()
        
        if len(df_enriquecidas) > 0:
            ruta_enriquecidas = self.config.ENRIQUECIDO_DIR / f"Licitaciones_Enriquecidas_{timestamp}.xlsx"
            self.logger.info("[>>] Guardando licitaciones enriquecidas...")
            guardar_excel_con_formato(df_enriquecidas, ruta_enriquecidas, nombre_hoja="Licitaciones Enriquecidas")
            self.logger.info(f"   [OK] {ruta_enriquecidas.name}")
            return [ruta_enriquecidas]
        return []
    
    def _imprimir_resumen(self):
        stats = self.estadisticas
        porcentaje = (stats['enriquecidos_ok'] / stats['total_registros'] * 100) if stats['total_registros'] > 0 else 0
        errores_500 = stats.get('errores_http_500', 0)
        
        self.logger.info(f"""
+==============================================================+
|           ESTADISTICAS DE ENRIQUECIMIENTO                    |
+==============================================================+

[*] Procesamiento:
   - Total a procesar:      {stats['total_registros']:,}
   - Exitosas:              {stats['enriquecidos_ok']:,}
   - Errores recuperables:  {stats['errores_registro']:,}
   - Errores fatales:       {stats['errores_fatales_etapa']:,}

[API] API:
   - Llamadas totales:      {stats.get('llamadas_api', 0):,}
   - Errores HTTP 500:      {errores_500:,} (servidor MP inestable)
   - Rate limit:            2 req/segundo

[+] Resultados:
   - % Éxito:               {porcentaje:.1f}%
   - Tiempo total:          {stats.get('tiempo_total', 'N/A')}
""")


def main():
    try:
        context = PipelineContext(config=Config())
        context.flags['allow_fallback'] = True
        enriquecedor = EnriquecedorAPI()
        resultados = enriquecedor.run(context)
        
        if resultados.success:
            print("\n[OK] ETAPA 3 COMPLETADA EXITOSAMENTE")
            print(f"[*] {resultados.metrics_produced['enriquecidos_ok']:,} licitaciones enriquecidas")
            return 0
        print(f"\n❌ ERROR CRÍTICO: {resultados.error_message}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR CRÍTICO EXCEPCIÓN: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
