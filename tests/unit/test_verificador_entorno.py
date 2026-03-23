"""
Tests para src/utils/verificador_entorno.py

Cubre: ResultadoCheck, VerificadorEntorno (todos los checks individuales
y los métodos públicos verificar_todo / hay_errores_criticos).
"""
import pytest
from pathlib import Path

from utils.verificador_entorno import VerificadorEntorno, ResultadoCheck


# ---------------------------------------------------------------------------
# ResultadoCheck — dataclass inmutable
# ---------------------------------------------------------------------------

class TestResultadoCheck:

    def test_campos_requeridos(self):
        r = ResultadoCheck(nombre="X", ok=True, mensaje="OK")
        assert r.nombre == "X"
        assert r.ok is True
        assert r.mensaje == "OK"
        assert r.critico is True  # default

    def test_critico_falso(self):
        r = ResultadoCheck(nombre="X", ok=False, mensaje="warn", critico=False)
        assert r.critico is False

    def test_es_inmutable(self):
        r = ResultadoCheck(nombre="X", ok=True, mensaje="OK")
        with pytest.raises((AttributeError, TypeError)):
            r.ok = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def base_completa(tmp_path):
    """Directorio con TODOS los archivos requeridos presentes."""
    (tmp_path / ".venv").mkdir()
    pivot_dir = tmp_path / "config_pivot"
    pivot_dir.mkdir()
    (pivot_dir / "PIVOT_MAESTRO.xlsx").touch()
    (tmp_path / ".env").write_text("LICIT_ENV=test")
    input_dir = tmp_path / "data" / "1. INPUT"
    input_dir.mkdir(parents=True)
    (input_dir / "Licitacion_Publicada.xlsx").touch()
    return tmp_path


@pytest.fixture
def base_minima(tmp_path):
    """Solo los archivos críticos (.venv + PIVOT) presentes."""
    (tmp_path / ".venv").mkdir()
    pivot_dir = tmp_path / "config_pivot"
    pivot_dir.mkdir()
    (pivot_dir / "PIVOT_MAESTRO.xlsx").touch()
    return tmp_path


@pytest.fixture
def base_vacia(tmp_path):
    """Ningún archivo presente."""
    return tmp_path


# ---------------------------------------------------------------------------
# verificar_todo — entorno completo
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestVerificarTodoCompleto:

    def test_retorna_cuatro_checks(self, base_completa):
        v = VerificadorEntorno(base_completa)
        assert len(v.verificar_todo()) == 4

    def test_todos_ok_cuando_entorno_completo(self, base_completa):
        v = VerificadorEntorno(base_completa)
        assert all(r.ok for r in v.verificar_todo())

    def test_no_hay_errores_criticos(self, base_completa):
        v = VerificadorEntorno(base_completa)
        assert v.hay_errores_criticos(v.verificar_todo()) is False


# ---------------------------------------------------------------------------
# _check_venv
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCheckVenv:

    def test_ok_cuando_existe(self, tmp_path):
        (tmp_path / ".venv").mkdir()
        r = VerificadorEntorno(tmp_path)._check_venv()
        assert r.ok is True
        assert r.critico is True

    def test_falla_cuando_no_existe(self, tmp_path):
        r = VerificadorEntorno(tmp_path)._check_venv()
        assert r.ok is False
        assert "python -m venv" in r.mensaje

    def test_nombre_descriptivo(self, tmp_path):
        r = VerificadorEntorno(tmp_path)._check_venv()
        assert "venv" in r.nombre.lower()


# ---------------------------------------------------------------------------
# _check_pivot
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCheckPivot:

    def test_ok_cuando_existe(self, tmp_path):
        d = tmp_path / "config_pivot"
        d.mkdir()
        (d / "PIVOT_MAESTRO.xlsx").touch()
        r = VerificadorEntorno(tmp_path)._check_pivot()
        assert r.ok is True
        assert r.critico is True

    def test_falla_cuando_no_existe(self, tmp_path):
        r = VerificadorEntorno(tmp_path)._check_pivot()
        assert r.ok is False
        assert "config_pivot" in r.mensaje

    def test_falla_cuando_carpeta_existe_pero_sin_archivo(self, tmp_path):
        (tmp_path / "config_pivot").mkdir()
        r = VerificadorEntorno(tmp_path)._check_pivot()
        assert r.ok is False


# ---------------------------------------------------------------------------
# _check_env
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCheckEnv:

    def test_ok_cuando_existe(self, tmp_path):
        (tmp_path / ".env").write_text("LICIT_ENV=test")
        r = VerificadorEntorno(tmp_path)._check_env()
        assert r.ok is True
        assert r.critico is False  # no bloqueante

    def test_falla_cuando_no_existe(self, tmp_path):
        r = VerificadorEntorno(tmp_path)._check_env()
        assert r.ok is False
        assert ".env.example" in r.mensaje

    def test_no_critico(self, tmp_path):
        r = VerificadorEntorno(tmp_path)._check_env()
        assert r.critico is False


# ---------------------------------------------------------------------------
# _check_input
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCheckInput:

    def test_ok_cuando_existe(self, tmp_path):
        d = tmp_path / "data" / "1. INPUT"
        d.mkdir(parents=True)
        (d / "Licitacion_Publicada.xlsx").touch()
        r = VerificadorEntorno(tmp_path)._check_input()
        assert r.ok is True
        assert r.critico is False

    def test_falla_pero_no_critico(self, tmp_path):
        r = VerificadorEntorno(tmp_path)._check_input()
        assert r.ok is False
        assert r.critico is False
        assert "Etapa 0" in r.mensaje


# ---------------------------------------------------------------------------
# hay_errores_criticos
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestHayErroresCriticos:

    def test_true_cuando_critico_falla(self, base_minima):
        """Eliminar el PIVOT debe provocar error crítico."""
        pivot = base_minima / "config_pivot" / "PIVOT_MAESTRO.xlsx"
        pivot.unlink()
        v = VerificadorEntorno(base_minima)
        assert v.hay_errores_criticos(v.verificar_todo()) is True

    def test_false_cuando_solo_falla_no_critico(self, base_minima):
        """Con .venv y PIVOT presentes pero sin .env, no debe haber error crítico."""
        v = VerificadorEntorno(base_minima)
        assert v.hay_errores_criticos(v.verificar_todo()) is False

    def test_false_con_lista_vacia(self, tmp_path):
        v = VerificadorEntorno(tmp_path)
        assert v.hay_errores_criticos([]) is False

    def test_true_si_venv_falta(self, tmp_path):
        pivot_dir = tmp_path / "config_pivot"
        pivot_dir.mkdir()
        (pivot_dir / "PIVOT_MAESTRO.xlsx").touch()
        v = VerificadorEntorno(tmp_path)
        # .venv falta → critico
        assert v.hay_errores_criticos(v.verificar_todo()) is True
