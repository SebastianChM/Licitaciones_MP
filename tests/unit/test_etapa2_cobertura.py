"""
Tests adicionales de cobertura para etapas/etapa2.py.

Cubre las ramas no alcanzadas por test_etapa2_contrato.py:
- _validar_prerequisitos (raise + ok)
- _cargar_filtros (cuerpo completo + clean_valores guardia col_idx)
- _generar_outputs con excluidas no vacías
- _imprimir_resumen
- main()
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import openpyxl
import pandas as pd
import pytest

from core.context import PipelineContext
from etapas.etapa2 import FiltradorLicitaciones
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
    """Crea un PIVOT_MAESTRO mínimo con hoja '00-Equipos' + hoja '06-Test' del equipo TEST."""
    wb = openpyxl.Workbook()
    # Hoja por defecto la borramos al final
    default = wb.active
    # Hoja 00-Equipos (catálogo)
    ws_eq = wb.create_sheet("00-Equipos")
    ws_eq.append(["codigo", "nombre", "hoja_filtros", "descripcion", "activo"])
    ws_eq.append(["TEST", "Equipo Test", "06-Test", "Equipo sintético para pruebas", "TRUE"])
    # Hoja 06-Test con reglas del equipo (4 filas de cabecera + datos)
    ws = wb.create_sheet("06-Test")
    for _ in range(4):
        ws.append([""] * 14)
    ws.append(["nombre", "nivel1", "nivel2", "nivel3",
               "nombre_exc", "nivel1_exc", "nivel2_exc", "nivel3_exc",
               "generico", "comp", "org", "valor", "bypass", "excl_dura"])
    ws.append(["consultoria", "", "", "",
               "arriendo", "", "", "",
               "", "", "", "", "", ""])
    if default is not None and default.title != "00-Equipos":
        wb.remove(default)
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
# _cargar_perfil (carga del FilterProfile del equipo activo)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCargarFiltros:

    def test_carga_perfil_desde_pivot_real(self, tmp_path):
        """Ejercita el cuerpo completo de _cargar_perfil con un PIVOT temporal."""
        pivot = tmp_path / "PIVOT_MAESTRO.xlsx"
        _pivot_06filtros(pivot)
        ctx = PipelineContext(config=Config())
        ctx.config.PIVOT_DIR = tmp_path
        ctx.flags['equipo'] = 'TEST'
        etapa = FiltradorLicitaciones()
        etapa.bind(ctx)

        profile = etapa._cargar_perfil(ctx)

        assert profile.equipo.codigo == "TEST"
        # ProfileLoader normaliza valores (uppercase + ASCII)
        assert "CONSULTORIA" in profile.incluir.get("nombre", [])
        assert "ARRIENDO" in profile.excluir.get("nombre", [])

    def test_equipo_inexistente_lanza_value_error(self, tmp_path):
        """Pedir un equipo no registrado en 00-Equipos debe lanzar ValueError claro."""
        pivot = tmp_path / "PIVOT_MAESTRO.xlsx"
        _pivot_06filtros(pivot)
        ctx = PipelineContext(config=Config())
        ctx.config.PIVOT_DIR = tmp_path
        ctx.flags['equipo'] = 'NO_EXISTE'
        etapa = FiltradorLicitaciones()
        etapa.bind(ctx)

        with pytest.raises(ValueError, match="Equipo inválido"):
            etapa._cargar_perfil(ctx)


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
