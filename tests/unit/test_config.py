from utils.config import Config


def test_config_loads_env_vars(monkeypatch):
    """Prueba que la configuración carga correctamente las variables de entorno"""
    monkeypatch.setenv("LICIT_CMF_API_KEY", "test_api_key_123")
    monkeypatch.setenv("LICIT_MERCADO_PUBLICO_TICKET", "test_ticket_456")
    monkeypatch.setenv("LICIT_ENV", "testing")
    
    config = Config()
    
    assert config.cmf_api_key == "test_api_key_123"
    assert config.mercado_publico_ticket == "test_ticket_456"
    assert config.env == "testing"
    
def test_config_has_required_dirs():
    """Prueba que la configuración instancie las rutas correctamente basadas en BASE_DIR"""
    config = Config()
    assert config.BASE_DIR.name == "Licitaciones_MP"
    assert config.OUTPUT_DIR.name == "2. OUTPUT"
    assert config.INPUT_DIR.name == "1. INPUT"
    assert config.PIVOT_DIR.name == "config_pivot"
