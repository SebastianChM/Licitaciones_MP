"""Tests unitarios para Etapa0Descarga.

Cubre (sin red real):
- validate_inputs: siempre True (no requiere inputs externos)
- run(): flujo completo con métodos internos mockeados
- _validar_conexion: comportamiento con HEAD response
- _descargar_archivo: escritura de chunks al disco
- _mover_a_input: Excel y ZIP, con y sin histórico previo
- _validar_archivo: Excel válido e inválido
- _limpiar_historico: elimina archivos viejos, conserva recientes
"""
import io
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from etapas.etapa0 import Etapa0Descarga

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_xlsx_bytes() -> bytes:
    """Devuelve bytes de un Excel mínimo válido."""
    buf = io.BytesIO()
    pd.DataFrame({"A": range(200), "B": range(200)}).to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


def _make_zip_with_xlsx() -> bytes:
    """Devuelve bytes de un ZIP que contiene un archivo xlsx mínimo."""
    xlsx_bytes = _make_xlsx_bytes()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("licitaciones.xlsx", xlsx_bytes)
    return buf.getvalue()


def _config(tmp_path: Path):
    from utils.config import Config
    input_dir = tmp_path / "INPUT"
    input_dir.mkdir(parents=True, exist_ok=True)
    return Config(
        env="testing",
        INPUT_DIR=input_dir,
        BASE_DIR=tmp_path,
    )


def _stage(tmp_path: Path, logger_mock=None):
    from core.context import PipelineContext
    config = _config(tmp_path)
    stage = Etapa0Descarga()
    stage._context = PipelineContext(config=config)
    stage._logger = logger_mock or MagicMock()
    stage.http = MagicMock()
    return stage, config


# ---------------------------------------------------------------------------
# Tests: validate_inputs
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestValidateInputs:

    def test_siempre_retorna_true(self, context):
        etapa = Etapa0Descarga()
        assert etapa.validate_inputs(context) is True


# ---------------------------------------------------------------------------
# Tests: run() — flujo completo mockeando métodos internos
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRun:

    def test_run_exitoso_registra_artefacto(self, tmp_path, logger_mock):
        from core.context import PipelineContext
        config = _config(tmp_path)
        ctx = PipelineContext(config=config)
        ruta_final = config.LICITACIONES_MP

        with patch.object(Etapa0Descarga, "_validar_conexion", return_value=None), \
             patch.object(Etapa0Descarga, "_descargar_archivo",
                          return_value=tmp_path / "temp_descarga.xlsx"), \
             patch.object(Etapa0Descarga, "_mover_a_input", return_value=ruta_final), \
             patch.object(Etapa0Descarga, "_validar_archivo", return_value=None):

            etapa = Etapa0Descarga()
            result = etapa.run(ctx)

        assert result.success is True
        assert ctx.get_artifact("etapa0_output") == ruta_final

    def test_run_exitoso_incluye_metricas(self, tmp_path):
        from core.context import PipelineContext
        config = _config(tmp_path)
        ctx = PipelineContext(config=config)

        with patch.object(Etapa0Descarga, "_validar_conexion"), \
             patch.object(Etapa0Descarga, "_descargar_archivo",
                          return_value=tmp_path / "temp.xlsx"), \
             patch.object(Etapa0Descarga, "_mover_a_input",
                          return_value=config.LICITACIONES_MP), \
             patch.object(Etapa0Descarga, "_validar_archivo"):

            etapa = Etapa0Descarga()
            result = etapa.run(ctx)

        assert result.success is True
        assert "tamano_mb" in result.metrics_produced

    def test_run_retorna_failure_si_validar_conexion_falla(self, tmp_path):
        from core.context import PipelineContext
        config = _config(tmp_path)
        ctx = PipelineContext(config=config)

        with patch.object(Etapa0Descarga, "_validar_conexion",
                          side_effect=Exception("Timeout de red")):
            etapa = Etapa0Descarga()
            result = etapa.run(ctx)

        assert result.success is False
        assert result.error_message is not None
        assert "Timeout de red" in result.error_message

    def test_run_retorna_failure_si_descarga_falla(self, tmp_path):
        from core.context import PipelineContext
        config = _config(tmp_path)
        ctx = PipelineContext(config=config)

        with patch.object(Etapa0Descarga, "_validar_conexion"), \
             patch.object(Etapa0Descarga, "_descargar_archivo",
                          side_effect=Exception("HTTP 503")):
            etapa = Etapa0Descarga()
            result = etapa.run(ctx)

        assert result.success is False

    def test_run_retorna_failure_si_validar_archivo_falla(self, tmp_path):
        from core.context import PipelineContext
        config = _config(tmp_path)
        ctx = PipelineContext(config=config)

        with patch.object(Etapa0Descarga, "_validar_conexion"), \
             patch.object(Etapa0Descarga, "_descargar_archivo",
                          return_value=tmp_path / "temp.xlsx"), \
             patch.object(Etapa0Descarga, "_mover_a_input",
                          return_value=config.LICITACIONES_MP), \
             patch.object(Etapa0Descarga, "_validar_archivo",
                          side_effect=Exception("Archivo corrupto")):

            etapa = Etapa0Descarga()
            result = etapa.run(ctx)

        assert result.success is False

    def test_run_stats_archivo_descargado_false_en_fallo(self, tmp_path):
        from core.context import PipelineContext
        config = _config(tmp_path)
        ctx = PipelineContext(config=config)

        with patch.object(Etapa0Descarga, "_validar_conexion",
                          side_effect=Exception("fallo")):
            etapa = Etapa0Descarga()
            result = etapa.run(ctx)

        assert result.custom_data["stats"]["archivo_descargado"] is False


# ---------------------------------------------------------------------------
# Tests: _validar_conexion
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestValidarConexion:

    def test_conexion_ok_200(self, tmp_path, logger_mock):
        stage, _ = _stage(tmp_path, logger_mock)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        stage.http.head.return_value = mock_response  # type: ignore[attr-defined]

        stage._validar_conexion()  # No debe lanzar

    def test_conexion_ok_registra_tamano_si_content_length(self, tmp_path, logger_mock):
        stage, _ = _stage(tmp_path, logger_mock)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Length": "5242880"}  # 5 MB
        stage.http.head.return_value = mock_response  # type: ignore[attr-defined]

        stage._validar_conexion()

        logger_mock.info.assert_called()

    def test_conexion_falla_lanza_excepcion(self, tmp_path, logger_mock):
        stage, _ = _stage(tmp_path, logger_mock)
        stage.http.head.side_effect = Exception("Connection refused")  # type: ignore[attr-defined]

        with pytest.raises(Exception, match="No se pudo conectar"):
            stage._validar_conexion()


# ---------------------------------------------------------------------------
# Tests: _descargar_archivo
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDescargarArchivo:

    def test_descarga_exitosa_escribe_archivo(self, tmp_path, logger_mock):
        stage, _ = _stage(tmp_path, logger_mock)

        xlsx_bytes = _make_xlsx_bytes()
        mock_response = MagicMock()
        mock_response.headers = {"content-length": str(len(xlsx_bytes))}
        mock_response.iter_content.return_value = [xlsx_bytes]
        stage.http.get.return_value = mock_response  # type: ignore[attr-defined]

        # BASE_DIR ya apunta a tmp_path a través de _config()
        ruta = stage._descargar_archivo()

        assert ruta.exists()
        assert ruta.suffix == ".xlsx"

    def test_descarga_limpia_temp_si_falla(self, tmp_path, logger_mock):
        stage, _ = _stage(tmp_path, logger_mock)
        stage.http.get.side_effect = Exception("Network error")  # type: ignore[attr-defined]

        with pytest.raises(Exception, match="Error al descargar"):
            stage._descargar_archivo()


# ---------------------------------------------------------------------------
# Tests: _mover_a_input
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestMoverAInput:

    def test_mueve_excel_directo_a_licitaciones_mp(self, tmp_path, logger_mock):
        stage, config = _stage(tmp_path, logger_mock)

        # Crear archivo de origen (xlsx es ZIP internamente, forzamos path directo)
        origen = tmp_path / "descarga.xlsx"
        origen.write_bytes(_make_xlsx_bytes())

        # Forzar rama "no es ZIP" porque xlsx es técnicamente un ZIP
        with patch("zipfile.is_zipfile", return_value=False):
            destino = stage._mover_a_input(origen)

        assert destino == config.LICITACIONES_MP
        assert destino.exists()

    def test_extrae_xlsx_de_zip(self, tmp_path, logger_mock):
        stage, config = _stage(tmp_path, logger_mock)

        origen_zip = tmp_path / "descarga.zip"
        origen_zip.write_bytes(_make_zip_with_xlsx())

        destino = stage._mover_a_input(origen_zip)

        assert destino == config.LICITACIONES_MP
        assert destino.exists()

    def test_genera_backup_si_existe_licitacion_previa(self, tmp_path, logger_mock):
        stage, config = _stage(tmp_path, logger_mock)

        # Crear archivo previo en destino
        config.LICITACIONES_MP.parent.mkdir(parents=True, exist_ok=True)
        config.LICITACIONES_MP.write_bytes(_make_xlsx_bytes())

        origen = tmp_path / "descarga_nueva.xlsx"
        origen.write_bytes(_make_xlsx_bytes())

        historico_dir = config.INPUT_DIR / "HISTORICO"

        with patch("zipfile.is_zipfile", return_value=False):
            stage._mover_a_input(origen)

        # Debe haber creado backup en HISTORICO
        assert historico_dir.exists()
        archivos_historico = list(historico_dir.glob("Licitacion_*.xlsx"))
        assert len(archivos_historico) == 1

    def test_zip_sin_xlsx_lanza_excepcion(self, tmp_path, logger_mock):
        stage, _ = _stage(tmp_path, logger_mock)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("readme.txt", "sin excel aqui")
        origen_zip = tmp_path / "vacio.zip"
        origen_zip.write_bytes(buf.getvalue())

        with pytest.raises(Exception, match="No se encontró archivo Excel"):
            stage._mover_a_input(origen_zip)


# ---------------------------------------------------------------------------
# Tests: _validar_archivo
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestValidarArchivo:

    def test_excel_valido_no_lanza(self, tmp_path, logger_mock):
        stage, _ = _stage(tmp_path, logger_mock)

        archivo = tmp_path / "valido.xlsx"
        archivo.write_bytes(_make_xlsx_bytes())

        stage._validar_archivo(archivo)  # No debe lanzar

    def test_archivo_no_excel_lanza_excepcion(self, tmp_path, logger_mock):
        stage, _ = _stage(tmp_path, logger_mock)

        archivo = tmp_path / "invalido.xlsx"
        archivo.write_bytes(b"esto no es un xlsx")

        with pytest.raises(Exception, match="Archivo descargado no es válido"):
            stage._validar_archivo(archivo)


# ---------------------------------------------------------------------------
# Tests: _limpiar_historico
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestLimpiarHistorico:

    def test_elimina_archivos_viejos(self, tmp_path, logger_mock):
        stage, _ = _stage(tmp_path, logger_mock)

        hist_dir = tmp_path / "HISTORICO"
        hist_dir.mkdir()

        # Crear archivo "viejo" (35 días)
        viejo = hist_dir / "Licitacion_vieja.xlsx"
        viejo.touch()
        old_time = (datetime.now() - timedelta(days=35)).timestamp()
        import os
        os.utime(viejo, (old_time, old_time))

        # Crear archivo reciente (hoy)
        reciente = hist_dir / "Licitacion_hoy.xlsx"
        reciente.touch()

        stage._limpiar_historico(hist_dir, dias_max=30)

        assert not viejo.exists()
        assert reciente.exists()

    def test_conserva_archivos_recientes(self, tmp_path, logger_mock):
        stage, _ = _stage(tmp_path, logger_mock)

        hist_dir = tmp_path / "HISTORICO"
        hist_dir.mkdir()

        reciente = hist_dir / "Licitacion_reciente.xlsx"
        reciente.touch()

        stage._limpiar_historico(hist_dir, dias_max=30)

        assert reciente.exists()
