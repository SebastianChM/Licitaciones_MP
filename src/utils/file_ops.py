"""
Utilidades para operaciones con archivos Excel y gestión de rutas.

Autor: Sebastian Chirino
Versión: 3.0.0
"""

import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import pandas as pd
import openpyxl
from openpyxl import load_workbook
from .logger import ProjectLogger
from .text_processing import normalizar_texto


def validar_archivo_excel(
    ruta: Path,
    debe_existir: bool = True,
    hojas_requeridas: Optional[List[str]] = None
) -> tuple[bool, str]:
    """
    Valida que un archivo Excel exista y tenga las hojas requeridas.
    
    Args:
        ruta: Ruta al archivo Excel
        debe_existir: Si True, el archivo debe existir
        hojas_requeridas: Lista de nombres de hojas que deben existir
    
    Returns:
        tuple: (es_valido, mensaje)
    """
    # Verificar existencia
    if debe_existir and not ruta.exists():
        return False, f"Archivo no encontrado: {ruta}"
    
    if not debe_existir:
        return True, "OK"
    
    # Verificar extensión
    if ruta.suffix.lower() not in ['.xlsx', '.xls', '.xlsm']:
        return False, f"Formato inválido: {ruta.suffix}. Se esperaba .xlsx"
    
    # Verificar hojas si se especificaron
    if hojas_requeridas:
        try:
            wb = load_workbook(ruta, read_only=True)
            hojas_existentes = wb.sheetnames
            wb.close()
            
            hojas_faltantes = [h for h in hojas_requeridas if h not in hojas_existentes]
            if hojas_faltantes:
                return False, f"Hojas faltantes: {hojas_faltantes}"
        
        except Exception as e:
            return False, f"Error al leer archivo: {e}"
    
    return True, "OK"


def crear_backup(
    archivo: Path,
    directorio_backup: Optional[Path] = None,
    logger: Optional[ProjectLogger] = None
) -> Optional[Path]:
    """
    Crea una copia de backup de un archivo.
    
    Args:
        archivo: Archivo a respaldar
        directorio_backup: Directorio donde guardar backup (mismo dir si None)
        logger: Logger para registrar operación
    
    Returns:
        Path: Ruta del backup creado, None si hubo error
    """
    if not archivo.exists():
        if logger:
            logger.warning(f"No se puede hacer backup, archivo no existe: {archivo}")
        return None
    
    try:
        # Determinar directorio de backup
        if directorio_backup is None:
            directorio_backup = archivo.parent
        else:
            directorio_backup.mkdir(parents=True, exist_ok=True)
        
        # Generar nombre de backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_backup = f"{archivo.stem}_backup_{timestamp}{archivo.suffix}"
        ruta_backup = directorio_backup / nombre_backup
        
        # Copiar archivo
        shutil.copy2(archivo, ruta_backup)
        
        if logger:
            logger.info(f"✅ Backup creado: {nombre_backup}")
        
        return ruta_backup
    
    except Exception as e:
        if logger:
            logger.error(f"❌ Error creando backup de {archivo.name}: {e}")
        return None


def encontrar_fila_encabezado(
    ruta: Path,
    hoja: Optional[str] = None,
    columna_referencia: str = "Nivel 1",
    max_filas: int = 50
) -> int:
    """
    Encuentra la fila donde están los encabezados en un archivo Excel.
    
    Args:
        ruta: Ruta al archivo Excel
        hoja: Nombre de la hoja (primera si None)
        columna_referencia: Columna a buscar para identificar header
        max_filas: Máximo de filas a revisar
    
    Returns:
        int: Número de fila (0-indexed) donde están los encabezados
    """
    try:
        df = pd.read_excel(ruta, sheet_name=hoja, nrows=max_filas, header=None)
        
        if isinstance(df, dict):
            df = df[hoja or list(df.keys())[0]]
        
        target = normalizar_texto(columna_referencia)
        
        for i in range(min(max_filas, len(df))):
            row_values = [normalizar_texto(str(v)) for v in df.iloc[i].values if pd.notna(v)]
            if target in row_values:
                return i
        
        # Búsqueda alternativa por palabras clave comunes
        keywords = ['nivel', 'codigo', 'nombre', 'descripcion']
        for i in range(min(max_filas, len(df))):
            row_values = [normalizar_texto(str(v)) for v in df.iloc[i].values if pd.notna(v)]
            row_text = ' '.join(row_values)
            if any(keyword in row_text for keyword in keywords):
                return i
        
        # Si no encuentra nada, asumir fila 0
        return 0
    
    except Exception as e:
        return 0


def encontrar_columna(
    df: pd.DataFrame,
    nombre_columna: str,
    normalizar: bool = True
) -> Optional[str]:
    """
    Encuentra una columna en un DataFrame por nombre (con normalización).
    
    Args:
        df: DataFrame donde buscar
        nombre_columna: Nombre de la columna a buscar
        normalizar: Si True, busca con normalización de texto
    
    Returns:
        str: Nombre real de la columna encontrada, None si no existe
    
    Examples:
        >>> encontrar_columna(df, "Nivel 1")  # Encuentra "Nivel 1", "nivel 1", "NIVEL1"
    """
    if nombre_columna in df.columns:
        return nombre_columna
    
    if not normalizar:
        return None
    
    nombre_norm = normalizar_texto(nombre_columna)
    
    for col in df.columns:
        if normalizar_texto(str(col)) == nombre_norm:
            return col
    
    return None


def leer_excel_con_header_dinamico(
    ruta: Path,
    hoja: Optional[str] = None,
    columna_referencia: str = "Nivel 1",
    **kwargs
) -> pd.DataFrame:
    """
    Lee un archivo Excel detectando automáticamente la fila de encabezados.
    
    Args:
        ruta: Ruta al archivo Excel
        hoja: Nombre de la hoja (primera si None)
        columna_referencia: Columna para detectar header
        **kwargs: Argumentos adicionales para pd.read_excel
    
    Returns:
        pd.DataFrame
    """
    header_row = encontrar_fila_encabezado(ruta, hoja, columna_referencia)
    
    # Si no se especifica hoja, usar la primera hoja
    if hoja is None:
        import openpyxl
        wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
        hoja = wb.sheetnames[0]
        wb.close()
    
    return pd.read_excel(
        ruta,
        sheet_name=hoja,
        header=header_row,
        **kwargs
    )


def guardar_excel_con_formato(
    df: pd.DataFrame,
    ruta: Path,
    nombre_hoja: str = "Datos",
    autoajustar_columnas: bool = True,
    congelar_encabezado: bool = True
) -> bool:
    """
    Guarda un DataFrame a Excel con formato profesional.
    
    Args:
        df: DataFrame a guardar
        ruta: Ruta de destino
        nombre_hoja: Nombre de la hoja
        autoajustar_columnas: Si True, ajusta ancho de columnas
        congelar_encabezado: Si True, congela la primera fila
    
    Returns:
        bool: True si se guardó correctamente
    """
    try:
        # Guardar DataFrame
        with pd.ExcelWriter(ruta, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=nombre_hoja, index=False)
        
        # Aplicar formato
        wb = load_workbook(ruta)
        ws = wb[nombre_hoja]
        
        # Congelar encabezado
        if congelar_encabezado:
            ws.freeze_panes = 'A2'
        
        # Autoajustar columnas
        if autoajustar_columnas:
            for column in ws.columns:
                max_length = 0
                column_letter = column[0].column_letter
                
                for cell in column:
                    try:
                        if cell.value:
                            max_length = max(max_length, len(str(cell.value)))
                    except:
                        pass
                
                adjusted_width = min(max_length + 2, 50)  # Máximo 50
                ws.column_dimensions[column_letter].width = adjusted_width
        
        # Formato de encabezado
        from openpyxl.styles import Font, PatternFill, Alignment
        
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")
        header_alignment = Alignment(horizontal="center", vertical="center")
        
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_alignment
        
        wb.save(ruta)
        return True
    
    except Exception as e:
        return False


def obtener_timestamp() -> str:
    """Retorna timestamp en formato estándar del proyecto"""
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def obtener_fecha_hoy() -> str:
    """Retorna fecha de hoy en formato estándar"""
    return datetime.now().strftime("%Y%m%d")


def listar_archivos_output(patron: str = "*.xlsx") -> List[Path]:
    """
    Lista archivos en el directorio OUTPUT.
    
    Args:
        patron: Patrón glob para filtrar archivos
    
    Returns:
        List[Path]: Lista de rutas encontradas
    """
    from .config import Config
    
    if not Config.OUTPUT_DIR.exists():
        return []
    
    return sorted(Config.OUTPUT_DIR.glob(patron), reverse=True)


def limpiar_outputs_antiguos(dias: int = 30, mantener_ultimos: int = 5):
    """
    Limpia archivos OUTPUT antiguos.
    
    Args:
        dias: Eliminar archivos más antiguos que N días
        mantener_ultimos: Mantener al menos N archivos más recientes
    """
    from .config import Config
    
    archivos = listar_archivos_output()
    
    if len(archivos) <= mantener_ultimos:
        return
    
    fecha_limite = datetime.now().timestamp() - (dias * 24 * 60 * 60)
    
    for archivo in archivos[mantener_ultimos:]:
        if archivo.stat().st_mtime < fecha_limite:
            try:
                archivo.unlink()
            except Exception:
                pass
