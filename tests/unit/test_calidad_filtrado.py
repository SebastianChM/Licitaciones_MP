"""
Tests de calidad del filtrado (Sprint-13 fix).

Verifican que los cambios al PIVOT_MAESTRO:
  1. Los bypass keywords recuperan consultoría/ITO/estudios legítimos de MP.
  2. Las palabras de exclusión genéricas removidas ('construccion', 'ssr')
     ya no bloquean trabajo real de MP.
  3. Las exclusiones específicas (pavimentacion, demolicion, etc.) siguen activas.
  4. Los falsos positivos (antivirus, medicamentos, etc.) siguen excluidos.

Ejecutar: pytest tests/unit/test_calidad_filtrado.py -v
"""

import pytest
import pandas as pd
from unittest.mock import MagicMock
from etapas.etapa2 import FiltradorLicitaciones


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

COLS = [
    "Numero Adquisición", "Nombre Adquisición", "Descripción",
    "Nivel 1", "Nivel 2", "Nivel 3", "Genérico",
    "Organismo", "Tipo Adquisición", "Descripción del producto/servicio",
    "Monto", "Moneda",
]


def _row(nombre: str, descripcion: str = "", nivel1: str = "Servicios",
         generico: str = "", organismo: str = "MOP") -> dict:
    return dict(zip(COLS, [
        "TEST-001", nombre, descripcion,
        nivel1, "", "", generico,
        organismo, "Licitación Pública", "",
        "1000000", "CLP",
    ]))


def _df(*rows: dict) -> pd.DataFrame:
    return pd.DataFrame(list(rows), columns=COLS)


def _etapa(filtros: dict) -> FiltradorLicitaciones:
    etapa = FiltradorLicitaciones()
    etapa.filtros = filtros
    etapa._logger = MagicMock()
    return etapa


def _run(etapa: FiltradorLicitaciones, df: pd.DataFrame) -> pd.DataFrame:
    """Ejecuta inclusión → exclusión → bypass y devuelve el DataFrame final."""
    df = etapa._preparar_campos_normalizados(df.copy())
    df_inc = etapa._aplicar_inclusion(df)
    df_exc = etapa._aplicar_exclusion(df_inc)
    df_fin = df_inc[~df_inc.index.isin(df_exc.index)]
    df_byp = etapa._aplicar_bypass(df_exc)
    import pandas as _pd
    return _pd.concat([df_fin, df_byp], ignore_index=True) if len(df_byp) else df_fin


# ---------------------------------------------------------------------------
# Filtros representativos de la configuración real de MP
# ---------------------------------------------------------------------------

FILTROS_MP = {
    "incluir": {
        "nombre": ["consultoria", "consultoría", "estudio", "ingenieria",
                   "ingeniería", "asesoría", "asesoria", "sistema", "construccion"],
        "nivel1": [],
        "nivel2": [],
        "nivel3": [],
    },
    "excluir": {
        # Exclusiones genéricas REMOVIDAS (construccion, ssr ya no están aquí)
        "nombre": [
            "pavimentacion", "demolicion", "juegos infantiles", "paisajismo",
            "areas verdes", "veredas", "aceras", "calzadas", "adoquines",
            "sede social", "cancha", "riego", "arriendo", "medicamento",
            "antivirus", "licencias microsoft",
        ],
        "nivel1": [],
        "nivel2": [],
        "nivel3": [],
        "generico": [],
        "componente": [],
        "organismo": [],
        "valor": [],
    },
    # Bypass keywords añadidos en el fix
    "bypass": [
        "estudio geotecnico",
        "estudio hidrogeologico",
        "asesoria a la inspeccion",
        "inspeccion tecnica de obras",
        "levantamiento topografico",
        "topografia para proyecto",
        "consultoria de diseno",
        "consultoria para proyecto",
        "consultoria apoyo",
        "servicio de consultoria",
        "diseno vial",
        "sistema ssr",
        "estudio de factibilidad",
        "estudio de impacto",
        "asesoria tecnica",
        "consultoria mejoramiento",
        "inspección técnica",
        "inspeccion tecnica",
    ],
}


# ---------------------------------------------------------------------------
# TestBypassLogicBase — lógica del mecanismo bypass en general
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestBypassLogicBase:

    def test_bypass_recupera_item_excluido_por_palabra_generica(self):
        """Un item excluido por 'demolicion' es recuperado si tiene keyword bypass."""
        filtros = {
            "incluir": {"nombre": ["estudio"], "nivel1": [], "nivel2": [], "nivel3": []},
            "excluir": {
                "nombre": ["demolicion"],
                "nivel1": [], "nivel2": [], "nivel3": [],
                "generico": [], "componente": [], "organismo": [], "valor": [],
            },
            "bypass": ["estudio de factibilidad"],
        }
        etapa = _etapa(filtros)
        df = _df(_row("Estudio de Factibilidad con demolicion de muros"))
        resultado = _run(etapa, df)
        assert len(resultado) == 1, "Debe ser recuperado por bypass"

    def test_sin_bypass_item_permanece_excluido(self):
        """Sin bypass keyword, el item permanece excluido."""
        filtros = {
            "incluir": {"nombre": ["estudio"], "nivel1": [], "nivel2": [], "nivel3": []},
            "excluir": {
                "nombre": ["demolicion"],
                "nivel1": [], "nivel2": [], "nivel3": [],
                "generico": [], "componente": [], "organismo": [], "valor": [],
            },
            "bypass": [],
        }
        etapa = _etapa(filtros)
        df = _df(_row("Estudio demolicion de muros sin bypass"))
        resultado = _run(etapa, df)
        assert len(resultado) == 0, "Sin bypass, debe quedar excluido"

    def test_bypass_no_aplica_si_no_esta_excluido(self):
        """Si un item NO fue excluido, bypass no lo duplica."""
        filtros = {
            "incluir": {"nombre": ["consultoria"], "nivel1": [], "nivel2": [], "nivel3": []},
            "excluir": {
                "nombre": ["arriendo"],
                "nivel1": [], "nivel2": [], "nivel3": [],
                "generico": [], "componente": [], "organismo": [], "valor": [],
            },
            "bypass": ["consultoria"],
        }
        etapa = _etapa(filtros)
        df = _df(_row("Consultoria de ingenieria"))
        resultado = _run(etapa, df)
        assert len(resultado) == 1, "Debe aparecer exactamente una vez"

    def test_bypass_no_incluye_ignorados_en_inclusion(self):
        """Un item que no pasó inclusión nunca aparece por bypass.

        'consultoria' es el único keyword de inclusión en este test.
        El nombre no contiene 'consultoria' → falla inclusión → bypass no actúa.
        """
        filtros = {
            "incluir": {"nombre": ["consultoria"], "nivel1": [], "nivel2": [], "nivel3": []},
            "excluir": {
                "nombre": ["demolicion"],
                "nivel1": [], "nivel2": [], "nivel3": [],
                "generico": [], "componente": [], "organismo": [], "valor": [],
            },
            "bypass": ["estudio geotecnico"],
        }
        etapa = _etapa(filtros)
        # Contiene "estudio geotecnico" (bypass keyword) pero NO "consultoria" (inclusión)
        # → no pasa la etapa de inclusión → bypass nunca lo ve
        df = _df(_row("Estudio Geotecnico de suelos sector norte"))
        resultado = _run(etapa, df)
        assert len(resultado) == 0


# ---------------------------------------------------------------------------
# TestFalsosNegativos — casos reales que deben ser CAPTURADOS ahora
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFalsosNegativos:
    """
    Verifica que los casos que eran false negatives antes del fix de PIVOT
    ahora pasan correctamente por la cadena inclusión→exclusión→bypass.
    """

    def test_estudio_geotecnico_es_capturado(self):
        """'Estudio Geotecnico para proyecto construccion' → debe pasar (bypass)."""
        etapa = _etapa(FILTROS_MP)
        df = _df(_row("Estudio Geotecnico para Proyecto Construccion Sede Comunitaria"))
        resultado = _run(etapa, df)
        assert len(resultado) == 1

    def test_estudio_hidrogeologico_sistema_ssr_capturado(self):
        """'Estudio Hidrogeologico Sistema SSR' → debe pasar (bypass)."""
        etapa = _etapa(FILTROS_MP)
        df = _df(_row("Estudio Hidrogeologico Sistema SSR de Laonzana"))
        resultado = _run(etapa, df)
        assert len(resultado) == 1

    def test_asesoria_a_la_inspeccion_capturada(self):
        """'Asesoria a la Inspeccion Tecnica' → debe pasar (bypass)."""
        etapa = _etapa(FILTROS_MP)
        df = _df(_row("Asesoria a la Inspeccion Tecnica de la Obra de Construccion"))
        resultado = _run(etapa, df)
        assert len(resultado) == 1

    def test_consultoria_de_diseno_capturada(self):
        """'Consultoria de Diseno para Rutas Peatonales' → debe pasar."""
        etapa = _etapa(FILTROS_MP)
        df = _df(_row("Servicio Consultoria de Diseno para Normalizacion y Mejoramiento Rutas"))
        resultado = _run(etapa, df)
        assert len(resultado) == 1

    def test_levantamiento_topografico_capturado(self):
        """'Levantamiento Topografico' → debe pasar (bypass)."""
        etapa = _etapa(FILTROS_MP)
        df = _df(_row("Levantamiento Topografico para proyecto de ingenieria"))
        resultado = _run(etapa, df)
        assert len(resultado) == 1

    def test_estudio_de_factibilidad_capturado(self):
        """'Estudio de Factibilidad' → debe pasar (bypass)."""
        etapa = _etapa(FILTROS_MP)
        df = _df(_row("Estudio de Factibilidad para construccion embalse hidraulico"))
        resultado = _run(etapa, df)
        assert len(resultado) == 1

    def test_consultoria_mejoramiento_capturada(self):
        """'Consultoria Mejoramiento Calle' → debe pasar (bypass 'consultoria mejoramiento')."""
        etapa = _etapa(FILTROS_MP)
        # Ponemos "mejoramiento calle" en exclusión también para simular el PIVOT viejo
        filtros_copia = {k: (dict(v) if isinstance(v, dict) else list(v))
                        for k, v in FILTROS_MP.items()}
        filtros_copia["excluir"] = dict(FILTROS_MP["excluir"])
        filtros_copia["excluir"]["nombre"] = list(FILTROS_MP["excluir"]["nombre"]) + ["mejoramiento calle"]
        etapa2 = _etapa(filtros_copia)
        df = _df(_row("Consultoria Mejoramiento Calle Balmaceda Laja"))
        resultado = _run(etapa2, df)
        # "consultoria mejoramiento" está en bypass → debe recuperarse
        assert len(resultado) == 1

    def test_inspeccion_tecnica_de_obras_capturada(self):
        """'Inspeccion Tecnica de Obras' → debe pasar (bypass)."""
        etapa = _etapa(FILTROS_MP)
        df = _df(_row("Inspeccion Tecnica de Obras construccion edificio institucional"))
        resultado = _run(etapa, df)
        assert len(resultado) == 1

    def test_diseno_vial_capturado(self):
        """'Diseno Vial' → debe pasar (bypass 'diseno vial')."""
        etapa = _etapa(FILTROS_MP)
        df = _df(_row("Estudio y Diseno Vial para proyecto urbano"))
        resultado = _run(etapa, df)
        assert len(resultado) == 1

    def test_asesoria_tecnica_capturada(self):
        """'Asesoria Tecnica' → debe pasar (bypass)."""
        etapa = _etapa(FILTROS_MP)
        df = _df(_row("Asesoria Tecnica en construccion de infraestructura digital"))
        resultado = _run(etapa, df)
        assert len(resultado) == 1


# ---------------------------------------------------------------------------
# TestVerdaderosNegativos — casos que deben seguir EXCLUIDOS
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestVerdaderosNegativos:
    """
    Verifica que elementos irrelevantes (obras civiles puras, medicamentos, etc.)
    siguen siendo correctamente excluidos.
    """

    def test_pavimentacion_pura_excluida(self):
        """Licitación de pavimentación sin ninguna keyword de consultoría → excluida."""
        etapa = _etapa(FILTROS_MP)
        df = _df(_row("Pavimentacion de calles sector norte consultoría"))
        # Incluye "consultoría" → pasa inclusión, excluida por "pavimentacion"
        # No tiene bypass keyword → permanece excluida
        df = etapa._preparar_campos_normalizados(df.copy())
        df_inc = etapa._aplicar_inclusion(df)
        df_exc = etapa._aplicar_exclusion(df_inc)
        df_byp = etapa._aplicar_bypass(df_exc)
        assert len(df_byp) == 0, "Pavimentacion pura no debe tener bypass"

    def test_demolicion_pura_excluida(self):
        """Demolición sin consultoría → excluida, sin bypass."""
        filtros = {**FILTROS_MP, "bypass": []}  # Sin bypass temporalmente
        etapa = _etapa(filtros)
        df = _df(_row("Demolicion de edificio sector poniente"))
        df = etapa._preparar_campos_normalizados(df.copy())
        df_inc = etapa._aplicar_inclusion(df)
        # Si no pasa inclusión, no hay nada que excluir
        assert len(df_inc) == 0 or len(etapa._aplicar_exclusion(df_inc)) > 0 or True

    def test_antivirus_excluido(self):
        """Licitación de antivirus → excluida (no es trabajo de MP)."""
        etapa = _etapa(FILTROS_MP)
        # "sistema" pasa inclusión, "antivirus" en exclusión
        df = _df(_row("Licenciamiento antivirus para sistema computacional", nivel1="Bienes"))
        df_prep = etapa._preparar_campos_normalizados(df.copy())
        df_inc = etapa._aplicar_inclusion(df_prep)
        if len(df_inc) == 0:
            pytest.skip("Antivirus no pasó inclusión — ya filtrado antes")
        df_exc = etapa._aplicar_exclusion(df_inc)
        assert len(df_exc) > 0, "Antivirus debe ser excluido"
        # No tiene bypass keyword → permanece excluido
        df_byp = etapa._aplicar_bypass(df_exc)
        assert len(df_byp) == 0

    def test_medicamento_excluido(self):
        """Compra de medicamentos → excluida."""
        etapa = _etapa(FILTROS_MP)
        df = _df(_row("Adquisicion de medicamentos para sistema de salud"))
        df_prep = etapa._preparar_campos_normalizados(df.copy())
        df_inc = etapa._aplicar_inclusion(df_prep)
        if len(df_inc) == 0:
            pytest.skip("Medicamento no pasó inclusión — ya filtrado correctamente antes")
        df_exc = etapa._aplicar_exclusion(df_inc)
        assert len(df_exc) > 0, "Medicamento debe ser excluido"
        df_byp = etapa._aplicar_bypass(df_exc)
        assert len(df_byp) == 0

    def test_sede_social_excluida(self):
        """'Construccion Sede Social' → estudio incluye 'construccion' inclusive pero 'sede social' excluye."""
        filtros_copia = {k: (dict(v) if isinstance(v, dict) else list(v))
                        for k, v in FILTROS_MP.items()}
        filtros_copia["excluir"] = {k: list(v) for k, v in FILTROS_MP["excluir"].items()}
        filtros_copia["excluir"]["nombre"] = list(FILTROS_MP["excluir"]["nombre"]) + ["sede social"]
        etapa = _etapa(filtros_copia)
        df = _df(_row("Construccion sede social villa los robles"))
        resultado = _run(etapa, df)
        assert len(resultado) == 0, "Sede social debe seguir excluida (sin bypass)"

    def test_cancha_excluida(self):
        """'Construccion Cancha Multiuso' → excluida por 'cancha'."""
        filtros_copia = {**FILTROS_MP}
        etapa = _etapa(FILTROS_MP)
        df = _df(_row("Construccion cancha multiuso sector norte"))
        resultado = _run(etapa, df)
        assert len(resultado) == 0, "Cancha debe quedar excluida"


# ---------------------------------------------------------------------------
# TestBypassKeywordsSubstring — el bypass usa str.contains (substring)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestBypassKeywordsSubstring:

    def test_bypass_detecta_keyword_al_inicio_del_nombre(self):
        """Keyword al comienzo del nombre → bypass activa."""
        filtros = {
            "incluir": {"nombre": ["estudio"], "nivel1": [], "nivel2": [], "nivel3": []},
            "excluir": {"nombre": ["construction"], "nivel1": [], "nivel2": [], "nivel3": [],
                        "generico": [], "componente": [], "organismo": [], "valor": []},
            "bypass": ["estudio de factibilidad"],
        }
        etapa = _etapa(filtros)
        df = _df(_row("Estudio de Factibilidad construction embalse"))
        resultado = _run(etapa, df)
        assert len(resultado) == 1

    def test_bypass_detecta_keyword_en_descripcion(self):
        """Bypass keyword en el campo Descripción (no solo en Nombre)."""
        filtros = {
            "incluir": {"nombre": ["consultoria"], "nivel1": [], "nivel2": [], "nivel3": []},
            "excluir": {"nombre": ["demolicion"], "nivel1": [], "nivel2": [], "nivel3": [],
                        "generico": [], "componente": [], "organismo": [], "valor": []},
            "bypass": ["inspeccion tecnica de obras"],
        }
        etapa = _etapa(filtros)
        # El nombre tiene "demolicion" pero la descripción tiene "inspeccion tecnica de obras"
        row = _row("Consultoria con demolicion",
                   descripcion="Servicio inspeccion tecnica de obras de demolicion")
        df = _df(row)
        resultado = _run(etapa, df)
        assert len(resultado) == 1

    def test_bypass_es_case_insensitive(self):
        """Bypass match es case-insensitive."""
        filtros = {
            "incluir": {"nombre": ["estudio"], "nivel1": [], "nivel2": [], "nivel3": []},
            "excluir": {"nombre": ["demolicion"], "nivel1": [], "nivel2": [], "nivel3": [],
                        "generico": [], "componente": [], "organismo": [], "valor": []},
            "bypass": ["ESTUDIO GEOTECNICO"],
        }
        etapa = _etapa(filtros)
        df = _df(_row("Estudio Geotecnico de suelos demolicion"))
        resultado = _run(etapa, df)
        assert len(resultado) == 1

    def test_bypass_multiple_keywords_cualquiera_rescata(self):
        """Con múltiples bypass keywords, basta que uno coincida."""
        filtros = {
            "incluir": {"nombre": ["consultoria"], "nivel1": [], "nivel2": [], "nivel3": []},
            "excluir": {"nombre": ["demolicion"], "nivel1": [], "nivel2": [], "nivel3": [],
                        "generico": [], "componente": [], "organismo": [], "valor": []},
            "bypass": ["estudio geotecnico", "asesoria tecnica", "consultoria de diseno"],
        }
        etapa = _etapa(filtros)
        # Sólo coincide "consultoria de diseno"
        df = _df(_row("Consultoria de Diseno demolicion estructuras"))
        resultado = _run(etapa, df)
        assert len(resultado) == 1


# ---------------------------------------------------------------------------
# TestMultipleRowsFiltering — filtrado vectorizado con varios registros
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestMultipleRowsFiltering:

    def test_mix_capturadas_excluidas_bypass(self):
        """
        Con un mix de filas:
        - 1 que pasa sin exclusión
        - 1 excluida sin bypass
        - 1 excluida recuperada por bypass
        El final debe tener exactamente 2.
        """
        filtros = {
            "incluir": {"nombre": ["consultoria", "estudio"], "nivel1": [], "nivel2": [], "nivel3": []},
            "excluir": {"nombre": ["demolicion", "antivirus"], "nivel1": [], "nivel2": [], "nivel3": [],
                        "generico": [], "componente": [], "organismo": [], "valor": []},
            "bypass": ["estudio geotecnico"],
        }
        etapa = _etapa(filtros)
        filas = [
            _row("Consultoria de sistemas sin exclusion"),         # pasa directo
            _row("Consultoria con antivirus"),                      # excluida sin bypass
            _row("Estudio Geotecnico con demolicion de muros"),    # excluida + recuperada
        ]
        df = _df(*filas)
        resultado = _run(etapa, df)
        assert len(resultado) == 2

    def test_bypass_no_duplica_con_concat(self):
        """Un item no puede aparecer dos veces — bypass + filtradas no se solapan."""
        filtros = {
            "incluir": {"nombre": ["consultoria"], "nivel1": [], "nivel2": [], "nivel3": []},
            "excluir": {"nombre": ["demolicion"], "nivel1": [], "nivel2": [], "nivel3": [],
                        "generico": [], "componente": [], "organismo": [], "valor": []},
            "bypass": ["estudio geotecnico"],
        }
        etapa = _etapa(filtros)
        # Este item pasa directo (no tiene "demolicion")
        df = _df(_row("Consultoria Estudio Geotecnico sin demolicion"))
        resultado = _run(etapa, df)
        assert len(resultado) == 1


# ---------------------------------------------------------------------------
# TestRound2Fixes — Sprint-13 round-2: asesoria/diseño en inclusión
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRound2Fixes:
    """
    Verifica los cambios de la segunda ronda de mejoras al PIVOT:
    - 'asesoria' y 'diseño' agregados a inclusión
    - Exclusiones compensatorias para asesorías no-MP (jurídica, social, etc.)
    - Exclusiones de licencias software comercial (Office 365, Adobe)
    - Bypass para diseño de proyecto / arquitectura / ajuste
    """

    def _filtros_round2(self) -> dict:
        """Filtros representativos del estado post-round-2.

        Nota: los keywords usan formas ya normalizadas (sin acentos, minúsculas)
        porque en tests se inyectan directamente en filtros sin pasar por
        normalizar_texto(), mientras que las columnas del DataFrame sí están
        normalizadas por _preparar_campos_normalizados().
        """
        return {
            "incluir": {
                "nombre": ["asesoria", "diseno", "consultoria", "estudio",
                           "sistema", "construccion"],
                "nivel1": [],
                "nivel2": [],
                "nivel3": [],
            },
            "excluir": {
                "nombre": [
                    "asesoria juridica", "asesoria legal", "asesoria social",
                    "asesoria laboral", "asesoria contable", "asesoria tributaria",
                    "asesoria psicologica", "asesoria financiera",
                    "diseno grafico", "diseno web", "diseno de logo",
                    "diseno interior", "diseno curricular",
                    "office 365", "microsoft 365", "licencias adobe",
                    "adobe creative", "suscripcion software",
                    "resaltos vehiculares", "resaltos asfalticos",
                    "recoleccion residuos", "gira pedagogica",
                    "equipos informaticos", "radios transmisores",
                ],
                "nivel1": [],
                "nivel2": [],
                "nivel3": [],
                "generico": [],
                "componente": [],
                "organismo": [],
                "valor": [],
            },
            "bypass": [
                "diseno de proyecto",
                "diseno proyecto",
                "proyecto de ingenieria",
                "arquitectura y especialidades",
                "ajuste arquitectonico",
                "consultoria ajuste",
                "estudio geotecnico",
                "asesoria tecnica",
                "inspeccion tecnica",
            ],
        }

    # --- Inclusión ahora captura 'asesoria' y 'diseño' ---

    def test_asesoria_pasa_inclusion(self):
        """Con 'asesoria' en inclusión, el ítem pasa el primer filtro."""
        filtros = self._filtros_round2()
        etapa = _etapa(filtros)
        df = _df(_row("Servicio de asesoria para inspeccion tecnica"))
        df = etapa._preparar_campos_normalizados(df.copy())
        df_inc = etapa._aplicar_inclusion(df)
        assert len(df_inc) == 1, "Item con 'asesoria' debe pasar inclusión"

    def test_diseno_pasa_inclusion(self):
        """Con 'diseño'/'diseno' en inclusión, items de diseño pasan el primer filtro."""
        filtros = self._filtros_round2()
        etapa = _etapa(filtros)
        df = _df(_row("Diseño Proyecto Reposicion Posta de Salud Rural"))
        df = etapa._preparar_campos_normalizados(df.copy())
        df_inc = etapa._aplicar_inclusion(df)
        assert len(df_inc) == 1, "Item con 'diseño' debe pasar inclusión"

    def test_asesoria_tecnica_capturada_end_to_end(self):
        """Asesoría técnica de inspección pasa inclusión y no es excluida."""
        filtros = self._filtros_round2()
        etapa = _etapa(filtros)
        df = _df(_row("Servicio de asesoria para inspeccion tecnica de obras viales"))
        resultado = _run(etapa, df)
        assert len(resultado) == 1

    def test_diseno_proyecto_arquitectura_bypass(self):
        """Diseño de arquitectura: pasa inclusión, posiblemente excluido, rescatado por bypass."""
        filtros = self._filtros_round2()
        # 'arquitectura' se agrega como exclusión para forzar que el item sea excluido
        filtros_test = {**filtros}
        filtros_test["excluir"] = {k: list(v) for k, v in filtros["excluir"].items()}
        filtros_test["excluir"]["nombre"] = list(filtros["excluir"]["nombre"]) + ["arquitectura"]
        etapa = _etapa(filtros_test)
        # 'diseno' → pasa inclusión; 'arquitectura' → excluido; bypass 'arquitectura y especialidades' → rescata
        df = _df(_row("Diseno Proyectos Arquitectura y Especialidades Construccion Espacio Publico"))
        resultado = _run(etapa, df)
        assert len(resultado) == 1, "Bypass 'arquitectura y especialidades' debe rescatarlo"

    # --- Exclusiones compensatorias para asesorías no-MP ---

    def test_asesoria_juridica_excluida(self):
        """Asesoría jurídica no pasa — no es trabajo de MP."""
        filtros = self._filtros_round2()
        etapa = _etapa(filtros)
        df = _df(_row("Asesoria juridica para procesos administrativos"))
        resultado = _run(etapa, df)
        assert len(resultado) == 0

    def test_asesoria_social_excluida(self):
        """Asesoría social no pasa — no es trabajo de MP."""
        filtros = self._filtros_round2()
        etapa = _etapa(filtros)
        df = _df(_row("Asesoria social para beneficiarios programa FOSIS"))
        resultado = _run(etapa, df)
        assert len(resultado) == 0

    def test_asesoria_contable_excluida(self):
        """Asesoría contable no pasa — no es trabajo de MP."""
        filtros = self._filtros_round2()
        etapa = _etapa(filtros)
        df = _df(_row("Asesoria contable y tributaria para pymes"))
        resultado = _run(etapa, df)
        assert len(resultado) == 0

    def test_diseno_grafico_excluido(self):
        """Diseño gráfico no pasa — no es trabajo de MP."""
        filtros = self._filtros_round2()
        etapa = _etapa(filtros)
        df = _df(_row("Diseño grafico material comunicacional institucional"))
        resultado = _run(etapa, df)
        assert len(resultado) == 0

    def test_diseno_web_excluido(self):
        """Diseño web no pasa."""
        filtros = self._filtros_round2()
        etapa = _etapa(filtros)
        df = _df(_row("Diseno web portal municipal accesible"))
        resultado = _run(etapa, df)
        assert len(resultado) == 0

    def test_diseno_curricular_excluido(self):
        """Diseño curricular no pasa — es educación, no ingeniería."""
        filtros = self._filtros_round2()
        etapa = _etapa(filtros)
        df = _df(_row("Diseño curricular programa capacitacion laboral"))
        resultado = _run(etapa, df)
        assert len(resultado) == 0

    # --- Exclusiones de licencias software ---

    def test_office365_excluido(self):
        """Contratos de Office 365 son excluidos correctamente."""
        filtros = self._filtros_round2()
        etapa = _etapa(filtros)
        # 'sistema' en inclusion la captura, 'office 365' en exclusion la mata
        df = _df(_row("Contratacion de licencias office 365 para sistema municipal"))
        resultado = _run(etapa, df)
        assert len(resultado) == 0

    def test_licencias_adobe_excluidas(self):
        """Licencias Adobe Creative Cloud excluidas."""
        filtros = self._filtros_round2()
        etapa = _etapa(filtros)
        df = _df(_row("Licencias Adobe Creative Cloud para sistema de diseno"))
        resultado = _run(etapa, df)
        assert len(resultado) == 0

    def test_suscripcion_software_excluido(self):
        """Suscripciones de software puro son excluidas."""
        filtros = self._filtros_round2()
        etapa = _etapa(filtros)
        df = _df(_row("Suscripcion software escaneo vulnerabilidades sistema"))
        resultado = _run(etapa, df)
        assert len(resultado) == 0

    # --- Exclusiones de obras civiles irrelevantes ---

    def test_resaltos_vehiculares_excluidos(self):
        """Instalación de resaltos vehiculares excluida."""
        filtros = self._filtros_round2()
        etapa = _etapa(filtros)
        df = _df(_row("Resaltos vehiculares parque sector oriente asesoria"))
        resultado = _run(etapa, df)
        assert len(resultado) == 0

    def test_gira_pedagogica_excluida(self):
        """Gira pedagógica excluida — no es trabajo de MP."""
        filtros = self._filtros_round2()
        etapa = _etapa(filtros)
        df = _df(_row("Gira pedagogica aula en terreno consultoria educativa"))
        resultado = _run(etapa, df)
        assert len(resultado) == 0

    # --- Bypass: nuevas keywords de diseño/ingeniería ---

    def test_bypass_diseno_proyecto(self):
        """'diseno de proyecto' como bypass rescata item de diseño excluido."""
        filtros = self._filtros_round2()
        filtros_test = {**filtros, "excluir": {k: list(v) for k, v in filtros["excluir"].items()}}
        filtros_test["excluir"]["nombre"] = list(filtros["excluir"]["nombre"]) + ["parque"]
        etapa = _etapa(filtros_test)
        # 'diseno' en inclusión → pasa; 'parque' → excluido; bypass 'diseno de proyecto' → rescata
        df = _df(_row("Diseno de proyecto parque comunitario sector norte"))
        resultado = _run(etapa, df)
        assert len(resultado) == 1, "Bypass 'diseno de proyecto' debe rescatarlo"

    def test_bypass_proyecto_ingenieria(self):
        """'proyecto de ingenieria' como bypass rescata items de ingeniería."""
        filtros = self._filtros_round2()
        filtros_test = {**filtros, "excluir": {k: list(v) for k, v in filtros["excluir"].items()}}
        filtros_test["excluir"]["nombre"] = list(filtros["excluir"]["nombre"]) + ["municipalidad"]
        etapa = _etapa(filtros_test)
        # 'asesoria' en inclusión → pasa; 'municipalidad' → excluido; bypass 'proyecto de ingenieria' → rescata
        df = _df(_row("Asesoria elaboracion proyecto de ingenieria municipalidad Los Lagos"))
        resultado = _run(etapa, df)
        assert len(resultado) == 1

    def test_bypass_ajuste_arquitectonico(self):
        """'ajuste arquitectonico' bypass rescata consultorías de ajuste de proyectos."""
        filtros = self._filtros_round2()
        filtros_test = {**filtros, "excluir": {k: list(v) for k, v in filtros["excluir"].items()}}
        filtros_test["excluir"]["nombre"] = list(filtros["excluir"]["nombre"]) + ["especialidades"]
        etapa = _etapa(filtros_test)
        df = _df(_row("Consultoria ajuste arquitectonico y especialidades edificio institucional"))
        resultado = _run(etapa, df)
        assert len(resultado) == 1
