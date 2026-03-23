"""
Fixtures compartidos para toda la suite de tests.

Disponibles en tests/ y tests/unit/ sin import explícito (pytest los inyecta).
"""

import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Config y contexto
# ---------------------------------------------------------------------------

@pytest.fixture
def config():
    """Config con valores de test (no carga .env real)."""
    from utils.config import Config
    return Config(env="testing", TEST_MODE=True, TEST_LIMIT=10)


@pytest.fixture
def context(config):
    """PipelineContext limpio para cada test."""
    from core.context import PipelineContext
    ctx = PipelineContext(config=config)
    ctx.flags["allow_fallback"] = True
    return ctx


# ---------------------------------------------------------------------------
# DataFrames de muestra
# ---------------------------------------------------------------------------

COLS_LICITACION = [
    "Numero Adquisición",
    "Nombre Adquisición",
    "Descripción",
    "Nivel 1",
    "Nivel 2",
    "Nivel 3",
    "Genérico",
    "Organismo",
    "Tipo Adquisición",
    "Descripción del producto/servicio",
    "Monto",
    "Moneda",
]


@pytest.fixture
def df_licitaciones_minimo():
    """DataFrame con las columnas mínimas requeridas por las etapas (3 filas)."""
    filas = [
        ["2025-123-L1", "Consultoría TI infraestructura", "Servicios de consultoría tecnológica",
         "Servicios", "Tecnología", "Consultoría", "Software",
         "Ministerio de Obras Públicas", "Licitación Pública", "Consultoría TI", "5000000", "CLP"],
        ["2025-456-L1", "Construcción edificio público", "Obras civiles y construcción de edificio",
         "Obras", "Construcción", "Edificación", "Civil",
         "Municipalidad de Santiago", "Licitación Pública", "Construcción civil", "100000000", "CLP"],
        ["2025-789-L1", "Compra computadores escritorio", "Adquisición de equipos computacionales",
         "Bienes", "Tecnología", "Equipos", "Hardware",
         "Ministerio de Salud", "Compra Ágil", "Computadores", "2000000", "CLP"],
    ]
    return pd.DataFrame(filas, columns=COLS_LICITACION)


@pytest.fixture
def df_un_registro():
    """DataFrame de una sola fila — útil para tests de lógica de inclusión/exclusión."""
    return pd.DataFrame([
        ["TEST-001", "Consultoría en gestión de proyectos TI",
         "Asesoría técnica en gestión proyectos", "Servicios", "Consultoría",
         "Gestión", "Proyectos", "CORFO", "Licitación Pública", "Consultoría gestión",
         "8000000", "CLP"]
    ], columns=COLS_LICITACION)


@pytest.fixture
def filtros_incluir_ti():
    """Filtros de inclusión orientados a TI para tests de etapa2."""
    return {
        "incluir": {
            "nombre": ["consultoria", "tecnologia", "ti", "sistemas", "software"],
            "nivel1": ["servicios"],
            "nivel2": ["tecnologia"],
            "nivel3": [],
        },
        "excluir": {
            "nombre": [],
            "nivel1": [],
            "nivel2": [],
            "nivel3": [],
            "generico": [],
            "componente": [],
            "organismo": [],
            "valor": [],
        },
        "bypass": [],
    }


@pytest.fixture
def filtros_excluir_construccion():
    """Filtros de exclusión con 'construccion' en nombre para tests."""
    return {
        "incluir": {
            "nombre": ["consultoria", "tecnologia", "ti"],
            "nivel1": [],
            "nivel2": [],
            "nivel3": [],
        },
        "excluir": {
            "nombre": ["construccion", "obras", "edificio"],
            "nivel1": ["obras"],
            "nivel2": [],
            "nivel3": [],
            "generico": [],
            "componente": [],
            "organismo": [],
            "valor": [],
        },
        "bypass": ["corfo", "ministerio de salud"],
    }


# ---------------------------------------------------------------------------
# Archivos temporales
# ---------------------------------------------------------------------------

@pytest.fixture
def excel_licitaciones(tmp_path, df_licitaciones_minimo):
    """Excel temporal con el DataFrame mínimo de licitaciones."""
    ruta = tmp_path / "Licitacion_Publicada.xlsx"
    df_licitaciones_minimo.to_excel(ruta, index=False)
    return ruta


@pytest.fixture
def logger_mock():
    """Logger mockeado para tests que instancian etapas."""
    from utils.logger import ProjectLogger
    mock = MagicMock(spec=ProjectLogger)
    mock.info = MagicMock()
    mock.warning = MagicMock()
    mock.error = MagicMock()
    mock.section = MagicMock()
    mock.subsection = MagicMock()
    mock.progress = MagicMock()
    mock.finalize = MagicMock()
    return mock
