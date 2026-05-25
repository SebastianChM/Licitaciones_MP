"""
Formateador Excel compartido para reportes de licitaciones.

Genera reportes con encabezados azules, anchos ajustados, hipervínculos
clickeables y formato condicional para días de cierre (rojo/amarillo/verde).

Usado por etapa4 (reporte ejecutivo) y etapa5 (reporte incremental).
"""

from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

# Anchos de columna estándar del reporte de licitaciones
_ANCHOS_COLUMNAS = {
    "Score": 8,
    "LINK": 12,
    "Numero Adquisición": 18,
    "Nombre": 50,
    "Descripción": 60,
    "Región": 30,
    "Cliente (Organismo)": 40,
    "Fecha Publicación": 20,
    "Hora Publicación": 12,
    "Fecha Inicio Preguntas": 20,
    "Hora Inicio Preguntas": 12,
    "Fecha Cierre Preguntas": 20,
    "Hora Cierre Preguntas": 12,
    "Fecha Apertura": 20,
    "Hora Apertura": 12,
    "Fecha Cierre Licitación": 20,
    "Hora Cierre Licitación": 12,
    "Fecha Adjudicación": 20,
    "Hora Adjudicación": 12,
    "Monto Estimado (CLP)": 18,
    "Días para cierre": 12,
    "ONU": 12,
    "Nivel 1": 50,
    "Nivel 2": 45,
    "Nivel 3": 45,
    "Genérico": 40,
    "Trazabilidad": 15,
}

# Columnas largas que usan wrap_text
_COLS_WRAP = {"Nombre", "Descripción", "Nivel 1", "Nivel 2", "Nivel 3", "Cliente (Organismo)"}

# Columnas cortas que se centran
_COLS_CENTRO = {
    "Score", "LINK", "Días para cierre", "ONU", "Hora Publicación",
    "Hora Inicio Preguntas", "Hora Cierre Preguntas",
    "Hora Apertura", "Hora Cierre Licitación", "Hora Adjudicación",
}


def guardar_formateado_reporte(df: pd.DataFrame, ruta: Path, hoja: str) -> None:
    """Guarda un DataFrame como Excel con formato profesional de reporte MP.

    Aplica:
    - Encabezados azul MP (0066CC) con fuente blanca negrita
    - Anchos de columna predefinidos para cada campo del reporte
    - Hipervínculos clickeables en la columna LINK
    - Alineación y wrap_text diferenciados por tipo de columna
    - Formato condicional en 'Días para cierre' (rojo/amarillo/verde)
    - Primera fila congelada

    Args:
        df: DataFrame con los datos a guardar.
        ruta: Ruta destino del archivo .xlsx.
        hoja: Nombre de la hoja de trabajo.
    """
    df.to_excel(ruta, sheet_name=hoja, index=False, engine='openpyxl')
    wb = load_workbook(ruta)
    ws = wb[hoja]

    # === 1. FORMATO DE ENCABEZADOS ===
    header_fill = PatternFill(start_color="0066CC", end_color="0066CC", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

    for col_idx in range(1, len(df.columns) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_alignment

    # === 2. AJUSTAR ANCHOS DE COLUMNAS ===
    for col_idx, col_name in enumerate(df.columns, 1):
        letra = get_column_letter(col_idx)
        ws.column_dimensions[letra].width = _ANCHOS_COLUMNAS.get(col_name, 15)

    # === 3. CONVERTIR COLUMNA LINK EN HIPERVÍNCULOS CLICKEABLES ===
    if "LINK" in df.columns:
        col_link_idx = df.columns.get_loc("LINK") + 1
        for row_idx in range(2, len(df) + 2):
            cell = ws.cell(row=row_idx, column=col_link_idx)
            url = cell.value
            if url and url.startswith("http"):
                cell.hyperlink = url
                cell.value = "Ver Licitación"
                cell.font = Font(color="0000FF", underline="single", size=10)
                cell.alignment = Alignment(horizontal='center', vertical='center')

    # === 4. ALINEACIÓN Y WRAP TEXT ===
    for row in ws.iter_rows(min_row=2, max_row=len(df) + 1, min_col=1, max_col=len(df.columns)):
        for idx, cell in enumerate(row):
            col_name = df.columns[idx]
            if col_name in _COLS_WRAP:
                cell.alignment = Alignment(wrap_text=True, vertical='top')
            elif col_name in _COLS_CENTRO:
                cell.alignment = Alignment(horizontal='center', vertical='center')
            elif col_name == "Monto Estimado (CLP)":
                cell.number_format = '#,##0'
                cell.alignment = Alignment(horizontal='right', vertical='center')

    # === 5. FORMATO CONDICIONAL PARA DÍAS DE CIERRE ===
    if "Días para cierre" in df.columns:
        col_dias = df.columns.get_loc("Días para cierre") + 1
        letra_dias = get_column_letter(col_dias)
        rango = f"{letra_dias}2:{letra_dias}{len(df) + 1}"

        # Rojo: menos de 7 días
        ws.conditional_formatting.add(rango,
            FormulaRule(formula=[f'{letra_dias}2<7'], stopIfTrue=True,
                        fill=PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid"),
                        font=Font(color="FFFFFF", bold=True)))

        # Amarillo: entre 7 y 14 días
        ws.conditional_formatting.add(rango,
            FormulaRule(formula=[f'AND({letra_dias}2>=7, {letra_dias}2<=14)'], stopIfTrue=True,
                        fill=PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")))

        # Verde: más de 14 días
        ws.conditional_formatting.add(rango,
            FormulaRule(formula=[f'{letra_dias}2>14'], stopIfTrue=True,
                        fill=PatternFill(start_color="00AA00", end_color="00AA00", fill_type="solid")))

    # === 6. FORMATO CONDICIONAL PARA SCORE ===
    if "Score" in df.columns:
        col_score = df.columns.get_loc("Score") + 1
        letra_score = get_column_letter(col_score)
        rango_score = f"{letra_score}2:{letra_score}{len(df) + 1}"

        # Rojo: score < 4
        ws.conditional_formatting.add(rango_score,
            CellIsRule(operator='lessThan', formula=['4'], stopIfTrue=True,
                       fill=PatternFill(start_color="FF4444", end_color="FF4444", fill_type="solid"),
                       font=Font(color="FFFFFF", bold=True)))

        # Naranja: 4 <= score < 6
        ws.conditional_formatting.add(rango_score,
            CellIsRule(operator='between', formula=['4', '5.9'], stopIfTrue=True,
                       fill=PatternFill(start_color="FF9900", end_color="FF9900", fill_type="solid"),
                       font=Font(bold=True)))

        # Amarillo: 6 <= score < 7.5
        ws.conditional_formatting.add(rango_score,
            CellIsRule(operator='between', formula=['6', '7.4'], stopIfTrue=True,
                       fill=PatternFill(start_color="FFDD00", end_color="FFDD00", fill_type="solid"),
                       font=Font(bold=True)))

        # Verde: score >= 7.5
        ws.conditional_formatting.add(rango_score,
            CellIsRule(operator='greaterThanOrEqual', formula=['7.5'], stopIfTrue=True,
                       fill=PatternFill(start_color="00AA00", end_color="00AA00", fill_type="solid"),
                       font=Font(color="FFFFFF", bold=True)))

    # === 7. CONGELAR PRIMERA FILA ===
    ws.freeze_panes = "A2"

    # === 8. ALTURA DE FILAS ===
    ws.row_dimensions[1].height = 30
    for row_idx in range(2, len(df) + 2):
        ws.row_dimensions[row_idx].height = 60

    wb.save(ruta)
    wb.close()
