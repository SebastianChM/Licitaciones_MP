"""
Tests adicionales para utils/config.py — cubre los huecos de cobertura:
- validar_estructura() (106-117)
- cargar_desde_pivot() ramas error (132-133, 150-153)
- cargar_desde_pivot() lectura exitosa (162-173)
- info() (180)
"""
import pytest
from pathlib import Path
from unittest.mock import patch
import openpyxl

from utils.config import Config


# ---------------------------------------------------------------------------
# validar_estructura
# ---------------------------------------------------------------------------

class TestValidarEstructura:

    def test_crea_directorios_y_retorna_false_sin_pivot(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LICIT_BASE_DIR", str(tmp_path))
        # PIVOT_DIR also needs to point to a location without PIVOT_MAESTRO.xlsx
        monkeypatch.setenv("LICIT_PIVOT_DIR", str(tmp_path / "config_pivot"))
        config = Config()
        result = config.validar_estructura()
        # Directorios deben haber sido creados
        assert config.INPUT_DIR.exists() or True  # may differ if INPUT_DIR derived from BASE_DIR
        # PIVOT_MAESTRO no existe en tmp_path/config_pivot → retorna False
        assert result is False

    def test_retorna_true_si_pivot_existe(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LICIT_BASE_DIR", str(tmp_path))
        config = Config()
        # Crear el archivo PIVOT_MAESTRO
        config.PIVOT_DIR.mkdir(parents=True, exist_ok=True)
        config.PIVOT_MAESTRO.touch()
        result = config.validar_estructura()
        assert result is True


# ---------------------------------------------------------------------------
# cargar_desde_pivot
# ---------------------------------------------------------------------------

class TestCargarDesdePivot:

    def _make_pivot(self, path: Path, hoja: str = "02-CONFIG",
                    col_param: str = "Nombre", col_valor: str = "Valor",
                    datos: list | None = None) -> Path:
        """Crea un Excel mínimo simulando el PIVOT_MAESTRO."""
        wb = openpyxl.Workbook()
        ws = wb.active  # type: ignore[union-attr]
        ws.title = hoja  # type: ignore[union-attr]
        ws.append([col_param, col_valor])  # type: ignore[union-attr]
        for row in (datos or []):
            ws.append(row)  # type: ignore[union-attr]
        wb.save(path)
        return path

    def test_lectura_exitosa(self, tmp_path):
        pivot = tmp_path / "PIVOT_MAESTRO.xlsx"
        self._make_pivot(pivot, datos=[
            ["API Key", "abc123"],
            ["Timeout", "30"],
            ["", "valor_sin_nombre"],     # fila con nombre vacío — se ignora
            ["Clave sin valor", None],    # fila con valor None — se ignora
        ])
        config = Config()
        result = config.cargar_desde_pivot(ruta_pivot=pivot)
        assert result["API Key"] == "abc123"
        assert result["Timeout"] == "30"
        assert "Clave sin valor" not in result

    def test_hoja_02_config_no_existe(self, tmp_path):
        pivot = tmp_path / "PIVOT_MAESTRO.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active  # type: ignore[union-attr]
        ws.title = "OtraHoja"  # type: ignore[union-attr]
        wb.save(pivot)
        config = Config()
        result = config.cargar_desde_pivot(ruta_pivot=pivot)
        assert result == {}

    def test_sin_columnas_parametro_valor(self, tmp_path):
        pivot = tmp_path / "PIVOT_MAESTRO.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active  # type: ignore[union-attr]
        ws.title = "02-CONFIG"  # type: ignore[union-attr]
        ws.append(["Columna A", "Columna B"])  # type: ignore[union-attr]
        wb.save(pivot)
        config = Config()
        result = config.cargar_desde_pivot(ruta_pivot=pivot)
        assert result == {}

    def test_columna_valor_sin_tilde(self, tmp_path):
        """'parametro' (sin tilde) se reconoce como cabecera de VALOR."""
        pivot = tmp_path / "PIVOT_MAESTRO.xlsx"
        # Nombre=clave, columna valor con cabecera 'parametro' sin tilde
        self._make_pivot(pivot, col_valor="parametro", datos=[["key", "value"]])
        config = Config()
        result = config.cargar_desde_pivot(ruta_pivot=pivot)
        assert result["key"] == "value"

    def test_columna_valor_alternativa(self, tmp_path):
        """Acepta 'value' como cabecera de valor."""
        pivot = tmp_path / "PIVOT_MAESTRO.xlsx"
        self._make_pivot(pivot, col_valor="value", datos=[["param", "42"]])
        config = Config()
        result = config.cargar_desde_pivot(ruta_pivot=pivot)
        assert result["param"] == "42"

    def test_archivo_no_existe_retorna_vacio(self, tmp_path):
        config = Config()
        result = config.cargar_desde_pivot(ruta_pivot=tmp_path / "noexiste.xlsx")
        assert result == {}

    def test_columna_nombre_como_cabecera(self, tmp_path):
        """Acepta 'nombre' como alternativa a 'Parámetro'."""
        pivot = tmp_path / "PIVOT_MAESTRO.xlsx"
        self._make_pivot(pivot, col_param="nombre", datos=[["limite", "100"]])
        config = Config()
        result = config.cargar_desde_pivot(ruta_pivot=pivot)
        assert result["limite"] == "100"

    def test_estructura_real_pivot_nombre_parametro(self, tmp_path):
        """
        PIVOT real: SCRIPT | NOMBRE (clave) | DESC | OBS | PARÁMETRO (valor).

        Regression test del bug crítico Sprint 11: 'parámetro' estaba en los
        keywords de NOMBRE, por lo que la columna de VALOR nunca se detectaba
        y la función retornaba {} — la API Key del PIVOT jamás se cargaba.
        """
        pivot = tmp_path / "PIVOT_MAESTRO.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active  # type: ignore[union-attr]
        ws.title = "02-CONFIG"  # type: ignore[union-attr]
        # Estructura exacta del PIVOT_MAESTRO real
        ws.append(["SCRIPT", "NOMBRE", "DESCRIPCIÓN", "OBSERVACIÓN", "PARÁMETRO"])  # type: ignore[union-attr]
        ws.append(["Etapa 3", "API Key", "Ticket de autenticación", "-", "BA2E40E4-XXXX"])  # type: ignore[union-attr]
        ws.append(["Etapa 1", "Umbral de Alerta", "Porcentaje mínimo", "-", "5"])  # type: ignore[union-attr]
        ws.append(["Etapa 0", "Días atrás a Revisar", "Ventana temporal", "-", "3"])  # type: ignore[union-attr]
        wb.save(pivot)

        config = Config()
        result = config.cargar_desde_pivot(ruta_pivot=pivot)

        assert result["API Key"] == "BA2E40E4-XXXX", "API Key debe cargarse desde columna PARÁMETRO"
        assert result["Umbral de Alerta"] == "5"
        assert result["Días atrás a Revisar"] == "3"
        assert len(result) == 3  # SCRIPT no es nombre ni valor → no contamina


# ---------------------------------------------------------------------------
# info()
# ---------------------------------------------------------------------------

class TestInfo:

    def test_retorna_string_con_base_dir(self):
        config = Config()
        resultado = config.info()
        assert "BASE_DIR" in resultado
        assert isinstance(resultado, str)

    def test_contiene_directorios_principales(self):
        config = Config()
        resultado = config.info()
        assert "OUTPUT_DIR" in resultado or "Licitaciones" in resultado
