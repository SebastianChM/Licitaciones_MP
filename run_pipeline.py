"""
Pipeline Licitaciones MP
Orquestador que ejecuta las etapas del procesamiento de licitaciones.

Version: 5.0.0
Autor: Sebastian Chirino
"""

__version__ = "5.0.0"

import sys
from pathlib import Path

# Asegurar que src/ está en el path al ejecutar desde la raíz del proyecto
_SRC = Path(__file__).parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from datetime import datetime
from typing import Dict, Any, Optional

from core.context import PipelineContext
from core.contracts import StageResult

from utils import Config, ProjectLogger
from utils.alerts import AlertManager, ConsoleAlertSink, FileAlertSink
from utils.observability import ObservabilityRules, RunSummaryReporter
from etapas.etapa0 import Etapa0Descarga
from etapas.etapa1 import AuditorTaxonomia
from etapas.etapa2 import FiltradorLicitaciones
from etapas.etapa3 import EnriquecedorAPI
from etapas.etapa4 import GeneradorReporte
from etapas.etapa5 import GeneradorReporteIncremental


class PipelineLicitaciones:
    """
    Orquestador del pipeline completo de licitaciones.
    
    Ejecuta las 5 etapas en secuencia:
    1. Auditoria de taxonomia
    2. Filtrado inteligente
    3. Enriquecimiento via API
    4. Generacion de reporte ejecutivo
    5. Analisis incremental (preserva trabajo manual)
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Inicializa el pipeline.
        
        Args:
            config: Configuracion del proyecto (usa Config por defecto si None)
        """
        self.config = config or Config()
        self.context = PipelineContext(config=self.config)
        self.logger = ProjectLogger('pipeline_completo', self.config.LOG_DIR)

        # Sistema de alertas: console + archivo JSONL en LOG_DIR
        self.alerts = AlertManager()
        self.alerts.add_sink(ConsoleAlertSink())
        alerts_file = self.config.LOG_DIR / f"alerts_{self.context.run_id}.jsonl"
        self.alerts.add_sink(FileAlertSink(alerts_file))

        # Diccionario transitorio para backward compatibility hasta refactor Fase 2B
        self.resultados = {
            'etapa0': None,
            'etapa1': None,
            'etapa2': None,
            'etapa3': None,
            'etapa4': None,
            'etapa5': None,
            'tiempo_total': None,
            'exito': False
        }

    def ejecutar(
        self,
        etapas=None,
        descargar_archivo: bool = True,
        archivo_entrada: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Ejecuta el pipeline completo o etapas especificas.
        
        Args:
            etapas: Lista de etapas a ejecutar ([1,2,3,4] por defecto)
            descargar_archivo: Si True, ejecuta Etapa 0 para descargar archivo fresco
            archivo_entrada: Archivo de entrada (opcional)
        
        Returns:
            dict: Resultados de cada etapa
        """
        if etapas is None:
            etapas = [1, 2, 3, 4]
        
        self.logger.section("PIPELINE COMPLETO - LICITACIONES MP", 80)
        self.logger.info(f"Version {__version__}")
        self.logger.info(f"RUN ID Global: {self.context.run_id}")
        self.logger.info(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"Etapas a ejecutar: {etapas}")
        self.logger.info("")
        
        try:
            tiempo_inicio = datetime.now()

            # ETAPA 0: Descarga automática (opcional)
            if descargar_archivo:
                self.logger.section("=" * 80, 80)
                self.logger.info("EJECUTANDO ETAPA 0 - DESCARGA AUTOMÁTICA")
                self.logger.section("=" * 80, 80)
                
                descargador = Etapa0Descarga()
                stage_res = descargador.run(self.context)
                self.context.stage_results['etapa0'] = stage_res
                self.resultados['etapa0'] = stage_res.custom_data
                
                if not stage_res.success:
                    self.logger.warning(f"⚠️ Etapa 0 falló ({stage_res.error_message}), continuando con archivo existente")
                else:
                    self.logger.info("\n✅ ETAPA 0 COMPLETADA")
                    stats0 = stage_res.custom_data.get('stats', {})
                    if stats0:
                        self.logger.info(f"   * Archivo descargado: {stats0.get('archivo', 'N/A')}")
                        self.logger.info(f"   * Tamaño: {stats0.get('tamano_mb', 0):.2f} MB")
                self.logger.info("")
            else:
                # Sin descarga: registrar el archivo de entrada para las etapas siguientes
                _archivo_input = archivo_entrada or self.config.LICITACIONES_MP
                self.context.add_artifact('etapa0_output', _archivo_input)
                self.logger.info(f"Etapa 0 omitida — usando: {_archivo_input.name}")
                self.logger.info("")
            
            # ETAPA 1: Auditoria de Taxonomia
            if 1 in etapas:
                self.logger.section("=" * 80, 80)
                self.logger.info("EJECUTANDO ETAPA 1 - AUDITORIA DE TAXONOMIA")
                self.logger.section("=" * 80, 80)
                
                auditor = AuditorTaxonomia()
                stage_res = auditor.run(self.context)
                self.context.stage_results['etapa1'] = stage_res
                self.resultados['etapa1'] = stage_res.custom_data
                
                if not stage_res.success:
                    raise Exception(f"Etapa 1 falló: {stage_res.error_message}")
                
                self.logger.info("\nETAPA 1 COMPLETADA")
                stats1 = self.resultados['etapa1'].get('stats', {})
                if stats1:
                    self.logger.info(f"   * Nuevos valores detectados: {stats1.get('nuevos', 0)}")
                self.logger.info("")
            
            # ETAPA 2: Filtrado Inteligente
            if 2 in etapas:
                self.logger.section("=" * 80, 80)
                self.logger.info("EJECUTANDO ETAPA 2 - FILTRADO INTELIGENTE")
                self.logger.section("=" * 80, 80)
                
                filtrador = FiltradorLicitaciones()
                stage_res = filtrador.run(self.context)
                self.context.stage_results['etapa2'] = stage_res
                self.resultados['etapa2'] = stage_res.custom_data
                
                if not stage_res.success:
                    raise Exception(f"Etapa 2 falló: {stage_res.error_message}")
                
                self.logger.info("\nETAPA 2 COMPLETADA")
                stats2 = stage_res.custom_data.get('stats', {})
                self.logger.info(f"   * Licitaciones filtradas: {stats2.get('final', 0)}")
                
                try:
                    ret_rate = (stats2.get('final', 0) / stats2.get('original', 1)) * 100
                except Exception:
                    ret_rate = 0
                self.logger.info(f"   * Tasa de retención: {ret_rate:.2f}%")
                self.logger.info("")
            
            # ETAPA 3: Enriquecimiento via API
            if 3 in etapas:
                self.logger.section("=" * 80, 80)
                self.logger.info("EJECUTANDO ETAPA 3 - ENRIQUECIMIENTO API")
                self.logger.section("=" * 80, 80)
                
                enriquecedor = EnriquecedorAPI()
                stage_res = enriquecedor.run(self.context)
                self.context.stage_results['etapa3'] = stage_res
                self.resultados['etapa3'] = stage_res.custom_data
                
                if not stage_res.success:
                    self.logger.error(f"❌ Etapa 3 falló con error crítico: {stage_res.error_message}")
                    raise Exception(f"Falla fatal de Etapa 3: {stage_res.error_message}")
                
                if stage_res.warnings:
                    self.logger.warning(f"Etapa 3 completada con {len(stage_res.warnings)} warnings: {stage_res.warnings[0]}")
                
                self.logger.info("\nETAPA 3 FINALIZADA (Parcial o Total)")
                stats3 = stage_res.custom_data.get('stats', {})
                self.logger.info(f"   * Licitaciones procesadas: {stats3.get('total_registros', 0)}")
                self.logger.info(f"   * Enriquecidas con datos: {stats3.get('enriquecidos_ok', 0)}")
                self.logger.info(f"   * Errores individuales: {stats3.get('errores_registro', 0)}")
                self.logger.info(f"   * Errores de etapa: {stats3.get('errores_fatales_etapa', 0)}")
                self.logger.info("")
            
            # ETAPA 4: Generacion de Reporte
            if 4 in etapas:
                self.logger.section("=" * 80, 80)
                self.logger.info("EJECUTANDO ETAPA 4 - REPORTE EJECUTIVO")
                self.logger.section("=" * 80, 80)
                
                generador = GeneradorReporte()
                stage_res = generador.run(self.context)
                self.context.stage_results['etapa4'] = stage_res
                self.resultados['etapa4'] = stage_res.custom_data
                
                if not stage_res.success:
                    raise Exception(f"Falla fatal de Etapa 4: {stage_res.error_message}")
                
                if stage_res.warnings:
                    self.logger.warning(f"Etapa 4 completada con warnings: {stage_res.warnings[0]}")
                
                self.logger.info("\nETAPA 4 COMPLETADA")
                self.logger.info(f"   * Licitaciones vigentes: {self.resultados['etapa4'].get('vigentes', 0)}")
                self.logger.info(f"   * Historico: {self.resultados['etapa4'].get('vencidas', 0)}")
                self.logger.info("")
            
            # ETAPA 5: Análisis Incremental
            if 5 in etapas:
                self.logger.section("=" * 80, 80)
                self.logger.info("EJECUTANDO ETAPA 5 - ANÁLISIS INCREMENTAL")
                self.logger.section("=" * 80, 80)

                generador_incremental = GeneradorReporteIncremental()
                stage_res = generador_incremental.run(self.context)
                self.context.stage_results['etapa5'] = stage_res
                self.resultados['etapa5'] = stage_res.custom_data

                if not stage_res.success:
                    self.logger.warning(f"Etapa 5 tuvo problemas: {stage_res.error_message}. Continuando...")

                self.logger.info("\nETAPA 5 COMPLETADA")
                stats5 = self.resultados['etapa5'] or {}
                self.logger.info(f"   * Nuevas agregadas: {stats5.get('licitaciones_nuevas', 0)}")
                self.logger.info(f"   * Existentes actualizadas: {stats5.get('licitaciones_existentes', 0)}")
                self.logger.info(f"   * Vencidas movidas: {stats5.get('licitaciones_vencidas', 0)}")
                self.logger.info(f"   * Tipo reporte: {stats5.get('tipo', 'N/A')}")
                self.logger.info("")
            
            # Calculo de tiempos
            self.resultados['tiempo_total'] = datetime.now() - tiempo_inicio
            self.resultados['exito'] = True

            # Observabilidad: evaluar reglas de negocio y generar JSON de resumen del run
            obs = ObservabilityRules(self.context, self.alerts)
            obs.evaluate_all()
            reporter = RunSummaryReporter(self.context, self.alerts)
            summary_path = reporter.generate_and_save()
            self.logger.info(f"📋 Run summary: {summary_path.name}")

            # Resumen final
            self._imprimir_resumen_final()
            
            return self.resultados
        
        except Exception as e:
            self.logger.error(f"Error en el pipeline: {e}", exc_info=True)
            self.resultados['exito'] = False
            self.resultados['error'] = str(e)
            raise
        
        finally:
            self.logger.finalize()
    
    def _imprimir_resumen_final(self):
        """Imprime resumen final del pipeline"""
        self.logger.section("=" * 80, 80)
        self.logger.section("RESUMEN FINAL DEL PIPELINE", 80)
        self.logger.section("=" * 80, 80)
        
        resumen = "\n"
        resumen += "+" + "=" * 62 + "+\n"
        resumen += "|" + " " * 15 + "PIPELINE COMPLETADO EXITOSAMENTE" + " " * 15 + "|\n"
        resumen += "+" + "=" * 62 + "+\n"
        resumen += f"\nTIEMPO TOTAL: {self.resultados['tiempo_total']}\n"
        
        # Etapa 1
        if self.resultados['etapa1']:
            e1_stats = self.resultados['etapa1'].get('stats', {})
            resumen += "\nETAPA 1 - AUDITORIA:\n"
            resumen += f"   * Valores nuevos detectados: {e1_stats.get('nuevos', 0)}\n"
            resumen += f"   * Similares encontrados: {e1_stats.get('similares', 0)}\n"
        
        # Etapa 2
        if self.resultados['etapa2']:
            e2_stats = self.resultados['etapa2'].get('stats', {})
            resumen += "\nETAPA 2 - FILTRADO:\n"
            resumen += f"   * Total filtradas: {e2_stats.get('total_filtradas', 0)}\n"
            resumen += f"   * Tasa retencion: {e2_stats.get('tasa_retencion', 0):.1f}%\n"
        
        # Etapa 3
        if self.resultados['etapa3']:
            e3_stats = self.resultados['etapa3'].get('stats', {})
            resumen += "\nETAPA 3 - ENRIQUECIMIENTO:\n"
            resumen += f"   * Total enriquecidas: {e3_stats.get('total_enriquecidas', 0)}\n"
        
        # Etapa 4
        if self.resultados['etapa4']:
            e4_stats = self.resultados['etapa4'].get('stats', {})
            resumen += "\nETAPA 4 - REPORTE:\n"
            resumen += f"   * Vigentes: {e4_stats.get('vigentes', 0)}\n"
            resumen += f"   * Vencidas: {e4_stats.get('vencidas', 0)}\n"
        
        # Etapa 5
        if self.resultados['etapa5']:
            resumen += "\nETAPA 5 - INCREMENTAL:\n"
            resumen += f"   * Nuevas agregadas: {self.resultados['etapa5'].get('licitaciones_nuevas', 0)}\n"
            resumen += f"   * Existentes actualizadas: {self.resultados['etapa5'].get('licitaciones_existentes', 0)}\n"
            resumen += f"   * Vencidas movidas: {self.resultados['etapa5'].get('licitaciones_vencidas', 0)}\n"
            resumen += f"   * Tipo: {self.resultados['etapa5'].get('tipo', 'N/A')}\n"
        
        resumen += "\n" + "=" * 64 + "\n"
        
        self.logger.info(resumen)


def main():
    """Funcion principal de ejecucion"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Pipeline Licitaciones MP')
    parser.add_argument(
        '--etapas',
        type=int,
        nargs='+',
        default=[1, 2, 3, 4, 5],
        help='Etapas a ejecutar (1-5). Etapa 5 = Análisis Incremental'
    )
    parser.add_argument(
        '--archivo',
        type=Path,
        default=None,
        help='Archivo de entrada (opcional)'
    )
    parser.add_argument(
        '--no-descargar',
        action='store_true',
        help='Omitir descarga automática (Etapa 0)'
    )
    parser.add_argument(
        '--standalone',
        action='store_true',
        help='Permitir que las etapas lean archivos directo del disco (fallback) sin etapa anterior'
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'Pipeline Licitaciones v{__version__}'
    )
    
    args = parser.parse_args()
    
    # Validar etapas
    etapas_validas = [e for e in args.etapas if 1 <= e <= 5]
    if not etapas_validas:
        print("ERROR: Debe especificar al menos una etapa valida (1-5)")
        return 1
    
    try:
        print("\n" + "=" * 80)
        print(f"PIPELINE LICITACIONES MP v{__version__}".center(80))
        print("=" * 80 + "\n")
        
        pipeline = PipelineLicitaciones()
        resultados = pipeline.ejecutar(
            etapas=etapas_validas,
            descargar_archivo=not args.no_descargar,
            archivo_entrada=args.archivo
        )
        
        if resultados['exito']:
            print("\nPIPELINE COMPLETADO EXITOSAMENTE")
            return 0
        else:
            print("\nPIPELINE COMPLETADO CON ERRORES")
            return 1
    
    except KeyboardInterrupt:
        print("\n\nPIPELINE INTERRUMPIDO POR EL USUARIO")
        return 130
    
    except Exception as e:
        print(f"\nERROR CRITICO: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
