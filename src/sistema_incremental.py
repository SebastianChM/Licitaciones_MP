# Sistema de Análisis Incremental y Sugerencias de Filtros
# Ejecuta análisis completo de cambios y genera recomendaciones

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from src.utils import Config, AnalizadorIncremental, ProjectLogger
from src.etapas.etapa1 import AuditorTaxonomia
import pandas as pd
import json
from datetime import datetime


class SistemaAnalisisIncremental:
    """Sistema completo de análisis incremental y sugerencias"""
    
    def __init__(self):
        self.config = Config()
        self.logger = ProjectLogger('sistema_incremental', self.config.LOG_DIR)
        self.analizador = AnalizadorIncremental(self.config)
        
    def ejecutar_analisis_completo(self):
        """Ejecuta análisis completo del sistema"""
        
        self.logger.section("SISTEMA DE ANÁLISIS INCREMENTAL", 80)
        self.logger.info("🔍 Iniciando análisis completo...")
        
        try:
            # Cargar datos más recientes
            datos_actuales = self._cargar_datos_actuales()
            if datos_actuales is None or len(datos_actuales) == 0:
                self.logger.warning("⚠️ No se encontraron datos actuales para analizar")
                return
            
            self.logger.info(f"📊 Datos cargados: {len(datos_actuales):,} licitaciones")
            
            # 1. Análisis de cambios en taxonomía
            self.logger.subsection("Análisis de Taxonomía")
            analisis_taxonomia = self.analizador.analizar_cambios_taxonomia(datos_actuales)
            
            # 2. Análisis incremental de reporte
            self.logger.subsection("Análisis de Reporte")
            analisis_reporte = self.analizador.analizar_reporte_incremental(datos_actuales)
            
            # 3. Generar reporte completo
            self.logger.subsection("Generando Reporte")
            reporte_completo = self.analizador.generar_reporte_cambios(analisis_taxonomia, analisis_reporte)
            
            # 4. Mostrar resultados
            self._mostrar_resultados_detallados(reporte_completo)
            
            # 5. Generar sugerencias para PIVOT
            self._generar_sugerencias_pivot(analisis_taxonomia)
            
            self.logger.info("✅ Análisis incremental completado exitosamente")
            
        except Exception as e:
            self.logger.error(f"❌ Error en análisis: {e}")
            raise
        finally:
            self.logger.finalize()
    
    def _cargar_datos_actuales(self):
        """Carga los datos más actuales del pipeline"""
        
        # Intentar cargar desde licitaciones filtradas más recientes
        try:
            archivos_filtrados = list(self.config.FILTRADO_DIR.glob("Licitaciones_Filtradas_*.xlsx"))
            if archivos_filtrados:
                archivo_mas_reciente = max(archivos_filtrados, key=lambda x: x.stat().st_mtime)
                df = pd.read_excel(archivo_mas_reciente)
                self.logger.info(f"📂 Usando datos filtrados: {archivo_mas_reciente.name}")
                return df
        except Exception as e:
            self.logger.warning(f"⚠️ Error cargando filtrados: {e}")
        
        # Fallback: cargar desde datos raw
        try:
            if self.config.LICITACIONES_MP.exists():
                df = pd.read_excel(self.config.LICITACIONES_MP)
                self.logger.info(f"📂 Usando datos raw: {self.config.LICITACIONES_MP.name}")
                return df
        except Exception as e:
            self.logger.warning(f"⚠️ Error cargando raw: {e}")
        
        return None
    
    def _mostrar_resultados_detallados(self, reporte: dict):
        """Muestra resultados detallados del análisis"""
        
        resumen = reporte['resumen']
        
        self.logger.info("📈 RESUMEN DE CAMBIOS DETECTADOS:")
        self.logger.info("")
        
        # Taxonomía
        tax = resumen['taxonomia']
        total_nuevos = sum(tax.values())
        self.logger.info(f"🗂️  TAXONOMÍA ({total_nuevos} nuevos valores):")
        self.logger.info(f"   • Nivel 1: {tax['nuevos_nivel1']} nuevos")
        self.logger.info(f"   • Nivel 2: {tax['nuevos_nivel2']} nuevos")
        self.logger.info(f"   • Nivel 3: {tax['nuevos_nivel3']} nuevos")
        self.logger.info(f"   • Genéricos: {tax['nuevos_genericos']} nuevos")
        self.logger.info("")
        
        # Licitaciones
        lic = resumen['licitaciones']
        self.logger.info(f"📋 LICITACIONES:")
        self.logger.info(f"   • Nuevas: {lic['nuevas']} (requieren procesamiento)")
        self.logger.info(f"   • Existentes: {lic['existentes']} (preservar trabajo manual)")
        self.logger.info(f"   • Vencidas: {lic['vencidas']} (mover a histórico)")
        self.logger.info("")
        
        # Sugerencias
        sug = resumen['sugerencias_filtros']
        total_sug = sug['inclusion'] + sug['exclusion']
        self.logger.info(f"🎯 SUGERENCIAS DE FILTROS ({total_sug} total):")
        self.logger.info(f"   • Para Inclusión: {sug['inclusion']} términos")
        self.logger.info(f"   • Para Exclusión: {sug['exclusion']} términos")
        self.logger.info("")
    
    def _generar_sugerencias_pivot(self, analisis_taxonomia: dict):
        """Genera archivo de sugerencias para actualizar PIVOT_MAESTRO"""
        
        sugerencias = analisis_taxonomia['sugerencias_filtros']
        
        # Crear archivo de sugerencias
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        archivo_sugerencias = self.config.LOG_DIR / f"sugerencias_filtros_{timestamp}.json"
        
        sugerencias_para_pivot = {
            'timestamp': timestamp,
            'instrucciones': {
                'inclusion': "Agregue estos términos a la columna de inclusión en PIVOT_MAESTRO hoja 06-FILTROS",
                'exclusion': "Agregue estos términos a la columna de exclusión en PIVOT_MAESTRO hoja 06-FILTROS"
            },
            'sugerencias_inclusion': sugerencias['inclusion'],
            'sugerencias_exclusion': sugerencias['exclusion']
        }
        
        with open(archivo_sugerencias, 'w', encoding='utf-8') as f:
            json.dump(sugerencias_para_pivot, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"💾 Sugerencias guardadas: {archivo_sugerencias.name}")
        
        # Mostrar top sugerencias
        if sugerencias['inclusion']:
            self.logger.info("🎯 TOP SUGERENCIAS DE INCLUSIÓN:")
            for i, sug in enumerate(sugerencias['inclusion'][:5], 1):
                self.logger.info(f"   {i}. '{sug['termino']}' - {sug['razon']}")
        
        if sugerencias['exclusion']:
            self.logger.info("🚫 TOP SUGERENCIAS DE EXCLUSIÓN:")
            for i, sug in enumerate(sugerencias['exclusion'][:5], 1):
                self.logger.info(f"   {i}. '{sug['termino']}' - {sug['razon']}")


def main():
    """Función principal"""
    try:
        sistema = SistemaAnalisisIncremental()
        sistema.ejecutar_analisis_completo()
        print("\n✅ ANÁLISIS INCREMENTAL COMPLETADO")
        print("📁 Revisa los archivos JSON generados en la carpeta de logs")
        print("🎯 Las sugerencias de filtros están listas para aplicar al PIVOT_MAESTRO")
        return 0
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return 1


if __name__ == "__main__":
    exit(main())