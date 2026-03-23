"""Tests unitarios para la lógica de filtrado vectorizado de Etapa 2.

Testean directamente los métodos _preparar_campos_normalizados,
_aplicar_inclusion, _aplicar_exclusion, _aplicar_bypass sin tocar
disco ni PIVOT_MAESTRO.

Ejecutar con: pytest tests/unit/test_filtrado.py -v
"""

import pytest
import pandas as pd
from unittest.mock import MagicMock
from etapas.etapa2 import FiltradorLicitaciones


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _etapa_con_filtros(filtros: dict) -> FiltradorLicitaciones:
    """Instancia FiltradorLicitaciones con filtros inyectados y logger mockeado."""
    etapa = FiltradorLicitaciones()
    etapa.filtros = filtros
    # Inyectamos un logger mock para tests que no necesitan pipeline completo
    etapa._logger = MagicMock()
    return etapa


# ---------------------------------------------------------------------------
# _preparar_campos_normalizados
# ---------------------------------------------------------------------------

class TestPrepararCamposNormalizados:
    def test_crea_columnas_norm(self, df_licitaciones_minimo):
        etapa = _etapa_con_filtros({})
        df = etapa._preparar_campos_normalizados(df_licitaciones_minimo.copy())
        assert "Nombre Adquisición (norm)" in df.columns
        assert "Nivel 1 (norm)" in df.columns

    def test_columnas_norm_en_mayusculas(self, df_licitaciones_minimo):
        etapa = _etapa_con_filtros({})
        df = etapa._preparar_campos_normalizados(df_licitaciones_minimo.copy())
        for val in df["Nombre Adquisición (norm)"]:
            assert val == val.upper(), f"Se esperaba mayúsculas: {val!r}"

    def test_no_modifica_columnas_originales(self, df_licitaciones_minimo):
        etapa = _etapa_con_filtros({})
        original = df_licitaciones_minimo["Nombre Adquisición"].tolist()
        df = etapa._preparar_campos_normalizados(df_licitaciones_minimo.copy())
        assert df["Nombre Adquisición"].tolist() == original


# ---------------------------------------------------------------------------
# _aplicar_inclusion
# ---------------------------------------------------------------------------

class TestAplicarInclusion:
    def test_incluye_fila_con_palabra_en_nombre(self, df_licitaciones_minimo, filtros_incluir_ti):
        etapa = _etapa_con_filtros(filtros_incluir_ti)
        df = etapa._preparar_campos_normalizados(df_licitaciones_minimo.copy())
        result = etapa._aplicar_inclusion(df)
        # "Consultoría TI" y "computadores" (tecnología) deben estar
        assert len(result) >= 1

    def test_incluye_por_nivel1(self, df_licitaciones_minimo):
        filtros = {
            "incluir": {"nombre": [], "nivel1": ["servicios"], "nivel2": [], "nivel3": []},
            "excluir": {k: [] for k in ["nombre","nivel1","nivel2","nivel3","generico","componente","organismo","valor"]},
            "bypass": [],
        }
        etapa = _etapa_con_filtros(filtros)
        df = etapa._preparar_campos_normalizados(df_licitaciones_minimo.copy())
        result = etapa._aplicar_inclusion(df)
        # La primera fila tiene Nivel 1 = "Servicios"
        assert any("Consultoría" in n for n in result["Nombre Adquisición"].tolist())

    def test_sin_palabras_inclusión_retorna_vacio(self, df_licitaciones_minimo):
        filtros = {
            "incluir": {"nombre": [], "nivel1": [], "nivel2": [], "nivel3": []},
            "excluir": {k: [] for k in ["nombre","nivel1","nivel2","nivel3","generico","componente","organismo","valor"]},
            "bypass": [],
        }
        etapa = _etapa_con_filtros(filtros)
        df = etapa._preparar_campos_normalizados(df_licitaciones_minimo.copy())
        result = etapa._aplicar_inclusion(df)
        assert len(result) == 0

    def test_palabra_con_acento_se_normaliza(self, df_un_registro):
        # "consultoria" (sin tilde) debe coincidir con "Consultoría" normalizado
        filtros = {
            "incluir": {"nombre": ["consultoria"], "nivel1": [], "nivel2": [], "nivel3": []},
            "excluir": {k: [] for k in ["nombre","nivel1","nivel2","nivel3","generico","componente","organismo","valor"]},
            "bypass": [],
        }
        etapa = _etapa_con_filtros(filtros)
        df = etapa._preparar_campos_normalizados(df_un_registro.copy())
        result = etapa._aplicar_inclusion(df)
        assert len(result) == 1

    def test_dataframe_vacio_retorna_vacio(self, filtros_incluir_ti):
        etapa = _etapa_con_filtros(filtros_incluir_ti)
        df_vacio = pd.DataFrame(columns=[
            "Nombre Adquisición", "Nombre Adquisición (norm)",
            "Nivel 1", "Nivel 1 (norm)", "Nivel 2", "Nivel 2 (norm)", "Nivel 3", "Nivel 3 (norm)",
        ])
        result = etapa._aplicar_inclusion(df_vacio)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# _aplicar_exclusion
# ---------------------------------------------------------------------------

class TestAplicarExclusion:
    def test_excluye_fila_con_palabra_en_nombre(self, df_licitaciones_minimo, filtros_excluir_construccion):
        etapa = _etapa_con_filtros(filtros_excluir_construccion)
        df = etapa._preparar_campos_normalizados(df_licitaciones_minimo.copy())
        excluidas = etapa._aplicar_exclusion(df)
        nombres = excluidas["Nombre Adquisición"].tolist()
        assert any("Construcción" in n for n in nombres)

    def test_no_excluye_lo_que_no_corresponde(self, df_un_registro, filtros_excluir_construccion):
        etapa = _etapa_con_filtros(filtros_excluir_construccion)
        df = etapa._preparar_campos_normalizados(df_un_registro.copy())
        excluidas = etapa._aplicar_exclusion(df)
        # "Consultoría en gestión de proyectos TI" no tiene "construccion"
        assert len(excluidas) == 0

    def test_excluye_por_nivel1(self, df_licitaciones_minimo):
        filtros = {
            "incluir": {"nombre": [], "nivel1": [], "nivel2": [], "nivel3": []},
            "excluir": {
                "nombre": [], "nivel1": ["obras"], "nivel2": [], "nivel3": [],
                "generico": [], "componente": [], "organismo": [], "valor": [],
            },
            "bypass": [],
        }
        etapa = _etapa_con_filtros(filtros)
        df = etapa._preparar_campos_normalizados(df_licitaciones_minimo.copy())
        excluidas = etapa._aplicar_exclusion(df)
        # La segunda fila tiene Nivel 1 = "Obras"
        assert any("Construcción" in n for n in excluidas["Nombre Adquisición"].tolist())

    def test_filtros_excluir_vacios_no_excluye_nada(self, df_licitaciones_minimo):
        filtros = {
            "incluir": {"nombre": [], "nivel1": [], "nivel2": [], "nivel3": []},
            "excluir": {k: [] for k in ["nombre","nivel1","nivel2","nivel3","generico","componente","organismo","valor"]},
            "bypass": [],
        }
        etapa = _etapa_con_filtros(filtros)
        df = etapa._preparar_campos_normalizados(df_licitaciones_minimo.copy())
        excluidas = etapa._aplicar_exclusion(df)
        assert len(excluidas) == 0


# ---------------------------------------------------------------------------
# _aplicar_bypass
# ---------------------------------------------------------------------------

class TestAplicarBypass:
    def test_bypass_recupera_excluidas_con_palabra(self, filtros_excluir_construccion):
        """Un registro excluido por 'construccion' se recupera si tiene 'corfo' en organismo."""
        etapa = _etapa_con_filtros(filtros_excluir_construccion)
        # Fila que activa exclusión (construccion) Y bypass (corfo)
        df_mixto = pd.DataFrame([
            ["TEST-001", "Construcción instalaciones CORFO", "Obra",
             "Obras", "Construcción", "Civil", "Infraestructura",
             "CORFO", "Licitación Pública", "Obras civiles", "5000000", "CLP"],
        ], columns=[
            "Numero Adquisición", "Nombre Adquisición", "Descripción",
            "Nivel 1", "Nivel 2", "Nivel 3", "Genérico",
            "Organismo", "Tipo Adquisición", "Descripción del producto/servicio",
            "Monto", "Moneda",
        ])
        df = etapa._preparar_campos_normalizados(df_mixto)
        excluidas = etapa._aplicar_exclusion(df)
        assert len(excluidas) == 1, "La fila debería haber sido excluida por 'construccion'"
        bypass = etapa._aplicar_bypass(excluidas)
        assert len(bypass) == 1, "La fila debería ser recuperada por bypass ('corfo')"

    def test_bypass_vacio_retorna_df_vacio(self, df_licitaciones_minimo):
        filtros = {
            "incluir": {"nombre": ["ti"], "nivel1": [], "nivel2": [], "nivel3": []},
            "excluir": {"nombre": ["construccion"], "nivel1": [], "nivel2": [], "nivel3": [],
                        "generico": [], "componente": [], "organismo": [], "valor": []},
            "bypass": [],
        }
        etapa = _etapa_con_filtros(filtros)
        df = etapa._preparar_campos_normalizados(df_licitaciones_minimo.copy())
        excluidas = etapa._aplicar_exclusion(df)
        bypass = etapa._aplicar_bypass(excluidas)
        assert len(bypass) == 0

    def test_bypass_con_df_excluidas_vacio_retorna_df_vacio(self, filtros_excluir_construccion):
        etapa = _etapa_con_filtros(filtros_excluir_construccion)
        bypass = etapa._aplicar_bypass(pd.DataFrame())
        assert len(bypass) == 0


# ---------------------------------------------------------------------------
# Flujo completo de filtrado (sin I/O)
# ---------------------------------------------------------------------------

class TestFlujoFiltradoCompleto:
    def test_inclusion_exclusion_bypass_conjunto(self, df_licitaciones_minimo, filtros_excluir_construccion):
        """Las 3 fases encadenadas producen un resultado coherente."""
        etapa = _etapa_con_filtros(filtros_excluir_construccion)
        df = etapa._preparar_campos_normalizados(df_licitaciones_minimo.copy())

        df_incluidas = etapa._aplicar_inclusion(df)
        df_excluidas = etapa._aplicar_exclusion(df_incluidas)
        df_final_sin_bypass = df_incluidas[~df_incluidas.index.isin(df_excluidas.index)]
        df_bypass = etapa._aplicar_bypass(df_excluidas)

        total_final = len(df_final_sin_bypass) + len(df_bypass)
        # El total debe ser <= al de incluidas
        assert total_final <= len(df_incluidas)
        # No puede haber duplicados de índice entre final y bypass
        idx_final = set(df_final_sin_bypass.index)
        idx_bypass = set(df_bypass.index)
        assert idx_final.isdisjoint(idx_bypass)

    def test_regex_caracteres_especiales_no_rompen(self, df_licitaciones_minimo):
        """Palabras clave con caracteres especiales de regex se escapan correctamente."""
        filtros = {
            "incluir": {"nombre": ["(consultoría)", "TI+"], "nivel1": [], "nivel2": [], "nivel3": []},
            "excluir": {k: [] for k in ["nombre","nivel1","nivel2","nivel3","generico","componente","organismo","valor"]},
            "bypass": [],
        }
        etapa = _etapa_con_filtros(filtros)
        df = etapa._preparar_campos_normalizados(df_licitaciones_minimo.copy())
        # No debe lanzar excepción — re.escape protege los caracteres especiales
        result = etapa._aplicar_inclusion(df)
        assert isinstance(result, pd.DataFrame)
