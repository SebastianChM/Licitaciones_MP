"""
Tests adicionales de cobertura para etapas/etapa2.py.

Cubre las ramas no alcanzadas por test_etapa2_contrato.py:
- _validar_prerequisitos (raise + ok)
- _cargar_filtros (cuerpo completo + clean_valores guardia col_idx)
- _generar_outputs con excluidas no vacías
- _imprimir_resumen
- main()
"""
import pytest
import pandas as pd
import openpyxl
from pathlib import Path
from unittest.mock import patch, MagicMock

from etapas.etapa2 import FiltradorLicitaciones
from core.context import PipelineContext
from utils.config import Config


# ---------------------------------------------------------------------------
# Fixtures helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def ctx_base(tmp_path):
    """Contexto con config apuntando a tmp_path."""
    ctx = PipelineContext(config=Config())
    ctx.config.FILTRADO_DIR = tmp_path
    return ctx


@pytest.fixture
def etapa_bound(ctx_base):
    """FiltradorLicitaciones enlazado al contexto base."""
    e = FiltradorLicitaciones()
    e.bind(ctx_base)
    return e, ctx_base


def _pivot_06filtros(path: Path) -> Path:
    """Crea un PIVOT_MAESTRO mínimo con hoja 06-FILTROS."""
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "06-FILTROS"
    # 5 filas de cabecera + datos (header=4 en pd.read_excel → row 5 es header)
    for _ in range(4):
        ws.append([""] * 13)
    ws.append(["nombre", "nivel1", "nivel2", "nivel3",
               "nombre_exc", "nivel1_exc", "nivel2_exc", "nivel3_exc",
               "generico", "comp", "org", "valor", "bypass"])
    ws.append(["consultoria", "", "", "", "arriendo", "", "", "", "", "", "", "", ""])
    wb.save(path)
    return path


# ---------------------------------------------------------------------------
# _validar_prerequisitos
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestValidarPrerequisitos:

    def test_lanza_error_si_pivot_invalido(self, tmp_path):
        """Si el PIVOT no existe, raise FileNotFoundError."""
        ctx = PipelineContext(config=Config())
        ctx.config.PIVOT_DIR = tmp_path  # tmp_path no tiene PIVOT_MAESTRO
        etapa = FiltradorLicitaciones()
        etapa.bind(ctx)
        with pytest.raises(FileNotFoundError, match="PIVOT_MAESTRO"):
            etapa._validar_prerequisitos()

    def test_ok_cuando_pivot_valido(self, tmp_path):
        """Si el PIVOT existe con la hoja, no lanza excepción."""
        pivot = tmp_path / "PIVOT_MAESTRO.xlsx"
        _pivot_06filtros(pivot)
        ctx = PipelineContext(config=Config())
        ctx.config.PIVOT_DIR = tmp_path
        etapa = FiltradorLicitaciones()
        etapa.bind(ctx)
        etapa._validar_prerequisitos()   # no debe lanzar


# ---------------------------------------------------------------------------
# _cargar_filtros
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCargarFiltros:

    def test_carga_filtros_desde_pivot_real(self, tmp_path):
        """Ejercita el cuerpo completo de _cargar_filtros con un PIVOT temporal."""
        pivot = tmp_path / "PIVOT_MAESTRO.xlsx"
        _pivot_06filtros(pivot)
        ctx = PipelineContext(config=Config())
        ctx.config.PIVOT_DIR = tmp_path
        etapa = FiltradorLicitaciones()
        etapa.bind(ctx)

        filtros = etapa._cargar_filtros()

        assert "incluir" in filtros
        assert "excluir" in filtros
        assert "bypass" in filtros

    def test_clean_valores_columna_fuera_de_rango(self, tmp_path):
        """clean_valores devuelve [] cuando col_idx >= len(df.columns)."""
        wb = openpyxl.Workbook()
        ws = wb.active
        assert ws is not None
        ws.title = "06-FILTROS"
        for _ in range(5):
            ws.append(["solo_dos_cols", "columna_b"])
        pivot = tmp_path / "PIVOT_MAESTRO.xlsx"
        wb.save(pivot)
        ctx = PipelineContext(config=Config())
        ctx.config.PIVOT_DIR = tmp_path
        etapa = FiltradorLicitaciones()
        etapa.bind(ctx)

        # No debe lanzar aunque col_idx > len(df.columns)
        filtros = etapa._cargar_filtros()
        assert isinstance(filtros, dict)


# ---------------------------------------------------------------------------
# _generar_outputs — rama excluidas no vacías
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGenerarOutputs:

    def test_genera_archivo_excluidas_cuando_hay_datos(self, tmp_path):
        """Cuando df_excluidas tiene filas se genera el archivo Excluidas_*.xlsx."""
        ctx = PipelineContext(config=Config())
        ctx.config.FILTRADO_DIR = tmp_path
        etapa = FiltradorLicitaciones()
        etapa.bind(ctx)

        df_filtradas = pd.DataFrame({"Nombre Adquisición": ["A"]})
        df_excluidas = pd.DataFrame({"Nombre Adquisición": ["B", "C"]})

        with patch('etapas.etapa2.guardar_excel_con_formato') as mock_guardar, \
             patch('etapas.etapa2.obtener_timestamp', return_value="20260101_000000"):
            mock_guardar.return_value = None
            archivos = etapa._generar_outputs(df_filtradas, df_excluidas)

        assert len(archivos) == 2   # filtradas + excluidas
        nombres = [a.name for a in archivos]
        assert any("Excluidas" in n for n in nombres)
        assert mock_guardar.call_count == 2

    def test_no_genera_archivo_excluidas_cuando_vacio(self, tmp_path):
        """Cuando df_excluidas está vacío solo se genera el de filtradas."""
        ctx = PipelineContext(config=Config())
        ctx.config.FILTRADO_DIR = tmp_path
        etapa = FiltradorLicitaciones()
        etapa.bind(ctx)

        df_filtradas = pd.DataFrame({"Nombre": ["A"]})
        df_excluidas = pd.DataFrame()

        with patch('etapas.etapa2.guardar_excel_con_formato') as mock_guardar, \
             patch('etapas.etapa2.obtener_timestamp', return_value="20260101_000000"):
            mock_guardar.return_value = None
            archivos = etapa._generar_outputs(df_filtradas, df_excluidas)

        assert len(archivos) == 1
        assert mock_guardar.call_count == 1


# ---------------------------------------------------------------------------
# _imprimir_resumen
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestImprimirResumen:

    def test_imprime_sin_errores(self, tmp_path):
        """_imprimir_resumen no lanza excepción con stats rellenos."""
        ctx = PipelineContext(config=Config())
        etapa = FiltradorLicitaciones()
        etapa.bind(ctx)
        etapa.stats.update({'original': 100, 'incluidas': 40, 'excluidas': 50,
                            'bypass': 10, 'final': 50, 'tiempo': None})
        etapa._imprimir_resumen()   # smoke: no debe lanzar

    def test_pct_cero_si_original_0(self, tmp_path):
        """Evita ZeroDivisionError cuando original=0."""
        ctx = PipelineContext(config=Config())
        etapa = FiltradorLicitaciones()
        etapa.bind(ctx)
        etapa.stats.update({'original': 0, 'incluidas': 0, 'excluidas': 0,
                            'bypass': 0, 'final': 0, 'tiempo': None})
        etapa._imprimir_resumen()   # no debe lanzar


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestMain:

    def test_main_retorna_0_en_exito(self):
        from etapas.etapa2 import main
        resultado_ok = MagicMock(success=True, error_message=None,
                                 metrics_produced={'final': 5, 'original': 10})
        with patch('etapas.etapa2.FiltradorLicitaciones') as MockFilt:
            MockFilt.return_value.run.return_value = resultado_ok
            rc = main()
        assert rc == 0

    def test_main_retorna_1_si_falla(self):
        from etapas.etapa2 import main
        resultado_fallo = MagicMock(success=False, error_message="algo falló")
        with patch('etapas.etapa2.FiltradorLicitaciones') as MockFilt:
            MockFilt.return_value.run.return_value = resultado_fallo
            rc = main()
        assert rc == 1

    def test_main_retorna_1_en_excepcion(self):
        from etapas.etapa2 import main
        with patch('etapas.etapa2.FiltradorLicitaciones') as MockFilt:
            MockFilt.return_value.run.side_effect = RuntimeError("crash")
            rc = main()
        assert rc == 1
