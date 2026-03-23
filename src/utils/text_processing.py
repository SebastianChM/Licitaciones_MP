# Utilidades de texto para el pipeline
# Normalización y búsqueda de palabras clave

import unicodedata
import re
from typing import Any, Optional
import pandas as pd
import difflib


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
    """
    Limpia texto que viene de celdas de Excel.
    Remueve saltos de línea, tabulaciones y caracteres especiales.
    
    Args:
        texto: Texto a limpiar
    
    Returns:
        str: Texto limpio
    """
    if pd.isna(texto) or texto is None:
        return ""
    
    texto = str(texto)
    
    # Remover saltos de línea y tabulaciones
    texto = texto.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
    
    # Remover caracteres de control
    texto = ''.join(char for char in texto if ord(char) >= 32 or char in '\n\r\t')
    
    # Normalizar espacios
    texto = re.sub(r'\s+', ' ', texto).strip()
    
    return texto


def calcular_similitud(texto1: str, texto2: str) -> float:
    """
    Calcula similitud entre dos textos usando SequenceMatcher.
    
    Args:
        texto1: Primer texto
        texto2: Segundo texto
    
    Returns:
        float: Similitud entre 0 y 1 (1 = idénticos)
    
    Examples:
        >>> calcular_similitud("Servicios de Consultoría", "Servicio de Consultoria")
        0.95
    """
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
    """
    Encuentra valores similares en una lista.
    
    Args:
        valor: Valor a buscar
        lista_valores: Lista donde buscar
        umbral: Umbral de similitud (0-1)
        max_resultados: Máximo número de resultados
    
    Returns:
        list: Lista de tuplas (valor_similar, similitud)
    
    Examples:
        >>> lista = ["Consultoría", "Consultoria", "Asesoría", "Servicios"]
        >>> encontrar_similares("Consultoria", lista, umbral=0.8)
        [('Consultoría', 0.95), ('Consultoria', 1.0)]
    """
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
    palabras_comunes: Optional[set] = None
) -> set:
    """
    Extrae palabras clave de un texto.
    
    Args:
        texto: Texto del cual extraer palabras
        min_longitud: Longitud mínima de palabras
        palabras_comunes: Set de palabras a excluir (stopwords)
    
    Returns:
        set: Conjunto de palabras clave
    """
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
    """
    Verifica si un texto contiene palabras clave.
    
    Args:
        texto: Texto a verificar
        palabras_clave: Lista de palabras clave a buscar
        operador: 'OR' (cualquiera) o 'AND' (todas)
    
    Returns:
        bool: True si cumple la condición
    
    Examples:
        >>> contiene_palabras_clave("Consultoría de TI", ["consultoria", "ti"], "OR")
        True
        >>> contiene_palabras_clave("Servicios varios", ["consultoria", "ti"], "AND")
        False
    """
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


def truncar_texto(texto: Optional[str], max_length: int = 100, sufijo: str = "...") -> str:
    """
    Trunca texto a una longitud máxima.
    
    Args:
        texto: Texto a truncar
        max_length: Longitud máxima
        sufijo: Sufijo a agregar si se trunca
    
    Returns:
        str: Texto truncado
    """
    if texto is None:
        return ""
    if not texto or len(texto) <= max_length:
        return str(texto) if texto else ""
    
    return texto[:max_length - len(sufijo)] + sufijo


def limpiar_codigo_licitacion(codigo: Any) -> str:
    """
    Limpia y formatea código de licitación.
    
    Args:
        codigo: Código de licitación (puede tener formato variado)
    
    Returns:
        str: Código limpio (solo números y guiones)
    
    Examples:
        >>> limpiar_codigo_licitacion("1234-56-LP21")
        '1234-56-LP21'
        >>> limpiar_codigo_licitacion("  1234 - 56 - LP21  ")
        '1234-56-LP21'
    """
    if pd.isna(codigo) or codigo is None:
        return ""
    
    codigo = str(codigo).strip()
    
    # Remover espacios alrededor de guiones
    codigo = re.sub(r'\s*-\s*', '-', codigo)
    
    # Remover caracteres especiales excepto guiones y alfanuméricos
    codigo = re.sub(r'[^\w\-]', '', codigo)
    
    return codigo.upper()
