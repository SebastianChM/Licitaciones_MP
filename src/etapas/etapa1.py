"""ETAPA 1 - Auditoría de Taxonomía"""
__version__ = "3.0.0"

import pandas as pd
import openpyxl
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))
from src.utils import (Config, ProjectLogger, normalizar_texto, calcular_similitud, 
                      encontrar_similares, validar_archivo_excel, encontrar_columna,
                      leer_excel_con_header_dinamico, obtener_timestamp)

class AuditorTaxonomia:
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.logger = ProjectLogger('etapa1', self.config.LOG_DIR)
        self.umbral_alerta = self.config.ETAPA1_UMBRAL_ALERTA
        self.detectar_similares = self.config.ETAPA1_DETECTAR_SIMILARES
        self.umbral_similitud = self.config.ETAPA1_SIMILITUD_THRESHOLD
        self._cargar_parametros_pivot()
        self.stats = {'total_mp': 0, 'nuevos': 0, 'similares': 0, 'campos': 0, 'inicio': datetime.now()}
    
    def _cargar_parametros_pivot(self):
        try:
            params = self.config.cargar_desde_pivot()
            if 'Umbral de Alerta' in params:
                self.umbral_alerta = int(params['Umbral de Alerta'])
            if 'Detectar Similares' in params:
                self.detectar_similares = str(params['Detectar Similares']).lower() in ['true', '1', 'si', 'yes']
            if 'Umbral Similitud' in params:
                self.umbral_similitud = float(params['Umbral Similitud'])
        except Exception as e:
            self.logger.warning(f"No se cargaron parámetros PIVOT: {e}")
    
    def ejecutar(self) -> Dict[str, Any]:
        self.logger.section("ETAPA 1 - AUDITORÍA DE TAXONOMÍA", 80)
        self.logger.info(f"[>>] Iniciando v{__version__} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            self._validar_prerequisitos()
            df_mp, valores_pivot = self._cargar_datos()
            hallazgos = self._procesar_campos(df_mp, valores_pivot)
            
            if hallazgos['nuevos'] or hallazgos['similares']:
                ruta = self._generar_reporte(hallazgos)
                self.logger.info(f"[OK] Reporte: {ruta.name}")
            else:
                self.logger.info("[OK] Sin hallazgos (todos los valores existen)")
            
            self.stats['tiempo'] = datetime.now() - self.stats['inicio']
            self.logger.section("RESUMEN", 80)
            self._imprimir_resumen()
            
            return {'exito': True, 'stats': self.stats, 'hallazgos': hallazgos}
        except Exception as e:
            self.logger.error(f"[X] Error: {e}", exc_info=True)
            raise
        finally:
            self.logger.finalize()
    
    def _validar_prerequisitos(self):
        self.logger.subsection("Validando prerequisitos")
        for nombre, ruta in [('PIVOT_MAESTRO', self.config.PIVOT_MAESTRO),
                             ('Licitaciones MP', self.config.LICITACIONES_MP)]:
            valido, msg = validar_archivo_excel(ruta, debe_existir=True)
            if not valido:
                raise FileNotFoundError(f"{nombre}: {msg}")
            self.logger.info(f"[OK] {nombre}")
    
    def _cargar_datos(self) -> Tuple[pd.DataFrame, Dict[str, set]]:
        self.logger.subsection("Cargando datos")
        df_mp = leer_excel_con_header_dinamico(self.config.LICITACIONES_MP, columna_referencia="Nivel 1")
        self.stats['total_mp'] = len(df_mp)
        self.logger.info(f"[IN] {len(df_mp):,} licitaciones MP")
        
        valores_pivot = self._cargar_valores_pivot()
        for campo, valores in valores_pivot.items():
            self.logger.info(f"[PIVOT] {campo}: {len(valores):,} valores")
        
        return df_mp, valores_pivot
    
    def _cargar_valores_pivot(self) -> Dict[str, set]:
        wb = openpyxl.load_workbook(self.config.PIVOT_MAESTRO, data_only=True)
        ws = wb['04-BASE']
        valores = {'Nivel 1': set(), 'Nivel 2': set(), 'Nivel 3': set(), 'Generico': set()}
        
        header_row = None
        indices = {}
        for i, row in enumerate(ws.iter_rows(max_row=30), 1):
            vals = [normalizar_texto(str(c.value)) if c.value else "" for c in row[:10]]
            if any(('NIVEL' in v and '1' in v) or 'NIVEL1' in v for v in vals):
                header_row = i
                for j, celda in enumerate(row[:10]):
                    if celda.value:
                        norm = normalizar_texto(str(celda.value))
                        if 'NIVEL' in norm and '1' in norm:
                            indices['Nivel 1'] = j
                        elif 'NIVEL' in norm and '2' in norm:
                            indices['Nivel 2'] = j
                        elif 'NIVEL' in norm and '3' in norm:
                            indices['Nivel 3'] = j
                        elif 'GENERICO' in norm:
                            indices['Generico'] = j
                break
        
        if not header_row:
            wb.close()
            raise ValueError("No se encontró header en PIVOT_MAESTRO")
        
        for row in ws.iter_rows(min_row=header_row + 1):
            for campo, idx in indices.items():
                val = row[idx].value
                if val and not pd.isna(val):
                    valores[campo].add(normalizar_texto(val))
        
        wb.close()
        return valores
    
    def _procesar_campos(self, df_mp: pd.DataFrame, valores_pivot: Dict[str, set]) -> Dict[str, List]:
        self.logger.subsection("Procesando taxonomía")
        hallazgos = {'nuevos': [], 'similares': []}
        
        for campo in ['Nivel 1', 'Nivel 2', 'Nivel 3', 'Generico']:
            self.logger.info(f"\n[#] {campo}")
            col = encontrar_columna(df_mp, campo)
            if not col:
                self.logger.warning(f"   Columna '{campo}' no encontrada")
                continue
            
            conteo = df_mp[col].dropna().value_counts()
            self.logger.info(f"   {len(conteo):,} valores únicos")
            
            nuevos_campo = []
            similares_campo = []
            
            for valor, cant in conteo.items():
                norm = normalizar_texto(valor)
                if norm in valores_pivot[campo]:
                    continue
                
                nuevos_campo.append({
                    'campo': campo, 'valor': valor, 'normalizado': norm,
                    'ocurrencias': cant, 'porcentaje': (cant / len(df_mp)) * 100
                })
                
                if self.detectar_similares:
                    sims = encontrar_similares(norm, list(valores_pivot[campo]), umbral=self.umbral_similitud)
                    if sims:
                        similares_campo.append({
                            'campo': campo, 'valor_nuevo': valor,
                            'similares': sims, 'ocurrencias': cant
                        })
            
            nuevos_campo = [v for v in nuevos_campo if v['ocurrencias'] >= self.umbral_alerta]
            
            if nuevos_campo:
                self.logger.info(f"   ⚠️  {len(nuevos_campo)} NUEVOS")
                hallazgos['nuevos'].extend(nuevos_campo)
                self.stats['nuevos'] += len(nuevos_campo)
            
            if similares_campo:
                self.logger.info(f"   🔍 {len(similares_campo)} SIMILARES")
                hallazgos['similares'].extend(similares_campo)
                self.stats['similares'] += len(similares_campo)
            
            self.stats['campos'] += 1
        
        return hallazgos
    
    def _generar_reporte(self, hallazgos: Dict) -> Path:
        self.logger.subsection("Generando reporte")
        ruta = self.config.HALLAZGOS_DIR / f"HALLAZGOS_{obtener_timestamp()}.xlsx"
        
        with pd.ExcelWriter(ruta, engine='openpyxl') as writer:
            if hallazgos['nuevos']:
                df_nuevos = pd.DataFrame(hallazgos['nuevos']).sort_values(['campo', 'ocurrencias'], ascending=[True, False])
                df_nuevos.to_excel(writer, sheet_name='Valores Nuevos', index=False)
            
            if hallazgos['similares']:
                registros = []
                for item in hallazgos['similares']:
                    for similar, sim in item['similares']:
                        registros.append({
                            'Campo': item['campo'], 'Valor Nuevo': item['valor_nuevo'],
                            'Similar en PIVOT': similar, 'Similitud': f"{sim:.1%}",
                            'Ocurrencias': item['ocurrencias']
                        })
                pd.DataFrame(registros).to_excel(writer, sheet_name='Valores Similares', index=False)
        
        return ruta
    
    def _imprimir_resumen(self):
        s = self.stats
        self.logger.info(f"""
╔══════════════════════════════════════════════════════════════╗
║         ESTADÍSTICAS DE AUDITORÍA                            ║
╚══════════════════════════════════════════════════════════════╝

[#] Datos:
   - Licitaciones MP:    {s['total_mp']:,}
   - Campos:             {s['campos']}

⚠️  Hallazgos:
   - Valores nuevos:     {s['nuevos']:,}
   - Valores similares:  {s['similares']:,}

⏱️  Rendimiento:
   - Tiempo:             {s.get('tiempo', 'N/A')}

🔧 Parámetros:
   - Umbral alerta:      {self.umbral_alerta} ocurrencias
   - Similares:          {'Sí' if self.detectar_similares else 'No'}
   - Umbral similitud:   {self.umbral_similitud:.1%}
""")

def main():
    try:
        auditor = AuditorTaxonomia()
        res = auditor.ejecutar()
        if res['exito']:
            print("\n[OK] ETAPA 1 COMPLETADA")
            return 0
        return 1
    except Exception as e:
        print(f"\n[X] ERROR: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
