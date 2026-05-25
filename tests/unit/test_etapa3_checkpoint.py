import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from core.context import PipelineContext
from etapas.etapa3 import EnriquecedorAPI
from utils.config import Config


@pytest.fixture
def clean_ctx(tmp_path):
    ctx = PipelineContext(config=Config())
    fake_input = tmp_path / 'fake_input.xlsx'
    df = pd.DataFrame({"Numero Adquisición": ["LIC-1", "LIC-2", "LIC-3"]})
    df.to_excel(fake_input, index=False)
    ctx.add_artifact('etapa2_output', fake_input)
    
    # Redirigimos BASE_DIR para que use tmp_path
    ctx.config.BASE_DIR = tmp_path
    ctx.config.ENRIQUECIDO_DIR = tmp_path
    return ctx, tmp_path

def test_etapa3_crea_checkpoint_y_luego_lo_borra(clean_ctx):
    ctx, tmp_path = clean_ctx
    etapa = EnriquecedorAPI()
    
    # Configuramos para evitar que se demore
    etapa.delay_segundos = 0
    etapa.api_base_url = "dummy"
    etapa.api_key = "dummy"
    
    def mock_consultar(codigo):
        return {'_api_disponible': True, 'MontoEstimado': 100}
        
    with patch.object(EnriquecedorAPI, '_cargar_api_key', return_value="FAKE"), \
         patch.object(etapa, '_health_check_api', return_value=True), \
         patch.object(EnriquecedorAPI, '_consultar_api', side_effect=mock_consultar):
         
         result = etapa.run(ctx)
         
         assert result.success is True
         assert "etapa3_output" in ctx.artifacts
         # Checkpoint debe estar borrado ya que terminó con éxito
         checkpoints = list((tmp_path / 'temp' / 'checkpoints').glob("*.jsonl"))
         assert len(checkpoints) == 0

def test_etapa3_reanuda_exito_sin_reprocesar(clean_ctx):
    ctx, tmp_path = clean_ctx
    etapa = EnriquecedorAPI()
    etapa.delay_segundos = 0
    
    df = pd.DataFrame({"Numero Adquisición": ["LIC-1", "LIC-2", "LIC-3"]})
    hash_val = etapa._get_dataset_hash(df, "Numero Adquisición")
    
    # Creamos un checkpoint artificial donde LIC-1 y LIC-2 ya están listos
    cp_dir = tmp_path / 'temp' / 'checkpoints'
    cp_dir.mkdir(parents=True, exist_ok=True)
    cp_file = cp_dir / f"e3_checkpoint_{hash_val}.jsonl"
    
    # Guardamos estado previo para 1 y 2
    with cp_file.open('w', encoding='utf-8') as f:
        f.write(json.dumps({'codigo': 'LIC-1', 'status': 'success', 'data': {'_api_disponible': True, 'Monto': 10}}) + '\n')
        f.write(json.dumps({'codigo': 'LIC-2', 'status': 'success', 'data': {'_api_disponible': True, 'Monto': 20}}) + '\n')
        f.write(json.dumps({'codigo': 'LIC-1_duplicado_dummy', 'status': 'error', 'data': {}}) + '\n') # Corrupto logicamente pero procesable json
        
    mock_api_call = MagicMock(return_value={'_api_disponible': True, 'Monto': 30})
    
    with patch.object(EnriquecedorAPI, '_cargar_api_key', return_value="FAKE"), \
         patch.object(etapa, '_health_check_api', return_value=True), \
         patch.object(EnriquecedorAPI, '_consultar_api', mock_api_call):
         
         result = etapa.run(ctx)
         assert result.success is True
         
         # LIC-3 fue la unica que llamó a la API porque 1 y 2 estaban en checkpoint exitoso
         assert mock_api_call.call_count == 1
         assert mock_api_call.call_args[0][0] == 'LIC-3'
         
         # Como completó exito, el checkpoint se elimina
         assert not cp_file.exists()

def test_etapa3_mismatch_input_hash_crea_diferente_checkpoint(clean_ctx):
    ctx, tmp_path = clean_ctx
    etapa = EnriquecedorAPI()
    etapa.delay_segundos = 0
    
    # Creamos un checkpoint para un hash viejo
    cp_dir = tmp_path / 'temp' / 'checkpoints'
    cp_dir.mkdir(parents=True, exist_ok=True)
    cp_file = cp_dir / "e3_checkpoint_viejo_xyz.jsonl"
    with cp_file.open('w', encoding='utf-8') as f:
        f.write(json.dumps({'codigo': 'LIC-1', 'status': 'success', 'data': {'_api_disponible': True}}) + '\n')
        
    def mock_consultar(codigo):
        return {'_api_disponible': True}
        
    with patch.object(EnriquecedorAPI, '_cargar_api_key', return_value="FAKE"), \
         patch.object(etapa, '_health_check_api', return_value=True), \
         patch.object(EnriquecedorAPI, '_consultar_api', side_effect=mock_consultar) as m_consultar:
         
         etapa.run(ctx)
         
         # Debería haber procesado todas (3 llamadas) porque el hash viejo no aplica al input nuevo
         assert m_consultar.call_count == 3
