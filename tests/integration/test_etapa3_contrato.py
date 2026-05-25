from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from core.context import PipelineContext
from etapas.etapa3 import EnriquecedorAPI
from utils.config import Config


def test_etapa3_falla_por_input_ausente_pipeline():
    etapa = EnriquecedorAPI()
    ctx = PipelineContext(config=Config())
    # Modo pipeline por defecto
    with pytest.raises(ValueError, match="Falta artefacto 'etapa2_output'"):
        etapa.validate_inputs(ctx)

def test_etapa3_standalone_mode_usa_fallback():
    etapa = EnriquecedorAPI()
    ctx = PipelineContext(config=Config())
    ctx.flags['allow_fallback'] = True
    
    with patch('etapas.etapa3.EnriquecedorAPI._obtener_archivo_fallback', return_value=Path('/tmp/fake.xlsx')):
        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(FileNotFoundError, match="no existe físicamente"):
                etapa.validate_inputs(ctx)

def test_etapa3_falla_por_falta_de_columnas():
    # Enriquecedor necesita Numero Adquisición
    etapa = EnriquecedorAPI()
    ctx = PipelineContext(config=Config())
    fake_input = Path('/tmp/etapa2.xlsx')
    ctx.add_artifact('etapa2_output', fake_input)
    
    df_sin_codigo = pd.DataFrame({"Otra Columna": [1, 2]})
    with patch('pathlib.Path.exists', return_value=True):
        with patch('pandas.read_excel', return_value=df_sin_codigo), \
             patch.object(EnriquecedorAPI, '_cargar_api_key', return_value="FAKE"):
            result = etapa.run(ctx)
            assert result.success is False
            assert "No se encontró columna" in result.error_message

def test_etapa3_flujo_exitoso_y_errores_por_registro():
    etapa = EnriquecedorAPI()
    ctx = PipelineContext(config=Config())
    fake_input = Path('/tmp/etapa2.xlsx')
    ctx.add_artifact('etapa2_output', fake_input)
    
    df_test = pd.DataFrame({
        "Numero Adquisición": ["LIC-1", "LIC-2"] # Dos licitaciones a simular
    })
    
    def _mock_consultar_api(codigo):
        if codigo == "LIC-1":
            return {'MontoEstimado': 100, '_api_disponible': True}
        return {'_api_error': 'Error de conexion', '_api_disponible': False}
        
    with patch('pathlib.Path.exists', return_value=True), \
         patch.object(EnriquecedorAPI, '_cargar_licitaciones', return_value=df_test), \
         patch.object(EnriquecedorAPI, '_cargar_api_key', return_value="FAKE_KEY"), \
         patch.object(EnriquecedorAPI, '_health_check_api', return_value=True), \
         patch.object(EnriquecedorAPI, '_consultar_api', side_effect=_mock_consultar_api), \
         patch.object(EnriquecedorAPI, '_generar_outputs', return_value=[Path('/tmp/enriquecida.xlsx')]):
         
         result = etapa.run(ctx)
         
         # Debe triunfar porque es robusto a fallos por fila
         assert result.success is True
         assert ctx.get_artifact('etapa3_output') == Path('/tmp/enriquecida.xlsx')
         
         # Los stats deben estar separados
         assert result.metrics_produced['total_registros'] == 2
         assert result.metrics_produced['enriquecidos_ok'] == 1
         assert result.metrics_produced['errores_registro'] == 1
         assert result.metrics_produced['errores_fatales_etapa'] == 0

def test_etapa3_falla_fatal_de_etapa():
    etapa = EnriquecedorAPI()
    ctx = PipelineContext(config=Config())
    fake_input = Path('/tmp/etapa2.xlsx')
    ctx.add_artifact('etapa2_output', fake_input)
    
    with patch('pathlib.Path.exists', return_value=True), \
         patch.object(EnriquecedorAPI, '_cargar_licitaciones', side_effect=Exception("Base de datos corrupta")):
         
         result = etapa.run(ctx)
         assert result.success is False
         # Contabiliza error crítico
         assert result.metrics_produced['errores_fatales_etapa'] == 1
         assert "Base de datos corrupta" in result.error_message
