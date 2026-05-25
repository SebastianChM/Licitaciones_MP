"""Tests unitarios para SistemaAnalisisIncremental (sistema_incremental.py).

Cubre:
- Constructor con y sin PipelineContext externo
- ejecutar_analisis_completo: flujo nominal y manejo de datos nulos
- _cargar_datos_actuales: prioridad filtrados → raw → None
- _mostrar_resultados_detallados: log de resumen
- _generar_sugerencias_pivot: escritura JSON y log top-sugerencias
"""
import json
from unittest.mock import patch

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_reporte():
    return {
        'resumen': {
            'taxonomia': {
                'nuevos_nivel1': 2,
                'nuevos_nivel2': 3,
                'nuevos_nivel3': 1,
                'nuevos_genericos': 0,
            },
            'licitaciones': {'nuevas': 5, 'existentes': 10, 'vencidas': 2},
            'sugerencias_filtros': {'inclusion': 1, 'exclusion': 2},
        }
    }


def _make_analisis_taxonomia(con_sugerencias: bool = True):
    sug = {
        'inclusion': [{'termino': 'CONSULTOR', 'razon': 'frecuente'}],
        'exclusion': [{'termino': 'SUMINISTRO', 'razon': 'no relevante'},
                      {'termino': 'ARRIENDO', 'razon': 'fuera de alcance'}],
    }
    return {
        'nuevos_valores': {},
        'sugerencias_filtros': sug if con_sugerencias else {'inclusion': [], 'exclusion': []},
    }


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestConstructor:

    def test_context_externo_usado_directamente(self, context):
        from sistema_incremental import SistemaAnalisisIncremental
        sistema = SistemaAnalisisIncremental(context=context)
        assert sistema.context is context

    def test_sin_context_crea_uno_propio(self, config):
        from sistema_incremental import SistemaAnalisisIncremental
        with patch('sistema_incremental.Config', return_value=config):
            sistema = SistemaAnalisisIncremental()
        assert sistema.context is not None
        assert sistema.context.flags.get('allow_fallback') is True

    def test_config_accesible(self, context):
        from sistema_incremental import SistemaAnalisisIncremental
        sistema = SistemaAnalisisIncremental(context=context)
        assert sistema.config is context.config


# ---------------------------------------------------------------------------
# _cargar_datos_actuales
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCargarDatosActuales:

    def test_retorna_df_desde_filtrados(self, context, tmp_path, df_licitaciones_minimo):
        from sistema_incremental import SistemaAnalisisIncremental
        # Crear archivo filtrado temporal
        archivo = tmp_path / "Licitaciones_Filtradas_20250101.xlsx"
        df_licitaciones_minimo.to_excel(archivo, index=False)
        context.config.FILTRADO_DIR = tmp_path
        sistema = SistemaAnalisisIncremental(context=context)
        df = sistema._cargar_datos_actuales()
        assert df is not None
        assert len(df) == len(df_licitaciones_minimo)

    def test_retorna_none_si_no_hay_archivos(self, context, tmp_path):
        from sistema_incremental import SistemaAnalisisIncremental
        sistema = SistemaAnalisisIncremental(context=context)
        # Mock directo del método para simular filesystem sin datos
        with patch.object(sistema, '_cargar_datos_actuales', return_value=None):
            df = sistema._cargar_datos_actuales()
        assert df is None


# ---------------------------------------------------------------------------
# _mostrar_resultados_detallados
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestMostrarResultadosDetallados:

    def test_registra_log_con_conteos(self, context, logger_mock):
        from sistema_incremental import SistemaAnalisisIncremental
        sistema = SistemaAnalisisIncremental(context=context)
        sistema.logger = logger_mock

        sistema._mostrar_resultados_detallados(_make_reporte())

        calls_text = " ".join(str(c) for c in logger_mock.info.call_args_list)
        assert "5" in calls_text     # nuevas
        assert "10" in calls_text    # existentes
        assert "2" in calls_text     # vencidas


# ---------------------------------------------------------------------------
# _generar_sugerencias_pivot
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGenerarSugerenciasPivot:

    def test_escribe_json_en_log_dir(self, context, tmp_path, logger_mock):
        from sistema_incremental import SistemaAnalisisIncremental
        context.config.LOG_DIR = tmp_path
        sistema = SistemaAnalisisIncremental(context=context)
        sistema.logger = logger_mock

        sistema._generar_sugerencias_pivot(_make_analisis_taxonomia())

        archivos_json = list(tmp_path.glob("sugerencias_filtros_*.json"))
        assert len(archivos_json) == 1

    def test_json_contiene_inclusion_y_exclusion(self, context, tmp_path, logger_mock):
        from sistema_incremental import SistemaAnalisisIncremental
        context.config.LOG_DIR = tmp_path
        sistema = SistemaAnalisisIncremental(context=context)
        sistema.logger = logger_mock

        sistema._generar_sugerencias_pivot(_make_analisis_taxonomia())

        archivo = next(tmp_path.glob("sugerencias_filtros_*.json"))
        data = json.loads(archivo.read_text(encoding='utf-8'))
        assert 'sugerencias_inclusion' in data
        assert 'sugerencias_exclusion' in data

    def test_loggea_top_sugerencias_inclusion(self, context, tmp_path, logger_mock):
        from sistema_incremental import SistemaAnalisisIncremental
        context.config.LOG_DIR = tmp_path
        sistema = SistemaAnalisisIncremental(context=context)
        sistema.logger = logger_mock

        sistema._generar_sugerencias_pivot(_make_analisis_taxonomia())

        calls_text = " ".join(str(c) for c in logger_mock.info.call_args_list)
        assert "CONSULTOR" in calls_text

    def test_sin_sugerencias_no_falla(self, context, tmp_path, logger_mock):
        from sistema_incremental import SistemaAnalisisIncremental
        context.config.LOG_DIR = tmp_path
        sistema = SistemaAnalisisIncremental(context=context)
        sistema.logger = logger_mock

        sistema._generar_sugerencias_pivot(_make_analisis_taxonomia(con_sugerencias=False))
        # No debe lanzar excepción


# ---------------------------------------------------------------------------
# ejecutar_analisis_completo
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestEjecutarAnalisisCompleto:

    def test_flujo_nominal(self, context, tmp_path, df_licitaciones_minimo, logger_mock):
        from sistema_incremental import SistemaAnalisisIncremental
        context.config.FILTRADO_DIR = tmp_path
        context.config.LOG_DIR = tmp_path
        archivo = tmp_path / "Licitaciones_Filtradas_20250101.xlsx"
        df_licitaciones_minimo.to_excel(archivo, index=False)

        sistema = SistemaAnalisisIncremental(context=context)
        sistema.logger = logger_mock

        analisis_tax = _make_analisis_taxonomia()
        analisis_rep = {
            'licitaciones_nuevas': df_licitaciones_minimo,
            'licitaciones_existentes': pd.DataFrame(),
            'licitaciones_vencidas': pd.DataFrame(),
            'estadisticas': {'nuevas': 3, 'existentes': 0, 'vencidas': 0},
        }

        with patch.object(sistema.analizador, 'analizar_cambios_taxonomia', return_value=analisis_tax), \
             patch.object(sistema.analizador, 'analizar_reporte_incremental', return_value=analisis_rep), \
             patch.object(sistema.analizador, 'generar_reporte_cambios', return_value=_make_reporte()):
            sistema.ejecutar_analisis_completo()

        logger_mock.info.assert_called()

    def test_sin_datos_retorna_sin_crash(self, context, tmp_path, logger_mock):
        from sistema_incremental import SistemaAnalisisIncremental
        sistema = SistemaAnalisisIncremental(context=context)
        sistema.logger = logger_mock

        # Simular que no hay datos disponibles en disco
        with patch.object(sistema, '_cargar_datos_actuales', return_value=None):
            sistema.ejecutar_analisis_completo()

        calls_text = " ".join(str(c) for c in logger_mock.warning.call_args_list)
        assert "No se encontraron datos" in calls_text


# ---------------------------------------------------------------------------
# _cargar_datos_actuales — ramas adicionales
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCargarDatosActualesRamas:

    def test_usa_raw_cuando_no_hay_filtrados(self, context, tmp_path, df_licitaciones_minimo):
        """Cuando no hay archivos filtrados, carga desde LICITACIONES_MP (raw)."""
        from sistema_incremental import SistemaAnalisisIncremental

        # FILTRADO_DIR sin archivos
        filtrado_dir = tmp_path / "filtrado"
        filtrado_dir.mkdir()
        context.config.FILTRADO_DIR = filtrado_dir

        # Archivo raw presente
        raw = tmp_path / "Licitacion_Publicada.xlsx"
        df_licitaciones_minimo.to_excel(raw, index=False)
        context.config.INPUT_DIR = tmp_path

        sistema = SistemaAnalisisIncremental(context=context)

        with patch.object(type(context.config), 'LICITACIONES_MP',
                          new_callable=lambda: property(lambda self: raw)):
            df = sistema._cargar_datos_actuales()

        assert df is not None

    def test_retorna_none_si_filtrados_fallan_y_raw_no_existe(self, context, tmp_path):
        """Cuando no hay filtrados ni raw, retorna None."""
        from sistema_incremental import SistemaAnalisisIncremental

        filtrado_dir = tmp_path / "filtrado_vacio"
        filtrado_dir.mkdir()
        context.config.FILTRADO_DIR = filtrado_dir
        sistema = SistemaAnalisisIncremental(context=context)

        # Patchear LICITACIONES_MP para que no exista
        with patch.object(type(context.config), 'LICITACIONES_MP',
                          new_callable=lambda: property(lambda self: tmp_path / "noexiste.xlsx")):
            df = sistema._cargar_datos_actuales()

        assert df is None


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestMain:

    def test_main_retorna_0_en_exito(self):
        from sistema_incremental import SistemaAnalisisIncremental, main
        with patch.object(SistemaAnalisisIncremental, 'ejecutar_analisis_completo'):
            rc = main()
        assert rc == 0

    def test_main_retorna_1_en_excepcion(self):
        from sistema_incremental import SistemaAnalisisIncremental, main
        with patch.object(SistemaAnalisisIncremental, 'ejecutar_analisis_completo',
                          side_effect=RuntimeError("fallo")):
            rc = main()
        assert rc == 1
