"""Funciones de normalización y búsqueda de texto para el pipeline."""

import difflib
import re
import unicodedata
from typing import Any

import pandas as pd


def normalizar_texto(texto: Any, uppercase: bool = True, remover_espacios_extra: bool = True) -> str:
    """Normaliza texto removiendo acentos y caracteres especiales"""
    # Manejar valores nulos o NaN
    if pd.isna(texto) or texto is None:
        return ""
    
    # Convertir a string
    texto = str(texto).strip()
    
    # Si está vacío después del strip, retornar vacío
    if not texto:
        return ""
    
    # Normalizar unicode (NFD) y remover acentos
    texto = unicodedata.normalize('NFKD', texto)
    texto = texto.encode('ascii', 'ignore').decode('ascii')
    
    # Remover espacios múltiples
    if remover_espacios_extra:
        texto = re.sub(r'\s+', ' ', texto).strip()
    
    # Convertir a mayúsculas o minúsculas
    return texto.upper() if uppercase else texto.lower()


def limpiar_texto_excel(texto: Any) -> str:
    """Limpia texto de celdas Excel: saltos de línea, tabulaciones y caracteres de control."""
    if pd.isna(texto) or texto is None:
        return ""
    
    texto = str(texto)
    
    # Remover saltos de línea y tabulaciones
    texto = texto.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
    
    # Remover caracteres de control (ord < 32 que pudieran quedar)
    texto = ''.join(char for char in texto if ord(char) >= 32)
    
    # Normalizar espacios
    texto = re.sub(r'\s+', ' ', texto).strip()
    
    return texto


def calcular_similitud(texto1: str, texto2: str) -> float:
    """Calcula similitud [0..1] entre dos textos normalizados usando SequenceMatcher."""
    # Normalizar ambos textos
    t1 = normalizar_texto(texto1)
    t2 = normalizar_texto(texto2)
    
    if not t1 or not t2:
        return 0.0
    
    # Usar SequenceMatcher
    return difflib.SequenceMatcher(None, t1, t2).ratio()


def encontrar_similares(
    valor: str,
    lista_valores: list,
    umbral: float = 0.85,
    max_resultados: int = 5
) -> list:
    """Devuelve lista de (valor, similitud) de los más similares al texto dado en la lista."""
    if not valor or not lista_valores:
        return []
    
    similares = []
    valor_norm = normalizar_texto(valor)
    
    for item in lista_valores:
        if pd.notna(item):
            similitud = calcular_similitud(valor_norm, str(item))
            if similitud >= umbral:
                similares.append((str(item), similitud))
    
    # Ordenar por similitud descendente
    similares.sort(key=lambda x: x[1], reverse=True)
    
    # Retornar máximo N resultados
    return similares[:max_resultados]


def extraer_palabras_clave(
    texto: str,
    min_longitud: int = 3,
    palabras_comunes: set | None = None
) -> set:
    """Extrae palabras clave del texto filtrando stopwords y términos cortos."""
    if not texto:
        return set()
    
    # Palabras comunes por defecto (stopwords español)
    if palabras_comunes is None:
        palabras_comunes = {
            'de', 'la', 'el', 'en', 'y', 'a', 'los', 'las', 'del', 'para',
            'con', 'por', 'un', 'una', 'al', 'es', 'lo', 'su', 'que', 'se'
        }
    
    # Normalizar y dividir en palabras
    texto_norm = normalizar_texto(texto, uppercase=False)
    palabras = re.findall(r'\b\w+\b', texto_norm)
    
    # Filtrar palabras
    palabras_clave = {
        p for p in palabras
        if len(p) >= min_longitud and p not in palabras_comunes
    }
    
    return palabras_clave


def contiene_palabras_clave(
    texto: str,
    palabras_clave: list,
    operador: str = 'OR'
) -> bool:
    """Verifica si el texto contiene palabras clave (OR por defecto, AND si se especifica)."""
    if not texto or not palabras_clave:
        return False
    
    texto_norm = normalizar_texto(texto)
    
    matches = []
    for palabra in palabras_clave:
        palabra_norm = normalizar_texto(str(palabra))
        matches.append(palabra_norm in texto_norm)
    
    if operador.upper() == 'AND':
        return all(matches)
    else:  # OR
        return any(matches)


def truncar_texto(texto: str | None, max_length: int = 100, sufijo: str = "...") -> str:
    """Trunca el texto a max_length caracteres añadiendo sufijo si se corta."""
    if texto is None:
        return ""
    if not texto or len(texto) <= max_length:
        return str(texto) if texto else ""
    
    return texto[:max_length - len(sufijo)] + sufijo


def limpiar_codigo_licitacion(codigo: Any) -> str:
    """Limpia y normaliza un código de licitación eliminando espacios y caracteres extraños."""
    if pd.isna(codigo) or codigo is None:
        return ""
    
    codigo = str(codigo).strip()
    
    # Remover espacios alrededor de guiones
    codigo = re.sub(r'\s*-\s*', '-', codigo)
    
    # Remover caracteres especiales excepto guiones y alfanuméricos
    codigo = re.sub(r'[^\w\-]', '', codigo)
    
    return codigo.upper()
