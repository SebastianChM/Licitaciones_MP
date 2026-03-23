# Plan de Arquitectura Multi-Área — MP Licitaciones

**Estado:** En diseño / pendiente de aprobación  
**Branch:** `feature/multi-area`  
**Fecha:** 23 de marzo de 2026  
**Autor:** Sebastian Chirino + GitHub Copilot

---

## Índice

1. [Estado actual del sistema](#1-estado-actual-del-sistema)
2. [Problema que resuelve este plan](#2-problema-que-resuelve-este-plan)
3. [Decisiones de arquitectura y por qué](#3-decisiones-de-arquitectura-y-por-qué)
4. [Nueva estructura del PIVOT_MAESTRO.xlsx](#4-nueva-estructura-del-pivot_maestroxlsx)
5. [Nueva estructura del código](#5-nueva-estructura-del-código)
6. [Nueva interfaz gráfica](#6-nueva-interfaz-gráfica)
7. [Flujo completo de ejecución](#7-flujo-completo-de-ejecución)
8. [Flujo para agregar un área nueva](#8-flujo-para-agregar-un-área-nueva)
9. [Archivos de salida](#9-archivos-de-salida)
10. [Plan de implementación paso a paso](#10-plan-de-implementación-paso-a-paso)
11. [Tests que se escribirán](#11-tests-que-se-escribirán)
12. [Lo que NO cambia](#12-lo-que-no-cambia)
13. [Riesgos y preguntas abiertas](#13-riesgos-y-preguntas-abiertas)

---

## 1. Estado actual del sistema

### 1.1 Qué tenemos hoy (Sprint-13, commit `7d21cbe`)

El sistema es una aplicación Python que descarga licitaciones de Mercado Público (Chile) y aplica un pipeline de 6 etapas para filtrar y enriquecer solo las oportunidades relevantes para MP.

#### Pipeline de etapas

| Etapa | Archivo | Función |
|-------|---------|---------|
| 0 | `etapa0.py` | Descarga el Excel de licitaciones publicadas desde Mercado Público |
| 1 | `etapa1.py` | Auditoría de taxonomía — detecta valores nuevos no contemplados en el PIVOT |
| 2 | `etapa2.py` | **Filtrado inteligente** — reduce ~12.000 licitaciones a ~300 relevantes |
| 3 | `etapa3.py` | Enriquece los datos consultando la API de Mercado Público |
| 4 | `etapa4.py` | Genera el reporte Excel final formateado |
| 5 | `etapa5.py` | Análisis incremental — detecta licitaciones nuevas respecto al histórico |

#### Archivos principales

```
C:\Licitaciones_MP\
│
├── lanzador_licitaciones.py     ← GUI Tkinter (ventana de Windows)
├── run_pipeline.py              ← Orquestador del pipeline
├── requirements.txt             ← Dependencias Python
│
├── config_pivot/
│   └── PIVOT_MAESTRO.xlsx       ← EL archivo de configuración central
│
├── src/
│   ├── etapas/
│   │   ├── etapa0.py  etapa1.py  etapa2.py  etapa3.py  etapa4.py  etapa5.py
│   │   └── __init__.py
│   └── utils/
│       ├── config.py            ← Configuración centralizada (Pydantic)
│       ├── analizador_incremental.py
│       ├── file_ops.py
│       ├── logger.py
│       ├── text_processing.py
│       ├── verificador_entorno.py
│       └── __init__.py
│
├── data/
│   ├── 1. INPUT/                ← Licitacion_Publicada.xlsx entra aquí
│   └── 2. OUTPUT/
│       ├── 1. LOGS/             ← Auditorías y logs de cada ejecución
│       ├── 2. HALLAZGOS/        ← Taxonomía detectada nueva
│       ├── 2. HISTORICO/        ← Histórico de lo filtrado anteriormente
│       ├── 3. FILTRADO/         ← Resultado de etapa2 (filtradas + excluidas)
│       ├── 4. ENRIQUECIDO/      ← Resultado de etapa3 (con datos de API)
│       └── 5. PRESENTACION/     ← Reporte final para usuarios
│           ├── ORIGINALES/
│           └── INCREMENTALES/
│
└── tests/                       ← 545 tests, todos en verde
    ├── unit/   (31 archivos)
    └── integration/
```

#### Estructura actual del PIVOT_MAESTRO.xlsx

El PIVOT tiene varias hojas, la más importante para el filtrado:

| Hoja | Función |
|------|---------|
| `02-CONFIG` | Parámetros del sistema (API key, umbrales) |
| `04-BASE` | Taxonomía de referencia (Nivel 1, 2, 3) |
| `06-FILTROS` | **Keywords de filtrado** — la hoja principal de la etapa 2 |

La hoja `06-FILTROS` tiene esta estructura (header en fila 5, datos desde fila 6):

| Col | Índice | Contenido |
|-----|--------|-----------|
| A | 0 | **Inclusión — NOMBRE** (174 keywords) |
| B | 1 | Inclusión — NIVEL1 |
| C | 2 | Inclusión — NIVEL2 |
| D | 3 | Inclusión — NIVEL3 |
| E | 4 | **Exclusión — NOMBRE** (433 keywords) |
| F | 5 | Exclusión — NIVEL1 |
| G | 6 | Exclusión — NIVEL2 |
| H | 7 | Exclusión — NIVEL3 |
| I | 8 | Exclusión — GENÉRICO |
| J | 9 | Exclusión — COMPONENTE |
| K | 10 | Exclusión — ORGANISMO |
| L | 11 | Exclusión — VALOR |
| M | 12 | **BYPASS** (58 keywords — recupera los que la exclusión bloqueó pero son válidos) |

#### Cómo funciona el filtrado hoy (3 fases en etapa2.py)

```
12.000 licitaciones
       │
       ▼ FASE 1 — INCLUSIÓN
       │  ¿El nombre/nivel contiene alguna keyword de inclusión?
       │  Solo pasan las que SÍ coinciden
       │
       ▼ ~600 licitaciones
       │
       ▼ FASE 2 — EXCLUSIÓN
       │  ¿El nombre/nivel/organismo contiene alguna keyword de exclusión?
       │  Se elimina las que SÍ coinciden
       │
       ▼ ~200 excluidas recuperables → BYPASS
       │  ¿Algún campo contiene keyword de bypass (ej: "MP", "ITO")?
       │  Si sí → se recupera aunque la exclusión la hubiera bloqueado
       │
       ▼ ~301 licitaciones filtradas (92 vía bypass)
```

#### Resultados actuales — área TI/Telecomunicaciones

- **Total input:** ~12.000 licitaciones publicadas
- **Total filtradas:** ~301 (2.5% del total)
- **Recuperadas vía bypass:** 92
- **Precisión estimada:** ~95% (5% de falsos positivos)
- **Tests pasando:** 545 de 545

#### GUI actual

Ventana de 600×540px con:
- Botón "EJECUTAR PIPELINE COMPLETO"
- Botón "SOLO ANÁLISIS INCREMENTAL"
- Botón "Abrir carpeta de resultados"
- Panel de estado del entorno (verifica .venv, PIVOT, .env)
- Log de ejecución en vivo
- Barra de progreso

#### Estado del código en `config.py` (branch `feature/multi-area`)

Ya se hizo una modificación parcial al inicio de esta rama: se añadió `_CATALOGO_AREAS` (un mapa hardcoded de área → archivo .xlsx) y `PIVOTS_AREAS` (propiedad). **Esta modificación se va a descartar** porque la arquitectura definitiva acordada es diferente (ver sección 3): las áreas no serán archivos separados sino hojas dentro del mismo PIVOT_MAESTRO.xlsx.

---

## 2. Problema que resuelve este plan

### 2.1 El problema de negocio

El sistema actual sirve exclusivamente al **área TI/Telecomunicaciones** de MP. Para que otra área (por ejemplo, Hidráulica) quiera usar el sistema, necesitaría:

1. Crear un archivo Excel nuevo con el formato exacto del PIVOT
2. Saber qué 433 keywords de exclusión poner
3. Modificar el código Python para que lo lea
4. Modificar la GUI para que aparezca la opción

Esto requiere un programador cada vez. No es escalable.

### 2.2 El problema del usuario

Los usuarios finales (coordinadores de área) no saben Python ni Excel avanzado. Necesitan:
- Una interfaz visual para elegir qué áreas filtrar
- Un proceso simple para agregar su área sin tocar código
- No tener que repetir 433 keywords de exclusión que ya existen

### 2.3 Lo que queremos lograr

> Cualquier área de MP puede incorporarse al sistema en menos de 30 minutos, sin tocar una sola línea de código, solo editando el Excel. La app detecta automáticamente las áreas disponibles y las muestra como opciones.

---

## 3. Decisiones de arquitectura y por qué

### 3.1 Opción descartada: un archivo PIVOT por área

```
config_pivot/
  PIVOT_MAESTRO.xlsx      ← TI
  PIVOT_HIDRAULICA.xlsx   ← Hidráulica  ← DESCARTADO
  PIVOT_VIALIDAD.xlsx     ← Vialidad    ← DESCARTADO
```

**Por qué se descartó:**
- Las 433 exclusiones genéricas habría que copiarlas en cada archivo
- Si se mejora una exclusión global, hay que actualizar 5 archivos
- El coordinador de área no sabe qué formato usar ni qué columnas van dónde
- No hay un lugar único de verdad

### 3.2 Opción elegida: hojas por área dentro del mismo PIVOT

```
PIVOT_MAESTRO.xlsx
  ├── 06-EXCL-GLOBALES       ← Exclusiones compartidas por TODAS las áreas
  ├── 06-FILTROS-TI          ← Inclusión + exclusiones específicas TI
  ├── 06-FILTROS-HIDRAULICA  ← Inclusión + exclusiones específicas Hidráulica
  ├── 06-FILTROS-VIALIDAD    ← (futuro)
  └── 06-FILTROS-TEMPLATE    ← Plantilla vacía para copiar
```

**Por qué esta opción:**
- Un solo archivo para versionar y distribuir
- Las exclusiones globales se mantienen en un solo lugar
- Cada área solo rellena sus keywords de inclusión (20-50 términos)
- El script detecta las áreas automáticamente leyendo los nombres de las hojas
- Agregar un área nueva = copiar una hoja plantilla + escribir keywords

### 3.3 Cómo el script detecta las áreas disponibles (zero código nuevo)

```python
import openpyxl
wb = openpyxl.load_workbook("PIVOT_MAESTRO.xlsx", read_only=True)
areas = [
    hoja.replace("06-FILTROS-", "")
    for hoja in wb.sheetnames
    if hoja.startswith("06-FILTROS-") and hoja != "06-FILTROS-TEMPLATE"
]
# → ["TI", "HIDRAULICA", "VIALIDAD"]
```

Si mañana alguien copia la plantilla y la llama `06-FILTROS-AMBIENTAL`, la próxima vez que se abra la app, "Ambiental" aparece automáticamente como opción. **Zero cambios de código.**

### 3.4 Por qué no usar macros VBA en Excel para el botón "crear área"

Los botones con macros VBA en Excel son bloqueados por defecto en organizaciones (política de seguridad de Windows/Office). El usuario vería:

```
⚠️ Las macros han sido deshabilitadas por razones de seguridad
```

La solución es mover ese botón a la app de Windows (GUI Python), que ya tenemos y controlamos completamente.

### 3.5 Output: un solo Excel con pestañas por área

```
Licitaciones_Filtradas_20260323_143022.xlsx
  ├── RESUMEN      ← Todas las áreas, columna "ÁREA" visible
  ├── TI           ← Solo TI (301 licitaciones)
  └── HIDRAULICA   ← Solo Hidráulica
```

**Por qué esta estructura:**
- Un solo archivo para enviar por correo o compartir en red
- Cada área va a su pestaña sin ver las de los demás
- Gerencia puede usar la hoja RESUMEN para visión global
- Si en el futuro se necesita archivo separado, el cambio es mínimo

---

## 4. Nueva estructura del PIVOT_MAESTRO.xlsx

### 4.1 Hojas que tendrá el nuevo PIVOT

| Hoja | Estado | Descripción |
|------|--------|-------------|
| `01-PORTADA` | Existente | Información del archivo |
| `02-CONFIG` | Existente | Parámetros del sistema |
| `03-TAXONOMIA` | Existente | Jerarquía Mercado Público |
| `04-BASE` | Existente | Taxonomía de referencia |
| `05-HISTORICO` | Existente | Histórico |
| `06-EXCL-GLOBALES` | **NUEVA** | Exclusiones compartidas por todas las áreas |
| `06-FILTROS-TI` | **MIGRADA** (era `06-FILTROS`) | Inclusión + bypass + excl. propias de TI |
| `06-FILTROS-TEMPLATE` | **NUEVA** | Plantilla vacía protegida |
| `07-AREAS` | **NUEVA** | Registro de áreas: nombre display, descripción |

### 4.2 Estructura de `06-EXCL-GLOBALES`

Misma estructura de columnas que `06-FILTROS`. Solo se rellenan las columnas de exclusión (columnas E a L). Las columnas de inclusión (A-D) y bypass (M) van vacías.

Aquí van las **433 keywords actuales** de exclusión — que aplican a todas las áreas por igual (pavimentación, demolición, medicamentos, etc.).

### 4.3 Estructura de `06-FILTROS-TI` (migrada del actual `06-FILTROS`)

**Igual que hoy**, pero renombrada. Las columnas E-L contendrán solo las exclusiones **específicas de TI** (no las genéricas, que van a `06-EXCL-GLOBALES`).

Hay que hacer una separación: de las 433 exclusiones actuales, ¿cuáles son genéricas universales y cuáles son específicas de TI? Esta es la única tarea manual de la migración.

```
EXCLUSIONES GLOBALES (van a 06-EXCL-GLOBALES):
  - pavimentacion, demolicion, juegos infantiles, medicamentos,
    vestuario, calzado, semillas, fertilizantes, ...
    (todo lo que NINGUNA área de MP querría nunca)

EXCLUSIONES ESPECÍFICAS TI (quedan en 06-FILTROS-TI):
  - clausula social, jornada laboral, convenio colectivo, ...
    (conceptos que podrían ser válidos para Hidráulica/Vialidad
     pero no para TI)
```

### 4.4 Estructura de `06-FILTROS-TEMPLATE`

Hoja protegida (solo lectura en Excel) que sirve de plantilla. Tiene:
- Las mismas 14 columnas con encabezados formateados
- Instrucciones en las primeras 4 filas (en gris, texto de ayuda)
- 20 filas vacías para empezar a rellenar
- Un comentario en cada columna explicando qué poner

```
Fila 1: [TÍTULO] "Plantilla para nueva área - No modificar encabezados"
Fila 2: [INSTRUCCIÓN] "Col A: keywords de inclusión en nombre de licitación"
Fila 3: [INSTRUCCIÓN] "Col M: bypass (recupera excluidas si contienen esta palabra)"
Fila 4: [INSTRUCCIÓN] "No rellenes columnas de exclusión global, solo las específicas de tu área"
Fila 5: [HEADER]  nombre | nivel1 | nivel2 | nivel3 | nombre_exc | ... | bypass
Fila 6+: (vacío)
```

### 4.5 Estructura de `07-AREAS`

Registro simple de áreas para mostrar nombres bonitos en la GUI:

| ID_AREA | NOMBRE_DISPLAY | DESCRIPCION | ACTIVA |
|---------|---------------|-------------|--------|
| TI | TI / Tecnología | Sistemas, software, telecomunicaciones | S |
| HIDRAULICA | Hidráulica | Estudios hidráulicos, recursos hídricos | S |
| VIALIDAD | Vialidad | Diseño vial, puentes, túneles | N |

La columna `ACTIVA` permite desactivar un área sin borrar su hoja de filtros.

---

## 5. Nueva estructura del código

### 5.1 Cambios en `config.py`

**Eliminar** la modificación actual (catálogo hardcoded de PIVOTs separados).

**Reemplazar** con una propiedad que lee el PIVOT dinámicamente:

```python
@property  
def AREAS_DISPONIBLES(self) -> dict[str, str]:
    """
    Lee el PIVOT_MAESTRO y devuelve las áreas disponibles.
    Retorna: {"TI": "TI / Tecnología", "HIDRAULICA": "Hidráulica"}
    Detecta hojas con prefijo '06-FILTROS-' (excepto TEMPLATE).
    Si existe la hoja 07-AREAS, usa nombre_display de allí.
    Si no, usa el ID como nombre.
    """
```

**Eliminar:** `AREAS_ACTIVAS`, `_CATALOGO_AREAS`, `PIVOTS_AREAS` (el enfoque de múltiples archivos).  
**Mantener:** `PIVOT_MAESTRO` (sigue siendo el mismo archivo único).

### 5.2 Cambios en `etapa2.py`

Esta es la etapa más afectada. Los cambios son:

#### Cambio 1: `_cargar_filtros_globales()` (método nuevo)

```python
def _cargar_filtros_globales(self) -> dict:
    """
    Lee la hoja 06-EXCL-GLOBALES del PIVOT_MAESTRO.
    Retorna el mismo dict-formato que _cargar_filtros() pero 
    solo con exclusiones rellenas (inclusión y bypass vacíos).
    Se llama una sola vez al inicio del run() y se reutiliza 
    para todas las áreas.
    """
```

#### Cambio 2: `_cargar_filtros(area: str)` (firma modificada)

```python
def _cargar_filtros(self, area: str) -> dict:
    """
    Lee la hoja 06-FILTROS-{area} del PIVOT_MAESTRO.
    Fusiona las exclusiones con los filtros globales.
    Los filtros del área siempre tienen prioridad sobre los globales
    en caso de conflicto (para el bypass).
    """
    hoja = f"06-FILTROS-{area}"
    filtros_area = self._leer_hoja_filtros(hoja)
    filtros_area["excluir"] = {
        k: self._filtros_globales["excluir"].get(k, []) + filtros_area["excluir"].get(k, [])
        for k in set(list(self._filtros_globales["excluir"]) + list(filtros_area["excluir"]))
    }
    return filtros_area
```

#### Cambio 3: `run()` — loop por áreas

```python
def run(self, context: PipelineContext) -> StageResult:
    ...
    # areas_a_procesar viene del contexto (el usuario las eligió en la GUI)
    areas = context.flags.get("areas_seleccionadas", ["TI"])
    
    self._filtros_globales = self._cargar_filtros_globales()
    resultados_por_area = {}
    
    for area in areas:
        self.logger.info(f"[ÁREA] Procesando: {area}")
        self.filtros = self._cargar_filtros(area)
        df_filtradas, df_excluidas = self._aplicar_filtrado(df)
        df_filtradas["ÁREA"] = area        # ← columna nueva
        resultados_por_area[area] = df_filtradas
    
    df_total = pd.concat(resultados_por_area.values(), ignore_index=True)
    # Deduplica por código de licitación + área (una licitación puede 
    # aparecer en dos áreas si ambas la capturan — eso es válido)
    
    rutas = self._generar_outputs(resultados_por_area)
    ...
```

#### Cambio 4: `_generar_outputs()` — multi-hoja

```python
def _generar_outputs(self, resultados: dict[str, pd.DataFrame]) -> list[Path]:
    """
    Genera un solo Excel con:
    - Una hoja por área (ej: "TI", "HIDRAULICA")
    - Una hoja "RESUMEN" con todo concatenado y columna ÁREA
    """
    timestamp = obtener_timestamp()
    ruta = self.config.FILTRADO_DIR / f"Licitaciones_Filtradas_{timestamp}.xlsx"
    
    with pd.ExcelWriter(ruta, engine="openpyxl") as writer:
        # Hoja RESUMEN primero
        df_total = pd.concat(resultados.values(), ignore_index=True)
        df_total.to_excel(writer, sheet_name="RESUMEN", index=False)
        
        # Una hoja por área
        for area, df in resultados.items():
            df.to_excel(writer, sheet_name=area, index=False)
    
    return [ruta]
```

### 5.3 Cambios en `lanzador_licitaciones.py` (GUI)

Tres cambios en la interfaz visual:

#### Cambio 1: Sección "Áreas a analizar" con checkboxes dinámicos

La GUI lee el PIVOT al arrancar y crea un checkbox por cada área disponible. Si el PIVOT tiene 3 áreas, aparecen 3 checkboxes. Si tiene 1, aparece solo 1 (sin sección visual para no confundir).

```
┌─────────────────────────────────────────┐
│  Áreas a analizar:                      │
│  ☑ TI / Tecnología                      │
│  ☐ Hidráulica                           │
│  ☐ Vialidad                             │
└─────────────────────────────────────────┘
```

Los checkboxes pasan las áreas seleccionadas al pipeline via `context.flags["areas_seleccionadas"]`.

#### Cambio 2: Botón "➕ Gestionar áreas" — asistente de nueva área

Un nuevo botón pequeño abre una ventana secundaria (dialog):

```
┌─────────────────────────────────────────────┐
│  ➕ Crear nueva área                         │
├─────────────────────────────────────────────┤
│                                             │
│  ID del área (sin espacios):                │
│  [HIDRAULICA                           ]    │
│                                             │
│  Nombre para mostrar:                       │
│  [Hidráulica                           ]    │
│                                             │
│  Keywords iniciales (una por línea):        │
│  ┌─────────────────────────────────────┐   │
│  │ estudio hidraulico                  │   │
│  │ recursos hidricos                   │   │
│  │ cuenca                              │   │
│  │ embalse                             │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  [ Cancelar ]      [ ✅ Crear área ]        │
└─────────────────────────────────────────────┘
```

Al hacer clic en "Crear área", Python (sin abrir Excel):
1. Abre `PIVOT_MAESTRO.xlsx`
2. Copia la hoja `06-FILTROS-TEMPLATE`
3. La renombra a `06-FILTROS-HIDRAULICA`
4. Rellena las keywords en la columna A (fila 6 en adelante)
5. Agrega la entrada en la hoja `07-AREAS`
6. Guarda el archivo
7. Actualiza los checkboxes en la GUI automáticamente

#### Cambio 3: Tamaño de la ventana principal

La ventana crece de 600×540 a 600×620 para acomodar la sección de áreas.

### 5.4 Cambios en `run_pipeline.py`

Recibir el argumento `--areas` desde la GUI:

```python
parser.add_argument(
    "--areas",
    default="TI",
    help="Áreas a procesar, separadas por coma. Ej: TI,HIDRAULICA"
)
# → context.flags["areas_seleccionadas"] = args.areas.split(",")
```

### 5.5 Cambios en `verificador_entorno.py`

El verificador de entorno (el panel de "Estado del entorno" en la GUI) actualmente verifica si `PIVOT_MAESTRO.xlsx` existe. Hay que añadir que verifique que tenga al menos una hoja `06-FILTROS-*` válida.

---

## 6. Nueva interfaz gráfica

### 6.1 Pantalla principal completa (wireframe)

```
┌─────────────────────────────────────────────────────┐
│  🏛️ MP CONSULTING                                  │
│  Sistema de Licitaciones Mercado Público             │
├─────────────────────────────────────────────────────┤
│  Estado del entorno:                                │
│  ✅ Entorno virtual (.venv): OK                     │
│  ✅ PIVOT_MAESTRO.xlsx: OK (3 áreas disponibles)    │
│  ✅ API Key: Configurada                            │
│  ✅ Archivo de entrada: Encontrado                  │
│  [🔄 Re-verificar]                                  │
├─────────────────────────────────────────────────────┤
│  Áreas a analizar:                    [+ Gestionar] │
│  ☑ TI / Tecnología                                  │
│  ☐ Hidráulica                                       │
│  ☐ Vialidad                                         │
├─────────────────────────────────────────────────────┤
│  [ 🚀 EJECUTAR PIPELINE COMPLETO                  ] │
│  [ 📊 SOLO ANÁLISIS INCREMENTAL                   ] │
│  [ 📂 Abrir carpeta de resultados                 ] │
├─────────────────────────────────────────────────────┤
│  Estado: ✅ Sistema listo para ejecutar             │
│  ════════════════════════════════════════════      │
│  Log de ejecución:                                  │
│  ┌─────────────────────────────────────────────┐   │
│  │ [10:23:01] 🎯 Sistema iniciado              │   │
│  │ [10:23:01] 💡 Selecciona una opción         │   │
│  └─────────────────────────────────────────────┘   │
│  [ ❌ Salir ]                                       │
└─────────────────────────────────────────────────────┘
```

### 6.2 Comportamiento de los checkboxes

- **Si solo hay 1 área:** no se muestra la sección de checkboxes (evitar confusión)
- **Si hay 2+ áreas:** se muestra la sección con todos los checkboxes
- **Al iniciar:** todas las áreas marcadas como activas en `07-AREAS` aparecen marcadas por defecto
- **Validación:** si el usuario desmarca todas, el botón ejecutar se deshabilita con mensaje "Selecciona al menos un área"

---

## 7. Flujo completo de ejecución

```
USUARIO ABRE LA APP
        │
        ▼
GUI LEE PIVOT_MAESTRO.xlsx
Detecta áreas: ["TI", "HIDRAULICA"]
Muestra checkboxes
        │
        ▼
USUARIO MARCA: ☑ TI  ☑ Hidráulica
Hace clic en "EJECUTAR PIPELINE COMPLETO"
        │
        ▼
run_pipeline.py --areas TI,HIDRAULICA
        │
        ├── Etapa 0: Descarga Licitacion_Publicada.xlsx (~12.000 filas)
        │
        ├── Etapa 1: Auditoría taxonomía (detecta valores nuevos en PIVOT)
        │
        ├── Etapa 2: FILTRADO MULTI-ÁREA ← el más cambiado
        │     │
        │     ├── Carga 06-EXCL-GLOBALES (427 exclusiones genéricas)
        │     │
        │     ├── Para área TI:
        │     │     Carga 06-FILTROS-TI
        │     │     Fusiona exclusiones: globales + específicas TI
        │     │     Aplica inclusión → exclusión → bypass
        │     │     df_TI["ÁREA"] = "TI"
        │     │     Resultado: ~301 licitaciones
        │     │
        │     ├── Para área HIDRAULICA:
        │     │     Carga 06-FILTROS-HIDRAULICA
        │     │     Fusiona exclusiones: globales + específicas Hidráulica
        │     │     Aplica inclusión → exclusión → bypass
        │     │     df_HID["ÁREA"] = "HIDRAULICA"
        │     │     Resultado: ~45 licitaciones (estimado)
        │     │
        │     └── Genera Excel con hojas: RESUMEN, TI, HIDRAULICA
        │
        ├── Etapa 3: Enriquece datos vía API (para todas las áreas)
        │
        ├── Etapa 4: Reporte final (multi-hoja)
        │
        └── Etapa 5: Incremental (detecta novedades por área y global)
```

---

## 8. Flujo para agregar un área nueva

### Para el coordinador de área (sin conocimientos técnicos)

```
PASO 1
Abre la app (doble clic en Lanzador_MP.bat)
Clic en el botón "➕ Gestionar áreas"
        │
        ▼
PASO 2
Rellena el formulario:
  - ID área: HIDRAULICA
  - Nombre: Hidráulica  
  - Keywords: (lista de 10-30 términos clave de su área)
Clic en "✅ Crear área"
        │
        ▼
PASO 3
La app abre PIVOT_MAESTRO.xlsx internamente y crea la hoja 06-FILTROS-HIDRAULICA
El checkbox "Hidráulica" aparece en la pantalla principal
        │
        ▼
PASO 4 (opcional, para afinar)
Abrir PIVOT_MAESTRO.xlsx en Excel
Agregar más keywords en la columna A de la hoja 06-FILTROS-HIDRAULICA
Agregar exclusiones específicas (si hay términos que solo esta área quiere excluir)
        │
        ▼
PASO 5
Ejecutar el pipeline con ☑ Hidráulica seleccionado
Revisar los resultados → ajustar keywords → repetir
```

### Para el administrador del sistema

No hay nada adicional. El sistema es autoconfigurado.

---

## 9. Archivos de salida

### 9.1 Etapa 2 (Filtrado)

**Antes:**
```
data/2. OUTPUT/3. FILTRADO/
  Licitaciones_Filtradas_20260323_143022.xlsx   ← una hoja "Filtradas"
  Licitaciones_Excluidas_20260323_143022.xlsx   ← una hoja "Excluidas"
```

**Después:**
```
data/2. OUTPUT/3. FILTRADO/
  Licitaciones_Filtradas_20260323_143022.xlsx
    ├── RESUMEN        (todas las áreas, columna ÁREA)
    ├── TI             (solo TI)
    └── HIDRAULICA     (solo Hidráulica, si fue seleccionada)
  
  Licitaciones_Excluidas_20260323_143022.xlsx
    ├── TI_excluidas
    └── HIDRAULICA_excluidas
```

### 9.2 Etapa 4 (Reporte final)

El reporte de presentación también tendrá hojas por área + RESUMEN.

### 9.3 Columna nueva: ÁREA

Todos los outputs tendrán una columna `ÁREA` que indica de qué perfil de filtrado viene cada licitación. Esto permite:
- Filtrar en Excel por área
- Identificar licitaciones que aparecen en más de un área (son las más relevantes)

---

## 10. Plan de implementación paso a paso

### PRE-REQUISITO: deshacer cambio parcial en config.py

El branch `feature/multi-area` tiene una modificación en `config.py` (catálogo hardcoded de PIVOTs separados) que corresponde al enfoque descartado. Hay que revertirla antes de implementar la arquitectura correcta.

```bash
git checkout HEAD -- src/utils/config.py  # vuelve config.py al estado del commit
```

---

### PASO 1 — Migrar PIVOT_MAESTRO.xlsx a nueva estructura

**Archivos afectados:** Solo `config_pivot/PIVOT_MAESTRO.xlsx`  
**Riesgo:** Alto (es el archivo de producción). Se hace backup antes.  
**Quién lo hace:** Manual + script Python de asistencia

**Subtareas:**
1. Hacer backup: `PIVOT_MAESTRO.xlsx` → `PIVOT_MAESTRO_backup_20260323.xlsx`
2. Crear hoja `06-EXCL-GLOBALES`:
   - Copiar estructura de columnas de `06-FILTROS`
   - Mover las exclusiones genéricas universales de cols E-L de `06-FILTROS` a la nueva hoja
3. Renombrar hoja `06-FILTROS` → `06-FILTROS-TI`
   - Las exclusiones que quedan son las específicas de TI
4. Crear hoja `06-FILTROS-TEMPLATE`:
   - Misma estructura que `06-FILTROS-TI`
   - Instrucciones en filas 1-4
   - Todo vacío desde fila 6
5. Crear hoja `07-AREAS`:
   - Una fila para TI con nombre display "TI / Tecnología"
6. Verificar que los 545 tests siguen pasando con el PIVOT migrado

**Decisión manual requerida:** Clasificar las 433 exclusiones actuales entre "globales" y "específicas de TI". Criterio:
- **Global:** si NO la querría NINGUNA área de MP (ej: pavimentación, medicamentos, semillas)
- **Específica TI:** si solo aplica a TI (ej: quizás ninguna — la mayoría son globales)

---

### PASO 2 — Actualizar `config.py`

**Archivos afectados:** `src/utils/config.py`  
**Riesgo:** Bajo — solo añade una propiedad nueva, sin romper las existentes

**Cambios específicos:**
1. Revertir al estado del commit `7d21cbe` (eliminar los cambios parciales del branch)
2. Añadir propiedad `AREAS_DISPONIBLES` que lee el PIVOT dinámicamente:
   ```python
   @property
   def AREAS_DISPONIBLES(self) -> dict[str, str]:
       """Lee el PIVOT y devuelve {id_area: nombre_display}"""
   ```
3. Añadir propiedad `EXCL_GLOBALES_SHEET` que retorna `"06-EXCL-GLOBALES"` (constante)
4. Mantener `PIVOT_MAESTRO` tal cual (sin cambios)
5. Actualizar `validar_estructura()` para verificar que exista al menos una hoja `06-FILTROS-*`

**Tests a actualizar:** `tests/unit/test_config_cobertura.py` — añadir test para `AREAS_DISPONIBLES`

---

### PASO 3 — Actualizar `etapa2.py`

**Archivos afectados:** `src/etapas/etapa2.py`  
**Riesgo:** Alto — es el núcleo del sistema  
**Estrategia:** Modificar in-place manteniendo compatibilidad con tests existentes

**Cambios específicos:**

1. **Añadir** `_cargar_filtros_globales(self) -> dict`
   - Lee hoja `06-EXCL-GLOBALES`
   - Misma lógica que el `_cargar_filtros()` actual
   - Retorna dict con solo exclusiones rellenas

2. **Modificar** `_cargar_filtros(self, area: str = "TI") -> dict`
   - Añadir parámetro `area` (default `"TI"` para no romper tests)
   - Leer hoja `06-FILTROS-{area}` en vez de `06-FILTROS`
   - Fusionar exclusiones globales con las del área

3. **Añadir** `_iteracion_por_area(self, df, area) -> tuple[DataFrame, DataFrame]`
   - Llama `_cargar_filtros(area)` y ejecuta las 3 fases
   - Añade columna `ÁREA` al resultado

4. **Modificar** `run(self, context)`:
   - Leer `areas = context.flags.get("areas_seleccionadas", ["TI"])`
   - Llamar a `_iteracion_por_area()` por cada área
   - Concatenar resultados

5. **Modificar** `_generar_outputs()`:
   - Recibe `dict[str, DataFrame]` en vez de un solo DataFrame
   - Genera Excel multi-hoja (RESUMEN + una por área)

6. **Modificar** `_validar_prerequisitos()`:
   - Verificar que existan las hojas `06-FILTROS-{area}` para las áreas seleccionadas
   - Verificar que exista `06-EXCL-GLOBALES`

**Tests a actualizar:**
- `tests/unit/test_etapa2_cobertura.py` — los tests de `_cargar_filtros` necesitan el parámetro área y el mock del PIVOT debe tener la nueva estructura de hojas
- `tests/integration/test_pipeline_smoke.py` — los mocks de `_cargar_filtros` necesitan adaptarse
- `tests/unit/test_calidad_filtrado.py` — no requiere cambios (testea la lógica de filtrado puro, sin tocar disco)
- `tests/unit/test_filtrado.py` — no requiere cambios (misma razón)

---

### PASO 4 — Actualizar `run_pipeline.py`

**Archivos afectados:** `run_pipeline.py`  
**Riesgo:** Bajo

**Cambios específicos:**
1. Añadir argumento `--areas` al parser:
   ```python
   parser.add_argument("--areas", default="TI",
                       help="Áreas separadas por coma: TI,HIDRAULICA")
   ```
2. Pasar las áreas al contexto:
   ```python
   context.flags["areas_seleccionadas"] = [a.strip() for a in args.areas.split(",")]
   ```

---

### PASO 5 — Actualizar `lanzador_licitaciones.py` (GUI)

**Archivos afectados:** `lanzador_licitaciones.py`  
**Riesgo:** Medio — cambios visuales, nada en la lógica del pipeline

**Cambios específicos:**

1. **Añadir** método `_cargar_areas_disponibles(self) -> dict[str, str]`
   - Llama a `Config().AREAS_DISPONIBLES`
   - Retorna `{"TI": "TI / Tecnología", "HIDRAULICA": "Hidráulica"}`
   - Si falla (PIVOT no encontrado), retorna `{"TI": "TI / Tecnología"}` como fallback

2. **Añadir** sección de checkboxes en `setup_ui()`:
   - Solo visible si hay 2+ áreas
   - `self.vars_areas: dict[str, tk.BooleanVar]` — un BooleanVar por área
   - Checkboxes generados dinámicamente del resultado de `_cargar_areas_disponibles()`

3. **Añadir** método `_get_areas_seleccionadas(self) -> list[str]`
   - Lee los BooleanVars y retorna las áreas marcadas
   - Si no hay checkboxes (modo 1 área), retorna `["TI"]`

4. **Modificar** `ejecutar_pipeline_completo()` y `ejecutar_solo_incremental()`:
   - Añadir `--areas {",".join(self._get_areas_seleccionadas())}` al comando

5. **Añadir** botón "➕ Gestionar" junto a la sección de áreas:
   - Abre ventana dialog `_abrir_gestor_areas()`

6. **Añadir** ventana `_abrir_gestor_areas(self)`:
   - Toplevel con campos: ID área, Nombre display, Keywords (Text widget)
   - Botón "Crear área" → llama `_crear_area_en_pivot(id, nombre, keywords)`

7. **Añadir** método `_crear_area_en_pivot(self, id_area, nombre, keywords)`:
   - Usa openpyxl para abrir el PIVOT
   - Copia hoja `06-FILTROS-TEMPLATE`
   - Renombra a `06-FILTROS-{id_area}`
   - Rellena keywords en col A desde fila 6
   - Actualiza hoja `07-AREAS`
   - Guarda y cierra
   - Recarga los checkboxes en la GUI

8. **Agrandar** ventana principal: 600×540 → 600×660

---

### PASO 6 — Actualizar `verificador_entorno.py`

**Archivos afectados:** `src/utils/verificador_entorno.py`  
**Riesgo:** Bajo

**Cambios específicos:**
1. Check existente "PIVOT_MAESTRO.xlsx existe" → ampliar a verificar también que el PIVOT contiene al menos 1 hoja `06-FILTROS-*`
2. Mensaje actualizado: "PIVOT_MAESTRO.xlsx: OK (2 áreas disponibles)"

---

### PASO 7 — Escribir tests nuevos

Ver sección 11.

---

### PASO 8 — Ejecutar suite completa y verificar

```bash
cd C:\Licitaciones_MP
.venv\Scripts\python.exe -m pytest --tb=short -q
# Target: 545 tests existentes + nuevos todos en verde
```

---

### PASO 9 — Commit y merge

```bash
git add .
git commit -m "feat(multi-area): pivot multi-hoja, checkboxes dinámicos, asistente nueva área"
git push origin feature/multi-area
# Crear PR → merge a master
```

---

## 11. Tests que se escribirán

Todos en el archivo nuevo `tests/unit/test_multi_area.py`.

### Grupo A — Config

| Test | Qué verifica |
|------|-------------|
| `test_areas_disponibles_lee_pivot` | `AREAS_DISPONIBLES` detecta hojas `06-FILTROS-TI` y `06-FILTROS-HIDRAULICA` en un PIVOT temporal |
| `test_areas_disponibles_ignora_template` | La hoja `06-FILTROS-TEMPLATE` NO aparece como área disponible |
| `test_areas_disponibles_pivot_sin_hojas` | Si no hay hojas `06-FILTROS-*`, retorna dict vacío sin lanzar excepción |
| `test_areas_disponibles_usa_07_areas_para_nombre` | Si existe hoja `07-AREAS`, usa el nombre display de allí |

### Grupo B — Etapa 2 — Filtros globales

| Test | Qué verifica |
|------|-------------|
| `test_cargar_filtros_globales_lee_hoja_correcta` | Lee hoja `06-EXCL-GLOBALES` y retorna exclusiones |
| `test_cargar_filtros_globales_hoja_faltante` | Si falta `06-EXCL-GLOBALES`, retorna dict vacío (no lanza, no bloquea) |
| `test_cargar_filtros_area_fusiona_globales` | Para área TI, las exclusiones del área + las globales = exclusiones totales |
| `test_cargar_filtros_area_invalida` | Si se pide área "INEXISTENTE", lanza `ValueError` con mensaje claro |

### Grupo C — Etapa 2 — Multi-área

| Test | Qué verifica |
|------|-------------|
| `test_run_dos_areas_genera_columna_area` | Con 2 áreas, el output tiene columna ÁREA con valores "TI" e "HIDRAULICA" |
| `test_run_dos_areas_hoja_resumen_existe` | El Excel de salida contiene hoja "RESUMEN" |
| `test_run_dos_areas_cada_area_tiene_hoja` | El Excel contiene hojas "TI" y "HIDRAULICA" |
| `test_run_area_sin_resultados` | Un área con 0 licitaciones no rompe el pipeline (hoja vacía en el output) |
| `test_run_contexto_sin_areas` | Sin `areas_seleccionadas` en el contexto, usa `["TI"]` por defecto |
| `test_estadisticas_por_area` | El resumen de stats incluye conteo por área |

### Grupo D — GUI — Asistente nueva área

| Test | Qué verifica |
|------|-------------|
| `test_crear_area_agrega_hoja_al_pivot` | `_crear_area_en_pivot("HIDRAULICA", "Hidráulica", ["cuenca"])` crea hoja `06-FILTROS-HIDRAULICA` en PIVOT temporal |
| `test_crear_area_rellena_keywords` | Las keywords se escriben en columna A desde fila 6 |
| `test_crear_area_id_ya_existe` | Si el área ya existe, lanza error descriptivo (no duplica hoja) |
| `test_crear_area_actualiza_07_areas` | La hoja `07-AREAS` se actualiza con la nueva entrada |

---

## 12. Lo que NO cambia

Para claridad, estos componentes **no se tocan en este plan**:

| Componente | Por qué no cambia |
|------------|------------------|
| `etapa0.py` | La descarga es genérica, no depende del área |
| `etapa1.py` | La auditoría de taxonomía es global, no por área |
| `etapa3.py` | El enriquecimiento via API es fila a fila, no depende del área |
| `etapa5.py` | El incremental trabaja sobre el output final, detecta novedades globalmente |
| `etapa4.py` | Mínimos cambios: debe soportar columna ÁREA en el input |
| `run_pipeline.py` | Solo añade argumento `--areas` |
| Tests de lógica de filtrado | `test_filtrado.py`, `test_calidad_filtrado.py` no cambian — testean la lógica pura |
| `.env` / credenciales | Sin cambios |
| Estructura de carpetas `data/` | Sin cambios |

---

## 13. Riesgos y preguntas abiertas

### Riesgo 1 — Clasificación de exclusiones globales vs específicas TI

**Descripción:** Al migrar el PIVOT, hay que decidir qué exclusiones van a `06-EXCL-GLOBALES` y cuáles se quedan en `06-FILTROS-TI`. Si se mueven mal, el área TI puede empezar a capturar cosas que no quiere (porque la exclusión global no las cubre) o viceversa.

**Mitigación:** Correr el filtrado con el nuevo PIVOT sobre el mismo input que produjo 301 licitaciones. El resultado debe seguir siendo ~301. Si cambia, ajustar.

### Riesgo 2 — Performance con muchas áreas

**Descripción:** Cada área es una pasada completa sobre las 12.000 licitaciones. Con 5 áreas, son 5 pasadas.

**Impacto esperado:** Cada pasada toma ~2-3 segundos. Con 5 áreas: ~15 segundos adicionales. Aceptable.

**Si se vuelve problema:** Cachear el DataFrame normalizado (la preparación de campos es la parte más lenta).

### Riesgo 3 — Usuario crea área con keywords incorrectas

**Descripción:** Si el coordinador de Hidráulica escribe keywords demasiado genéricas (ej: "agua"), el resultado puede inundar de falsos positivos.

**Mitigación:** El asistente de nueva área mostrará una advertencia si alguna keyword tiene menos de 4 caracteres. Agregar un campo de "ejecutar preview" (filtrar y mostrar conteo antes de guardar) — esto es una mejora futura, no bloqueante.

### Pregunta abierta 1 — ¿Cómo se distribuye el PIVOT actualizado?

Cuando alguien añade un área nueva desde su máquina, ¿cómo llega ese cambio al resto del equipo? Opciones:
- (A) El PIVOT vive en una carpeta compartida de red (todos apuntan al mismo archivo)
- (B) Cada quien tiene su copia y se sincroniza manualmente
- (C) Git — el PIVOT está en el repositorio y se hace `git pull` para actualizar

Esta decisión afecta la arquitectura de distribución pero no el código.

### Pregunta abierta 2 — ¿Qué hacer con licitaciones que aparecen en dos áreas?

Una licitación "Sistema de monitoreo de caudales con software IoT" podría ser capturada por TI e Hidráulica. En el output actual aparecería en ambas hojas. ¿Es eso deseado?

Propuesta: En la hoja RESUMEN, la licitación aparece dos veces (una por área). Eso es correcto — cada coordinador la ve en su pestaña. Si alguien mira el RESUMEN, la columna ÁREA lo aclara.

---

*Fin del documento. Versión 1.0 — pendiente de revisión y aprobación.*
