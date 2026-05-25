# Logger del proyecto - maneja logs de archivo y consola
# Desarrollado para el pipeline de licitaciones

import logging
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


class ProjectLogger:
    """Logger con funcionalidades básicas necesarias para el pipeline"""
    
    def __init__(self, nombre: str, log_dir: Path, nivel: int = logging.INFO) -> None:
        self.nombre = nombre
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Crear timestamp para el archivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"{nombre}_{timestamp}.log"
        
        # Configurar logger
        self.logger = logging.getLogger(f"{nombre}_{timestamp}")
        self.logger.setLevel(nivel)
        self.logger.handlers.clear()  # Limpiar handlers existentes
        
        # Handler para archivo
        file_handler = logging.FileHandler(
            self.log_file,
            encoding='utf-8',
            mode='w'
        )
        file_handler.setLevel(nivel)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # Handler para consola — UTF-8 forzado para evitar garbled chars en Windows
        # Se usa sys.stdout directamente para evitar doble-buffer con el fileno
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(nivel)
        console_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        # Evitar que el root logger duplique los mensajes (logging.propagate=True por defecto)
        self.logger.propagate = False
        
        # Metricas
        self.metrics: dict[str, int] = defaultdict(int)
        self.start_time = datetime.now()
        
        # Log inicial
        self.info(f"Logger inicializado: {nombre}")
        self.info(f"Archivo de log: {self.log_file.name}")
    
    def debug(self, message: str, **kwargs) -> None:
        """Log nivel DEBUG"""
        self.metrics['debug'] += 1
        self.logger.debug(message, **kwargs)
    
    def info(self, message: str, **kwargs) -> None:
        """Log nivel INFO"""
        self.metrics['info'] += 1
        self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """Log nivel WARNING"""
        self.metrics['warning'] += 1
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, exc_info: bool = False, **kwargs) -> None:
        """Log nivel ERROR"""
        self.metrics['error'] += 1
        self.logger.error(message, exc_info=exc_info, **kwargs)
    
    def critical(self, message: str, exc_info: bool = False, **kwargs) -> None:
        """Log nivel CRITICAL"""
        self.metrics['critical'] += 1
        self.logger.critical(message, exc_info=exc_info, **kwargs)
    
    def section(self, title: str, width: int = 80) -> None:
        """Imprime un separador visual centrado en el log."""
        self.info(f"\n{title.center(width)}\n")
    
    def subsection(self, title: str) -> None:
        """Imprime un separador de subsección en el log."""
        self.info(f"\n--- {title} ---")
    
    def progress(self, current: int, total: int, prefix: str = "Progreso") -> None:
        """Registra el progreso actual/total como porcentaje."""
        porcentaje = (current / total) * 100 if total > 0 else 0
        self.info(f"{prefix}: {current}/{total} ({porcentaje:.1f}%)")
    
    def get_metrics_summary(self) -> str:
        """Devuelve un resumen formateado con contadores de log y tiempo transcurrido."""
        elapsed_time = datetime.now() - self.start_time
        
        summary = "\n"
        summary += "+" + "=" * 62 + "+\n"
        summary += "|" + "RESUMEN DE EJECUCION".center(62) + "|\n"
        summary += "+" + "=" * 62 + "+\n"
        summary += "\nMetricas de Logging:\n"
        summary += f"   - DEBUG:    {self.metrics.get('debug', 0)}\n"
        summary += f"   - INFO:     {self.metrics.get('info', 0)}\n"
        summary += f"   - WARNING:  {self.metrics.get('warning', 0)}\n"
        summary += f"   - ERROR:    {self.metrics.get('error', 0)}\n"
        summary += f"   - CRITICAL: {self.metrics.get('critical', 0)}\n"
        summary += f"\nTiempo Total: {elapsed_time}\n"
        summary += f"\nLog guardado en: {self.log_file}\n"
        
        return summary
    
    def finalize(self) -> None:
        """Finaliza el logger con resumen de metricas"""
        self.info(self.get_metrics_summary())
        
        # Cerrar handlers
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)


def get_logger(nombre: str, log_dir: Path, nivel: int = logging.INFO) -> ProjectLogger:
    return ProjectLogger(nombre, log_dir, nivel)


def configurar_consola_utf8() -> None:
    """Reconfigura stdout/stderr para emitir en UTF-8 con reemplazo silencioso.

    En Windows, el codepage por defecto (cp1252) levanta `UnicodeEncodeError`
    al imprimir emojis o caracteres fuera del rango latino-1, abortando
    silenciosamente líneas de log o alertas de la consola. Esta función debe
    invocarse UNA vez al entry-point del proceso (run_pipeline.py / launcher).

    Es segura/idempotente: no falla si stdout no soporta `reconfigure`
    (p. ej. cuando ha sido reemplazado por un test runner o por una pipe
    de subprocess que ya forzó la codificación).
    """
    for stream in (sys.stdout, sys.stderr):
        reconf = getattr(stream, "reconfigure", None)
        if reconf is None:
            continue
        try:
            reconf(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            # Stream ya cerrado, no-tty redirigido o readonly: ignorar.
            continue


def cleanup_old_logs(log_dir: Path, keep_days: int = 30) -> int:
    """Elimina archivos .log de log_dir cuya fecha en el nombre sea anterior a keep_days días.

    El patrón esperado en el nombre es  _YYYYMMDD_HHMMSS  (e.g. filtrado_20260322_161015.log).
    Archivos que no sigan ese patrón se dejan intactos.
    Retorna el número de archivos eliminados.
    """
    import re
    from datetime import timedelta

    cutoff = datetime.now() - timedelta(days=keep_days)
    patron = re.compile(r'_(\d{8})_\d{6}\.log$')
    eliminados = 0

    for f in Path(log_dir).glob('*.log'):
        m = patron.search(f.name)
        if not m:
            continue
        try:
            fecha = datetime.strptime(m.group(1), '%Y%m%d')  # noqa: DTZ007 — filename-based date, no timezone
            if fecha < cutoff:
                f.unlink(missing_ok=True)
                eliminados += 1
        except (ValueError, PermissionError, OSError):
            pass

    return eliminados
