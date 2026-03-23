"""Tests unitarios para la lógica de conversión de montos en Etapa 4.

No instancia GeneradorReporte completo (requiere contexto).
Extrae y testea la lógica pura de _convertir_monto directamente.

Ejecutar con: pytest tests/unit/test_monto_conversion.py -v
"""

import re
import pytest
import pandas as pd


# ---------------------------------------------------------------------------
# Lógica pura extraída de GeneradorReporte._convertir_monto
# Copiada aquí para permitir tests sin instanciar toda la etapa.
# Si la función original cambia, actualizar este helper también.
# ---------------------------------------------------------------------------

REGEX_NUMERO = r'[^\d.]'
VALOR_UTM_TEST = 65_000
VALOR_USD_TEST = 900


def _convertir_monto(row: pd.Series, valor_utm: int = VALOR_UTM_TEST, valor_usd: int = VALOR_USD_TEST) -> int:
    """Réplica de GeneradorReporte._convertir_monto para tests aislados."""
    try:
        moneda = str(row.get('Moneda', '')).upper().strip()

        if moneda in ('CLP', 'PESO'):
            # Strips ALL non-digit characters — handles '5.000.000' thousands separators
            monto_str = re.sub(r'[^\d]', '', str(row.get('Monto', '0')))
            return int(monto_str) if monto_str else 0

        if 'UTM' in moneda:
            tipo = str(row.get('Tipo Adquisición', ''))
            nums = re.findall(r'(\d+(?:\.\d+)?)', tipo.replace('.', '').replace(',', '.'))
            if nums:
                return int(float(nums[0]) * valor_utm)

        if moneda in ('USD', 'DOLAR'):
            monto = float(re.sub(REGEX_NUMERO, '', str(row.get('Monto', '0'))))
            if monto > 0:
                return int(monto * valor_usd)

        # Fallback: intentar parsear el monto directamente
        monto_str = re.sub(r'[^\d]', '', str(row.get('Monto', '0')))
        return int(monto_str) if monto_str else 0
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Tests CLP
# ---------------------------------------------------------------------------

class TestConversionCLP:
    def test_entero_clp(self):
        row = pd.Series({'Moneda': 'CLP', 'Monto': '5000000'})
        assert _convertir_monto(row) == 5_000_000

    def test_clp_con_separador_miles(self):
        row = pd.Series({'Moneda': 'CLP', 'Monto': '5.000.000'})
        # El regex elimina puntos, queda "5000000"
        assert _convertir_monto(row) == 5_000_000

    def test_peso_como_moneda(self):
        row = pd.Series({'Moneda': 'PESO', 'Monto': '1000000'})
        assert _convertir_monto(row) == 1_000_000

    def test_clp_cero(self):
        row = pd.Series({'Moneda': 'CLP', 'Monto': '0'})
        assert _convertir_monto(row) == 0

    def test_clp_monto_vacio_retorna_cero(self):
        row = pd.Series({'Moneda': 'CLP', 'Monto': ''})
        assert _convertir_monto(row) == 0


# ---------------------------------------------------------------------------
# Tests UTM
# ---------------------------------------------------------------------------

class TestConversionUTM:
    def test_utm_extrae_cantidad_de_tipo(self):
        # "10 UTM" → 10 * 65000 = 650000
        row = pd.Series({'Moneda': 'UTM', 'Monto': '10', 'Tipo Adquisición': 'Monto 10 UTM'})
        assert _convertir_monto(row) == 10 * VALOR_UTM_TEST

    def test_utm_decimal(self):
        row = pd.Series({'Moneda': 'UTM', 'Monto': '5.5', 'Tipo Adquisición': 'Presupuesto 5,5 UTM'})
        resultado = _convertir_monto(row)
        assert resultado == int(5.5 * VALOR_UTM_TEST)

    def test_utm_sin_cantidad_en_tipo_retorna_cero(self):
        row = pd.Series({'Moneda': 'UTM', 'Monto': '', 'Tipo Adquisición': 'Sin monto especificado'})
        assert _convertir_monto(row) == 0


# ---------------------------------------------------------------------------
# Tests USD
# ---------------------------------------------------------------------------

class TestConversionUSD:
    def test_usd_conversion_basica(self):
        row = pd.Series({'Moneda': 'USD', 'Monto': '1000', 'Tipo Adquisición': ''})
        assert _convertir_monto(row) == 1000 * VALOR_USD_TEST

    def test_dolar_como_moneda(self):
        row = pd.Series({'Moneda': 'DOLAR', 'Monto': '500', 'Tipo Adquisición': ''})
        assert _convertir_monto(row) == 500 * VALOR_USD_TEST

    def test_usd_cero_retorna_cero(self):
        row = pd.Series({'Moneda': 'USD', 'Monto': '0', 'Tipo Adquisición': ''})
        assert _convertir_monto(row) == 0


# ---------------------------------------------------------------------------
# Tests fallback / edge cases
# ---------------------------------------------------------------------------

class TestConversionEdgeCases:
    def test_moneda_desconocida_parsea_monto_directo(self):
        row = pd.Series({'Moneda': 'EUR', 'Monto': '2000000', 'Tipo Adquisición': ''})
        assert _convertir_monto(row) == 2_000_000

    def test_monto_none_retorna_cero(self):
        row = pd.Series({'Moneda': 'CLP', 'Monto': None})
        assert _convertir_monto(row) == 0

    def test_monto_texto_invalido_retorna_cero(self):
        row = pd.Series({'Moneda': 'CLP', 'Monto': 'no es un número'})
        assert _convertir_monto(row) == 0

    def test_sin_columna_moneda_usa_fallback(self):
        row = pd.Series({'Monto': '3000000'})
        assert _convertir_monto(row) == 3_000_000

    def test_row_vacio_retorna_cero(self):
        row = pd.Series({})
        assert _convertir_monto(row) == 0
