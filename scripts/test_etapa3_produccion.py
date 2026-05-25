"""
Prueba manual de la Etapa 3 con datos reales de producción.

Uso (desde la raíz del proyecto):
    python scripts/test_etapa3_produccion.py

Prerequisito: debe existir al menos un archivo en data/2. OUTPUT/3. FILTRADO/
"""
from pathlib import Path
import sys

# Asegurar que src/ esté en el path cuando se ejecuta desde la raíz
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.config import Config
from core.context import PipelineContext
from etapas.etapa3 import EnriquecedorAPI


def main() -> None:
    config = Config()
    context = PipelineContext(config=config)
    context.flags['allow_fallback'] = True

    filtrados = sorted(
        config.FILTRADO_DIR.glob('Licitaciones_Filtradas_*.xlsx'),
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )
    if not filtrados:
        print('ERROR: No hay archivo filtrado disponible', file=sys.stderr)
        sys.exit(1)

    archivo = filtrados[0]
    print(f'Usando archivo: {archivo.name}')
    context.add_artifact('etapa2_output', archivo)

    etapa = EnriquecedorAPI()
    resultado = etapa.run(context)

    print(f'\n{"="*60}')
    print(f'success         = {resultado.success}')
    if resultado.files_produced:
        print(f'archivo salida  = {resultado.files_produced[0].name}')
    if resultado.metrics_produced:
        m = resultado.metrics_produced
        total = m.get('total_registros', 0)
        ok    = m.get('enriquecidos_ok', 0)
        fail  = m.get('errores_registro', 0)
        print(f'total           = {total}')
        print(f'enriquecidos_ok = {ok}  ({ok/total*100:.1f}%)' if total else 'total = 0')
        print(f'sin_respuesta   = {fail}')
    if resultado.error_message:
        print(f'error           = {resultado.error_message}')
    print('='*60)


if __name__ == "__main__":
    main()
