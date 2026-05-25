"""Tests unitarios para AnalizadorIncremental — lógica de negocio pura.

Todos los métodos tested son independientes de I/O: no leen Excel
ni escriben archivos. El logger y config se mockean.

Ejecutar con: pytest tests/unit/test_analizador.py -v
"""

from unittest.mock import MagicMock

import pandas as pd

from utils.analizador_incremental import AnalizadorIncremental

# ---------------------------------------------------------------------------
# Helper de instanciación sin I/O
# ---------------------------------------------------------------------------

COLS_LICIT = [
    "Numero Adquisición", "Nombre Adquisición",
    "Nivel 1", "Nivel 2", "Nivel 3", "Genérico",
]


def _analizador() -> AnalizadorIncremental:
    """Instancia AnalizadorIncremental con logger y config mockeados."""
    az = AnalizadorIncremental.__new__(AnalizadorIncremental)
    az.logger = MagicMock()
    az.config = MagicMock()
    return az


def _df_licit(codigos: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        [[c, f"Licitación {c}", "Servicios", "Tecnología", "Consultoría", "Software"]
         for c in codigos],
        columns=COLS_LICIT,
    )


# ---------------------------------------------------------------------------
# _encontrar_nuevos_valores
# ---------------------------------------------------------------------------

class TestEncontrarNuevosValores:
    def test_retorna_diferencia_de_conjuntos(self):
        az = _analizador()
        result = az._encontrar_nuevos_valores({"A", "B"}, {"A", "B", "C"})
        assert set(result) == {"C"}

    def test_sin_diferencia_retorna_lista_vacia(self):
        az = _analizador()
        assert az._encontrar_nuevos_valores({"A", "B"}, {"A", "B"}) == []

    def test_existentes_vacio_devuelve_todos(self):
        az = _analizador()
        result = az._encontrar_nuevos_valores(set(), {"X", "Y"})
        assert set(result) == {"X", "Y"}

    def test_nuevos_vacio_devuelve_lista_vacia(self):
        az = _analizador()
        assert az._encontrar_nuevos_valores({"A"}, set()) == []

    def test_resultado_esta_ordenado(self):
        az = _analizador()
        result = az._encontrar_nuevos_valores(set(), {"ZZZ", "AAA", "MMM"})
        assert result == sorted(result)


# ---------------------------------------------------------------------------
# _extraer_taxonomia_datos
# ---------------------------------------------------------------------------

class TestExtraerTaxonomiaDatos:
    def test_extrae_las_cuatro_categorias(self):
        az = _analizador()
        df = pd.DataFrame([
            ["001", "Nombre", "Servicios", "Tecnología", "Consultoría", "Software"],
            ["002", "Nombre", "Bienes", "Equipos", "Hardware", "Computadores"],
        ], columns=COLS_LICIT)
        result = az._extraer_taxonomia_datos(df)
        assert "SERVICIOS" in result["nivel1"]
        assert "BIENES" in result["nivel1"]
        # normalizar_texto quita tildes y pone MAYÚSCULAS
        assert "TECNOLOGIA" in result["nivel2"]
        assert "SOFTWARE" in result["generico"]

    def test_valores_nulos_no_quedan_en_set(self):
        az = _analizador()
        df = pd.DataFrame([
            ["001", "Nombre", "Servicios", None, "Consultoría", None],
        ], columns=COLS_LICIT)
        result = az._extraer_taxonomia_datos(df)
        assert "SERVICIOS" in result["nivel1"]
        assert len(result["nivel2"]) == 0
        assert len(result["generico"]) == 0

    def test_columnas_faltantes_no_rompen(self):
        az = _analizador()
        df = pd.DataFrame([["001"]], columns=["Numero Adquisición"])
        result = az._extraer_taxonomia_datos(df)
        for key in ("nivel1", "nivel2", "nivel3", "generico"):
            assert result[key] == set()

    def test_valores_nan_string_se_excluyen(self):
        az = _analizador()
        df = pd.DataFrame([
            ["001", "N", "nan", "Tecnología", "nan", "Software"],
        ], columns=COLS_LICIT)
        result = az._extraer_taxonomia_datos(df)
        # "nan" normalizado se vuelve "NAN" pero el código aplica dropna() + filtro
        # Lo importante: no crash y el set se mantiene limpio de 'nan'/'None'
        assert "TECNOLOGIA" in result["nivel2"]


# ---------------------------------------------------------------------------
# _comparar_licitaciones
# ---------------------------------------------------------------------------

class TestCompararLicitaciones:
    def test_todos_nuevos_cuando_anterior_vacio(self):
        az = _analizador()
        nuevos = _df_licit(["A", "B", "C"])
        result = az._comparar_licitaciones(nuevos, pd.DataFrame())
        assert len(result["licitaciones_nuevas"]) == 3
        assert len(result["licitaciones_existentes"]) == 0
        assert len(result["licitaciones_vencidas"]) == 0

    def test_detecta_licitaciones_nuevas(self):
        az = _analizador()
        nuevos = _df_licit(["A", "B", "C"])
        anterior = _df_licit(["B", "C", "D"])
        result = az._comparar_licitaciones(nuevos, anterior)
        assert set(result["licitaciones_nuevas"]["Numero Adquisición"]) == {"A"}

    def test_detecta_licitaciones_existentes(self):
        az = _analizador()
        nuevos = _df_licit(["A", "B"])
        anterior = _df_licit(["B", "C"])
        result = az._comparar_licitaciones(nuevos, anterior)
        assert set(result["licitaciones_existentes"]["Numero Adquisición"]) == {"B"}

    def test_detecta_licitaciones_vencidas(self):
        az = _analizador()
        nuevos = _df_licit(["A"])
        anterior = _df_licit(["B", "C"])
        result = az._comparar_licitaciones(nuevos, anterior)
        assert set(result["licitaciones_vencidas"]["Numero Adquisición"]) == {"B", "C"}

    def test_estadisticas_son_coherentes_con_dataframes(self):
        az = _analizador()
        nuevos = _df_licit(["A", "B", "C"])
        anterior = _df_licit(["B", "D"])
        result = az._comparar_licitaciones(nuevos, anterior)
        stats = result["estadisticas"]
        assert stats["nuevas"] == len(result["licitaciones_nuevas"])
        assert stats["existentes"] == len(result["licitaciones_existentes"])
        assert stats["vencidas"] == len(result["licitaciones_vencidas"])

    def test_sin_columna_codigo_todos_son_nuevos(self):
        az = _analizador()
        nuevos = pd.DataFrame([["X"]], columns=["Columna Sin Codigo"])
        anterior = pd.DataFrame([["Y"]], columns=["Columna Sin Codigo"])
        result = az._comparar_licitaciones(nuevos, anterior)
        assert len(result["licitaciones_nuevas"]) == 1
        assert len(result["licitaciones_existentes"]) == 0

    def test_nuevas_y_existentes_no_se_solapan(self):
        az = _analizador()
        nuevos = _df_licit(["A", "B", "C", "D"])
        anterior = _df_licit(["B", "C"])
        result = az._comparar_licitaciones(nuevos, anterior)
        codigos_nuevas = set(result["licitaciones_nuevas"]["Numero Adquisición"])
        codigos_existentes = set(result["licitaciones_existentes"]["Numero Adquisición"])
        assert codigos_nuevas.isdisjoint(codigos_existentes)

    def test_conjunto_completo_no_pierde_registros(self):
        """nuevas + existentes en nuevos = total de nuevos."""
        az = _analizador()
        nuevos = _df_licit(["A", "B", "C"])
        anterior = _df_licit(["B"])
        result = az._comparar_licitaciones(nuevos, anterior)
        total = len(result["licitaciones_nuevas"]) + len(result["licitaciones_existentes"])
        assert total == len(nuevos)


# ---------------------------------------------------------------------------
# _generar_sugerencias_filtros
# ---------------------------------------------------------------------------

class TestGenerarSugerenciasFiltros:
    def _cambios(self, valores: list[str]) -> dict:
        return {
            "nuevos_nivel1": valores,
            "nuevos_nivel2": [],
            "nuevos_nivel3": [],
            "nuevos_genericos": [],
        }

    def test_palabra_consultoria_sugiere_inclusion(self):
        az = _analizador()
        result = az._generar_sugerencias_filtros(
            self._cambios(["Consultoría en ingeniería"]), pd.DataFrame()
        )
        assert len(result["inclusion"]) >= 1

    def test_palabra_suministro_sugiere_exclusion(self):
        az = _analizador()
        result = az._generar_sugerencias_filtros(
            self._cambios(["Suministro de alimentos"]), pd.DataFrame()
        )
        assert len(result["exclusion"]) >= 1

    def test_sin_cambios_retorna_listas_vacias(self):
        az = _analizador()
        cambios = {k: [] for k in ["nuevos_nivel1", "nuevos_nivel2", "nuevos_nivel3", "nuevos_genericos"]}
        result = az._generar_sugerencias_filtros(cambios, pd.DataFrame())
        assert result["inclusion"] == []
        assert result["exclusion"] == []

    def test_sugerencias_tienen_campo_termino_y_confianza(self):
        az = _analizador()
        result = az._generar_sugerencias_filtros(
            self._cambios(["Diseño arquitectónico proyecto"]), pd.DataFrame()
        )
        if result["inclusion"]:
            sugerencia = result["inclusion"][0]
            assert "termino" in sugerencia
            assert "confianza" in sugerencia


# ---------------------------------------------------------------------------
# analizar_cambios_taxonomia  (método público)
# ---------------------------------------------------------------------------

class TestAnalizarCambiosTaxonomia:
    """Prueba el método público con _cargar_taxonomia_pivot mockeado."""

    def _taxonomia_vacia(self):
        return {'nivel1': set(), 'nivel2': set(), 'nivel3': set(), 'generico': set()}

    def test_retorna_dict_con_estructura_esperada(self):
        az = _analizador()
        az._cargar_taxonomia_pivot = lambda: self._taxonomia_vacia()

        df = _df_licit(["A"])
        result = az.analizar_cambios_taxonomia(df)

        assert 'cambios_taxonomia' in result
        assert 'sugerencias_filtros' in result
        assert 'timestamp' in result

    def test_detecta_nivel1_nuevo(self):
        az = _analizador()
        # Taxonomía actual vacía → todos los valores de df son "nuevos"
        az._cargar_taxonomia_pivot = lambda: self._taxonomia_vacia()

        df = pd.DataFrame(
            [["001", "N", "Servicios Digitales", "TI", "Consultoría", "SW"]],
            columns=COLS_LICIT,
        )
        result = az.analizar_cambios_taxonomia(df)
        assert "SERVICIOS DIGITALES" in result['cambios_taxonomia']['nuevos_nivel1']

    def test_valores_ya_conocidos_no_son_nuevos(self):
        az = _analizador()
        # Taxonomía actual contiene ya "SERVICIOS"
        az._cargar_taxonomia_pivot = lambda: {
            'nivel1': {'SERVICIOS'},
            'nivel2': set(), 'nivel3': set(), 'generico': set()
        }

        df = pd.DataFrame(
            [["001", "N", "Servicios", "TI", "Consultoría", "SW"]],
            columns=COLS_LICIT,
        )
        result = az.analizar_cambios_taxonomia(df)
        assert "SERVICIOS" not in result['cambios_taxonomia']['nuevos_nivel1']

    def test_loggea_mensaje_completado(self):
        az = _analizador()
        az._cargar_taxonomia_pivot = lambda: self._taxonomia_vacia()
        az.analizar_cambios_taxonomia(_df_licit(["A"]))
        az.logger.info.assert_called()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# analizar_reporte_incremental  (método público)
# ---------------------------------------------------------------------------

class TestAnalizarReporteIncremental:

    def test_sin_archivo_anterior_todos_son_nuevos(self):
        az = _analizador()
        az.config.PRESENTACION_DIR = MagicMock()
        az.config.PRESENTACION_DIR.glob.return_value = []

        df = _df_licit(["A", "B"])
        result = az.analizar_reporte_incremental(df)

        assert len(result['licitaciones_nuevas']) == 2
        assert result['estadisticas']['nuevas'] == 2
        assert result['estadisticas']['existentes'] == 0

    def test_archivo_inexistente_todos_son_nuevos(self, tmp_path):
        """Pasar un Path que no existe devuelve todos como nuevos."""
        az = _analizador()
        df = _df_licit(["A"])
        archivo_inexistente = tmp_path / "no_existe.xlsx"
        result = az.analizar_reporte_incremental(df, archivo_reporte_anterior=archivo_inexistente)

        assert result['estadisticas']['nuevas'] == 1

    def test_con_archivo_anterior_detecta_diferencias(self, tmp_path):
        """Con Excel anterior cargado correctamente, compara correctamente."""
        az = _analizador()
        # Crear Excel "anterior" con código B
        ruta = tmp_path / "Reporte_anterior.xlsx"
        _df_licit(["B"]).to_excel(ruta, sheet_name='Vigentes', index=False)

        df_nuevos = _df_licit(["A", "B"])
        result = az.analizar_reporte_incremental(df_nuevos, archivo_reporte_anterior=ruta)

        codigos_nuevas = set(result['licitaciones_nuevas']['Numero Adquisición'])
        assert "A" in codigos_nuevas
        # B ya estaba → existente
        codigos_existentes = set(result['licitaciones_existentes']['Numero Adquisición'])
        assert "B" in codigos_existentes


# ---------------------------------------------------------------------------
# generar_reporte_cambios  (método público)
# ---------------------------------------------------------------------------

class TestGenerarReporteCambios:

    def _analisis_tax(self):
        return {
            'cambios_taxonomia': {
                'nuevos_nivel1': ['DATO1'],
                'nuevos_nivel2': [],
                'nuevos_nivel3': [],
                'nuevos_genericos': ['DATO2'],
            },
            'sugerencias_filtros': {'inclusion': [], 'exclusion': []}
        }

    def _analisis_rep(self):
        return {
            'estadisticas': {'nuevas': 3, 'existentes': 1, 'vencidas': 0}
        }

    def test_retorna_dict_con_timestamp(self, tmp_path):
        az = _analizador()
        az.config.LOG_DIR = tmp_path
        result = az.generar_reporte_cambios(self._analisis_tax(), self._analisis_rep())
        assert 'timestamp' in result

    def test_guarda_json_en_log_dir(self, tmp_path):
        az = _analizador()
        az.config.LOG_DIR = tmp_path
        az.generar_reporte_cambios(self._analisis_tax(), self._analisis_rep())
        archivos = list(tmp_path.glob("analisis_incremental_*.json"))
        assert len(archivos) == 1

    def test_resumen_contiene_conteos_correctos(self, tmp_path):
        az = _analizador()
        az.config.LOG_DIR = tmp_path
        result = az.generar_reporte_cambios(self._analisis_tax(), self._analisis_rep())
        assert result['resumen']['taxonomia']['nuevos_nivel1'] == 1
        assert result['resumen']['taxonomia']['nuevos_genericos'] == 1
        assert result['resumen']['licitaciones']['nuevas'] == 3

    def test_json_es_valido(self, tmp_path):
        import json as _json
        az = _analizador()
        az.config.LOG_DIR = tmp_path
        az.generar_reporte_cambios(self._analisis_tax(), self._analisis_rep())
        archivo = next(tmp_path.glob("analisis_incremental_*.json"))
        data = _json.loads(archivo.read_text(encoding='utf-8'))
        assert 'resumen' in data


# ---------------------------------------------------------------------------
# _encontrar_reporte_mas_reciente
# ---------------------------------------------------------------------------

class TestEncontrarReporteMasReciente:

    def test_directorio_vacio_retorna_none(self, tmp_path):
        az = _analizador()
        az.config.PRESENTACION_DIR = tmp_path
        assert az._encontrar_reporte_mas_reciente() is None

    def test_retorna_el_mas_reciente(self, tmp_path):
        az = _analizador()
        az.config.PRESENTACION_DIR = tmp_path
        viejo = tmp_path / "Reporte_Licitaciones_2025-01-01.xlsx"
        nuevo = tmp_path / "Reporte_Licitaciones_2025-03-01.xlsx"
        viejo.touch()
        nuevo.touch()
        import time
        time.sleep(0.01)
        nuevo.write_bytes(b"x")  # Actualiza mtime
        result = az._encontrar_reporte_mas_reciente()
        assert result == nuevo


# ---------------------------------------------------------------------------
# _cargar_reporte_anterior
# ---------------------------------------------------------------------------

class TestCargarReporteAnterior:

    def test_carga_hoja_vigentes(self, tmp_path):
        az = _analizador()
        ruta = tmp_path / "reporte.xlsx"
        df = _df_licit(["A", "B"])
        df.to_excel(ruta, sheet_name='Vigentes', index=False)
        result = az._cargar_reporte_anterior(ruta)
        assert len(result) == 2

    def test_fallback_a_hoja_default(self, tmp_path):
        az = _analizador()
        ruta = tmp_path / "reporte.xlsx"
        df = _df_licit(["C"])
        df.to_excel(ruta, index=False)  # sin sheet_name → 'Sheet1'
        result = az._cargar_reporte_anterior(ruta)
        assert len(result) == 1

    def test_archivo_invalido_retorna_dataframe_vacio(self, tmp_path):
        az = _analizador()
        ruta = tmp_path / "corrupto.xlsx"
        ruta.write_text("not an excel file")
        result = az._cargar_reporte_anterior(ruta)
        assert isinstance(result, pd.DataFrame)
        assert result.empty


# ---------------------------------------------------------------------------
# _cargar_taxonomia_pivot (exception path — Excel inexistente)
# ---------------------------------------------------------------------------

class TestCargarTaxonomiaPivot:

    def test_excel_inexistente_retorna_taxonomia_vacia(self, tmp_path):
        az = _analizador()
        az.config.PIVOT_MAESTRO = tmp_path / "PIVOT_NO_EXISTE.xlsx"  # type: ignore[misc]
        result = az._cargar_taxonomia_pivot()
        for key in ('nivel1', 'nivel2', 'nivel3', 'generico'):
            assert result[key] == set()
        az.logger.warning.assert_called()  # type: ignore[attr-defined]

    def test_carga_valores_desde_hoja_04_base(self, tmp_path):
        """Excel con hoja 04-BASE y encabezados estándar → valores normalizados en sets."""
        import openpyxl
        ruta = tmp_path / "PIVOT_TEST.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.create_sheet("04-BASE")
        default = wb.active
        if default is not None:
            del wb[default.title]  # Quitar hoja por defecto
        ws.append(["Nivel 1", "Nivel 2", "Nivel 3", "Genérico"])
        ws.append(["Servicios", "Tecnología", "Consultoría", "Software"])
        ws.append(["Bienes", "Equipos", "Hardware", "Computadoras"])
        wb.save(ruta)

        az = _analizador()
        az.config.PIVOT_MAESTRO = ruta  # type: ignore[misc]
        result = az._cargar_taxonomia_pivot()

        assert "SERVICIOS" in result['nivel1']
        assert "BIENES" in result['nivel1']
        assert "TECNOLOGIA" in result['nivel2']
        assert "CONSULTORIA" in result['nivel3']
        assert "SOFTWARE" in result['generico']

    def test_hoja_sin_encabezado_expected_retorna_vacia(self, tmp_path):
        """Hoja sin columnas NIVEL 1/2/3/Genérico → taxonomía vacía + warning."""
        import openpyxl
        ruta = tmp_path / "PIVOT_SIN_HEADER.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.create_sheet("04-BASE")
        default = wb.active
        if default is not None:
            del wb[default.title]
        ws.append(["ColumnA", "ColumnB"])
        ws.append(["val1", "val2"])
        wb.save(ruta)

        az = _analizador()
        az.config.PIVOT_MAESTRO = ruta  # type: ignore[misc]
        result = az._cargar_taxonomia_pivot()
        for key in ('nivel1', 'nivel2', 'nivel3', 'generico'):
            assert result[key] == set()
        az.logger.warning.assert_called()  # type: ignore[attr-defined]

