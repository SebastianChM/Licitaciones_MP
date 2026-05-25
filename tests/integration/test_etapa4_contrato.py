from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from core.context import PipelineContext
from etapas.etapa4 import GeneradorReporte
from utils.config import Config


def test_etapa4_falla_por_input_ausente_pipeline():
    etapa = GeneradorReporte()
    ctx = PipelineContext(config=Config())
    with pytest.raises(ValueError, match="Falta artefacto 'etapa3_output'"):
        etapa.validate_inputs(ctx)

def test_etapa4_falla_por_excel_invalido():
    etapa = GeneradorReporte()
    ctx = PipelineContext(config=Config())
    ctx.flags['allow_fallback'] = True
    
    with patch('etapas.etapa4.GeneradorReporte._obtener_archivo', return_value=Path('/tmp/fake.xlsx')):
        with patch('pathlib.Path.exists', return_value=True):
            # Simulamos que pd.read_excel explote en validate
            with patch('pandas.read_excel', side_effect=Exception("Corrupt Zip Invalid File")):
                with pytest.raises(ValueError, match="no es un Excel válido o está corrupto"):
                    etapa.validate_inputs(ctx)

def test_etapa4_creacion_reporte_completa():
    etapa = GeneradorReporte()
    ctx = PipelineContext(config=Config())
    ctx.add_artifact('etapa3_output', Path('/tmp/fake.xlsx'))
    
    # Creamos DF crudo
    df = pd.DataFrame({
        "Numero Adquisición": ["LIC-1"],
        "Días para cierre": [15] # Obligatorio para separar bien sin errores raros (aunque el script sobreescribe)
    })
    
    with patch('pathlib.Path.exists', return_value=True), \
         patch('pandas.read_excel', return_value=df), \
         patch.object(GeneradorReporte, '_actualizar_tasas'), \
         patch.object(GeneradorReporte, '_generar_excel', return_value=[Path('/tmp/reporte_1.xlsx')]):
         
        result = etapa.run(ctx)
        
        assert result.success is True
        assert ctx.get_artifact('etapa4_output') == Path('/tmp/reporte_1.xlsx')
        assert result.metrics_produced['vigentes'] == 1 # Fue guardado en vigentes
        assert result.metrics_produced['vencidas'] == 0
