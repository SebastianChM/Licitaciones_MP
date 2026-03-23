"""
Etapa 5: Análisis Incremental
Combina inteligentemente datos nuevos con reportes existentes preservando trabajo manual.

Esta etapa toma el reporte generado en Etapa 4 y lo combina con reportes anteriores,
preservando colores, filtros y ordenamientos aplicados por compañeros mientras
agrega solo las licitaciones realmente nuevas.
"""

import shutil
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from openpyxl import load_workbook, Workbook
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.formatting.rule import FormulaRule
from openpyxl.utils import get_column_letter

from utils.analizador_incremental import AnalizadorIncremental
from core.contracts import BaseStage, StageResult
from core.context import PipelineContext


class GeneradorReporteIncremental(BaseStage):
    """
    Etapa 5: Genera reporte incremental preservando trabajo manual de compañeros.
    
    Funcionalidades:
    - Detecta licitaciones nuevas vs existentes
    - Preserva colores, filtros y formateo manual
    - Solo agrega datos realmente nuevos
    - Actualiza campos críticos (días para cierre)
    - Mueve licitaciones vencidas a hoja separada
    """
    
    # Nombres canónicos de columnas del reporte (generados por Etapa 4)
    NUMERO_ADQ_COL = 'Numero Adquisición'
    REGION_COL = 'Región'
    FECHA_CIERRE_COL = 'Fecha Cierre Licitación'

    def __init__(self):
        super().__init__()
        self.analizador = AnalizadorIncremental()
        
    @property
    def name(self) -> str:
        return "incremental"
        
    def validate_inputs(self, context: PipelineContext) -> bool:
        permite_fallback = context.flags.get('allow_fallback', False)
        archivo_entrada = context.get_artifact('etapa4_output')
        
        if not archivo_entrada:
            if not permite_fallback:
                raise ValueError("Modo pipeline: Fallo al iniciar Etapa 5. Falta artefacto 'etapa4_output'.")
            
            # Buscar el archivo más reciente de etapa 4 en caso de fallback
            archivos = list(context.config.PRESENTACION_ORIGINAL_DIR.glob("Reporte_Licitaciones_*.xlsx"))
            if not archivos:
                raise FileNotFoundError(f"No hay archivo base de fallback en {context.config.PRESENTACION_ORIGINAL_DIR}")
            archivo_entrada = max(archivos, key=lambda f: f.stat().st_mtime)
            
        if not archivo_entrada.exists():
            raise FileNotFoundError(f"El archivo de entrada no existe físicamente: {archivo_entrada}")
            
        try:
            pd.read_excel(archivo_entrada, engine='openpyxl', nrows=1)
        except Exception as e:
            raise ValueError(f"El archivo base aportado a Etapa 5 es corrupto o no es Excel: {str(e)}")
            
        return True

    def run(self, context: PipelineContext) -> StageResult:
        self.bind(context)
        
        try:
            self.validate_inputs(context)
            self.logger.section("ETAPA 5: REPORTE INCREMENTAL")
            inicio = datetime.now()
            
            self.dir_presentacion_incremental = self.config.PRESENTACION_INCREMENTAL_DIR
            self.dir_presentacion_incremental.mkdir(parents=True, exist_ok=True)
            
            archivo_reporte_nuevo = context.get_artifact('etapa4_output')
            if not archivo_reporte_nuevo:
                archivos = list(self.config.PRESENTACION_ORIGINAL_DIR.glob("Reporte_Licitaciones_*.xlsx"))
                archivo_reporte_nuevo = max(archivos, key=lambda f: f.stat().st_mtime)
                
            self.logger.info(f"📂 Cargando reporte nuevo: {archivo_reporte_nuevo.name}")
            datos_nuevos = pd.read_excel(archivo_reporte_nuevo)
            self.logger.info(f"📊 Datos cargados: {len(datos_nuevos)} licitaciones")
            
            # 2. Buscar reporte incremental anterior
            reporte_anterior = self._encontrar_reporte_incremental_anterior()
            
            if reporte_anterior:
                self.logger.info(f"📋 Reporte anterior encontrado: {reporte_anterior.name}")
                resultado = self._actualizar_reporte_existente(datos_nuevos, reporte_anterior)
            else:
                self.logger.info("📄 No hay reporte anterior, creando reporte inicial")
                resultado = self._crear_reporte_inicial(datos_nuevos)
            
            # 3. Generar análisis de cambios
            analisis = self._generar_analisis_cambios(datos_nuevos, reporte_anterior)
            
            # 4. Guardar sugerencias para PIVOT
            self._guardar_sugerencias_pivot(analisis)
            
            
            rutas_generadas = []
            if 'archivo_generado' in resultado and resultado['archivo_generado']:
                rutas_generadas.append(resultado['archivo_generado'])
                context.add_artifact('etapa5_output', resultado['archivo_generado'])
            
            tiempo_total = datetime.now() - inicio
            resultado['tiempo_ejecucion'] = str(tiempo_total)
            
            self.logger.info(f"✅ Etapa 5 completada en {tiempo_total}")
            return StageResult(
                success=True,
                stage_name=self.name,
                files_produced=rutas_generadas,
                metrics_produced=resultado,
                custom_data={'detalles': resultado}
            )
            
        except Exception as e:
            self.logger.error(f"❌ Error crítico en Etapa 5: {e}", exc_info=True)
            return StageResult(success=False, stage_name=self.name, error_message=str(e))
        finally:
            self.logger.finalize()
    
    def _encontrar_reporte_incremental_anterior(self) -> Optional[Path]:
        """Encuentra el reporte incremental más reciente"""
        
        archivos = list(self.dir_presentacion_incremental.glob("Reporte_Incremental_*.xlsx"))
        
        if archivos:
            # Ordenar por fecha de modificación
            archivo_mas_reciente = max(archivos, key=lambda x: x.stat().st_mtime)
            return archivo_mas_reciente
        
        return None
    
    def _actualizar_reporte_existente(self, datos_nuevos: pd.DataFrame, reporte_anterior: Path) -> Dict:
        """Actualiza reporte existente preservando trabajo manual a nivel de celda.

        Copia el archivo anterior (conservando colores y formatos manuales), luego:
        - Actualiza 'Días para cierre' de filas existentes
        - Mueve vencidas a hoja 'Vencidas'
        - Agrega filas nuevas al final
        """
        self.logger.info("🔄 Actualizando reporte existente (preservando formato manual)...")

        analisis = self.analizador.analizar_reporte_incremental(datos_nuevos, reporte_anterior)
        licitaciones_nuevas = analisis['licitaciones_nuevas']
        licitaciones_existentes = analisis['licitaciones_existentes']
        licitaciones_vencidas = analisis['licitaciones_vencidas']

        self.logger.info(f"📊 Análisis: {len(licitaciones_nuevas)} nuevas, "
                         f"{len(licitaciones_existentes)} existentes, "
                         f"{len(licitaciones_vencidas)} vencidas")

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        archivo_incremental = self.dir_presentacion_incremental / f"Reporte_Incremental_{timestamp}.xlsx"

        # Copiar archivo anterior para preservar TODOS los formatos manuales (colores, filtros, etc.)
        shutil.copy2(reporte_anterior, archivo_incremental)

        wb = load_workbook(archivo_incremental)
        ws = wb['Vigentes'] if 'Vigentes' in wb.sheetnames else wb.active

        # Construir mapa: nombre_columna -> índice 1-based
        header_map = {
            str(ws.cell(1, c).value): c
            for c in range(1, ws.max_column + 1)
            if ws.cell(1, c).value is not None
        }
        col_codigo = header_map.get(self.NUMERO_ADQ_COL)
        col_dias = header_map.get('Días para cierre')

        # 1. Actualizar 'Días para cierre' de licitaciones existentes sin tocar su formato
        if col_codigo and col_dias and not datos_nuevos.empty:
            col_codigo_df = next(
                (c for c in [self.NUMERO_ADQ_COL, 'Código Externo', 'CodigoExterno']
                 if c in datos_nuevos.columns), None
            )
            if col_codigo_df and 'Días para cierre' in datos_nuevos.columns:
                dias_map = dict(zip(
                    datos_nuevos[col_codigo_df].astype(str),
                    datos_nuevos['Días para cierre']
                ))
                for row in ws.iter_rows(min_row=2):
                    codigo_val = row[col_codigo - 1].value
                    if codigo_val and str(codigo_val) in dias_map:
                        row[col_dias - 1].value = dias_map[str(codigo_val)]

        # 2. Mover vencidas a hoja separada
        if not licitaciones_vencidas.empty and col_codigo:
            self._mover_licitaciones_vencidas(wb, ws, licitaciones_vencidas, col_codigo)

        # 3. Agregar licitaciones nuevas al final preservando estructura de columnas
        if not licitaciones_nuevas.empty:
            cols_ws = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
            for _, row_data in licitaciones_nuevas.iterrows():
                last_row = ws.max_row + 1
                for col_idx, col_name in enumerate(cols_ws, 1):
                    if col_name and col_name in row_data.index:
                        ws.cell(last_row, col_idx).value = row_data.get(col_name, '')
            self.logger.info(f"➕ {len(licitaciones_nuevas)} licitaciones nuevas agregadas")

        wb.save(archivo_incremental)
        self.logger.info(f"💾 Reporte incremental guardado: {archivo_incremental.name}")

        return {
            'archivo_generado': archivo_incremental,
            'licitaciones_nuevas': len(licitaciones_nuevas),
            'licitaciones_existentes': len(licitaciones_existentes),
            'licitaciones_vencidas': len(licitaciones_vencidas),
            'tipo': 'incremental'
        }
    
    def _crear_reporte_inicial(self, datos_nuevos: pd.DataFrame) -> Dict:
        """Crea el primer reporte incremental"""
        
        self.logger.info("📄 Creando reporte incremental inicial...")
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        archivo_incremental = self.dir_presentacion_incremental / f"Reporte_Incremental_{timestamp}.xlsx"
        
        # Crear Excel con formato mejorado
        self._guardar_formateado(datos_nuevos, archivo_incremental, "Vigentes")
        self.logger.info(f"💾 Reporte inicial guardado: {archivo_incremental.name}")
        
        return {
            'archivo_generado': archivo_incremental,
            'licitaciones_nuevas': len(datos_nuevos),
            'licitaciones_existentes': 0,
            'licitaciones_vencidas': 0,
            'tipo': 'inicial'
        }

    def _mover_licitaciones_vencidas(
        self, wb: Workbook, ws_vigentes, vencidas: pd.DataFrame, col_codigo_idx: int
    ):
        """Copia licitaciones vencidas a hoja 'Vencidas' y las elimina de 'Vigentes'."""
        if 'Vencidas' not in wb.sheetnames:
            wb.create_sheet('Vencidas')
        ws_vencidas = wb['Vencidas']

        # Copiar encabezado si la hoja está vacía
        if ws_vencidas.max_row == 1 and ws_vencidas.cell(1, 1).value is None:
            for c in range(1, ws_vigentes.max_column + 1):
                ws_vencidas.cell(1, c).value = ws_vigentes.cell(1, c).value

        col_codigo_name = next(
            (c for c in [self.NUMERO_ADQ_COL, 'Código Externo', 'CodigoExterno']
             if c in vencidas.columns), None
        )
        if not col_codigo_name:
            self.logger.warning("⚠️ No se identificó columna de código para mover vencidas")
            return

        codigos_vencidos = set(vencidas[col_codigo_name].astype(str))
        rows_to_delete = []

        for row in ws_vigentes.iter_rows(min_row=2):
            val = row[col_codigo_idx - 1].value
            if val and str(val) in codigos_vencidos:
                new_row = ws_vencidas.max_row + 1
                for col_idx, cell in enumerate(row, 1):
                    ws_vencidas.cell(new_row, col_idx).value = cell.value
                rows_to_delete.append(row[0].row)

        for row_idx in reversed(rows_to_delete):
            ws_vigentes.delete_rows(row_idx)

        self.logger.info(f"📦 {len(rows_to_delete)} licitaciones movidas a hoja 'Vencidas'")
    
    def _generar_analisis_cambios(self, datos_nuevos: pd.DataFrame, reporte_anterior: Optional[Path]) -> Dict:
        """Genera análisis completo de cambios"""
        
        analisis_taxonomia = self.analizador.analizar_cambios_taxonomia(datos_nuevos)
        
        if reporte_anterior:
            analisis_reporte = self.analizador.analizar_reporte_incremental(datos_nuevos, reporte_anterior)
        else:
            analisis_reporte = {
                'licitaciones_nuevas': datos_nuevos,
                'licitaciones_existentes': pd.DataFrame(),
                'licitaciones_vencidas': pd.DataFrame(),
                'estadisticas': {
                    'nuevas': len(datos_nuevos),
                    'existentes': 0,
                    'vencidas': 0
                }
            }
        
        return self.analizador.generar_reporte_cambios(analisis_taxonomia, analisis_reporte)
    
    def _guardar_sugerencias_pivot(self, analisis: Dict):
        """Guarda sugerencias para actualizar PIVOT_MAESTRO"""
        
        import json
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archivo_sugerencias = self.config.LOG_DIR / f"sugerencias_pivot_etapa5_{timestamp}.json"
        
        with open(archivo_sugerencias, 'w', encoding='utf-8') as f:
            json.dump(analisis, f, indent=2, ensure_ascii=False, default=str)
        
        self.logger.info(f"💡 Sugerencias PIVOT guardadas: {archivo_sugerencias.name}")
    
    def _generar_link_licitacion(self, codigo: str) -> str:
        """Genera link a licitación en Mercado Público"""
        if codigo:
            return f"https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idlicitacion={codigo}"
        return ""
    
    def _calcular_dias_cierre(self, fecha_cierre) -> int:
        """Calcula días para cierre"""
        try:
            if pd.isna(fecha_cierre):
                return 999
            fecha = pd.to_datetime(fecha_cierre)
            hoy = datetime.now()
            return (fecha - hoy).days
        except Exception:
            return 999
    
    def _guardar_formateado(self, df: pd.DataFrame, ruta: Path, hoja: str):
        """Guarda Excel con formato mejorado: anchos automáticos, links clickeables, colores"""
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
        
        # === 2. AJUSTAR ANCHOS DE COLUMNAS AUTOMÁTICAMENTE ===
        anchos_columnas = {
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
            "Trazabilidad": 15
        }
        
        for col_idx, col_name in enumerate(df.columns, 1):
            letra = get_column_letter(col_idx)
            ancho_definido = anchos_columnas.get(col_name, 15)
            ws.column_dimensions[letra].width = ancho_definido
        
        # === 3. CONVERTIR COLUMNA LINK EN HIPERVÍNCULOS CLICKEABLES ===
        if "LINK" in df.columns:
            col_link_idx = df.columns.get_loc("LINK") + 1
            for row_idx in range(2, len(df) + 2):  # Desde fila 2 (después del header)
                cell = ws.cell(row=row_idx, column=col_link_idx)
                url = cell.value
                if url and url.startswith("http"):
                    cell.hyperlink = url
                    cell.value = "Ver Licitación"
                    cell.font = Font(color="0000FF", underline="single", size=10)
                    cell.alignment = Alignment(horizontal='center', vertical='center')
        
        # === 4. ALINEACIÓN Y WRAP TEXT ===
        for row in ws.iter_rows(min_row=2, max_row=len(df)+1, min_col=1, max_col=len(df.columns)):
            for idx, cell in enumerate(row):
                col_name = df.columns[idx]
                
                # Wrap text para columnas largas
                if col_name in ["Nombre", "Descripción", "Nivel 1", "Nivel 2", "Nivel 3", "Cliente (Organismo)"]:
                    cell.alignment = Alignment(wrap_text=True, vertical='top')
                
                # Centrar columnas cortas
                elif col_name in ["LINK", "Dias para cierre", "ONU", "Hora Publicación", 
                                  "Hora Inicio Preguntas", "Hora Cierre Preguntas", 
                                  "Hora Apertura", "Hora Cierre Licitación", "Hora Adjudicación"]:
                    cell.alignment = Alignment(horizontal='center', vertical='center')
                
                # Formato número para monto
                elif col_name == "Monto Estimado (CLP)":
                    cell.number_format = '#,##0'
                    cell.alignment = Alignment(horizontal='right', vertical='center')
        
        # === 5. FORMATO CONDICIONAL PARA DÍAS DE CIERRE ===
        if "Días para cierre" in df.columns:
            col_dias = df.columns.get_loc("Días para cierre") + 1
            letra_dias = get_column_letter(col_dias)
            
            # Rojo: menos de 7 días
            ws.conditional_formatting.add(f"{letra_dias}2:{letra_dias}{len(df)+1}",
                FormulaRule(formula=[f'{letra_dias}2<7'], stopIfTrue=True,
                           fill=PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid"),
                           font=Font(color="FFFFFF", bold=True)))
            
            # Amarillo: entre 7 y 14 días
            ws.conditional_formatting.add(f"{letra_dias}2:{letra_dias}{len(df)+1}",
                FormulaRule(formula=[f'AND({letra_dias}2>=7, {letra_dias}2<=14)'], stopIfTrue=True,
                           fill=PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")))
            
            # Verde: más de 14 días
            ws.conditional_formatting.add(f"{letra_dias}2:{letra_dias}{len(df)+1}",
                FormulaRule(formula=[f'{letra_dias}2>14'], stopIfTrue=True,
                           fill=PatternFill(start_color="00AA00", end_color="00AA00", fill_type="solid")))
        
        # === 6. CONGELAR PRIMERA FILA (ENCABEZADOS) ===
        ws.freeze_panes = "A2"
        
        # === 7. ALTURA DE FILAS ===
        ws.row_dimensions[1].height = 30  # Header más alto
        for row_idx in range(2, len(df) + 2):
            ws.row_dimensions[row_idx].height = 60  # Filas con más espacio para wrap text
        
        wb.save(ruta)
    
    def _encontrar_fila_por_codigo(self, worksheet, codigo: str) -> Optional[int]:
        """Encuentra la fila de una licitación por su código"""
        for fila in range(2, worksheet.max_row + 1):
            if worksheet.cell(row=fila, column=2).value == codigo:
                return fila
        return None
    
