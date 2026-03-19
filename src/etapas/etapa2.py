# Filtrado inteligente de licitaciones usando PIVOT_MAESTRO

import pandas as pd
from pathlib import Path
from typing import Dict, Tuple, Optional
from datetime import datetime
import sys

sys.path.append(str(Path(__file__).parent.parent.parent))
from src.utils import (Config, ProjectLogger, normalizar_texto, contiene_palabras_clave,
                       validar_archivo_excel, encontrar_columna, guardar_excel_con_formato,
                       obtener_timestamp, leer_excel_con_header_dinamico)


class FiltradorLicitaciones:
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.logger = ProjectLogger('etapa2', self.config.LOG_DIR)
        self.stats = {'original': 0, 'incluidas': 0, 'excluidas': 0, 'bypass': 0, 
                     'final': 0, 'inicio': datetime.now()}
        self.filtros = None
    
    def ejecutar(self, archivo_entrada: Optional[Path] = None):
        self.logger.section("ETAPA 2 - FILTRADO INTELIGENTE", 80)
        self.logger.info(f"[>>] Iniciando filtrado - Versión 3.0.0")
        self.logger.info(f"[DATE] Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            self._validar_prerequisitos()
            archivo_entrada = archivo_entrada or self._obtener_archivo_entrada()
            
            df = self._cargar_licitaciones(archivo_entrada)
            self.stats['original'] = len(df)
            
            self.filtros = self._cargar_filtros()
            df_filtradas, df_excluidas = self._aplicar_filtrado(df)
            self._generar_outputs(df_filtradas, df_excluidas)
            
            self.stats['tiempo'] = datetime.now() - self.stats['inicio']
            self.logger.section("RESUMEN DE FILTRADO", 80)
            self._imprimir_resumen()
            
            return {'exito': True, 'total_filtradas': len(df_filtradas)}
        except Exception as e:
            self.logger.error(f"Error: {e}")
            raise
        finally:
            self.logger.finalize()
    
    def _validar_prerequisitos(self):
        self.logger.subsection("Validando prerequisitos")
        valido, mensaje = validar_archivo_excel(self.config.PIVOT_MAESTRO, debe_existir=True, hojas_requeridas=['06-FILTROS'])
        if not valido:
            raise FileNotFoundError(f"PIVOT_MAESTRO: {mensaje}")
        self.logger.info("[OK] PIVOT_MAESTRO: OK")
    
    def _obtener_archivo_entrada(self) -> Path:
        if self.config.LICITACIONES_MP.exists():
            self.logger.info(f"[IN] Usando: {self.config.LICITACIONES_MP.name}")
            return self.config.LICITACIONES_MP
        raise FileNotFoundError("No se encontró archivo de entrada")
    
    def _cargar_licitaciones(self, ruta: Path) -> pd.DataFrame:
        self.logger.subsection("Cargando licitaciones")
        df = leer_excel_con_header_dinamico(ruta, columna_referencia="Nivel 1")
        self.logger.info(f"[OK] {len(df):,} licitaciones, {len(df.columns)} columnas")
        return df
    
    def _cargar_filtros(self):
        self.logger.subsection("Cargando filtros desde PIVOT")
        
        df = pd.read_excel(self.config.PIVOT_MAESTRO, sheet_name='06-FILTROS', header=4)
        
        def clean_valores(col_idx):
            if col_idx >= len(df.columns):
                return []
            return [normalizar_texto(v) for v in df.iloc[:, col_idx].dropna().astype(str)
                   if v and str(v).lower() not in ['nan', 'none', '']]
        
        filtros = {
            "incluir": {k: clean_valores(i) for i, k in enumerate(['nombre', 'nivel1', 'nivel2', 'nivel3'])},
            "excluir": {k: clean_valores(i) for i, k in {4: 'nombre', 5: 'nivel1', 6: 'nivel2', 7: 'nivel3', 
                       8: 'generico', 9: 'componente', 10: 'organismo', 11: 'valor'}.items()},
            "bypass": clean_valores(12)
        }
        
        inc = sum(len(v) for v in filtros["incluir"].values())
        exc = sum(len(v) for v in filtros["excluir"].values())
        self.logger.info(f"[OK] Inclusión: {inc}, Exclusión: {exc}, Bypass: {len(filtros['bypass'])}")
        
        return filtros
    
    def _aplicar_filtrado(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        self.logger.subsection("Aplicando filtrado")
        df = self._preparar_campos_normalizados(df.copy())
        
        df_incluidas = self._aplicar_inclusion(df)
        self.stats['incluidas'] = len(df_incluidas)
        
        df_excluidas = self._aplicar_exclusion(df_incluidas)
        df_final = df_incluidas[~df_incluidas.index.isin(df_excluidas.index)]
        
        df_bypass = self._aplicar_bypass(df_excluidas)
        self.stats['bypass'] = len(df_bypass)
        
        df_filtradas = pd.concat([df_final, df_bypass], ignore_index=True) if len(df_bypass) > 0 else df_final
        
        # Remove duplicates
        col_codigo = encontrar_columna(df_filtradas, "Numero Adquisición")
        if col_codigo:
            df_filtradas = df_filtradas.drop_duplicates(subset=[col_codigo])
        
        self.stats['final'] = len(df_filtradas)
        self.stats['excluidas'] = len(df_excluidas)
        
        self.logger.info(f"[OK] Filtradas: {len(df_filtradas):,}/{len(df):,} ({len(df_bypass):,} por bypass)")
        return df_filtradas, df_excluidas
    
    def _preparar_campos_normalizados(self, df: pd.DataFrame) -> pd.DataFrame:
        campos = ["Nombre Adquisición", "Descripción", "Nivel 1", "Nivel 2", "Nivel 3",
                 "Genérico", "Organismo", "Tipo Adquisición", "Descripción del producto/servicio"]
        for campo in campos:
            col_real = encontrar_columna(df, campo)
            if col_real:
                df[f"{campo} (norm)"] = df[col_real].astype(str).apply(normalizar_texto)
        return df
    
    def _aplicar_inclusion(self, df: pd.DataFrame) -> pd.DataFrame:
        def cumple(row):
            campos = [("Nombre Adquisición (norm)", "nombre"), ("Descripción (norm)", "nombre"),
                     ("Nivel 1 (norm)", "nivel1"), ("Nivel 2 (norm)", "nivel2"), ("Nivel 3 (norm)", "nivel3")]
            for campo, key in campos:
                if campo in df.columns and pd.notna(row[campo]):
                    if contiene_palabras_clave(str(row[campo]), self.filtros["incluir"][key]):
                        return True
            return False
        
        df_incluidas = df[df.apply(cumple, axis=1)]
        self.logger.info(f"🔍 Inclusión: {len(df_incluidas):,}/{len(df):,}")
        return df_incluidas
    
    def _aplicar_exclusion(self, df: pd.DataFrame) -> pd.DataFrame:
        def cumple(row):
            campos = [("Nombre Adquisición (norm)", "nombre"), ("Descripción (norm)", "nombre"),
                     ("Nivel 1 (norm)", "nivel1"), ("Nivel 2 (norm)", "nivel2"), ("Nivel 3 (norm)", "nivel3"),
                     ("Genérico (norm)", "generico"), ("Organismo (norm)", "organismo"), 
                     ("Tipo Adquisición (norm)", "valor"), ("Descripción del producto/servicio (norm)", "componente")]
            for campo, key in campos:
                if campo in df.columns and pd.notna(row[campo]):
                    if contiene_palabras_clave(str(row[campo]), self.filtros["excluir"][key]):
                        return True
            return False
        
        df_excluidas = df[df.apply(cumple, axis=1)]
        self.logger.info(f"🚫 Exclusión: {len(df_excluidas):,}/{len(df):,}")
        return df_excluidas
    
    def _aplicar_bypass(self, df_excluidas: pd.DataFrame) -> pd.DataFrame:
        if not self.filtros["bypass"] or len(df_excluidas) == 0:
            return pd.DataFrame()
        
        def cumple(row):
            campos = ["Nombre Adquisición (norm)", "Descripción (norm)", "Descripción del producto/servicio (norm)", 
                     "Organismo (norm)", "Tipo Adquisición (norm)"]
            for campo in campos:
                if campo in df_excluidas.columns and pd.notna(row[campo]):
                    if contiene_palabras_clave(str(row[campo]), self.filtros["bypass"]):
                        return True
            return False
        
        df_bypass = df_excluidas[df_excluidas.apply(cumple, axis=1)]
        self.logger.info(f"🔄 Bypass: {len(df_bypass):,}")
        return df_bypass
    
    def _generar_outputs(self, df_filtradas: pd.DataFrame, df_excluidas: pd.DataFrame):
        self.logger.subsection("Generando archivos")
        timestamp = obtener_timestamp()
        
        cols_remove = [col for col in df_filtradas.columns if '(norm)' in col]
        
        ruta = self.config.FILTRADO_DIR / f"Licitaciones_Filtradas_{timestamp}.xlsx"
        guardar_excel_con_formato(df_filtradas.drop(columns=cols_remove), ruta, nombre_hoja="Filtradas")
        self.logger.info(f"[OK] {ruta.name}")
        
        if len(df_excluidas) > 0:
            ruta_exc = self.config.FILTRADO_DIR / f"Licitaciones_Excluidas_{timestamp}.xlsx"
            guardar_excel_con_formato(df_excluidas.drop(columns=cols_remove), ruta_exc, nombre_hoja="Excluidas")
            self.logger.info(f"[OK] {ruta_exc.name}")
    
    def _imprimir_resumen(self):
        s = self.stats
        pct = (s['final'] / s['original'] * 100) if s['original'] > 0 else 0
        
        self.logger.info(f"""
╔══════════════════════════════════════════════════════════════╗
║              ESTADÍSTICAS DE FILTRADO                        ║
╚══════════════════════════════════════════════════════════════╝

[#] Procesamiento:
   - Total original:        {s['original']:,}
   - Total incluidas:       {s['incluidas']:,}
   - Total excluidas:       {s['excluidas']:,}
   - Recuperadas (bypass):  {s['bypass']:,}
   - Total final:           {s['final']:,}

📈 Eficiencia:
   - % Retenido:            {pct:.1f}%
   - Reducción:             {s['original'] - s['final']:,} licitaciones

⏱️  Rendimiento:
   - Tiempo total:          {s.get('tiempo', 'N/A')}
""")


def main():
    try:
        filtrador = FiltradorLicitaciones()
        resultado = filtrador.ejecutar()
        print("\n✅ ETAPA 2 COMPLETADA")
        print(f"   * Licitaciones filtradas: {resultado['total_filtradas']:,}")
        print(f"   * Tasa de retención: {(resultado['total_filtradas']/filtrador.stats['original']*100):.2f}%")
        return 0
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
