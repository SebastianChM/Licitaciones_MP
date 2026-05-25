from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from core.context import PipelineContext
from etapas.etapa5 import GeneradorReporteIncremental
from utils.config import Config


def test_etapa5_falla_por_input_ausente_pipeline():
    etapa = GeneradorReporteIncremental()
    ctx = PipelineContext(config=Config())
    with pytest.raises(ValueError, match="Falta artefacto 'etapa4_output'"):
        etapa.validate_inputs(ctx)

def test_etapa5_falla_por_excel_invalido():
    etapa = GeneradorReporteIncremental()
    ctx = PipelineContext(config=Config())
    ctx.flags['allow_fallback'] = True
    
    fake_file = MagicMock()
    fake_file.stat.return_value.st_mtime = 1
    fake_file.exists.return_value = True
    
    with patch('pathlib.Path.glob', return_value=[fake_file]):
        # Simulamos que pd.read_excel explote en validate
        with patch('pandas.read_excel', side_effect=Exception("Corrupt Zip Invalid File")):
            with pytest.raises(ValueError, match="corrupto o no es Excel"):
                etapa.validate_inputs(ctx)

def test_etapa5_creacion_sin_reporte_previo():
    etapa = GeneradorReporteIncremental()
    ctx = PipelineContext(config=Config())
    ctx.add_artifact('etapa4_output', Path('/tmp/fake4.xlsx'))
    
    df = pd.DataFrame({"Numero Adquisición": ["LIC-1"]})
    resultado_mock = {
        'archivo_generado': Path('/tmp/incremental_nuevo.xlsx'),
        'licitaciones_nuevas': 1,
        'licitaciones_existentes': 0,
        'licitaciones_vencidas': 0,
        'tipo': 'inicial'
    }
    
    with patch('pathlib.Path.exists', return_value=True), \
         patch('pandas.read_excel', return_value=df), \
         patch.object(GeneradorReporteIncremental, '_encontrar_reporte_incremental_anterior', return_value=None), \
         patch.object(GeneradorReporteIncremental, '_crear_reporte_inicial', return_value=resultado_mock), \
         patch.object(GeneradorReporteIncremental, '_generar_analisis_cambios', return_value={}), \
         patch.object(GeneradorReporteIncremental, '_guardar_sugerencias_pivot'):
         
        result = etapa.run(ctx)
        
        assert result.success is True
        assert ctx.get_artifact('etapa5_output') == Path('/tmp/incremental_nuevo.xlsx')
        assert result.metrics_produced['tipo'] == 'inicial'
        assert result.metrics_produced['licitaciones_nuevas'] == 1
