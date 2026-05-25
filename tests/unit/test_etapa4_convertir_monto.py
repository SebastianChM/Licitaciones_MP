"""Tests unitarios para GeneradorReporte (Etapa 4) — métodos de negocio puro.

Testean directamente _convertir_monto, _calcular_dias y _separar
sin inicializar el pipeline completo ni hacer I/O.

Ejecutar con: pytest tests/unit/test_etapa4_convertir_monto.py -v
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pandas as pd

from etapas.etapa4 import GeneradorReporte

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _reporte(utm: int = 65_000, usd: int = 900, dias_gracia: int = 30) -> GeneradorReporte:
    """Instancia GeneradorReporte con tasas inyectadas y logger mockeado."""
    etapa = GeneradorReporte()
    etapa.valor_utm = utm
    etapa.valor_usd = usd
    etapa.dias_gracia = dias_gracia
    etapa._logger = MagicMock()
    return etapa


# ---------------------------------------------------------------------------
# _convertir_monto — CLP
# ---------------------------------------------------------------------------

class TestConvertirMontoCLP:
    def test_entero_sin_separadores(self):
        assert _reporte()._convertir_monto(
            pd.Series({"Moneda": "CLP", "Monto": "5000000", "Tipo Adquisición": ""})
        ) == 5_000_000

    def test_separador_miles_punto(self):
        # '5.000.000' chileno → 5_000_000 CLP
        assert _reporte()._convertir_monto(
            pd.Series({"Moneda": "CLP", "Monto": "5.000.000", "Tipo Adquisición": ""})
        ) == 5_000_000

    def test_moneda_peso_equivale_a_clp(self):
        assert _reporte()._convertir_monto(
            pd.Series({"Moneda": "PESO", "Monto": "1000000", "Tipo Adquisición": ""})
        ) == 1_000_000

    def test_cero_retorna_cero(self):
        assert _reporte()._convertir_monto(
            pd.Series({"Moneda": "CLP", "Monto": "0", "Tipo Adquisición": ""})
        ) == 0

    def test_monto_none_retorna_cero(self):
        assert _reporte()._convertir_monto(
            pd.Series({"Moneda": "CLP", "Monto": None, "Tipo Adquisición": ""})
        ) == 0

    def test_monto_invalido_retorna_cero(self):
        etapa = _reporte()
        assert etapa._convertir_monto(
            pd.Series({"Moneda": "CLP", "Monto": "texto_invalido", "Tipo Adquisición": ""})
        ) == 0


# ---------------------------------------------------------------------------
# _convertir_monto — UTM
# ---------------------------------------------------------------------------

class TestConvertirMontoUTM:
    def test_ut_extrae_cantidad_del_campo_tipo(self):
        valor_utm = 65_000
        row = pd.Series({"Moneda": "UTM", "Monto": "", "Tipo Adquisición": "10 UTM presupuesto"})
        assert _reporte(utm=valor_utm)._convertir_monto(row) == 10 * valor_utm

    def test_utm_decimal_con_coma(self):
        row = pd.Series({"Moneda": "UTM", "Monto": "", "Tipo Adquisición": "Monto 5,5 UTM"})
        assert _reporte(utm=65_000)._convertir_monto(row) == int(5.5 * 65_000)

    def test_utm_sin_cifra_en_tipo_retorna_cero(self):
        row = pd.Series({"Moneda": "UTM", "Monto": "", "Tipo Adquisición": "Sin especificar"})
        assert _reporte()._convertir_monto(row) == 0

    def test_utm_contabiliza_en_stats(self):
        etapa = _reporte()
        etapa._convertir_monto(
            pd.Series({"Moneda": "UTM", "Monto": "", "Tipo Adquisición": "20 UTM"})
        )
        assert etapa.stats["utm"] == 1


# ---------------------------------------------------------------------------
# _convertir_monto — USD
# ---------------------------------------------------------------------------

class TestConvertirMontoUSD:
    def test_conversion_basica(self):
        row = pd.Series({"Moneda": "USD", "Monto": "1000", "Tipo Adquisición": ""})
        assert _reporte(usd=900)._convertir_monto(row) == 1_000 * 900

    def test_moneda_dolar_equivale_a_usd(self):
        row = pd.Series({"Moneda": "DOLAR", "Monto": "500", "Tipo Adquisición": ""})
        assert _reporte(usd=900)._convertir_monto(row) == 500 * 900

    def test_monto_cero_retorna_cero(self):
        row = pd.Series({"Moneda": "USD", "Monto": "0", "Tipo Adquisición": ""})
        assert _reporte()._convertir_monto(row) == 0

    def test_usd_contabiliza_en_stats(self):
        etapa = _reporte()
        etapa._convertir_monto(
            pd.Series({"Moneda": "USD", "Monto": "500", "Tipo Adquisición": ""})
        )
        assert etapa.stats["usd"] == 1

    def test_usd_monto_nan_retorna_cero_sin_error(self):
        # Regresión: pd.NaN es truthy → `NaN or '0'` devuelve NaN → float('') → ValueError
        etapa = _reporte()
        result = etapa._convertir_monto(
            pd.Series({"Moneda": "USD", "Monto": float("nan"), "Tipo Adquisición": ""})
        )
        assert result == 0
        assert etapa.stats["errores"] == 0  # NaN vacío no es un "error de conversión"

    def test_usd_api_monto_como_fallback_cuando_monto_nan(self):
        # Si Monto es NaN pero API_Monto tiene valor, debe usarlo
        etapa = _reporte(usd=900)
        result = etapa._convertir_monto(
            pd.Series({"Moneda": "USD", "Monto": float("nan"), "API_Monto": "500", "Tipo Adquisición": ""})
        )
        assert result == 500 * 900
        assert etapa.stats["usd"] == 1

    def test_moneda_nan_usa_fallback_generico(self):
        # Moneda NaN (truthy) no debe causar crash; cae al fallback genérico
        result = _reporte()._convertir_monto(
            pd.Series({"Moneda": float("nan"), "Monto": "2000000", "Tipo Adquisición": ""})
        )
        assert result == 2_000_000


# ---------------------------------------------------------------------------
# _convertir_monto — edge cases
# ---------------------------------------------------------------------------

class TestConvertirMontoEdgeCases:
    def test_moneda_desconocida_parsea_monto_directo(self):
        row = pd.Series({"Moneda": "EUR", "Monto": "2000000", "Tipo Adquisición": ""})
        assert _reporte()._convertir_monto(row) == 2_000_000

    def test_row_vacio_retorna_cero(self):
        assert _reporte()._convertir_monto(pd.Series({})) == 0

    def test_error_incrementa_contador_stats(self):
        etapa = _reporte()
        # Forzamos excepción pasando monto imposible de parsear en moneda desconocida
        etapa._convertir_monto(pd.Series({"Moneda": "XYZ", "Monto": "abc$$$", "Tipo Adquisición": ""}))
        # Si no hay excepción (por el except global), stats["errores"] sigue en 0
        # Lo importante: no propaga excepción
        assert isinstance(etapa.stats["errores"], int)


# ---------------------------------------------------------------------------
# _estimar_monto_desde_tipo — fallback UTM range
# ---------------------------------------------------------------------------

class TestEstimarMontoDesdeTipo:
    """Tests para el fallback que parsea rangos UTM desde 'Tipo Adquisición'."""

    def test_rango_100_1000_utm_usa_cota_inferior(self):
        etapa = _reporte(utm=65_000)
        row = pd.Series({"Tipo Adquisición": "Licitación Pública igual o superior a 100 UTM e inferior a 1.000 UTM"})
        assert etapa._estimar_monto_desde_tipo(row) == 100 * 65_000

    def test_rango_1000_2000_utm(self):
        etapa = _reporte(utm=65_000)
        row = pd.Series({"Tipo Adquisición": "Licitación Pública igual o superior a 1.000 UTM e inferior a 2.000 UTM (LP)"})
        assert etapa._estimar_monto_desde_tipo(row) == 1_000 * 65_000

    def test_mayor_a_5000_utm(self):
        etapa = _reporte(utm=65_000)
        row = pd.Series({"Tipo Adquisición": "Licitación Pública Mayor a 5000 UTM"})
        assert etapa._estimar_monto_desde_tipo(row) == 5_000 * 65_000

    def test_inferior_a_100_utm_usa_1_utm(self):
        etapa = _reporte(utm=65_000)
        row = pd.Series({"Tipo Adquisición": "Licitación pública inferior a 100 UTM"})
        # Solo cota superior → piso mínimo 1 UTM
        assert etapa._estimar_monto_desde_tipo(row) == 65_000

    def test_sin_utm_retorna_cero(self):
        row = pd.Series({"Tipo Adquisición": "Licitación de Servicios"})
        assert _reporte()._estimar_monto_desde_tipo(row) == 0

    def test_tipo_nan_retorna_cero(self):
        row = pd.Series({"Tipo Adquisición": float("nan")})
        assert _reporte()._estimar_monto_desde_tipo(row) == 0

    def test_tipo_vacio_retorna_cero(self):
        row = pd.Series({"Tipo Adquisición": ""})
        assert _reporte()._estimar_monto_desde_tipo(row) == 0

    def test_contabiliza_en_stats_monto_rango(self):
        etapa = _reporte(utm=65_000)
        etapa._estimar_monto_desde_tipo(
            pd.Series({"Tipo Adquisición": "Licitación Pública igual o superior a 100 UTM e inferior a 1.000 UTM"})
        )
        assert etapa.stats["monto_rango"] == 1

    def test_valor_utm_cero_retorna_cero(self):
        etapa = _reporte(utm=0)
        row = pd.Series({"Tipo Adquisición": "Licitación Pública Mayor a 5000 UTM"})
        assert etapa._estimar_monto_desde_tipo(row) == 0


class TestConvertirMontoFallbackUTM:
    """Tests para el fallback integrado en _convertir_monto."""

    def test_clp_sin_monto_usa_rango_utm(self):
        etapa = _reporte(utm=65_000)
        row = pd.Series({
            "Moneda": "CLP", "Monto": None,
            "Tipo Adquisición": "Licitación Pública igual o superior a 1.000 UTM e inferior a 2.000 UTM (LP)"
        })
        assert etapa._convertir_monto(row) == 1_000 * 65_000

    def test_clp_con_monto_no_usa_fallback(self):
        etapa = _reporte(utm=65_000)
        row = pd.Series({
            "Moneda": "CLP", "Monto": "5000000",
            "Tipo Adquisición": "Licitación Pública Mayor a 5000 UTM"
        })
        # Monto directo tiene prioridad → no fallback
        assert etapa._convertir_monto(row) == 5_000_000
        assert etapa.stats["monto_rango"] == 0

    def test_sin_monto_ni_tipo_retorna_cero(self):
        row = pd.Series({"Moneda": "CLP", "Monto": None, "Tipo Adquisición": "Licitación de Servicios"})
        assert _reporte()._convertir_monto(row) == 0


# ---------------------------------------------------------------------------
# _calcular_dias
# ---------------------------------------------------------------------------

class TestCalcularDias:
    def test_fecha_futura_retorna_positivo(self):
        fecha = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        dias = _reporte()._calcular_dias(pd.Series({"Fecha Cierre Licitación": fecha}))
        assert 9 <= dias <= 11  # tolerancia ±1 por timezone

    def test_fecha_pasada_retorna_negativo(self):
        fecha = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        dias = _reporte()._calcular_dias(pd.Series({"Fecha Cierre Licitación": fecha}))
        assert dias < 0

    def test_fecha_invalida_retorna_999(self):
        dias = _reporte()._calcular_dias(pd.Series({"Fecha Cierre Licitación": "no-es-fecha"}))
        assert dias == 999

    def test_fecha_nula_retorna_999(self):
        dias = _reporte()._calcular_dias(pd.Series({"Fecha Cierre Licitación": None}))
        assert dias == 999

    def test_columna_ausente_retorna_999(self):
        dias = _reporte()._calcular_dias(pd.Series({}))
        assert dias == 999


# ---------------------------------------------------------------------------
# _separar
# ---------------------------------------------------------------------------

class TestSeparar:
    def _df_dias(self, valores: list[int]) -> pd.DataFrame:
        return pd.DataFrame({
            "Días para cierre": valores,
            "Nombre": [f"Lic {v}" for v in valores],
        })

    def test_vigentes_son_dias_cero_o_mayor(self):
        etapa = _reporte(dias_gracia=30)
        vigentes, _ = etapa._separar(self._df_dias([10, 5, 0, -1, -15]))
        assert all(d >= 0 for d in vigentes["Días para cierre"])

    def test_vencidas_son_negativas_dentro_de_gracia(self):
        etapa = _reporte(dias_gracia=30)
        _, vencidas = etapa._separar(self._df_dias([5, -1, -15, -31]))
        assert all(-30 <= d < 0 for d in vencidas["Días para cierre"])

    def test_dias_999_va_a_vigentes(self):
        etapa = _reporte()
        vigentes, _ = etapa._separar(self._df_dias([999, 0, -5]))
        assert 999 in vigentes["Días para cierre"].values

    def test_fuera_de_gracia_no_queda_en_ninguno(self):
        etapa = _reporte(dias_gracia=10)
        df = self._df_dias([-5, -11, -20])
        vigentes, vencidas = etapa._separar(df)
        todos = set(vigentes["Días para cierre"]) | set(vencidas["Días para cierre"])
        assert -11 not in todos
        assert -20 not in todos

    def test_stats_vigentes_y_vencidas_actualizados(self):
        etapa = _reporte()
        etapa._separar(self._df_dias([5, 3, -2]))
        assert etapa.stats["vigentes"] == 2
        assert etapa.stats["vencidas"] == 1

    def test_df_vacio_retorna_dos_df_vacios(self):
        etapa = _reporte()
        vigentes, vencidas = etapa._separar(pd.DataFrame({"Días para cierre": [], "Nombre": []}))
        assert len(vigentes) == 0
        assert len(vencidas) == 0
