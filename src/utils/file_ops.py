"""Utilidades para leer, escribir y validar archivos Excel."""

import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

from .logger import ProjectLogger
from .text_processing import normalizar_texto


def validar_archivo_excel(
    ruta: Path,
    debe_existir: bool = True,
    hojas_requeridas: list[str] | None = None
) -> tuple[bool, str]:
    """Valida existencia y hojas de un Excel. Devuelve (ok, mensaje)."""
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
            try:
                hojas_existentes = wb.sheetnames
                hojas_faltantes = [h for h in hojas_requeridas if h not in hojas_existentes]
            finally:
                wb.close()
            if hojas_faltantes:
                return False, f"Hojas faltantes: {hojas_faltantes}"
        
        except Exception as e:
            return False, f"Error al leer archivo: {e}"
    
    return True, "OK"


def crear_backup(
    archivo: Path,
    directorio_backup: Path | None = None,
    logger: ProjectLogger | None = None
) -> Path | None:
    """Crea una copia con timestamp. Devuelve la ruta del backup o None si falla."""
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
    hoja: str | None = None,
    columna_referencia: str = "Nivel 1",
    max_filas: int = 50
) -> int:
    """Detecta la fila de encabezados buscando columna_referencia. Devuelve índice 0-based."""
    try:
        df = pd.read_excel(ruta, sheet_name=hoja, nrows=max_filas, header=None)
        
        if isinstance(df, dict):
            df = df[hoja or next(iter(df.keys()))]
        
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
    
    except Exception:
        return 0


def encontrar_columna(
    df: pd.DataFrame,
    nombre_columna: str,
    normalizar: bool = True
) -> str | None:
    """Busca una columna en el DataFrame (con normalización opcional). Devuelve el nombre real o None."""
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
    hoja: str | None = None,
    columna_referencia: str = "Nivel 1",
    **kwargs
) -> pd.DataFrame:
    """Lee un Excel detectando automáticamente la fila de encabezados."""
    header_row = encontrar_fila_encabezado(ruta, hoja, columna_referencia)
    
    # Si no se especifica hoja, usar la primera hoja
    if hoja is None:
        wb = load_workbook(ruta, read_only=True, data_only=True)
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
    """Guarda un DataFrame en Excel con encabezado azul, columnas ajustadas y fila congelada."""
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
                    except Exception:  # noqa: S110 — cell formatting error, skip silently
                        pass
                
                adjusted_width = min(max_length + 2, 50)  # Máximo 50
                ws.column_dimensions[column_letter].width = adjusted_width
        
        # Formato de encabezado
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")
        header_alignment = Alignment(horizontal="center", vertical="center")
        
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_alignment
        
        wb.save(ruta)
        return True
    
    except Exception:
        return False


def obtener_timestamp() -> str:
    """Retorna timestamp en formato estándar del proyecto"""
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def obtener_fecha_hoy() -> str:
    """Retorna fecha de hoy en formato estándar"""
    return datetime.now().strftime("%Y%m%d")


def listar_archivos_output(patron: str = "*.xlsx") -> list[Path]:
    """Lista archivos en OUTPUT_DIR ordenados de más reciente a más antiguo."""
    from .config import Config
    
    config = Config()
    if not config.OUTPUT_DIR.exists():
        return []
    
    return sorted(config.OUTPUT_DIR.glob(patron), reverse=True)


def limpiar_outputs_antiguos(dias: int = 30, mantener_ultimos: int = 5) -> None:
    """Elimina archivos de OUTPUT más antiguos que 'dias' días, conservando los 'mantener_ultimos' más recientes."""
    archivos = listar_archivos_output()
    
    if len(archivos) <= mantener_ultimos:
        return
    
    fecha_limite = datetime.now().timestamp() - (dias * 24 * 60 * 60)
    
    for archivo in archivos[mantener_ultimos:]:
        if archivo.stat().st_mtime < fecha_limite:
            import contextlib
            with contextlib.suppress(Exception):
                archivo.unlink()
