# Filtrado inteligente de licitaciones usando PIVOT_MAESTRO

import re
import pandas as pd
from pathlib import Path
from typing import Tuple
from datetime import datetime
from utils import (normalizar_texto, validar_archivo_excel, encontrar_columna, guardar_excel_con_formato,
                       obtener_timestamp, leer_excel_con_header_dinamico)
from core.contracts import BaseStage, StageResult
from core.context import PipelineContext

class FiltradorLicitaciones(BaseStage):
    def __init__(self):
        super().__init__()
        self.stats = {'original': 0, 'incluidas': 0, 'excluidas': 0, 'bypass': 0, 
                     'final': 0, 'inicio': datetime.now()}
        self.filtros = None

    @property
    def name(self) -> str:
        return "filtrado"

    def validate_inputs(self, context: PipelineContext) -> bool:
        permite_fallback = context.flags.get('allow_fallback', False)
        archivo_entrada = context.get_artifact('etapa0_output')
        
        if not archivo_entrada:
            if not permite_fallback:
                raise ValueError("Modo pipeline: Fallo al iniciar Etapa 2. Falta artefacto 'etapa0_output'.")
            # Fallback explícito para stand-alone
            archivo_entrada = context.config.LICITACIONES_MP
            
        if not archivo_entrada or not archivo_entrada.exists():
            raise FileNotFoundError(f"El archivo de entrada no existe físicamente: {archivo_entrada}")
            
        return True
    def run(self, context: PipelineContext) -> StageResult:
        self.bind(context)
        self.logger.section("ETAPA 2 - FILTRADO INTELIGENTE", 80)
        self.logger.info(f"[>>] Iniciando filtrado - Versión 3.0.0 | RunID: {context.run_id}")
        self.logger.info(f"[DATE] Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            self.validate_inputs(context)
            archivo_entrada = context.get_artifact('etapa0_output') or self.config.LICITACIONES_MP
            
            self._validar_prerequisitos()
            
            df = self._cargar_licitaciones(archivo_entrada)
            self.stats['original'] = len(df)
            
            self.filtros = self._cargar_filtros()
            df_filtradas, df_excluidas = self._aplicar_filtrado(df)
            rutas_generadas = self._generar_outputs(df_filtradas, df_excluidas)
            if rutas_generadas and len(rutas_generadas) > 0:
                context.add_artifact('etapa2_output', rutas_generadas[0])
            
            self.stats['tiempo'] = datetime.now() - self.stats['inicio']
            self.logger.section("RESUMEN DE FILTRADO", 80)
            self._imprimir_resumen()
            
            return StageResult(
                success=True,
                stage_name=self.name,
                files_produced=rutas_generadas,
                metrics_produced=self.stats,
                custom_data={'stats': self.stats}
            )
        except Exception as e:
            self.logger.error(f"Error: {e}")
            return StageResult(success=False, stage_name=self.name, error_message=str(e), custom_data={'stats': self.stats})
        finally:
            self.logger.finalize()
    
    def _validar_prerequisitos(self):
        self.logger.subsection("Validando prerequisitos")
        valido, mensaje = validar_archivo_excel(self.config.PIVOT_MAESTRO, debe_existir=True, hojas_requeridas=['06-FILTROS'])
        if not valido:
            raise FileNotFoundError(f"PIVOT_MAESTRO: {mensaje}")
        self.logger.info("[OK] PIVOT_MAESTRO: OK")
    
    def _cargar_licitaciones(self, ruta: Path) -> pd.DataFrame:
        self.logger.subsection("Cargando licitaciones")
        df = leer_excel_con_header_dinamico(ruta, columna_referencia="Nivel 1")
        
        columnas_requeridas = [
            "Nombre Adquisición", "Descripción", "Nivel 1", "Nivel 2", "Nivel 3",
            "Genérico", "Organismo", "Tipo Adquisición", "Descripción del producto/servicio"
        ]
        
        faltantes = [col for col in columnas_requeridas if not encontrar_columna(df, col)]
        if faltantes:
            raise ValueError(f"El archivo origen no posee las columnas mínimas requeridas: {faltantes}")
            
        self.logger.info(f"[OK] {len(df):,} licitaciones, {len(df.columns)} columnas")
        return df
    
    # MULTI-AREA PASO 3a: Añadir _cargar_filtros_globales() que lee '06-EXCL-GLOBALES'
    # MULTI-AREA PASO 3b: Modificar _cargar_filtros(area='TI') para leer '06-FILTROS-{area}'
    #                     y fusionar con exclusiones globales
    def _cargar_filtros(self):
        self.logger.subsection("Cargando filtros desde PIVOT")
        # TODO: cambiar sheet_name a '06-FILTROS-{area}' cuando llegue PASO 3
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
    
    # MULTI-AREA PASO 3c: Refactorizar run() para iterar por áreas y añadir columna AREA
    # MULTI-AREA PASO 3d: Refactorizar _generar_outputs() para multi-hoja (RESUMEN + una por área)
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
        campos_map = [
            ("Nombre Adquisición (norm)", "nombre"),
            ("Descripción (norm)", "nombre"),
            ("Nivel 1 (norm)", "nivel1"),
            ("Nivel 2 (norm)", "nivel2"),
            ("Nivel 3 (norm)", "nivel3"),
        ]
        mask = pd.Series(False, index=df.index)
        for col, key in campos_map:
            palabras = self.filtros["incluir"].get(key, [])
            if col not in df.columns or not palabras:
                continue
            pattern = '|'.join(re.escape(p) for p in palabras)
            mask |= df[col].str.contains(pattern, regex=True, na=False, case=False)

        df_incluidas = df[mask]
        self.logger.info(f"🔍 Inclusión: {len(df_incluidas):,}/{len(df):,}")
        return df_incluidas
    
    def _aplicar_exclusion(self, df: pd.DataFrame) -> pd.DataFrame:
        campos_map = [
            ("Nombre Adquisición (norm)", "nombre"),
            ("Descripción (norm)", "nombre"),
            ("Nivel 1 (norm)", "nivel1"),
            ("Nivel 2 (norm)", "nivel2"),
            ("Nivel 3 (norm)", "nivel3"),
            ("Genérico (norm)", "generico"),
            ("Organismo (norm)", "organismo"),
            ("Tipo Adquisición (norm)", "valor"),
            ("Descripción del producto/servicio (norm)", "componente"),
        ]
        mask = pd.Series(False, index=df.index)
        for col, key in campos_map:
            palabras = self.filtros["excluir"].get(key, [])
            if col not in df.columns or not palabras:
                continue
            pattern = '|'.join(re.escape(p) for p in palabras)
            mask |= df[col].str.contains(pattern, regex=True, na=False, case=False)

        df_excluidas = df[mask]
        self.logger.info(f"🚫 Exclusión: {len(df_excluidas):,}/{len(df):,}")
        return df_excluidas
    
    def _aplicar_bypass(self, df_excluidas: pd.DataFrame) -> pd.DataFrame:
        if not self.filtros["bypass"] or len(df_excluidas) == 0:
            return pd.DataFrame()

        pattern = '|'.join(re.escape(p) for p in self.filtros["bypass"])
        cols = [
            "Nombre Adquisición (norm)",
            "Descripción (norm)",
            "Descripción del producto/servicio (norm)",
            "Organismo (norm)",
            "Tipo Adquisición (norm)",
        ]
        mask = pd.Series(False, index=df_excluidas.index)
        for col in cols:
            if col in df_excluidas.columns:
                mask |= df_excluidas[col].str.contains(pattern, regex=True, na=False, case=False)

        df_bypass = df_excluidas[mask]
        self.logger.info(f"🔄 Bypass: {len(df_bypass):,}")
        return df_bypass
    
    def _generar_outputs(self, df_filtradas: pd.DataFrame, df_excluidas: pd.DataFrame) -> list[Path]:
        self.logger.subsection("Generando archivos")
        timestamp = obtener_timestamp()
        archivos = []
        
        cols_remove = [col for col in df_filtradas.columns if '(norm)' in col]
        
        ruta = self.config.FILTRADO_DIR / f"Licitaciones_Filtradas_{timestamp}.xlsx"
        guardar_excel_con_formato(df_filtradas.drop(columns=cols_remove), ruta, nombre_hoja="Filtradas")
        self.logger.info(f"[OK] {ruta.name}")
        archivos.append(ruta)
        
        if len(df_excluidas) > 0:
            ruta_exc = self.config.FILTRADO_DIR / f"Licitaciones_Excluidas_{timestamp}.xlsx"
            guardar_excel_con_formato(df_excluidas.drop(columns=cols_remove), ruta_exc, nombre_hoja="Excluidas")
            self.logger.info(f"[OK] {ruta_exc.name}")
            archivos.append(ruta_exc)
        
        return archivos
    
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
    from core.context import PipelineContext
    from utils.config import Config
    try:
        context = PipelineContext(config=Config())
        context.flags['standalone_mode'] = True
        filtrador = FiltradorLicitaciones()
        resultado = filtrador.run(context)
        if resultado.success:
            print("\n✅ ETAPA 2 COMPLETADA")
            print(f"   * Licitaciones filtradas: {resultado.metrics_produced['final']:,}")
            print(f"   * Tasa de retención: {(resultado.metrics_produced['final']/resultado.metrics_produced['original']*100):.2f}%")
            return 0
        print(f"\n❌ ERROR: {resultado.error_message}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR CRITICO: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
