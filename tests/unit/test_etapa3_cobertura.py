"""
Tests adicionales para Etapa3 — cubre huecos de cobertura restantes:
- _procesar_respuesta_api     (líneas 241-306)
- _limpiar_checkpoints_antiguos (líneas 126-130)
- _cargar_licitaciones        (línea 95)
- _generar_outputs             (línea 318)
- _imprimir_resumen            (líneas 348-362)
- _consultar_api exception path (líneas 229-230)
"""
import json
import time
import pytest
import pandas as pd
import requests.exceptions
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def etapa3(config, logger_mock):
    from etapas.etapa3 import EnriquecedorAPI
    from core.context import PipelineContext
    stage = EnriquecedorAPI()
    ctx = PipelineContext(config=config)
    stage._context = ctx
    stage._logger = logger_mock
    stage.api_base_url = "https://api.example.com"
    stage.api_key = "FAKE"
    stage.delay_segundos = 0
    stage.max_reintentos = 1
    stage.timeout = 5
    stage.cache = {}
    stage.http = MagicMock()
    return stage


# ---------------------------------------------------------------------------
# _procesar_respuesta_api
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestProcesarRespuestaApi:

    def test_campos_simples(self, etapa3):
        datos_raw = {
            "Nombre": "Consultoría de Software",
            "Descripcion": "Desarrollo de sistema de gestión",
            "Estado": "Publicada",
            "CodigoEstado": "PU",
            "Moneda": "CLP",
            "MontoEstimado": 5000000,
            "UnidadTiempo": "Mes",
            "TiempoDuracionContrato": 6,
        }
        result = etapa3._procesar_respuesta_api(datos_raw)
        assert result["API_Nombre"] == "Consultoría de Software"
        assert result["API_Estado"] == "Publicada"
        assert result["API_Moneda"] == "CLP"
        assert result["API_Monto"] == 5000000

    def test_objeto_fechas_anidado(self, etapa3):
        datos_raw = {
            "Fechas": {
                "FechaPublicacion": "2026-01-01T08:00:00",
                "FechaCierre": "2026-02-01T17:00:00",
                "FechaInicio": "2026-03-01",
                "FechaFinal": "2026-09-01",
                "FechaPubRespuestas": "2026-01-15",
                "FechaActoAperturaTecnica": "2026-02-02",
                "FechaActoAperturaEconomica": "2026-02-03",
                "FechaAdjudicacion": "2026-02-10",
            }
        }
        result = etapa3._procesar_respuesta_api(datos_raw)
        assert result["API_FechaPublicacion"] == "2026-01-01T08:00:00"
        assert result["API_FechaCierre"] == "2026-02-01T17:00:00"
        assert result["API_FechaAdjudicacion"] == "2026-02-10"

    def test_objeto_comprador_anidado(self, etapa3):
        datos_raw = {
            "Comprador": {
                "RegionUnidad": "Metropolitana",
                "ComunaUnidad": "Santiago",
                "NombreUnidad": "Dirección de Tecnología",
            }
        }
        result = etapa3._procesar_respuesta_api(datos_raw)
        assert result["API_RegionUnidad"] == "Metropolitana"
        assert result["API_ComunaUnidad"] == "Santiago"
        assert result["API_NombreUnidad"] == "Dirección de Tecnología"

    def test_items_y_adjuntos(self, etapa3):
        datos_raw = {
            "Items": {"Listado": [{"id": 1}, {"id": 2}, {"id": 3}]},
            "Adjuntos": {"Listado": [{"archivo": "a.pdf"}, {"archivo": "b.pdf"}]},
        }
        result = etapa3._procesar_respuesta_api(datos_raw)
        assert result["API_TotalItems"] == 3
        assert result["API_TotalAdjuntos"] == 2

    def test_items_vacios(self, etapa3):
        datos_raw = {"Items": {}, "Adjuntos": {}}
        result = etapa3._procesar_respuesta_api(datos_raw)
        assert result["API_TotalItems"] == 0
        assert result["API_TotalAdjuntos"] == 0

    def test_items_none(self, etapa3):
        datos_raw = {"Items": None, "Adjuntos": None}
        result = etapa3._procesar_respuesta_api(datos_raw)
        assert result["API_TotalItems"] == 0
        assert result["API_TotalAdjuntos"] == 0

    def test_campos_ausentes_retornan_string_vacio(self, etapa3):
        result = etapa3._procesar_respuesta_api({})
        assert result["API_Nombre"] == ""
        assert result["API_FechaPublicacion"] == ""
        assert result["API_RegionUnidad"] == ""

    def test_fechas_none_en_objeto_anidado(self, etapa3):
        datos_raw = {"Fechas": None}
        result = etapa3._procesar_respuesta_api(datos_raw)
        assert result["API_FechaPublicacion"] == ""

    def test_comprador_none(self, etapa3):
        datos_raw = {"Comprador": None}
        result = etapa3._procesar_respuesta_api(datos_raw)
        assert result["API_RegionUnidad"] == ""

    def test_resultado_se_guarda_en_cache(self, etapa3):
        """_consultar_api guarda en caché el resultado de _procesar_respuesta_api."""
        datos_api = {"Listado": [{"Nombre": "TI Consultoría"}]}
        mock_resp = MagicMock()
        mock_resp.json.return_value = datos_api
        etapa3.http.get.return_value = mock_resp

        result = etapa3._consultar_api("LIC-CACHE")
        assert "LIC-CACHE" in etapa3.cache
        assert result["API_Nombre"] == "TI Consultoría"


# ---------------------------------------------------------------------------
# _limpiar_checkpoints_antiguos
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestLimpiarCheckpointsAntiguos:

    def test_no_elimina_archivos_recientes(self, etapa3, tmp_path):
        cp = tmp_path / "e3_checkpoint_abc123.jsonl"
        cp.write_text("{}")
        etapa3._limpiar_checkpoints_antiguos(tmp_path)
        assert cp.exists()

    def test_elimina_archivos_antiguos(self, etapa3, tmp_path, monkeypatch):
        cp = tmp_path / "e3_checkpoint_old.jsonl"
        cp.write_text("{}")
        # Simular mtime de 100 días atrás
        hace_100_dias = time.time() - (100 * 86400)
        import os
        os.utime(cp, (hace_100_dias, hace_100_dias))

        # Retention = 7 días por defecto
        etapa3._limpiar_checkpoints_antiguos(tmp_path)
        assert not cp.exists()

    def test_log_cuando_hay_eliminados(self, etapa3, tmp_path, logger_mock):
        import os
        cp = tmp_path / "e3_checkpoint_old2.jsonl"
        cp.write_text("{}")
        hace_100_dias = time.time() - (100 * 86400)
        os.utime(cp, (hace_100_dias, hace_100_dias))

        etapa3._limpiar_checkpoints_antiguos(tmp_path)
        logger_mock.info.assert_called()

    def test_directorio_vacio_no_crash(self, etapa3, tmp_path):
        etapa3._limpiar_checkpoints_antiguos(tmp_path)  # no debe lanzar excepción


# ---------------------------------------------------------------------------
# _cargar_licitaciones
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCargarLicitaciones:

    def test_detecta_columna_numero_adquisicion(self, etapa3, tmp_path, logger_mock):
        ruta = tmp_path / "filtradas.xlsx"
        df = pd.DataFrame({"Numero Adquisición": ["LIC-1", "LIC-2"], "Nombre": ["A", "B"]})
        df.to_excel(ruta, index=False)
        result = etapa3._cargar_licitaciones(ruta)
        assert len(result) == 2
        # Verifica que se logueó la columna de código
        calls = [str(c) for c in logger_mock.info.call_args_list]
        assert any("Numero Adquisición" in c for c in calls)

    def test_detecta_columna_codigo_alternativa(self, etapa3, tmp_path):
        ruta = tmp_path / "filtradas.xlsx"
        df = pd.DataFrame({"Codigo": ["LIC-1"], "Nombre": ["A"]})
        df.to_excel(ruta, index=False)
        result = etapa3._cargar_licitaciones(ruta)
        assert len(result) == 1

    def test_sin_columna_codigo_lanza_error(self, etapa3, tmp_path):
        ruta = tmp_path / "filtradas.xlsx"
        df = pd.DataFrame({"Nombre": ["A", "B"], "Monto": [100, 200]})
        df.to_excel(ruta, index=False)
        with pytest.raises(ValueError, match="columna con código"):
            etapa3._cargar_licitaciones(ruta)


# ---------------------------------------------------------------------------
# _generar_outputs
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGenerarOutputs:

    def test_genera_xlsx_con_datos(self, etapa3, config, monkeypatch):
        config.ENRIQUECIDO_DIR.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame({"Nombre": ["A", "B"], "Monto": [100, 200]})
        from utils import guardar_excel_con_formato
        with patch("etapas.etapa3.guardar_excel_con_formato") as mock_guardar:
            result = etapa3._generar_outputs(df)
        assert len(result) == 1
        assert isinstance(result[0], Path)
        mock_guardar.assert_called_once()

    def test_df_vacio_retorna_lista_vacia(self, etapa3):
        result = etapa3._generar_outputs(pd.DataFrame())
        assert result == []


# ---------------------------------------------------------------------------
# _imprimir_resumen
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestImprimirResumen:

    def test_no_crash_con_estadisticas_completas(self, etapa3, logger_mock):
        etapa3.estadisticas = {
            'total_registros': 10,
            'enriquecidos_ok': 8,
            'errores_registro': 2,
            'errores_fatales_etapa': 0,
            'llamadas_api': 9,
            'errores_http_500': 1,
            'tiempo_total': '0:00:30',
            'tiempo_inicio': None,
        }
        etapa3._imprimir_resumen()
        logger_mock.info.assert_called()

    def test_no_crash_con_total_cero(self, etapa3, logger_mock):
        """Sin registros no debe hacer división por cero."""
        etapa3.estadisticas = {
            'total_registros': 0,
            'enriquecidos_ok': 0,
            'errores_registro': 0,
            'errores_fatales_etapa': 0,
            'llamadas_api': 0,
            'errores_http_500': 0,
            'tiempo_total': '0:00:00',
            'tiempo_inicio': None,
        }
        etapa3._imprimir_resumen()
        logger_mock.info.assert_called()


# ---------------------------------------------------------------------------
# _consultar_api — ramas de excepción
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestConsultarApiExcepciones:

    def test_excepcion_con_response_500(self, etapa3):
        mock_e = requests.exceptions.HTTPError("Server Error")
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_e.response = mock_response

        etapa3.http.get.side_effect = mock_e
        result = etapa3._consultar_api("LIC-ERR500")
        assert result["_api_disponible"] is False
        assert etapa3.estadisticas["errores_http_500"] == 1

    def test_excepcion_con_response_404(self, etapa3):
        mock_e = requests.exceptions.HTTPError("Not Found")
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_e.response = mock_response

        etapa3.http.get.side_effect = mock_e
        result = etapa3._consultar_api("LIC-ERR404")
        assert result["_api_disponible"] is False
        # 404 no incrementa errores_http_500
        assert etapa3.estadisticas["errores_http_500"] == 0

    def test_excepcion_sin_response(self, etapa3):
        etapa3.http.get.side_effect = ConnectionError("timeout")
        result = etapa3._consultar_api("LIC-TIMEOUT")
        assert result["_api_disponible"] is False
        assert "timeout" in result["_api_error"]

    def test_listado_vacio_en_respuesta(self, etapa3):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"Listado": []}
        etapa3.http.get.return_value = mock_resp
        result = etapa3._consultar_api("LIC-EMPTY")
        assert result["_api_disponible"] is False
        assert result["_api_error"] == "Listado vacío"

    def test_cache_evita_segunda_llamada_api(self, etapa3):
        cached = {"API_Nombre": "Cached", "_api_disponible": True}
        etapa3.cache["LIC-CACHED"] = cached
        result = etapa3._consultar_api("LIC-CACHED")
        assert result == cached
        etapa3.http.get.assert_not_called()


# ---------------------------------------------------------------------------
# _enriquecer_licitaciones — ramas de checkpoint
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestEnriquecerCheckpointRamas:

    def test_checkpoint_con_linea_json_corrupta_se_ignora(self, etapa3, tmp_path, config):
        """Un checkpoint con una línea JSON inválida no debe crashear el enriquecimiento."""
        import hashlib

        df = pd.DataFrame({
            "Numero Adquisición": ["LIC-001"],
            "Nombre": ["Test"],
        })
        col_codigo = "Numero Adquisición"
        hash_ds = hashlib.sha256("LIC-001".encode()).hexdigest()

        checkpoint_dir = tmp_path / "temp" / "checkpoints"
        checkpoint_dir.mkdir(parents=True)
        checkpoint_file = checkpoint_dir / f"e3_checkpoint_{hash_ds}.jsonl"
        # Línea válida + línea corrupta
        checkpoint_file.write_text(
            '{"codigo": "LIC-001", "status": "success", "data": {"API_Nombre": "X"}}\n'
            'ESTO_NO_ES_JSON\n',
            encoding='utf-8'
        )

        etapa3.config.BASE_DIR = tmp_path
        # El segundo registro debería consultarse normalmente (fallback al api)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"Listado": [{"Nombre": "Desde API"}]}
        etapa3.http.get.return_value = mock_resp

        result = etapa3._enriquecer_licitaciones(df)
        assert len(result) == 1
        # LIC-001 debería venir del cache (checkpoint)
        assert result.iloc[0]["API_Nombre"] == "X"

    def test_checkpoint_recupera_registros_validos(self, etapa3, tmp_path):
        """Los registros 'success' del checkpoint se usan sin llamar a la API."""
        import hashlib

        df = pd.DataFrame({"Numero Adquisición": ["LIC-999"]})
        hash_ds = hashlib.sha256("LIC-999".encode()).hexdigest()

        checkpoint_dir = tmp_path / "temp" / "checkpoints"
        checkpoint_dir.mkdir(parents=True)
        cp = checkpoint_dir / f"e3_checkpoint_{hash_ds}.jsonl"
        cp.write_text(
            '{"codigo": "LIC-999", "status": "success", "data": {"API_Nombre": "Cached"}}\n',
            encoding='utf-8'
        )

        etapa3.config.BASE_DIR = tmp_path
        result = etapa3._enriquecer_licitaciones(df)

        # No debería haber llamado a la API
        etapa3.http.get.assert_not_called()
        assert result.iloc[0]["API_Nombre"] == "Cached"


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestMain:

    def test_main_retorna_0_en_exito(self):
        from etapas.etapa3 import main
        res_ok = MagicMock(success=True, metrics_produced={'enriquecidos_ok': 10})
        with patch('etapas.etapa3.EnriquecedorAPI') as MockStage:
            MockStage.return_value.run.return_value = res_ok
            rc = main()
        assert rc == 0

    def test_main_retorna_1_si_falla(self):
        from etapas.etapa3 import main
        res_fail = MagicMock(success=False, error_message="Error fatal")
        with patch('etapas.etapa3.EnriquecedorAPI') as MockStage:
            MockStage.return_value.run.return_value = res_fail
            rc = main()
        assert rc == 1

    def test_main_retorna_1_en_excepcion(self):
        from etapas.etapa3 import main
        with patch('etapas.etapa3.EnriquecedorAPI') as MockStage:
            MockStage.return_value.run.side_effect = RuntimeError("crash")
            rc = main()
        assert rc == 1
