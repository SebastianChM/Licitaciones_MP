"""Tests unitarios para el sistema de scoring de Etapa 4.

Cubre las 4 dimensiones (relevancia, monto, urgencia, limpieza),
la función integradora _aplicar_scoring y los conteos de etapa2.
"""
from unittest.mock import MagicMock

import pandas as pd
import pytest

from etapas.etapa4 import GeneradorReporte

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def gen() -> GeneradorReporte:
    """Instancia de GeneradorReporte sin inicialización HTTP."""
    g = GeneradorReporte()
    g.valor_utm = 65_000
    g.valor_usd = 950
    g._logger = MagicMock()
    return g


# ═══════════════════════════════════════════════════════════════════════════
# _score_relevancia
# ═══════════════════════════════════════════════════════════════════════════

class TestScoreRelevancia:
    """Score basado en cantidad de keywords matcheadas + bonus ALTA."""

    @pytest.mark.parametrize("n_matches, confianza, esperado", [
        (0, "BAJA", 3.0),    # 0 → umbral 1 → base 3.0
        (1, "BAJA", 3.0),    # 1 kw
        (2, "BAJA", 5.0),    # 2 kw
        (3, "BAJA", 6.5),    # 3 kw
        (4, "BAJA", 7.5),    # 4 kw
        (5, "BAJA", 8.0),    # 5+ kw
        (10, "BAJA", 8.0),   # muchos kw, sin bonus
    ])
    def test_sin_bonus(self, gen: GeneradorReporte, n_matches: int, confianza: str, esperado: float) -> None:
        assert gen._score_relevancia(n_matches, confianza) == esperado

    @pytest.mark.parametrize("n_matches, esperado", [
        (1, 5.0),   # 3.0 + 2.0
        (2, 7.0),   # 5.0 + 2.0
        (3, 8.5),   # 6.5 + 2.0
        (4, 9.5),   # 7.5 + 2.0
        (5, 10.0),  # 8.0 + 2.0 = 10.0 (capped)
        (8, 10.0),  # 8.0 + 2.0 = 10.0 (capped)
    ])
    def test_con_bonus_alta(self, gen: GeneradorReporte, n_matches: int, esperado: float) -> None:
        assert gen._score_relevancia(n_matches, "ALTA") == esperado

    def test_confianza_vacia(self, gen: GeneradorReporte) -> None:
        assert gen._score_relevancia(2, "") == 5.0

    def test_confianza_media(self, gen: GeneradorReporte) -> None:
        assert gen._score_relevancia(2, "MEDIA") == 5.0


# ═══════════════════════════════════════════════════════════════════════════
# _score_monto
# ═══════════════════════════════════════════════════════════════════════════

class TestScoreMonto:
    """Score por tramos de monto CLP."""

    @pytest.mark.parametrize("monto, esperado", [
        (0, 1.0),                # sin monto
        (-100, 1.0),             # negativo → 1.0
        (1_000_000, 1.0),        # < 100 UTM (~6.5M)
        (6_500_000, 1.0),        # exacto 100 UTM boundary
        (6_500_001, 3.0),        # primer peso sobre 100 UTM
        (65_000_000, 3.0),       # exacto 1.000 UTM boundary
        (65_000_001, 5.0),       # sobre 1.000 UTM
        (325_000_000, 5.0),      # exacto 5.000 UTM
        (325_000_001, 7.0),      # sobre 5.000 UTM
        (650_000_000, 7.0),      # exacto 10.000 UTM
        (650_000_001, 8.5),      # sobre 10.000 UTM
        (1_300_000_000, 8.5),    # exacto 20.000 UTM
        (1_300_000_001, 10.0),   # sobre 20.000 UTM
        (5_000_000_000, 10.0),   # muy alto
    ])
    def test_tramos(self, gen: GeneradorReporte, monto: int, esperado: float) -> None:
        assert gen._score_monto(monto) == esperado


# ═══════════════════════════════════════════════════════════════════════════
# _score_urgencia
# ═══════════════════════════════════════════════════════════════════════════

class TestScoreUrgencia:
    """Score por días para cierre."""

    @pytest.mark.parametrize("dias, esperado", [
        (-5, 1.0),       # vencida → 1.0
        (-1, 1.0),       # vencida ayer → 1.0
        (0, 2.0),        # hoy
        (1, 2.0),        # mañana
        (2, 2.0),        # demasiado pronto
        (3, 5.0),        # urgente pero posible
        (5, 5.0),        # urgente pero posible
        (6, 10.0),       # sweet spot
        (10, 10.0),      # sweet spot
        (15, 10.0),      # último día sweet spot
        (16, 10.0),      # 16+ → mantiene 10.0
        (30, 10.0),      # 30 días → 10.0
        (100, 10.0),     # lejos → 10.0
        (999, 3.0),      # sin fecha
    ])
    def test_tramos(self, gen: GeneradorReporte, dias: int, esperado: float) -> None:
        assert gen._score_urgencia(dias) == esperado


# ═══════════════════════════════════════════════════════════════════════════
# _score_limpieza
# ═══════════════════════════════════════════════════════════════════════════

class TestScoreLimpieza:
    """Score inversamente proporcional a exclusiones cercanas."""

    @pytest.mark.parametrize("n_excl, esperado", [
        (0, 10.0),
        (1, 8.0),
        (2, 6.0),
        (3, 4.0),
        (4, 2.0),
        (5, 2.0),
        (10, 2.0),
    ])
    def test_tramos(self, gen: GeneradorReporte, n_excl: int, esperado: float) -> None:
        assert gen._score_limpieza(n_excl) == esperado


# ═══════════════════════════════════════════════════════════════════════════
# _aplicar_scoring (integración)
# ═══════════════════════════════════════════════════════════════════════════

class TestAplicarScoring:
    """Test de integración para _aplicar_scoring: calcula y ordena."""

    @staticmethod
    def _make_df(
        montos: list[int],
        dias: list[int],
        confianza: list[str] | None = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Crea par (df_procesado, df_raw) minimal para _aplicar_scoring."""
        n = len(montos)
        confianza = confianza or ["BAJA"] * n
        df = pd.DataFrame({
            "Score": [""] * n,
            "Numero Adquisición": [f"TEST-{i:03d}" for i in range(n)],
            "Nombre": [f"Licitación {i}" for i in range(n)],
            "Monto Estimado (CLP)": montos,
            "Días para cierre": dias,
            "Nivel Confianza": confianza,
        })
        df_raw = pd.DataFrame({
            "_n_matches_inclusion": [2] * n,
            "_n_exclusiones_cercanas": [0] * n,
        })
        return df, df_raw

    def test_score_column_exists(self, gen: GeneradorReporte) -> None:
        df, df_raw = self._make_df([5_000_000], [10])
        result = gen._aplicar_scoring(df, df_raw)
        assert "Score" in result.columns
        assert result["Score"].iloc[0] > 0

    def test_sorted_descending(self, gen: GeneradorReporte) -> None:
        df, df_raw = self._make_df(
            [1_000_000, 2_000_000_000, 50_000_000],
            [10, 10, 10],
        )
        result = gen._aplicar_scoring(df, df_raw)
        scores = result["Score"].tolist()
        assert scores == sorted(scores, reverse=True)

    def test_alta_confianza_boost(self, gen: GeneradorReporte) -> None:
        """ALTA confianza debe dar score mayor que BAJA, mismas condiciones."""
        df_baja, raw_baja = self._make_df([100_000_000], [10], ["BAJA"])
        df_alta, raw_alta = self._make_df([100_000_000], [10], ["ALTA"])
        s_baja = gen._aplicar_scoring(df_baja, raw_baja)["Score"].iloc[0]
        s_alta = gen._aplicar_scoring(df_alta, raw_alta)["Score"].iloc[0]
        assert s_alta > s_baja

    def test_empty_df(self, gen: GeneradorReporte) -> None:
        df = pd.DataFrame(columns=["Score", "Monto Estimado (CLP)", "Días para cierre", "Nivel Confianza"])
        df_raw = pd.DataFrame(columns=["_n_matches_inclusion", "_n_exclusiones_cercanas"])
        result = gen._aplicar_scoring(df, df_raw)
        assert len(result) == 0
        assert "Score" in result.columns

    def test_missing_raw_columns(self, gen: GeneradorReporte) -> None:
        """Si df_raw no tiene columnas de scoring, usa 0."""
        df, _ = self._make_df([100_000_000], [10])
        df_raw = pd.DataFrame({"otro": [1]})
        result = gen._aplicar_scoring(df, df_raw)
        assert result["Score"].iloc[0] > 0

    def test_score_rango_valido(self, gen: GeneradorReporte) -> None:
        """Todos los scores deben estar en [1.0, 10.0]."""
        df, df_raw = self._make_df(
            [0, 1_000, 100_000_000, 5_000_000_000],
            [999, -5, 10, 30],
            ["BAJA", "ALTA", "ALTA", "BAJA"],
        )
        result = gen._aplicar_scoring(df, df_raw)
        for s in result["Score"]:
            assert 1.0 <= s <= 10.0, f"Score {s} fuera de rango"

    def test_pesos_suman_uno(self) -> None:
        total = sum(GeneradorReporte.SCORE_PESOS.values())
        assert abs(total - 1.0) < 1e-9

    def test_score_un_decimal(self, gen: GeneradorReporte) -> None:
        """Score redondeado a 1 decimal."""
        df, df_raw = self._make_df([100_000_000], [10])
        result = gen._aplicar_scoring(df, df_raw)
        score = result["Score"].iloc[0]
        assert score == round(score, 1)


# ═══════════════════════════════════════════════════════════════════════════
# Conteos etapa2 (_n_matches_inclusion, _contar_exclusiones_cercanas)
# ═══════════════════════════════════════════════════════════════════════════

class TestConteosEtapa2:
    """Verifica que etapa2 produce las columnas auxiliares para scoring."""

    def test_n_matches_vacio(self) -> None:
        """DataFrame vacío produce columna _n_matches_inclusion vacía."""
        from etapas.etapa2 import FiltradorLicitaciones
        etapa = FiltradorLicitaciones()
        etapa._logger = MagicMock()
        # Simular _aplicar_inclusion sobre DF que no matchea nada
        df = pd.DataFrame({
            "Nombre Adquisición (norm)": ["xyzzy"],
            "Nivel 1 (norm)": [""],
            "Nivel 2 (norm)": [""],
            "Nivel 3 (norm)": [""],
        })
        etapa.profile = type("P", (), {
            "incluir": {"nombre": ["consultoria"], "nivel1": [], "nivel2": [], "nivel3": []},
        })()
        result = etapa._aplicar_inclusion(df)
        assert len(result) == 0
        assert "_n_matches_inclusion" in result.columns
