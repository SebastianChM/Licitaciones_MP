"""Etapa 2 — filtrado inteligente multi-equipo.

Reduce el universo nacional de licitaciones diarias a las relevantes para el
equipo MP seleccionado. Cada equipo (Telecom, Arquitectura, Eléctrica, etc.)
tiene su propio FilterProfile cargado dinámicamente desde PIVOT_MAESTRO.xlsx.

Flujo:
    1. ProfileRegistry.buscar(código)  -> EquipoInfo
    2. ProfileLoader.cargar(equipo)    -> FilterProfile (inmutable)
    3. Aplicar inclusión / exclusión / bypass / exclusión dura sobre el DataFrame

El código del equipo se lee de:
    - context.flags['equipo']              (mayor prioridad, ej: --equipo ARQ)
    - context.config.equipo_seleccionado   (default desde config_usuario.json)
    - 'TELECOM'                            (fallback histórico)
"""
from importlib.metadata import version as _pkg_version

__version__ = _pkg_version("licitaciones-mp")

import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from core.context import PipelineContext
from core.contracts import BaseStage, StageResult
from core.filter_profile import FilterProfile
from core.profile_loader import PivotConfigError, ProfileLoader, ProfileRegistry, ProfileValidator
from utils import (
    encontrar_columna,
    guardar_excel_con_formato,
    leer_excel_con_header_dinamico,
    normalizar_texto,
    obtener_timestamp,
    validar_archivo_excel,
)


class FiltradorLicitaciones(BaseStage):
    """Filtra el universo nacional de licitaciones aplicando el FilterProfile del equipo activo."""
    # Keywords con longitud ≤ este umbral usan \b word-boundary en INCLUSIÓN para
    # evitar falsos positivos por substring matching. Cubre acrónimos típicos de
    # 2-4 chars (BI, IA, AI, DW, ITS, ITO, GPS, IOT, CCTV, MPLS, NGFW, SIEM…) que
    # de otro modo matchean dentro de palabras españolas no relacionadas
    # (p.ej. "ITO" capturaba "circuITO", "depósITO"; "IA" capturaba "familIA").
    # Las siglas siempre deben matchearse como palabra completa; si el usuario
    # quiere capturar la forma plural/derivada (p.ej. "REDES") debe agregarla
    # explícitamente al pivot — no inferir derivaciones por substring.
    _WORD_BOUNDARY_MAX_LEN = 4
    # Para BYPASS, mismo criterio: siglas técnicas (WAN, MPLS, VPN…) deben ser
    # palabra completa para evitar capturar en nombres propios (WANDERSLEBEN, SWAN).
    _BYPASS_WORD_BOUNDARY_MAX_LEN = 4
    # Campos de texto libre donde solo se matchean frases (≥2 palabras) para
    # evitar que keywords genéricas de una sola palabra generen falsos positivos.
    _CAMPOS_SOLO_FRASES = frozenset({"Descripción (norm)"})
    # Código de equipo default cuando no se especifica nada.
    _EQUIPO_DEFAULT = "TELECOM"
    # Umbral de "exclusión tóxica": si una sola keyword del filtro de exclusión
    # impacta a más de este % del universo original, se considera demasiado
    # genérica (probablemente palabra como "ADQUISICION" matcheando todos los
    # tipos de adquisición). Se emite un WARNING en el log y queda persistido
    # en stats['exclusiones_toxicas'] para el dashboard de la GUI.
    _UMBRAL_EXCLUSION_TOXICA_PCT: float = 10.0

    def __init__(self) -> None:
        super().__init__()
        self.stats = {'original': 0, 'incluidas': 0, 'excluidas': 0, 'bypass': 0,
                     'exclusion_dura': 0, 'intencion_vetadas': 0,
                     'confianza_alta': 0, 'confianza_revisar': 0,
                     'final': 0, 'inicio': datetime.now()}
        self.profile: FilterProfile | None = None

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
    def _execute(self, context: PipelineContext) -> StageResult:
        """Ejecuta el filtrado y produce el Excel con las licitaciones relevantes para MP."""
        self.logger.section("ETAPA 2 - FILTRADO INTELIGENTE", 80)
        self.logger.info(f"[>>] Iniciando filtrado - v{__version__} | RunID: {context.run_id}")
        self.logger.info(f"[DATE] Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            archivo_entrada = context.get_artifact('etapa0_output') or self.config.LICITACIONES_MP
            
            self._validar_prerequisitos()
            
            df = self._cargar_licitaciones(archivo_entrada)
            self.stats['original'] = len(df)

            self.profile = self._cargar_perfil(context)
            self.stats['equipo'] = self.profile.equipo.codigo
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
    
    def _validar_prerequisitos(self) -> None:
        self.logger.subsection("Validando prerequisitos")
        valido, mensaje = validar_archivo_excel(
            self.config.PIVOT_MAESTRO,
            debe_existir=True,
            hojas_requeridas=['00-Equipos'],
        )
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
    
    def _cargar_perfil(self, context: PipelineContext) -> FilterProfile:
        """Carga el FilterProfile del equipo activo. El código de equipo se obtiene de:
        context.flags['equipo'] → context.config.equipo_seleccionado → _EQUIPO_DEFAULT."""
        self.logger.subsection("Cargando perfil del equipo")
        codigo_equipo = (
            context.flags.get('equipo')
            or getattr(context.config, 'equipo_seleccionado', None)
            or self._EQUIPO_DEFAULT
        )

        registry = ProfileRegistry(self.config.PIVOT_MAESTRO)
        loader = ProfileLoader(self.config.PIVOT_MAESTRO)

        try:
            equipo = registry.buscar(codigo_equipo)
        except PivotConfigError as e:
            raise ValueError(f"Equipo inválido: {e}") from e

        profile = loader.cargar(equipo)

        # Validación no-bloqueante: advertir si el perfil tiene problemas
        for problema in ProfileValidator.validar(profile):
            self.logger.warning(f"[!] {problema}")

        r = profile.resumen()
        self.logger.info(
            f"[OK] Equipo: {equipo.codigo} ({equipo.nombre}) | "
            f"Inclusión: {r['total_incluir']}, Exclusión: {r['total_excluir']}, "
            f"Bypass: {r['bypass']}, Excl.dura: {r['exclusion_dura']}"
        )
        return profile

    def _aplicar_filtrado(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        self.logger.subsection("Aplicando filtrado")
        df = self._preparar_campos_normalizados(df.copy())
        
        df_incluidas = self._aplicar_inclusion(df)
        self.stats['incluidas'] = len(df_incluidas)
        
        df_excluidas = self._aplicar_exclusion(df_incluidas)
        df_final = df_incluidas[~df_incluidas.index.isin(df_excluidas.index)]
        
        df_bypass = self._aplicar_bypass(df_excluidas)
        self.stats['bypass'] = len(df_bypass)
        
        df_filtradas = pd.concat([df_final, df_bypass], ignore_index=True) if len(df_bypass) > 0 else df_final
        
        # Exclusión dura: categorías N1/N2 que nunca son relevantes (no bypasseables)
        df_filtradas = self._aplicar_exclusion_dura(df_filtradas)

        # Intent gate global: descarta compras/mantenciones (invariante MP) y
        # etiqueta cada fila con Nivel Confianza (ALTA / REVISAR) según si matcheó
        # una palabra de servicio profesional (ingeniería, consultoría, diseño...).
        df_filtradas = self._aplicar_intencion(df_filtradas)

        # Scoring: contar cuántas keywords de exclusión matchean en cada fila
        # que PASÓ el filtro. Más matches → menos "limpia" la licitación.
        df_filtradas = self._contar_exclusiones_cercanas(df_filtradas)

        # Eliminar duplicados por código de adquisición
        col_codigo = encontrar_columna(df_filtradas, "Numero Adquisición")
        if col_codigo:
            df_filtradas = df_filtradas.drop_duplicates(subset=[col_codigo])

        # 'Motivo Exclusión' es solo informativo en df_excluidas; si se arrastra
        # vía bypass, lo eliminamos del set de filtradas para no confundir al usuario.
        if 'Motivo Exclusión' in df_filtradas.columns:
            df_filtradas = df_filtradas.drop(columns=['Motivo Exclusión'])

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
            palabras = self.profile.incluir.get(key, []) if self.profile else []
            if col not in df.columns or not palabras:
                continue
            # En campos de texto libre (descripción), solo usar frases multi-palabra
            if col in self._CAMPOS_SOLO_FRASES:
                palabras = [p for p in palabras if ' ' in p.strip()]
                if not palabras:
                    continue
            pattern = '|'.join(self._make_pattern(p) for p in palabras)
            mask |= df[col].str.contains(pattern, regex=True, na=False, case=False)

        df_incluidas = df[mask].copy()
        # Agregar trazabilidad: qué palabras clave activaron la inclusión de cada fila
        df_incluidas['Trazabilidad Filtro'] = df_incluidas.apply(
            lambda row: self._calcular_trazabilidad(row, campos_map), axis=1
        )
        # Conteo de matches para scoring: contar separadores '|' + 1
        if len(df_incluidas) > 0:
            traza = df_incluidas['Trazabilidad Filtro'].fillna('').astype(str)
            df_incluidas['_n_matches_inclusion'] = (
                traza.str.count(r'\|')
                .add(1)
                .where(traza != '', 0)
                .astype(int)
            )
        else:
            df_incluidas['_n_matches_inclusion'] = pd.Series(dtype=int)
        self.logger.info(f"🔍 Inclusión: {len(df_incluidas):,}/{len(df):,}")
        return df_incluidas

    def _make_pattern(self, keyword: str) -> str:
        """Construye el patrón regex para una keyword.
        Para keywords cortas (≤ _WORD_BOUNDARY_MAX_LEN chars) agrega \\b para evitar
        que 'BI' capture 'BIobío' o 'IA' capture 'dIÁlisis'."""
        escaped = re.escape(keyword)
        if len(keyword) <= self._WORD_BOUNDARY_MAX_LEN:
            return r'\b' + escaped + r'\b'
        return escaped

    def _calcular_trazabilidad(self, row: pd.Series, campos_map: list[tuple[str, str]]) -> str:
        """Devuelve las palabras clave que hicieron pasar esta fila por el filtro de inclusión."""
        encontradas = []
        for col, key in campos_map:
            palabras = self.profile.incluir.get(key, []) if self.profile else []
            if col not in row.index or not palabras:
                continue
            # Consistente con _aplicar_inclusion: descripción solo frases
            if col in self._CAMPOS_SOLO_FRASES:
                palabras = [p for p in palabras if ' ' in p.strip()]
                if not palabras:
                    continue
            texto = str(row.get(col, ''))
            for p in palabras:
                if re.search(self._make_pattern(p), texto, re.IGNORECASE):
                    entrada = f"{p} ({col.replace(' (norm)', '')})"
                    if entrada not in encontradas:
                        encontradas.append(entrada)
        return ' | '.join(encontradas) if encontradas else ''

    def _contar_exclusiones_cercanas(self, df: pd.DataFrame) -> pd.DataFrame:
        """Cuenta cuántas keywords de exclusión matchean en cada fila que PASÓ el filtro.

        El resultado se guarda en la columna auxiliar ``_n_exclusiones_cercanas``.
        Un valor alto indica que la licitación es "riesgosa" — pasó por
        bypass o por margen estrecho.
        """
        if len(df) == 0 or not self.profile:
            df['_n_exclusiones_cercanas'] = 0
            return df
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
        conteos = pd.Series(0, index=df.index)
        for col, key in campos_map:
            palabras = self.profile.excluir.get(key, [])
            if col not in df.columns or not palabras:
                continue
            col_str = df[col].fillna('').astype(str)
            for p in palabras:
                conteos += col_str.str.contains(
                    re.escape(p), regex=True, na=False, case=False,
                ).astype(int)
        df = df.copy()
        df['_n_exclusiones_cercanas'] = conteos.values
        return df
    
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
            palabras = self.profile.excluir.get(key, []) if self.profile else []
            if col not in df.columns or not palabras:
                continue
            pattern = '|'.join(re.escape(p) for p in palabras)
            mask |= df[col].str.contains(pattern, regex=True, na=False, case=False)

        df_excluidas = df[mask].copy()
        # Trazabilidad y top keywords agregado para auditoría
        if len(df_excluidas) > 0:
            df_excluidas['Motivo Exclusión'] = df_excluidas.apply(
                lambda row: self._calcular_motivo_exclusion(row, campos_map), axis=1
            )
            self._registrar_top_keywords(df_excluidas['Motivo Exclusión'], universo=len(df))
        self.logger.info(f"🚫 Exclusión: {len(df_excluidas):,}/{len(df):,}")
        return df_excluidas

    def _calcular_motivo_exclusion(self, row: pd.Series, campos_map: list[tuple[str, str]]) -> str:
        """Devuelve las palabras clave que causaron la exclusión de esta fila."""
        encontradas = []
        for col, key in campos_map:
            palabras = self.profile.excluir.get(key, []) if self.profile else []
            if col not in row.index or not palabras:
                continue
            texto = str(row.get(col, ''))
            for p in palabras:
                if re.search(re.escape(p), texto, re.IGNORECASE):
                    entrada = f"{p} ({col.replace(' (norm)', '')})"
                    if entrada not in encontradas:
                        encontradas.append(entrada)
        return ' | '.join(encontradas) if encontradas else ''

    def _registrar_top_keywords(self, serie_motivos: pd.Series, universo: int) -> None:
        """Agrega al stats las 10 keywords más frecuentes y detecta tóxicas.

        Una keyword es "tóxica" si por sí sola excluye más de
        `_UMBRAL_EXCLUSION_TOXICA_PCT`% del universo original — señal de
        que está demasiado genérica para el equipo (p. ej. 'ADQUISICION'
        matcheando todas las filas de 'Tipo Adquisición').
        """
        conteo: dict[str, int] = {}
        for motivo in serie_motivos:
            if not motivo:
                continue
            # Cada motivo es "kw1 (campo) | kw2 (campo)" → extraemos solo las kws
            for entrada in str(motivo).split('|'):
                kw = entrada.strip().split(' (', 1)[0].strip()
                if kw:
                    conteo[kw] = conteo.get(kw, 0) + 1
        top = sorted(conteo.items(), key=lambda x: x[1], reverse=True)[:10]
        self.stats['top_keywords_exclusion'] = top

        # Detectar exclusiones tóxicas (impacto desproporcionado sobre el universo)
        toxicas: list[tuple[str, int, float]] = []
        if universo > 0:
            limite_abs = (self._UMBRAL_EXCLUSION_TOXICA_PCT / 100.0) * universo
            for kw, n in conteo.items():
                if n >= limite_abs:
                    pct = (n / universo) * 100.0
                    toxicas.append((kw, n, round(pct, 2)))
        toxicas.sort(key=lambda x: x[1], reverse=True)
        self.stats['exclusiones_toxicas'] = toxicas

        for kw, n, pct in toxicas:
            self.logger.warning(
                f"[!] Keyword de exclusión '{kw}' excluye {n:,} licitaciones "
                f"({pct:.1f}% del subconjunto post-inclusión). Es demasiado genérica "
                f"para el equipo; considera quitarla del PIVOT o reemplazarla por una "
                f"frase más específica."
            )
    
    def _make_bypass_pattern(self, keyword: str) -> str:
        """Como _make_pattern pero con _BYPASS_WORD_BOUNDARY_MAX_LEN para keywords cortas
        (ej: 'WAN' no debe rescatar 'WANDERSLEBEN'; 'MPLS' no debe rescatar texto irrelevante)."""
        escaped = re.escape(keyword)
        if len(keyword) <= self._BYPASS_WORD_BOUNDARY_MAX_LEN:
            return r'\b' + escaped + r'\b'
        return escaped

    def _aplicar_bypass(self, df_excluidas: pd.DataFrame) -> pd.DataFrame:
        bypass = list(self.profile.bypass) if self.profile else []
        if not bypass or len(df_excluidas) == 0:
            return pd.DataFrame()

        pattern = '|'.join(self._make_bypass_pattern(p) for p in bypass)
        # Solo matchear en nombre y descripción — organismo/tipo/producto generan
        # falsos rescates (ej: "infraestructura TI" en una descripción de compras)
        cols = [
            "Nombre Adquisición (norm)",
            "Descripción (norm)",
        ]
        mask = pd.Series(False, index=df_excluidas.index)
        for col in cols:
            if col in df_excluidas.columns:
                mask |= df_excluidas[col].str.contains(pattern, regex=True, na=False, case=False)

        df_bypass = df_excluidas[mask]
        self.logger.info(f"🔄 Bypass: {len(df_bypass):,}")
        return df_bypass

    def _aplicar_exclusion_dura(self, df: pd.DataFrame) -> pd.DataFrame:
        """Post-filtro: elimina licitaciones con N1/N2 que nunca son relevantes,
        incluso si fueron rescatadas por bypass. Driven by PIVOT col 'exclusion_dura'."""
        categorias = list(self.profile.exclusion_dura) if self.profile else []
        if not categorias or len(df) == 0:
            return df
        pattern = '|'.join(re.escape(c) for c in categorias)
        mask = pd.Series(False, index=df.index)
        for col in ("Nivel 1 (norm)", "Nivel 2 (norm)"):
            if col in df.columns:
                mask |= df[col].str.contains(pattern, regex=True, na=False, case=False)

        n_removidas = int(mask.sum())
        if n_removidas > 0:
            self.logger.info(f"🛡️ Exclusión dura: {n_removidas} removidas (N1/N2 no-ingeniería)")
        self.stats['exclusion_dura'] = n_removidas
        return df[~mask]

    # Columnas evaluadas por el intent gate (texto libre).
    _CAMPOS_INTENCION = ("Nombre Adquisición (norm)", "Descripción (norm)")

    # Taxonomía UNSPSC que implica ALTA confianza por definición.
    # Si el propio Mercado Público clasifica la licitación como "Consultoría" o
    # "Servicios profesionales de ingeniería", eso es señal más fuerte que el texto.
    _TAXONOMIA_ALTA_N1 = ("consultoria",)
    _TAXONOMIA_ALTA_N2 = ("servicios profesionales de ingeniería",
                          "servicios de consultoría de ingeniería")

    def _build_intencion_pattern(self, palabras: list[str]) -> str:
        """Construye el regex combinado de una lista de palabras de intención.
        Frases multi-palabra → substring escapado. Palabras sueltas → word boundary."""
        partes: list[str] = []
        for p in palabras:
            esc = re.escape(p)
            if ' ' in p.strip():
                partes.append(esc)
            else:
                partes.append(r'\b' + esc + r'\b')
        return '|'.join(partes)

    def _aplicar_intencion(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aplica el intent gate global (invariante de negocio MP).

        - Si la fila matchea alguna palabra de `intencion_global.vetada` → DESCARTAR.
        - Si matchea alguna de `intencion_global.requerida` → `Nivel Confianza = ALTA`.
        - Si no matchea ninguna → `Nivel Confianza = REVISAR` (zona gris; se conserva).

        Si ambas listas están vacías (hoja no presente o sin contenido), añade
        `Nivel Confianza = N/A` y no descarta nada (comportamiento legacy).
        """
        if len(df) == 0:
            return df

        intent = self.profile.intencion_global if self.profile else None
        if intent is None or not intent.habilitado:
            df = df.copy()
            df['Nivel Confianza'] = 'N/A'
            return df

        # Texto combinado a evaluar (nombre + descripción)
        cols_presentes = [c for c in self._CAMPOS_INTENCION if c in df.columns]
        if not cols_presentes:
            df = df.copy()
            df['Nivel Confianza'] = 'N/A'
            return df

        # Concatenamos las columnas presentes (separadas por espacio) — una sola
        # serie facilita el matching y mantiene la trazabilidad simple.
        texto = df[cols_presentes[0]].fillna('').astype(str)
        for c in cols_presentes[1:]:
            texto = texto.str.cat(df[c].fillna('').astype(str), sep=' ')

        # Veto duro
        n_vetadas = 0
        if intent.vetada:
            pat_veto = self._build_intencion_pattern(intent.vetada)
            mask_veto = texto.str.contains(pat_veto, regex=True, na=False, case=False)
            n_vetadas = int(mask_veto.sum())
            df = df[~mask_veto].copy()
            texto = texto[~mask_veto]

        # Etiqueta de confianza
        if intent.requerida and len(df) > 0:
            pat_req = self._build_intencion_pattern(intent.requerida)
            mask_req = texto.str.contains(pat_req, regex=True, na=False, case=False)
            df['Nivel Confianza'] = mask_req.map({True: 'ALTA', False: 'REVISAR'})
        else:
            df['Nivel Confianza'] = 'REVISAR'

        # Boost por taxonomía UNSPSC: si Mercado Público clasifica la licitación
        # como Consultoría o Ing. Profesional, elevar REVISAR → ALTA.
        if len(df) > 0:
            n_boost = 0
            for col_norm, cats in [("Nivel 1 (norm)", self._TAXONOMIA_ALTA_N1),
                                   ("Nivel 2 (norm)", self._TAXONOMIA_ALTA_N2)]:
                if col_norm in df.columns:
                    for cat in cats:
                        mask_tax = (
                            (df['Nivel Confianza'] == 'REVISAR') &
                            df[col_norm].str.contains(re.escape(cat), regex=True, na=False, case=False)
                        )
                        n_match = int(mask_tax.sum())
                        if n_match > 0:
                            df.loc[mask_tax, 'Nivel Confianza'] = 'ALTA'
                            n_boost += n_match
            if n_boost > 0:
                self.logger.info(f"📊 Boost taxonomía UNSPSC: {n_boost} REVISAR → ALTA")

        self.stats['intencion_vetadas'] = n_vetadas
        self.stats['confianza_alta'] = int((df['Nivel Confianza'] == 'ALTA').sum())
        self.stats['confianza_revisar'] = int((df['Nivel Confianza'] == 'REVISAR').sum())

        if n_vetadas > 0:
            self.logger.info(f"🚷 Intent gate (veto): {n_vetadas} descartadas (compras/mantenciones)")
        self.logger.info(
            f"🎯 Intent gate (confianza): {self.stats['confianza_alta']} ALTA | "
            f"{self.stats['confianza_revisar']} REVISAR"
        )
        return df

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
    
    def _imprimir_resumen(self) -> None:
        s = self.stats
        pct = (s['final'] / s['original'] * 100) if s['original'] > 0 else 0

        top = s.get('top_keywords_exclusion') or []
        if top:
            top_txt = "\n".join(f"      {i+1:>2}. {kw:<25} {n:>4} exclusiones"
                                for i, (kw, n) in enumerate(top))
        else:
            top_txt = "      (sin datos)"

        toxicas = s.get('exclusiones_toxicas') or []
        if toxicas:
            tox_txt = "\n".join(
                f"      [!] '{kw}'  ->  {n:,} exclusiones ({pct:.1f}% del universo)"
                for kw, n, pct in toxicas
            )
            tox_block = (
                "\n[!] EXCLUSIONES TOXICAS detectadas (keywords demasiado genericas):\n"
                f"{tox_txt}\n"
                "    Recomendacion: edita tu hoja del PIVOT y reemplaza/elimina estas keywords.\n"
            )
        else:
            tox_block = ""

        self.logger.info(f"""
╔══════════════════════════════════════════════════════════════╗
║              ESTADÍSTICAS DE FILTRADO                        ║
╚══════════════════════════════════════════════════════════════╝

[#] Procesamiento:
   - Total original:        {s['original']:,}
   - Total incluidas:       {s['incluidas']:,}
   - Total excluidas:       {s['excluidas']:,}
   - Recuperadas (bypass):  {s['bypass']:,}
   - Bloqueadas (excl.dura): {s.get('exclusion_dura', 0):,}
   - Vetadas (intent gate): {s.get('intencion_vetadas', 0):,}
   - Total final:           {s['final']:,}

🎯 Confianza (intent gate global):
   - ALTA (servicio profesional):    {s.get('confianza_alta', 0):,}
   - REVISAR (intent no detectado):  {s.get('confianza_revisar', 0):,}

📈 Eficiencia:
   - % Retenido:            {pct:.1f}%
   - Reducción:             {s['original'] - s['final']:,} licitaciones

🔑 Top 10 keywords de exclusión (auditoría):
{top_txt}
{tox_block}
⏱️  Rendimiento:
   - Tiempo total:          {s.get('tiempo', 'N/A')}
""")


def main() -> int | None:
    from utils.config import Config
    from utils.logger import configurar_consola_utf8
    configurar_consola_utf8()
    try:
        context = PipelineContext(config=Config())
        context.flags['allow_fallback'] = True  # permite usar LICITACIONES_MP si no hay artefacto etapa0
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
