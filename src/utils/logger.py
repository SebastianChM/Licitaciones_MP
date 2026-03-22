# Logger del proyecto - maneja logs de archivo y consola
# Desarrollado para el pipeline de licitaciones

import logging
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict


class ProjectLogger:
    """Logger con funcionalidades básicas necesarias para el pipeline"""
    
    def __init__(self, nombre: str, log_dir: Path, nivel: int = logging.INFO):
        """
        Inicializa el logger.
        
        Args:
            nombre: Nombre del logger (para el archivo)
            log_dir: Directorio donde guardar logs
            nivel: Nivel de logging (INFO por defecto)
        """
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
        
        # Handler para consola
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(nivel)
        console_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # Metricas
        self.metrics: dict[str, int] = defaultdict(int)
        self.start_time = datetime.now()
        
        # Log inicial
        self.info(f"Logger inicializado: {nombre}")
        self.info(f"Archivo de log: {self.log_file.name}")
    
    def debug(self, message: str, **kwargs):
        """Log nivel DEBUG"""
        self.metrics['debug'] += 1
        self.logger.debug(message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log nivel INFO"""
        self.metrics['info'] += 1
        self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log nivel WARNING"""
        self.metrics['warning'] += 1
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, exc_info: bool = False, **kwargs):
        """Log nivel ERROR"""
        self.metrics['error'] += 1
        self.logger.error(message, exc_info=exc_info, **kwargs)
    
    def critical(self, message: str, exc_info: bool = False, **kwargs):
        """Log nivel CRITICAL"""
        self.metrics['critical'] += 1
        self.logger.critical(message, exc_info=exc_info, **kwargs)
    
    def section(self, title: str, width: int = 80):
        """
        Imprime una seccion visual.
        
        Args:
            title: Titulo de la seccion
            width: Ancho de la seccion
        """
        self.info(f"\n{title.center(width)}\n")
    
    def subsection(self, title: str):
        """
        Imprime una subseccion visual.
        
        Args:
            title: Titulo de la subseccion
        """
        self.info(f"\n--- {title} ---")
    
    def progress(self, current: int, total: int, prefix: str = "Progreso"):
        """
        Imprime barra de progreso simple.
        
        Args:
            current: Valor actual
            total: Valor total
            prefix: Prefijo del mensaje
        """
        porcentaje = (current / total) * 100 if total > 0 else 0
        self.info(f"{prefix}: {current}/{total} ({porcentaje:.1f}%)")
    
    def get_metrics_summary(self) -> str:
        """
        Obtiene resumen de metricas de logging.
        
        Returns:
            str: Resumen formateado de metricas
        """
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
    
    def finalize(self):
        """Finaliza el logger con resumen de metricas"""
        self.info(self.get_metrics_summary())
        
        # Cerrar handlers
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)


def get_logger(nombre: str, log_dir: Path, nivel: int = logging.INFO) -> ProjectLogger:
    """
    Funcion auxiliar para crear un ProjectLogger.
    
    Args:
        nombre: Nombre del logger
        log_dir: Directorio de logs
        nivel: Nivel de logging
    
    Returns:
        ProjectLogger: Instancia del logger
    """
    return ProjectLogger(nombre, log_dir, nivel)


# Configuracion de logging por defecto del modulo
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
