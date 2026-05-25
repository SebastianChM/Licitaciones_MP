"""Tests para EnriquecedorAPI._cargar_api_key().

Verifica la lógica de prioridad:
  1. Si config.mercado_publico_ticket está definido → retorna ese valor
  2. Si no → intenta cargar desde PIVOT_MAESTRO (vía config.cargar_desde_pivot())
  3. Si PIVOT falla → retorna cadena vacía

Nota: Config es un modelo pydantic que bloquea patch.object en instancias para
atributos que no son campos. Se parchea a nivel de clase para los métodos.
"""
from unittest.mock import patch

import pytest

_PATCH_CARGAR_PIVOT = 'utils.config.Config.cargar_desde_pivot'


@pytest.fixture
def enriquecedor(config, logger_mock):
    """EnriquecedorAPI con contexto y logger mockeados."""
    from core.context import PipelineContext
    from etapas.etapa3 import EnriquecedorAPI
    stage = EnriquecedorAPI()
    ctx = PipelineContext(config=config)
    stage._context = ctx
    stage._logger = logger_mock
    return stage


@pytest.mark.unit
class TestCargarApiKey:

    def test_usa_env_var_si_esta_definida(self, enriquecedor):
        enriquecedor.config.mercado_publico_ticket = "TOKEN_ENV_123"
        key = enriquecedor._cargar_api_key()
        assert key == "TOKEN_ENV_123"

    def test_env_var_loggea_mensaje_ok(self, enriquecedor, logger_mock):
        enriquecedor.config.mercado_publico_ticket = "TOKEN_ENV_123"
        enriquecedor._cargar_api_key()
        calls_text = " ".join(str(c) for c in logger_mock.info.call_args_list)
        assert "variable de entorno" in calls_text.lower()

    def test_fallback_a_pivot_cuando_env_vacia(self, enriquecedor):
        enriquecedor.config.mercado_publico_ticket = ""
        with patch(_PATCH_CARGAR_PIVOT, return_value={'API Key': 'TOKEN_PIVOT_456'}):
            key = enriquecedor._cargar_api_key()
        assert key == "TOKEN_PIVOT_456"

    def test_fallback_pivot_loggea_deprecation(self, enriquecedor, logger_mock):
        enriquecedor.config.mercado_publico_ticket = ""
        with patch(_PATCH_CARGAR_PIVOT, return_value={'API Key': 'TOKEN_PIVOT_456'}):
            enriquecedor._cargar_api_key()
        calls_text = " ".join(str(c) for c in logger_mock.info.call_args_list)
        assert "migrar" in calls_text.lower() or "pivot" in calls_text.lower()

    def test_fallback_pivot_sin_api_key_retorna_vacio(self, enriquecedor):
        enriquecedor.config.mercado_publico_ticket = ""
        with patch(_PATCH_CARGAR_PIVOT, return_value={}):
            key = enriquecedor._cargar_api_key()
        assert key == ""

    def test_pivot_lanza_excepcion_retorna_vacio(self, enriquecedor):
        enriquecedor.config.mercado_publico_ticket = ""
        with patch(_PATCH_CARGAR_PIVOT, side_effect=Exception("Excel no encontrado")):
            key = enriquecedor._cargar_api_key()
        assert key == ""

    def test_pivot_excepcion_loggea_warning(self, enriquecedor, logger_mock):
        enriquecedor.config.mercado_publico_ticket = ""
        with patch(_PATCH_CARGAR_PIVOT, side_effect=Exception("Excel no encontrado")):
            enriquecedor._cargar_api_key()
        logger_mock.warning.assert_called_once()

    def test_env_var_none_no_usa_env(self, enriquecedor):
        enriquecedor.config.mercado_publico_ticket = None
        with patch(_PATCH_CARGAR_PIVOT, return_value={'API Key': 'DESDE_PIVOT'}):
            key = enriquecedor._cargar_api_key()
        assert key == "DESDE_PIVOT"
