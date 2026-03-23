"""Entrypoint: Generador de Reportes Incremental

Ejecuta la Etapa 5 del pipeline de forma standalone, preservando el trabajo
manual del equipo (colores, anotaciones, filtros) y agregando solo las
licitaciones nuevas.

Uso:
    python src/reporte_incremental.py
    python src/reporte_incremental.py --standalone
"""

import sys
import argparse
from pathlib import Path

# Ajustar sys.path para ejecucion standalone desde raiz o desde src/
_SRC = Path(__file__).parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from utils.config import Config
from utils.logger import ProjectLogger
from core.context import PipelineContext
from etapas.etapa5 import GeneradorReporteIncremental as _Etapa5GeneradorReporte


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Genera reporte incremental preservando trabajo manual del equipo'
    )
    parser.add_argument(
        '--standalone',
        action='store_true',
        default=True,
        help='Permitir leer archivos del disco sin depender de una etapa anterior (por defecto: True)'
    )
    args = parser.parse_args()

    config = Config()
    logger = ProjectLogger('reporte_incremental_entry', config.LOG_DIR)

    try:
        logger.section("REPORTE INCREMENTAL - ENTRYPOINT STANDALONE", 80)
        logger.info("Delegando en GeneradorReporteIncremental (Etapa 5)...")

        context = PipelineContext(config=config)
        context.flags['allow_fallback'] = args.standalone

        etapa5 = _Etapa5GeneradorReporte()
        resultado = etapa5.run(context)

        if resultado.success:
            detalles = resultado.custom_data.get('detalles', {})
            logger.info("\n[OK] REPORTE INCREMENTAL GENERADO EXITOSAMENTE")
            logger.info(f"   * Tipo: {detalles.get('tipo', 'N/A')}")
            logger.info(f"   * Nuevas: {detalles.get('licitaciones_nuevas', 0)}")
            logger.info(f"   * Existentes actualizadas: {detalles.get('licitaciones_existentes', 0)}")
            logger.info(f"   * Vencidas movidas: {detalles.get('licitaciones_vencidas', 0)}")
            if resultado.files_produced:
                logger.info(f"   * Archivo: {resultado.files_produced[0].name}")
            return 0

        logger.error(f"[X] Error en Etapa 5: {resultado.error_message}")
        return 1

    except Exception as e:
        logger.error(f"[X] Error critico: {e}", exc_info=True)
        return 1
    finally:
        logger.finalize()


if __name__ == "__main__":
    sys.exit(main())
