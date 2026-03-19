__version__ = "3.0.0"

import re
import requests
import pytz
import pandas as pd
from pathlib import Path
from typing import Dict, Optional, Any, Tuple
from datetime import datetime
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.formatting.rule import FormulaRule
from openpyxl.utils import get_column_letter
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))
from src.utils import Config, ProjectLogger, obtener_timestamp

class GeneradorReporte:
    REGEX_NUMERO = r'[^\d.]'
    
    COLUMNAS = ["LINK", "Numero Adquisición", "Nombre", "Descripción", "Región", "Cliente (Organismo)",
                "Fecha Publicación", "Hora Publicación", "Fecha Inicio Preguntas", "Hora Inicio Preguntas",
                "Fecha Cierre Preguntas", "Hora Cierre Preguntas", "Fecha Apertura", "Hora Apertura",
                "Fecha Cierre Licitación", "Hora Cierre Licitación", "Fecha Adjudicación", "Hora Adjudicación",
                "Monto Estimado (CLP)", "Días para cierre", "ONU", "Nivel 1", "Nivel 2", "Nivel 3",
                "Genérico", "Trazabilidad"]
    
    SINONIMOS = {
        "Numero Adquisición": ["Numero Adquisición", "Código Externo", "CodigoExterno"],
        "Nombre": ["Nombre Adquisición", "Nombre Licitación", "Nombre", "API_Nombre"],
        "Descripción": ["Descripción", "API_Descripcion"],
        "Región": ["Región Compradora", "Región", "RegionUnidad", "API_RegionUnidad"],
        "Cliente (Organismo)": ["Organismo", "Cliente", "OrganismoNombre"],
        "Fecha Publicación": ["Fecha Publicación", "FechaPublicacion", "API_FechaPublicacion"],
        "Hora Publicación": ["Hora Publicación", "API_FechaPublicacion"],
        "Fecha Inicio Preguntas": ["FechaInicioPregunta", "API_FechaInicio"],
        "Hora Inicio Preguntas": ["API_FechaInicio"],
        "Fecha Cierre Preguntas": ["FechaCierrePregunta", "API_FechaFinal"],
        "Hora Cierre Preguntas": ["API_FechaFinal"],
        "Fecha Apertura": ["FechaAperturaTecnica", "FechaAperturaEconomica", "API_FechaActoAperturaTecnica"],
        "Hora Apertura": ["API_FechaActoAperturaTecnica"],
        "Fecha Cierre Licitación": ["Fecha Cierre", "FechaCierre", "Fecha Cierre Licitación", "API_FechaCierre"],
        "Hora Cierre Licitación": ["API_FechaCierre"],
        "Fecha Adjudicación": ["FechaAdjudicacion", "API_FechaAdjudicacion"],
        "Hora Adjudicación": ["API_FechaAdjudicacion"],
        "Monto Estimado (CLP)": ["Monto", "API_Monto", "MontoEstimado"],
        "ONU": ["Código ONU", "CodigoProducto"],
        "Trazabilidad": ["Trazabilidad Filtro", "Trazabilidad", "Motivo Inclusión"]
    }
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.logger = ProjectLogger('etapa4', self.config.LOG_DIR)
        self.valor_utm = self.config.ETAPA4_VALOR_UTM
        self.valor_usd = 1000
        self.dias_gracia = self.config.ETAPA4_DIAS_GRACIA_HISTORICO
        self.tz_chile = pytz.timezone('America/Santiago')
        self.stats = {'total': 0, 'vigentes': 0, 'vencidas': 0, 'utm': 0, 'usd': 0, 'errores': 0}
    
    def ejecutar(self, archivo_entrada: Optional[Path] = None) -> Dict[str, Any]:
        self.logger.section("ETAPA 4 - GENERACIÓN DE REPORTE EJECUTIVO", 80)
        self.logger.info(f"[>>] Iniciando generación incremental - v{__version__}")
        
        try:
            self._actualizar_tasas()
            archivo = archivo_entrada or self._obtener_archivo()
            df_raw = pd.read_excel(archivo, engine='openpyxl')
            self.stats['total'] = len(df_raw)
            self.logger.info(f"[IN] {len(df_raw):,} licitaciones cargadas")
            
            # Procesamiento estándar
            df_procesado = self._preparar_reporte(df_raw)
            df_vigentes, df_vencidas = self._separar(df_procesado)
            self._generar_excel(df_vigentes, df_vencidas)
            
            self.logger.section("RESUMEN", 80)
            self._imprimir_resumen()
            
            return {'exito': True, 'stats': self.stats, 'vigentes': len(df_vigentes), 'vencidas': len(df_vencidas)}
        except Exception as e:
            self.logger.error(f"[X] Error: {e}", exc_info=True)
            raise
        finally:
            self.logger.finalize()
    
    def _actualizar_tasas(self):
        self.logger.subsection("Actualizando tasas")
        try:
            utm = self._obtener_utm()
            if utm > 0:
                self.valor_utm = utm
            self.logger.info(f"💱 UTM: ${self.valor_utm:,.0f}")
        except Exception as e:
            self.logger.warning(f"[!] UTM error: {e}")
        
        try:
            usd = self._obtener_usd()
            if usd > 0:
                self.valor_usd = usd
            self.logger.info(f"💱 USD: ${self.valor_usd:,.0f}")
        except Exception as e:
            self.logger.warning(f"[!] USD error: {e}")
    
    def _obtener_utm(self) -> float:
        r = requests.get("https://api.cmfchile.cl/api-sbifv3/recursos_api/utm",
                        params={'apikey': '3638141efe952b31a7e3422d2811bb15916bb794', 'formato': 'json'}, timeout=10)
        r.raise_for_status()
        return float(r.json().get('Valor', 0))
    
    def _obtener_usd(self) -> float:
        r = requests.get("https://api.exchangerate.host/latest", params={'base': 'USD', 'symbols': 'CLP'}, timeout=10)
        r.raise_for_status()
        return float(r.json()['rates']['CLP'])
    
    def _obtener_archivo(self) -> Path:
        archivos = list(self.config.ENRIQUECIDO_DIR.glob("Licitaciones_Enriquecidas_*.xlsx"))
        if not archivos:
            raise FileNotFoundError(f"No hay archivo en {self.config.ENRIQUECIDO_DIR}")
        archivos = sorted(archivos, key=lambda f: f.stat().st_mtime, reverse=True)
        self.logger.info(f"[IN] {archivos[0].name}")
        return archivos[0]
    
    def _preparar_reporte(self, df_raw: pd.DataFrame) -> pd.DataFrame:
        self.logger.subsection("Preparando reporte")
        data = {}
        
        for col in self.COLUMNAS:
            if col == "LINK":
                data[col] = df_raw['Numero Adquisición'].apply(
                    lambda x: f"https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idlicitacion={str(x)}"
                )
                continue
            
            if col in ["Días para cierre", "Monto Estimado (CLP)"]:
                data[col] = ""
                continue
            
            if "Hora" in col:
                col_fecha = col.replace("Hora", "Fecha")
                sinonimos_fecha = self.SINONIMOS.get(col_fecha, [col_fecha])
                col_fuente = next((c for c in sinonimos_fecha if c in df_raw.columns), None)
                if col_fuente:
                    data[col] = df_raw[col_fuente].apply(self._extraer_hora)
                else:
                    data[col] = ""
                continue
            
            col_fuente = next((c for c in self.SINONIMOS.get(col, [col]) if c in df_raw.columns), None)
            data[col] = df_raw[col_fuente].astype(str) if col_fuente else ""
        
        df = pd.DataFrame(data)
        df['Monto Estimado (CLP)'] = df_raw.apply(self._convertir_monto, axis=1)
        df['Días para cierre'] = df.apply(self._calcular_dias, axis=1)
        
        self.logger.info(f"[OK] Reporte preparado: {len(df)} filas")
        return df
    
    def _extraer_hora(self, timestamp) -> str:
        try:
            if pd.isna(timestamp) or str(timestamp) in ['', 'nan', 'None']:
                return ""
            dt = pd.to_datetime(timestamp, errors='coerce')
            if pd.isna(dt):
                return ""
            return dt.strftime('%H:%M')
        except Exception:
            return ""
    
    def _convertir_monto(self, row: pd.Series) -> int:
        try:
            moneda = str(row.get('Moneda', '')).upper().strip()
            
            if moneda in ['CLP', 'PESO']:
                return int(float(re.sub(self.REGEX_NUMERO, '', str(row.get('Monto', '0')))))
            
            if 'UTM' in moneda:
                tipo = str(row.get('Tipo Adquisición', ''))
                nums = re.findall(r'(\d+(?:\.\d+)?)', tipo.replace('.', '').replace(',', '.'))
                if nums:
                    self.stats['utm'] += 1
                    return int(float(nums[0]) * self.valor_utm)
            
            if moneda in ['USD', 'DOLAR']:
                monto = float(re.sub(self.REGEX_NUMERO, '', str(row.get('Monto', '0'))))
                if monto > 0:
                    self.stats['usd'] += 1
                    return int(monto * self.valor_usd)
            
            return int(float(re.sub(self.REGEX_NUMERO, '', str(row.get('Monto', '0')))))
        except Exception:
            self.stats['errores'] += 1
            return 0
    
    def _calcular_dias(self, row: pd.Series) -> int:
        try:
            fecha_str = str(row.get('Fecha Cierre Licitación', ''))
            if not fecha_str or fecha_str == 'nan':
                return 999
            fecha = pd.to_datetime(fecha_str, errors='coerce')
            if pd.isna(fecha):
                return 999
            return (fecha.date() - datetime.now(self.tz_chile).date()).days
        except Exception:
            return 999
    
    def _separar(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        self.logger.subsection("Separando vigentes/vencidas")
        vigentes = df[(df['Días para cierre'] >= 0) | (df['Días para cierre'] == 999)].copy()
        vencidas = df[(df['Días para cierre'] < 0) & (df['Días para cierre'] >= -self.dias_gracia)].copy()
        
        self.stats['vigentes'] = len(vigentes)
        self.stats['vencidas'] = len(vencidas)
        
        self.logger.info(f"[OK] Vigentes: {len(vigentes):,}")
        self.logger.info(f"📦 Vencidas: {len(vencidas):,}")
        return vigentes, vencidas
    
    def _generar_excel(self, df_vigentes: pd.DataFrame, df_vencidas: pd.DataFrame):
        self.logger.subsection("Generando Excel")
        ts = obtener_timestamp()
        
        ruta_principal = self.config.PRESENTACION_ORIGINAL_DIR / f"Reporte_Licitaciones_{ts}.xlsx"
        self._guardar_formateado(df_vigentes, ruta_principal, "Licitaciones")
        self.logger.info(f"[OK] {ruta_principal.name}")
        
        if len(df_vencidas) > 0:
            ruta_historico = self.config.HISTORICO_DIR / f"Historico_Licitaciones_{ts}.xlsx"
            self._guardar_formateado(df_vencidas, ruta_historico, "Histórico")
            self.logger.info(f"📦 {ruta_historico.name}")
    
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
        col_dias = self.COLUMNAS.index("Días para cierre") + 1
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
    
    def _imprimir_resumen(self):
        s = self.stats
        self.logger.info(f"""
╔══════════════════════════════════════════════════════════════╗
║         ESTADÍSTICAS DE GENERACIÓN                           ║
╚══════════════════════════════════════════════════════════════╝

[#] Licitaciones:
   - Total:      {s['total']:,}
   - Vigentes:   {s['vigentes']:,}
   - Vencidas:   {s['vencidas']:,}

💱 Conversiones:
   - UTM→CLP:    {s['utm']:,}
   - USD→CLP:    {s['usd']:,}
   - Errores:    {s['errores']:,}

💰 Tasas:
   - UTM:        ${self.valor_utm:,.0f}
   - USD:        ${self.valor_usd:,.0f}
""")

def main():
    try:
        gen = GeneradorReporte()
        res = gen.ejecutar()
        if res['exito']:
            print("\n[OK] ETAPA 4 COMPLETADA")
            print(f"[#] {res['vigentes']:,} vigentes | 📦 {res['vencidas']:,} vencidas")
            return 0
        return 1
    except Exception as e:
        print(f"\n[X] ERROR: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
