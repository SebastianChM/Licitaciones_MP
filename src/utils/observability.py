"""
Reglas de observabilidad y reporte de resumen de ejecución del pipeline.
Evalua métricas de cada etapa y dispara alertas según umbrales de negocio.
"""
import json
from datetime import datetime
from pathlib import Path

from core.context import PipelineContext
from utils.alerts import AlertManager, AlertSeverity

# Umbrales de negocio para reglas de observabilidad
_TASA_RETENCION_MAX: float = 0.05   # >5% del universo nacional = filtro demasiado permisivo
_TASA_ERROR_API_MAX: float = 0.20   # >20% de errores HTTP = API degradada/caída


class ObservabilityRules:
    def __init__(self, ctx: PipelineContext, alerts: AlertManager) -> None:
        self.ctx = ctx
        self.alerts = alerts
    
    def evaluate_all(self) -> None:
        """Dispara todas las reglas de negocio sobre los StageResult"""
        self._check_etapa0()
        self._check_etapa2()
        self._check_etapa3()
        self._check_etapa4()
        self._check_fallback_modes()

    def _check_etapa0(self) -> None:
        result = self.ctx.stage_results.get('etapa0')
        if not result or not result.success:
            return
        
        # Etapa 0 métricas: 'tamano_mb'
        metrics = result.metrics_produced
        if metrics.get('tamano_mb', 0) == 0:
            self.alerts.trigger(
                rule_id="E0_DESC_VACIA",
                message="El archivo de licitaciones de MP descargado pesa 0 MB.",
                severity=AlertSeverity.CRITICAL,
                stage="etapa0",
                recommendation="Revisar acceso a la URL de Mercado Público o si hubo corte en la red."
            )
            
    def _check_etapa2(self) -> None:
        result = self.ctx.stage_results.get('etapa2')
        if not result or not result.success:
            return
        
        metrics = result.metrics_produced
        total = metrics.get('original', 0)
        filtradas = metrics.get('final', 0)
        
        if filtradas == 0:
            self.alerts.trigger(
                rule_id="E2_FILTRO_VACIO",
                message="Ninguna licitación superó los filtros de Keywords y ONUs.",
                severity=AlertSeverity.WARNING,
                stage="etapa2",
                recommendation="Verificar si los diccionarios de PIVOT_MAESTRO son demasiado restrictivos."
            )
        elif total > 0:
            tasa = filtradas / total
            if tasa > _TASA_RETENCION_MAX:
                self.alerts.trigger(
                    rule_id="E2_TASA_FILTRADO_ALTA",
                    message=f"La tasa de retención es inusualmente alta: {tasa*100:.2f}% de la base nacional.",
                    severity=AlertSeverity.WARNING,
                    stage="etapa2",
                    recommendation="Revisar si un término general como 'Servicios' se coló en palabras clave."
                )

    def _check_etapa3(self) -> None:
        result = self.ctx.stage_results.get('etapa3')
        if not result or not result.success:
            return
        
        metrics = result.metrics_produced
        total = metrics.get('total_registros', 0)
        errores = metrics.get('errores_registro', 0)
        
        if total == 0:
            return
            
        tasa_error = errores / total
        if tasa_error > _TASA_ERROR_API_MAX:
            self.alerts.trigger(
                rule_id="E3_TASA_ERROR_ALTA",
                message=f"El {tasa_error*100:.1f}% de las comprobaciones HTTP a MP fallaron por timeout o no resuelta.",
                severity=AlertSeverity.CRITICAL,
                stage="etapa3",
                recommendation="Servidor de Mercado Público inestable o caído parcialmente."
            )

    def _check_etapa4(self) -> None:
        result = self.ctx.stage_results.get('etapa4')
        if not result:
            return
        
        if result.success and len(result.files_produced) == 0:
             self.alerts.trigger(
                rule_id="E4_SIN_OUTPUT",
                message="Etapa 4 retornó success pero no reportó archivos producidos.",
                severity=AlertSeverity.ERROR,
                stage="etapa4",
                recommendation="Corrupción en la generación nativa de openpyxl."
             )

    def _check_fallback_modes(self) -> None:
        if self.ctx.flags.get('allow_fallback'):
            self.alerts.trigger(
                rule_id="MODO_STANDALONE",
                message="El pipeline corrió en modo standalone / fallback.",
                severity=AlertSeverity.INFO,
                stage="GLOBAL",
                recommendation="El pipeline asume desvinculación estricta de etapas previas."
            )

class RunSummaryReporter:
    """Genera y persiste el resumen JSON de cada ejecución del pipeline."""

    def __init__(self, ctx: PipelineContext, alerts: AlertManager) -> None:
        self.ctx = ctx
        self.alerts = alerts
        self.run_id = self.ctx.run_id
    
    def generate_and_save(self) -> Path:
        """Extrae metadata, métricas puras y reporta un JSON unificado del Run"""
        
        start_time = self.ctx.start_time
        end_time = datetime.now(tz=start_time.tzinfo)
        duration = end_time - start_time
        
        etapas_exitosas = sum(1 for _, res in self.ctx.stage_results.items() if res.success)
        etapas_fallidas = sum(1 for _, res in self.ctx.stage_results.items() if not res.success)
        etapas_ejecutadas = len(self.ctx.stage_results)
        etapas_con_warning = sum(1 for _, res in self.ctx.stage_results.items() if res.warnings)
        
        estado_general = "SUCCESS"
        if etapas_fallidas > 0:
            estado_general = "ERROR"
        elif etapas_con_warning > 0 or any(a.severity in (AlertSeverity.WARNING, AlertSeverity.CRITICAL) for a in self.alerts.get_history()):
            estado_general = "WARNING_OR_DEGRADED"
        
        resumen = {
            "metadata": {
                "run_id": self.run_id,
                "timestamp_inicio": start_time.isoformat(),
                "timestamp_fin": end_time.isoformat(),
                "duracion_total": str(duration),
                "estado_general": estado_general
            },
            "metricas": {
                "etapas_ejecutadas": etapas_ejecutadas,
                "etapas_exitosas": etapas_exitosas,
                "etapas_con_warning": etapas_con_warning,
                "etapas_fallidas": etapas_fallidas
            },
            "alerts_disparadas": [
                {
                    "rule_id": a.rule_id,
                    "message": a.message,
                    "severity": a.severity.value,
                    "stage": a.stage
                } for a in self.alerts.get_history()
            ],
            "etapas_detalle": []
        }
        
        for stage_name, result in self.ctx.stage_results.items():
            resumen["etapas_detalle"].append({
                "nombre_etapa": stage_name,
                "success": result.success,
                "error_message": result.error_message,
                "warnings": result.warnings,
                "metrics_produced": result.metrics_produced,
                "files_produced": [str(f) for f in result.files_produced]
            })
            
        # Archivo final
        log_dir = self.ctx.config.BASE_DIR / 'logs' / 'runs'
        log_dir.mkdir(parents=True, exist_ok=True)
        summary_path = log_dir / f"run_{self.run_id}.json"
        
        with summary_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps(resumen, indent=4, ensure_ascii=False,
                               default=lambda o: o.isoformat() if hasattr(o, 'isoformat') else str(o)))
            
        return summary_path
