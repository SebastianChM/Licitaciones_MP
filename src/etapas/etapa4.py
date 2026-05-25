"""Etapa 4 — genera el reporte ejecutivo Excel con formato profesional MP."""
from importlib.metadata import version as _pkg_version

__version__ = _pkg_version("licitaciones-mp")

import re
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar

import pandas as pd
import pytz

from core.context import PipelineContext
from core.contracts import BaseStage, StageResult
from utils import Config, obtener_timestamp
from utils.excel_formatter import guardar_formateado_reporte
from utils.http import HTTPClient


class GeneradorReporte(BaseStage):
    """Genera el reporte ejecutivo Excel con formato MP, conversión de divisas y separación por vigencia."""
    REGEX_NUMERO = r'[^\d.]'
    
    COLUMNAS: ClassVar[list[str]] = ["LINK", "Numero Adquisición", "Nombre", "Descripción", "Región", "Cliente (Organismo)",
                "Fecha Publicación", "Hora Publicación", "Fecha Inicio Preguntas", "Hora Inicio Preguntas",
                "Fecha Cierre Preguntas", "Hora Cierre Preguntas", "Fecha Apertura", "Hora Apertura",
                "Fecha Cierre Licitación", "Hora Cierre Licitación", "Fecha Adjudicación", "Hora Adjudicación",
                "Monto Estimado (CLP)", "Días para cierre", "ONU", "Nivel 1", "Nivel 2", "Nivel 3",
                "Genérico", "Trazabilidad", "Nivel Confianza"]
    
    SINONIMOS: ClassVar[dict[str, list[str]]] = {
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
        "Trazabilidad": ["Trazabilidad Filtro", "Trazabilidad", "Motivo Inclusión"],
        "Nivel Confianza": ["Nivel Confianza"]
    }
    
    def __init__(self) -> None:
        super().__init__()
        self.valor_utm = 0.0
        self.valor_usd = 1000.0
        self.dias_gracia = 0
        self.tz_chile = pytz.timezone('America/Santiago')
        self.stats = {'total': 0, 'vigentes': 0, 'vencidas': 0, 'utm': 0, 'usd': 0, 'errores': 0}

    @property
    def name(self) -> str:
        return "reporte"

    def validate_inputs(self, context: PipelineContext) -> bool:
        permite_fallback = context.flags.get('allow_fallback', False)
        archivo_entrada = context.get_artifact('etapa3_output')
        
        if not archivo_entrada:
            if not permite_fallback:
                raise ValueError("Modo pipeline: Fallo al iniciar Etapa 4. Falta artefacto 'etapa3_output'.")
            archivo_entrada = self._obtener_archivo(context)
            
        if not archivo_entrada or not archivo_entrada.exists():
            raise FileNotFoundError(f"El archivo de entrada no existe físicamente: {archivo_entrada}")
            
        # Validación mínima del formato de Excel para prevenir lecturas ciegas
        try:
            pd.read_excel(archivo_entrada, engine='openpyxl', nrows=1)
        except Exception as e:
            raise ValueError(f"El archivo base proporcionado no es un Excel válido o está corrupto: {e!s}") from e
            
        return True
    def _execute(self, context: PipelineContext) -> StageResult:
        """Genera el reporte Excel a partir del archivo enriquecido de etapa 3."""
        self.http = HTTPClient(self.logger, max_retries=2, timeout=10)
        self.logger.section("ETAPA 4 - GENERACIÓN DE REPORTE EJECUTIVO", 80)
        self.logger.info(f"[>>] Iniciando generación - v{__version__} | RunID: {context.run_id}")
        
        try:
            self.valor_utm = self.config.ETAPA4_VALOR_UTM
            self.valor_usd = self.config.ETAPA4_VALOR_USD_CLP
            self.dias_gracia = self.config.ETAPA4_DIAS_GRACIA_HISTORICO

            self._actualizar_tasas()
            archivo = context.get_artifact('etapa3_output') or self._obtener_archivo(context)
            df_raw = pd.read_excel(archivo, engine='openpyxl')
            
            self.stats['total'] = len(df_raw)
            self.logger.info(f"[IN] {len(df_raw):,} licitaciones cargadas")
            
            df_procesado = self._preparar_reporte(df_raw)
            df_vigentes, df_vencidas = self._separar(df_procesado)
            rutas_generadas = self._generar_excel(df_vigentes, df_vencidas)
            
            if not rutas_generadas:
                raise ValueError("No se generó el Excel final. Abortando salida exitosa.")
                
            context.add_artifact('etapa4_output', rutas_generadas[0])
            if len(rutas_generadas) > 1:
                context.add_artifact('etapa4_historico', rutas_generadas[1])
            
            self.logger.section("RESUMEN", 80)
            self._imprimir_resumen()
            
            warnings = []
            if self.stats['errores'] > 0:
                warnings.append(f"Hubo {self.stats['errores']} conversiones de divisa o limpieza numéricas fallidas.")
                
            return StageResult(
                success=True,
                stage_name=self.name,
                files_produced=rutas_generadas,
                metrics_produced=self.stats,
                custom_data={'stats': self.stats, 'vigentes': len(df_vigentes), 'vencidas': len(df_vencidas)},
                warnings=warnings
            )
        except Exception as e:
            self.logger.error(f"[X] Error crítico Etapa 4: {e}", exc_info=True)
            return StageResult(success=False, stage_name=self.name, error_message=str(e), metrics_produced=self.stats)

    def _cleanup(self) -> None:
        """Cierra el cliente HTTP al finalizar la etapa."""
        if hasattr(self, 'http') and self.http:
            self.http.close()
    
    def _actualizar_tasas(self) -> None:
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
        apikey = self.config.cmf_api_key
        if not apikey:
            raise ValueError("CMF API key no configurada (LICIT_CMF_API_KEY). No se puede actualizar UTM de la API.")
        url = getattr(self.config, 'cmf_utm_url', "https://api.cmfchile.cl/api-sbifv3/recursos_api/utm")
        r = self.http.get(url, params={'apikey': apikey, 'formato': 'json'})
        try:
            payload = r.json()
        except ValueError as e:
            raise ValueError(f"Respuesta CMF no es JSON válido: {e}") from e
        # CMF puede devolver {'Valor': '68.785,00'} o {'UTMs':[{'Valor':...}]}
        valor_raw = payload.get('Valor')
        if valor_raw is None:
            utms = payload.get('UTMs') or []
            if utms and isinstance(utms, list) and isinstance(utms[0], dict):
                valor_raw = utms[0].get('Valor')
        if valor_raw is None or valor_raw == '':
            raise ValueError(f"Estructura inesperada en respuesta CMF (claves: {list(payload.keys())})")
        # CMF usa coma decimal y punto de miles → normalizar
        valor_str = str(valor_raw).replace('.', '').replace(',', '.') if isinstance(valor_raw, str) else str(valor_raw)
        return float(valor_str)

    def _obtener_usd(self) -> float:
        # frankfurter.app: gratuito, sin API key, mantenido activamente
        url = getattr(self.config, 'fx_provider_url', "https://api.frankfurter.app/latest")
        r = self.http.get(url, params={'from': 'USD', 'to': 'CLP'})
        try:
            payload = r.json()
        except ValueError as e:
            raise ValueError(f"Respuesta FX no es JSON válido: {e}") from e
        rates = payload.get('rates') if isinstance(payload, dict) else None
        if not isinstance(rates, dict) or 'CLP' not in rates:
            raise ValueError(f"Estructura inesperada en respuesta FX (claves: {list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__})")
        return float(rates['CLP'])
    
    def _obtener_archivo(self, context: PipelineContext) -> Path:
        archivos = list(context.config.ENRIQUECIDO_DIR.glob("Licitaciones_Enriquecidas_*.xlsx"))
        if not archivos:
            raise FileNotFoundError(f"No hay archivo de base en fallback en {context.config.ENRIQUECIDO_DIR}")
        archivos = sorted(archivos, key=lambda f: f.stat().st_mtime, reverse=True)
        return archivos[0]
    
    def _preparar_reporte(self, df_raw: pd.DataFrame) -> pd.DataFrame:
        self.logger.subsection("Preparando reporte")
        data = {}
        
        for col in self.COLUMNAS:
            if col == "LINK":
                data[col] = df_raw['Numero Adquisición'].apply(
                    lambda x: f"https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idlicitacion={x!s}"
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
            if col == "Numero Adquisición" and not col_fuente:
                raise ValueError(f"Falta columna base mandatoria para el reporte ejecutivo: {self.SINONIMOS['Numero Adquisición']}")
                
            data[col] = df_raw[col_fuente].astype(str) if col_fuente else ""
        
        df = pd.DataFrame(data)
        df['Monto Estimado (CLP)'] = df_raw.apply(self._convertir_monto, axis=1)
        df['Días para cierre'] = df.apply(self._calcular_dias, axis=1)
        
        self.logger.info(f"[OK] Reporte preparado: {len(df)} filas")
        return df
    
    def _extraer_hora(self, timestamp: Any) -> str:
        try:
            if pd.isna(timestamp) or str(timestamp) in ['', 'nan', 'None']:
                return ""
            dt = pd.to_datetime(timestamp, errors='coerce')
            if pd.isna(dt):
                return ""
            return dt.strftime('%H:%M')
        except Exception:
            return ""
    
    @staticmethod
    def _campo(row: pd.Series, *keys: str) -> Any:
        """Devuelve el primer valor no-nulo y no-NaN de las claves dadas."""
        for k in keys:
            v = row.get(k)
            try:
                if v is not None and not pd.isna(v):
                    return v
            except (TypeError, ValueError):
                if v is not None:
                    return v
        return None

    def _convertir_monto(self, row: pd.Series) -> int:
        try:
            # Buscar moneda: primero campo directo, luego columna API (producida por Etapa 3)
            # Nota: pd.NaN es truthy en Python → no usar `or` directamente con valores de Series
            moneda = str(self._campo(row, 'Moneda', 'API_Moneda') or '').upper().strip()
            # Buscar monto: primero campo directo, luego columna API
            monto_raw = str(self._campo(row, 'Monto', 'API_Monto') or '0')

            if moneda in ['CLP', 'PESO']:
                # Strip ALL non-digit chars — handles thousands separators like '5.000.000'
                monto_str = re.sub(r'[^\d]', '', monto_raw)
                return int(monto_str) if monto_str else 0

            if 'UTM' in moneda:
                tipo = str(row.get('Tipo Adquisición', ''))
                nums = re.findall(r'(\d+(?:\.\d+)?)', tipo.replace('.', '').replace(',', '.'))
                if nums:
                    self.stats['utm'] += 1
                    return int(float(nums[0]) * self.valor_utm)
                # Sin número en Tipo Adquisición: monto indeterminado, no es error de conversión
                return 0

            if moneda in ['USD', 'DOLAR']:
                monto_str = re.sub(self.REGEX_NUMERO, '', monto_raw)
                if not monto_str:
                    return 0
                monto = float(monto_str)
                if monto > 0:
                    self.stats['usd'] += 1
                    return int(monto * self.valor_usd)

            # Fallback genérico: strip de TODOS los no-dígitos (igual que CLP) para soportar
            # formato chileno de miles ("2.000.000") sin generar ValueError en float()
            monto_str = re.sub(r'[^\d]', '', monto_raw)
            return int(monto_str) if monto_str else 0
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
    
    def _separar(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        self.logger.subsection("Separando vigentes/vencidas")
        vigentes = df[(df['Días para cierre'] >= 0) | (df['Días para cierre'] == 999)].copy()
        vencidas = df[(df['Días para cierre'] < 0) & (df['Días para cierre'] >= -self.dias_gracia)].copy()
        
        self.stats['vigentes'] = len(vigentes)
        self.stats['vencidas'] = len(vencidas)
        
        self.logger.info(f"[OK] Vigentes: {len(vigentes):,}")
        self.logger.info(f"📦 Vencidas: {len(vencidas):,}")
        return vigentes, vencidas
    
    def _generar_excel(self, df_vigentes: pd.DataFrame, df_vencidas: pd.DataFrame) -> list[Path]:
        self.logger.subsection("Generando Excel")
        ts = obtener_timestamp()
        
        ruta_principal = self.config.PRESENTACION_ORIGINAL_DIR / f"Reporte_Licitaciones_{ts}.xlsx"
        guardar_formateado_reporte(df_vigentes, ruta_principal, "Licitaciones")
        self.logger.info(f"[OK] {ruta_principal.name}")
        rutas_generadas = [ruta_principal]
        
        if len(df_vencidas) > 0:
            ruta_historico = self.config.HISTORICO_DIR / f"Historico_Licitaciones_{ts}.xlsx"
            guardar_formateado_reporte(df_vencidas, ruta_historico, "Histórico")
            self.logger.info(f"📦 {ruta_historico.name}")
            rutas_generadas.append(ruta_historico)
            
        return rutas_generadas
    
    def _imprimir_resumen(self) -> None:
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

def main() -> int | None:
    from utils.logger import configurar_consola_utf8
    configurar_consola_utf8()
    try:
        context = PipelineContext(config=Config())
        context.flags['allow_fallback'] = True
        gen = GeneradorReporte()
        res = gen.run(context)
        if res.success:
            print("\n[OK] ETAPA 4 COMPLETADA")
            print(f"[#] {res.custom_data.get('vigentes')} vigentes | 📦 {res.custom_data.get('vencidas')} vencidas")
            return 0
        print(f"\n[X] ERROR FATAL ETAPA 4: {res.error_message}")
        return 1
    except Exception as e:
        print(f"\n[X] ERROR DE CAPA SUPERIOR: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
