"""Tests unitarios para utils.user_config."""
import json

import pytest

from utils.user_config import UserConfig


@pytest.mark.unit
class TestUserConfig:

    def test_carga_devuelve_defaults_si_no_existe(self, tmp_path):
        ruta = tmp_path / "no_existe.json"
        cfg = UserConfig.cargar(ruta)
        assert cfg.equipo_seleccionado == ""

    def test_guardar_y_recargar(self, tmp_path):
        ruta = tmp_path / "subdir" / "config.json"
        UserConfig(equipo_seleccionado="ARQ").guardar(ruta)
        assert ruta.exists()
        cfg = UserConfig.cargar(ruta)
        assert cfg.equipo_seleccionado == "ARQ"

    def test_archivo_corrupto_devuelve_defaults(self, tmp_path):
        ruta = tmp_path / "corrupto.json"
        ruta.write_text("{esto no es json", encoding="utf-8")
        cfg = UserConfig.cargar(ruta)
        assert cfg.equipo_seleccionado == ""

    def test_archivo_no_dict_devuelve_defaults(self, tmp_path):
        ruta = tmp_path / "lista.json"
        ruta.write_text("[1,2,3]", encoding="utf-8")
        cfg = UserConfig.cargar(ruta)
        assert cfg.equipo_seleccionado == ""

    def test_ruta_default_apunta_a_localappdata(self, monkeypatch, tmp_path):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        # Debemos forzar recálculo: ruta_default() llama a _ruta_default()
        ruta = UserConfig.ruta_default()
        assert str(tmp_path) in str(ruta)
        assert ruta.name == "config_usuario.json"

    def test_persistencia_es_utf8(self, tmp_path):
        ruta = tmp_path / "cfg.json"
        UserConfig(equipo_seleccionado="ÉLEC").guardar(ruta)
        data = json.loads(ruta.read_text(encoding="utf-8"))
        assert data["equipo_seleccionado"] == "ÉLEC"
