"""Tests unitarios para src/utils/text_processing.py

Cubre las funciones críticas usadas en filtrado (Etapa 2) y auditoría (Etapa 1).
Ejecutar con: pytest tests/unit/test_text_processing.py -v
"""

import pytest
from utils.text_processing import (
    normalizar_texto,
    limpiar_texto_excel,
    calcular_similitud,
    encontrar_similares,
    contiene_palabras_clave,
    extraer_palabras_clave,
    limpiar_codigo_licitacion,
    truncar_texto,
)


# ---------------------------------------------------------------------------
# normalizar_texto
# ---------------------------------------------------------------------------

class TestNormalizarTexto:
    def test_mayusculas_por_defecto(self):
        assert normalizar_texto("consultoría") == "CONSULTORIA"

    def test_remueve_acentos(self):
        assert normalizar_texto("Licitación") == "LICITACION"

    def test_remueve_tildes_multiples(self):
        assert normalizar_texto("áéíóúÁÉÍÓÚ") == "AEIOUAEIOU"

    def test_normaliza_espacios_multiples(self):
        assert normalizar_texto("Hola   mundo") == "HOLA MUNDO"

    def test_strip_espacios_borde(self):
        assert normalizar_texto("  texto  ") == "TEXTO"

    def test_none_retorna_vacio(self):
        assert normalizar_texto(None) == ""

    def test_nan_retorna_vacio(self):
        import math
        assert normalizar_texto(float("nan")) == ""

    def test_string_vacio_retorna_vacio(self):
        assert normalizar_texto("") == ""

    def test_minusculas_cuando_uppercase_false(self):
        assert normalizar_texto("CONSULTORÍA", uppercase=False) == "consultoria"

    def test_numeros_se_preservan(self):
        assert normalizar_texto("2024-01-15") == "2024-01-15"

    def test_string_solo_espacios_retorna_vacio(self):
        assert normalizar_texto("    ") == ""


# ---------------------------------------------------------------------------
# limpiar_texto_excel
# ---------------------------------------------------------------------------

class TestLimpiarTextoExcel:
    def test_remueve_saltos_de_linea(self):
        assert limpiar_texto_excel("hola\nmundo") == "hola mundo"

    def test_remueve_tabulaciones(self):
        assert limpiar_texto_excel("col1\tcol2") == "col1 col2"

    def test_normaliza_espacios_multiples(self):
        assert limpiar_texto_excel("a    b") == "a b"

    def test_none_retorna_vacio(self):
        assert limpiar_texto_excel(None) == ""

    def test_texto_normal_sin_cambios(self):
        assert limpiar_texto_excel("Texto normal") == "Texto normal"

    def test_crlf_reemplazado(self):
        assert limpiar_texto_excel("linea1\r\nlinea2") == "linea1  linea2".replace("  ", " ")


# ---------------------------------------------------------------------------
# calcular_similitud
# ---------------------------------------------------------------------------

class TestCalcularSimilitud:
    def test_identicos_retorna_uno(self):
        assert calcular_similitud("consultoria", "consultoria") == 1.0

    def test_completamente_diferentes_baja_similitud(self):
        assert calcular_similitud("consultoria", "suministros") < 0.5

    def test_con_acento_y_sin_acento(self):
        # La función normaliza antes de comparar
        sim = calcular_similitud("Consultoría", "Consultoria")
        assert sim == 1.0

    def test_texto_vacio_retorna_cero(self):
        assert calcular_similitud("", "consultoria") == 0.0
        assert calcular_similitud("consultoria", "") == 0.0

    def test_ambos_vacios_retorna_cero(self):
        assert calcular_similitud("", "") == 0.0

    def test_similitud_parcial_es_intermedia(self):
        sim = calcular_similitud("ingenieria civil", "ingenieria mecanica")
        assert 0.5 < sim < 1.0


# ---------------------------------------------------------------------------
# encontrar_similares
# ---------------------------------------------------------------------------

class TestEncontrarSimilares:
    LISTA = ["Consultoría", "Consultoria", "Asesoría Técnica", "Suministros", "Ingeniería"]

    def test_encuentra_coincidencia_exacta(self):
        resultados = encontrar_similares("Consultoria", self.LISTA, umbral=0.95)
        textos = [r[0] for r in resultados]
        assert "Consultoria" in textos

    def test_ordenado_por_similitud_desc(self):
        resultados = encontrar_similares("Ingenieria", self.LISTA, umbral=0.8)
        if len(resultados) > 1:
            assert resultados[0][1] >= resultados[1][1]

    def test_respeta_umbral(self):
        resultados = encontrar_similares("Consultoria", self.LISTA, umbral=0.99)
        for _, sim in resultados:
            assert sim >= 0.99

    def test_lista_vacia_retorna_vacio(self):
        assert encontrar_similares("Consultoria", []) == []

    def test_valor_vacio_retorna_vacio(self):
        assert encontrar_similares("", self.LISTA) == []

    def test_respeta_max_resultados(self):
        resultados = encontrar_similares("Consultoría", self.LISTA, umbral=0.0, max_resultados=2)
        assert len(resultados) <= 2


# ---------------------------------------------------------------------------
# contiene_palabras_clave
# ---------------------------------------------------------------------------

class TestContienePalabrasClave:
    def test_or_una_coincidencia(self):
        assert contiene_palabras_clave("Servicios de consultoría", ["consultoria", "ingenieria"])

    def test_or_sin_coincidencia(self):
        assert not contiene_palabras_clave("Suministro de materiales", ["consultoria", "ingenieria"])

    def test_and_todas_coinciden(self):
        assert contiene_palabras_clave(
            "Consultoría en ingeniería civil",
            ["consultoria", "ingenieria"],
            operador="AND"
        )

    def test_and_solo_una_coincide(self):
        assert not contiene_palabras_clave(
            "Servicios de consultoría técnica",
            ["consultoria", "ingenieria"],
            operador="AND"
        )

    def test_ignora_acentos(self):
        assert contiene_palabras_clave("Licitación de Consultoría", ["licitacion"])

    def test_texto_vacio_retorna_false(self):
        assert not contiene_palabras_clave("", ["consultoria"])

    def test_lista_vacia_retorna_false(self):
        assert not contiene_palabras_clave("Texto cualquiera", [])

    def test_coincidencia_parcial_de_palabra(self):
        # "ingenieria" debe coincidir dentro de "servicios de ingenieria sanitaria"
        assert contiene_palabras_clave("Servicios de ingeniería sanitaria", ["ingenieria"])


# ---------------------------------------------------------------------------
# extraer_palabras_clave
# ---------------------------------------------------------------------------

class TestExtraerPalabrasClave:
    def test_extrae_palabras_minimas(self):
        palabras = extraer_palabras_clave("Consultoría de ingeniería civil")
        assert "consultoria" in palabras or "CONSULTORIA" in palabras or len(palabras) > 0

    def test_excluye_stopwords(self):
        palabras = extraer_palabras_clave("Servicios de la empresa")
        # "de" y "la" son stopwords
        assert "de" not in palabras
        assert "la" not in palabras

    def test_respeta_longitud_minima(self):
        palabras = extraer_palabras_clave("Un gran servicio", min_longitud=5)
        for p in palabras:
            assert len(p) >= 5

    def test_texto_vacio_retorna_set_vacio(self):
        assert extraer_palabras_clave("") == set()


# ---------------------------------------------------------------------------
# limpiar_codigo_licitacion
# ---------------------------------------------------------------------------

class TestLimpiarCodigoLicitacion:
    def test_remueve_espacios_alrededor_guion(self):
        from utils.text_processing import limpiar_codigo_licitacion
        resultado = limpiar_codigo_licitacion("1234 - 5678")
        assert " " not in resultado or resultado == "1234-5678"

    def test_codigo_limpio_sin_cambios(self):
        from utils.text_processing import limpiar_codigo_licitacion
        codigo = "1234-5678-LP22"
        assert limpiar_codigo_licitacion(codigo) == codigo


# ---------------------------------------------------------------------------
# truncar_texto
# ---------------------------------------------------------------------------

class TestTruncarTexto:
    def test_texto_corto_sin_truncar(self):
        from utils.text_processing import truncar_texto
        assert truncar_texto("Hola", 10) == "Hola"

    def test_texto_largo_se_trunca(self):
        from utils.text_processing import truncar_texto
        resultado = truncar_texto("A" * 200, 50)
        assert len(resultado) <= 53  # 50 + posible "..."

    def test_none_retorna_vacio(self):
        from utils.text_processing import truncar_texto
        assert truncar_texto(None, 50) == ""
