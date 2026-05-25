"""Orquestador del pipeline: ejecuta las 6 etapas de procesamiento de licitaciones."""

from importlib.metadata import version as _pkg_version

__version__ = _pkg_version("licitaciones-mp")

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar

from core.context import PipelineContext
from core.contracts import BaseStage, StageResult
from etapas.etapa0 import Etapa0Descarga
from etapas.etapa1 import AuditorTaxonomia
from etapas.etapa2 import FiltradorLicitaciones
from etapas.etapa3 import EnriquecedorAPI
from etapas.etapa4 import GeneradorReporte
from etapas.etapa5 import GeneradorReporteIncremental
from utils import Config, ProjectLogger
from utils.alerts import AlertManager, ConsoleAlertSink, FileAlertSink
from utils.logger import cleanup_old_logs, configurar_consola_utf8
from utils.observability import ObservabilityRules, RunSummaryReporter


class PipelineLicitaciones:
    """Orquestador del pipeline completo: coordina las etapas 0-5 y gestiona alertas y observabilidad."""

    # Registro de etapas: (número, clase, nombre para logs, es_fatal_si_falla)
    _STAGE_REGISTRY: ClassVar[list[tuple[int, type[BaseStage], str, bool]]] = [
        (1, AuditorTaxonomia,           "AUDITORIA DE TAXONOMIA",  True),
        (2, FiltradorLicitaciones,      "FILTRADO INTELIGENTE",    True),
        (3, EnriquecedorAPI,            "ENRIQUECIMIENTO API",     True),
        (4, GeneradorReporte,           "REPORTE EJECUTIVO",       True),
        (5, GeneradorReporteIncremental,"ANÁLISIS INCREMENTAL",    False),
    ]
    
    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self.context = PipelineContext(config=self.config)
        cleanup_old_logs(self.config.LOG_DIR, keep_days=30)
        self.logger = ProjectLogger('pipeline_completo', self.config.LOG_DIR)

        # Sistema de alertas: console + archivo JSONL en LOG_DIR
        self.alerts = AlertManager()
        self.alerts.add_sink(ConsoleAlertSink())
        alerts_file = self.config.LOG_DIR / f"alerts_{self.context.run_id}.jsonl"
        self.alerts.add_sink(FileAlertSink(alerts_file))

        # Resumen de resultados por etapa (datos de custom_data de cada StageResult)
        self.resultados: dict[str, Any] = {
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
        etapas: list[int] | None = None,
        descargar_archivo: bool = True,
        archivo_entrada: Path | None = None
    ) -> dict[str, Any]:
        """Ejecuta las etapas indicadas en secuencia y devuelve el dict de resultados."""
        if etapas is None:
            etapas = [1, 2, 3, 4, 5]
        
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
                self._ejecutar_etapa0()
            else:
                _archivo_input = archivo_entrada or self.config.LICITACIONES_MP
                self.context.add_artifact('etapa0_output', _archivo_input)
                self.logger.info(f"Etapa 0 omitida — usando: {_archivo_input.name}")
                self.logger.info("")
            
            # ETAPAS 1-5: ejecutar las que estén habilitadas
            for num, StageClass, nombre, es_fatal in self._STAGE_REGISTRY:
                if num in etapas:
                    self._ejecutar_etapa(num, StageClass, nombre, es_fatal)
            
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
    
    def _ejecutar_etapa0(self) -> None:
        """Ejecuta la Etapa 0 (descarga). No es fatal si falla."""
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

    def _ejecutar_etapa(
        self,
        num: int,
        StageClass: type[BaseStage],
        nombre: str,
        es_fatal: bool,
    ) -> None:
        """Ejecuta una etapa genérica, registra resultados y loguea stats."""
        clave = f"etapa{num}"

        self.logger.section("=" * 80, 80)
        self.logger.info(f"EJECUTANDO ETAPA {num} - {nombre}")
        self.logger.section("=" * 80, 80)

        stage = StageClass()
        stage_res = stage.run(self.context)
        self.context.stage_results[clave] = stage_res
        self.resultados[clave] = stage_res.custom_data

        if not stage_res.success:
            if es_fatal:
                self.logger.error(f"❌ Etapa {num} falló: {stage_res.error_message}")
                raise RuntimeError(f"Falla fatal de Etapa {num}: {stage_res.error_message}")
            else:
                self.logger.warning(f"Etapa {num} tuvo problemas: {stage_res.error_message}. Continuando...")
                self.logger.info("")
                return

        if stage_res.warnings:
            self.logger.warning(
                f"Etapa {num} completada con {len(stage_res.warnings)} warnings: {stage_res.warnings[0]}"
            )

        self.logger.info(f"\nETAPA {num} COMPLETADA")
        self._loguear_stats_etapa(num, stage_res)
        self.logger.info("")

    def _loguear_stats_etapa(self, num: int, stage_res: StageResult) -> None:
        """Imprime las estadísticas relevantes de cada etapa."""
        data = stage_res.custom_data or {}
        stats = data.get('stats', {})

        if num == 1:
            self.logger.info(f"   * Nuevos valores detectados: {stats.get('nuevos', 0)}")
        elif num == 2:
            final = stats.get('final', 0)
            original = stats.get('original', 1)
            ret_rate = (final / original) * 100 if original > 0 else 0
            self.logger.info(f"   * Licitaciones filtradas: {final}")
            self.logger.info(f"   * Tasa de retención: {ret_rate:.2f}%")
        elif num == 3:
            self.logger.info(f"   * Licitaciones procesadas: {stats.get('total_registros', 0)}")
            self.logger.info(f"   * Enriquecidas con datos: {stats.get('enriquecidos_ok', 0)}")
            self.logger.info(f"   * Errores individuales: {stats.get('errores_registro', 0)}")
            self.logger.info(f"   * Errores de etapa: {stats.get('errores_fatales_etapa', 0)}")
        elif num == 4:
            self.logger.info(f"   * Licitaciones vigentes: {data.get('vigentes', 0)}")
            self.logger.info(f"   * Historico: {data.get('vencidas', 0)}")
        elif num == 5:
            detalles = data.get('detalles', {})
            self.logger.info(f"   * Nuevas agregadas: {detalles.get('licitaciones_nuevas', 0)}")
            self.logger.info(f"   * Existentes actualizadas: {detalles.get('licitaciones_existentes', 0)}")
            self.logger.info(f"   * Vencidas movidas: {detalles.get('licitaciones_vencidas', 0)}")
            self.logger.info(f"   * Tipo reporte: {detalles.get('tipo', 'N/A')}")

    def _imprimir_resumen_final(self) -> None:
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
            e2_final = e2_stats.get('final', 0)
            e2_original = e2_stats.get('original', 0)
            tasa_r = f"{(e2_final / e2_original * 100):.1f}%" if e2_original > 0 else "N/A"
            resumen += "\nETAPA 2 - FILTRADO:\n"
            resumen += f"   * Total filtradas: {e2_final}\n"
            resumen += f"   * Tasa retencion: {tasa_r}\n"
        
        # Etapa 3
        if self.resultados['etapa3']:
            e3_stats = self.resultados['etapa3'].get('stats', {})
            resumen += "\nETAPA 3 - ENRIQUECIMIENTO:\n"
            resumen += f"   * Total enriquecidas: {e3_stats.get('enriquecidos_ok', 0)}\n"
        
        # Etapa 4
        if self.resultados['etapa4']:
            resumen += "\nETAPA 4 - REPORTE:\n"
            resumen += f"   * Vigentes: {self.resultados['etapa4'].get('vigentes', 0)}\n"
            resumen += f"   * Vencidas: {self.resultados['etapa4'].get('vencidas', 0)}\n"
        
        # Etapa 5
        if self.resultados['etapa5']:
            e5 = self.resultados['etapa5'].get('detalles', {})
            resumen += "\nETAPA 5 - INCREMENTAL:\n"
            resumen += f"   * Nuevas agregadas: {e5.get('licitaciones_nuevas', 0)}\n"
            resumen += f"   * Existentes actualizadas: {e5.get('licitaciones_existentes', 0)}\n"
            resumen += f"   * Vencidas movidas: {e5.get('licitaciones_vencidas', 0)}\n"
            resumen += f"   * Tipo: {e5.get('tipo', 'N/A')}\n"
        
        resumen += "\n" + "=" * 64 + "\n"
        
        self.logger.info(resumen)


def main() -> int:
    # Forzar UTF-8 en stdout/stderr ANTES de cualquier logging: en Windows
    # cp1252 hace crashear los emojis (📋, ✅, etc.) de los logs y alertas.
    configurar_consola_utf8()

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
        '--equipo',
        type=str,
        default=None,
        help="Código del equipo MP cuyos filtros aplicar (ej: TELECOM, ARQ, ELEC). "
             "Si se omite, se usa el guardado en config_usuario.json o TELECOM por defecto. "
             "Si se especifica, se persiste como preferencia del usuario."
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'Pipeline Licitaciones v{__version__}'
    )
    
    args = parser.parse_args()
    
    # Validar etapas
    etapas_validas = [e for e in args.etapas if 1 <= e <= 5]
    etapas_invalidas = [e for e in args.etapas if e < 1 or e > 5]
    if etapas_invalidas:
        print(f"ADVERTENCIA: Etapas ignoradas (fuera de rango 1-5): {etapas_invalidas}", file=sys.stderr)
    if not etapas_validas:
        print("ERROR: Debe especificar al menos una etapa valida (1-5)", file=sys.stderr)
        return 1
    
    try:
        print("\n" + "=" * 80)
        print(f"PIPELINE LICITACIONES MP v{__version__}".center(80))
        print("=" * 80 + "\n")
        
        pipeline = PipelineLicitaciones()
        if args.standalone:
            pipeline.context.flags['allow_fallback'] = True

        # Resolver equipo: --equipo (mayor prioridad) → UserConfig persistente → default en etapa2
        from utils.user_config import UserConfig
        user_cfg = UserConfig.cargar()
        equipo_codigo = (args.equipo or user_cfg.equipo_seleccionado or "").strip().upper()
        if equipo_codigo:
            pipeline.context.flags['equipo'] = equipo_codigo
            # Si vino por CLI y es distinto al persistido, persistirlo
            if args.equipo and equipo_codigo != user_cfg.equipo_seleccionado:
                user_cfg.equipo_seleccionado = equipo_codigo
                user_cfg.guardar()
                print(f"[INFO] Equipo '{equipo_codigo}' guardado como preferencia del usuario.")

        pipeline.ejecutar(
            etapas=etapas_validas,
            descargar_archivo=not args.no_descargar,
            archivo_entrada=args.archivo
        )
        
        print("\nPIPELINE COMPLETADO EXITOSAMENTE")
        return 0
    
    except KeyboardInterrupt:
        print("\n\nPIPELINE INTERRUMPIDO POR EL USUARIO")
        return 130
    
    except Exception as e:
        print(f"\nERROR CRITICO: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
