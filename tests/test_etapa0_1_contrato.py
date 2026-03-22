from core.context import PipelineContext
from utils.config import Config
from etapas.etapa0 import Etapa0Descarga
from etapas.etapa1 import AuditorTaxonomia
from unittest.mock import patch, MagicMock
from pathlib import Path
import pytest

def test_etapa0_registra_artefacto():
    etapa = Etapa0Descarga()
    ctx = PipelineContext(config=Config())
    # Mockear dependencias duras
    with patch.object(Etapa0Descarga, '_validar_conexion', return_value=None), \
         patch.object(Etapa0Descarga, '_descargar_archivo', return_value=Path("/tmp/descarga.xlsx")), \
         patch.object(Etapa0Descarga, '_mover_a_input', return_value=Path("/tmp/final.xlsx")), \
         patch.object(Etapa0Descarga, '_validar_archivo', return_value=None):
        
        result = etapa.run(ctx)
        
        assert result.success is True
        assert ctx.get_artifact('etapa0_output') == Path("/tmp/final.xlsx")

def test_etapa1_consume_contexto():
    etapa = AuditorTaxonomia()
    ctx = PipelineContext(config=Config())
    fake_path = Path("/tmp/final.xlsx")
    ctx.add_artifact('etapa0_output', fake_path)
    
    with patch.object(AuditorTaxonomia, '_validar_prerequisitos') as mock_validar, \
         patch.object(AuditorTaxonomia, '_cargar_datos', return_value=(MagicMock(), MagicMock())), \
         patch.object(AuditorTaxonomia, '_procesar_campos', return_value={'nuevos': [], 'similares': []}):
        
        result = etapa.run(ctx)
        
        assert result.success is True
        mock_validar.assert_called_once_with(fake_path)

def test_etapa1_fallback_standalone():
    etapa = AuditorTaxonomia()
    cfg = Config()
    ctx = PipelineContext(config=cfg)
    
    with patch('pathlib.Path.exists', return_value=True), \
         patch.object(AuditorTaxonomia, '_validar_prerequisitos') as mock_validar, \
         patch.object(AuditorTaxonomia, '_cargar_datos', return_value=(MagicMock(), MagicMock())), \
         patch.object(AuditorTaxonomia, '_procesar_campos', return_value={'nuevos': [], 'similares': []}):
        
        result = etapa.run(ctx)
        
        assert result.success is True
        # Debe haber llamado a _validar con el LICITACIONES_MP fallback original
        mock_validar.assert_called_once_with(cfg.LICITACIONES_MP)

def test_etapa1_falla_si_no_hay_input():
    etapa = AuditorTaxonomia()
    cfg = Config()
    ctx = PipelineContext(config=cfg)
    
    with patch('pathlib.Path.exists', return_value=False):
        assert etapa.validate_inputs(ctx) is False

