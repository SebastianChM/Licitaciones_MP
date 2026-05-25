from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from core.context import PipelineContext
from core.filter_profile import EquipoInfo, FilterProfile
from etapas.etapa2 import FiltradorLicitaciones
from utils.config import Config


def _perfil_vacio() -> FilterProfile:
    """Perfil vacío para tests que solo validan el contrato (no la lógica de filtrado)."""
    equipo = EquipoInfo(codigo="TEST", nombre="Test", hoja_filtros="06-Test")
    return FilterProfile(equipo=equipo, incluir={}, excluir={}, bypass=(), exclusion_dura=())

def test_etapa2_falla_por_input_ausente_pipeline():
    etapa = FiltradorLicitaciones()
    ctx = PipelineContext(config=Config())
    # Modo pipeline (por defecto), sin artefacto etapa0_output
    with pytest.raises(ValueError, match="Falta artefacto 'etapa0_output'"):
        etapa.validate_inputs(ctx)

def test_etapa2_standalone_mode_usa_fallback():
    etapa = FiltradorLicitaciones()
    ctx = PipelineContext(config=Config())
    ctx.flags['allow_fallback'] = True
    
    # Validamos que en fallback evalúe la existencia física
    with patch('pathlib.Path.exists', return_value=False):
        with pytest.raises(FileNotFoundError, match="no existe físicamente"):
            etapa.validate_inputs(ctx)

def test_etapa2_falla_por_falta_de_columnas():
    etapa = FiltradorLicitaciones()
    ctx = PipelineContext(config=Config())
    ctx.add_artifact('etapa0_output', Path('/tmp/fake.xlsx'))
    
    with patch('pathlib.Path.exists', return_value=True), \
         patch.object(FiltradorLicitaciones, '_validar_prerequisitos'):
        
        df_incompleto = pd.DataFrame({"Columna Falsa": [1, 2]})
        with patch('etapas.etapa2.leer_excel_con_header_dinamico', return_value=df_incompleto):
            result = etapa.run(ctx)
            # Result debe contener la excepcion convertida
            assert result.success is False
            assert "no posee las columnas mínimas" in result.error_message

def test_etapa2_dataframe_minimo_real():
    etapa = FiltradorLicitaciones()
    ctx = PipelineContext(config=Config())
    ctx.add_artifact('etapa0_output', Path('/tmp/fake.xlsx'))
    
    # Creamos un dataframe con todas las requeridas
    cols = [
        "Nombre Adquisición", "Descripción", "Nivel 1", "Nivel 2", "Nivel 3",
        "Genérico", "Organismo", "Tipo Adquisición", "Descripción del producto/servicio", "Numero Adquisición"
    ]
    df_valido = pd.DataFrame([["" for _ in cols]], columns=cols)
    
    with patch('pathlib.Path.exists', return_value=True), \
         patch.object(FiltradorLicitaciones, '_validar_prerequisitos'), \
         patch('etapas.etapa2.leer_excel_con_header_dinamico', return_value=df_valido), \
         patch.object(FiltradorLicitaciones, '_cargar_perfil', return_value=_perfil_vacio()), \
         patch.object(FiltradorLicitaciones, '_aplicar_filtrado', return_value=(df_valido, pd.DataFrame())), \
         patch.object(FiltradorLicitaciones, '_generar_outputs', return_value=[Path('/tmp/filtradas.xlsx')]):
         
        result = etapa.run(ctx)
        assert result.success is True
        assert ctx.get_artifact('etapa2_output') == Path('/tmp/filtradas.xlsx')
