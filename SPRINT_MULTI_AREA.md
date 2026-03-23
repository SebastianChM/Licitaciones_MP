# Sprint Multi-Área — Checklist de Ejecución

**Branch:** `feature/multi-area`  
**Arquitectura de referencia:** `PLAN_MULTI_AREA.md`  
**Baseline:** commit `050790a` · 545 tests ✅ · PIVOT aún con `06-FILTROS`

---

## Reglas del sprint

> Estas reglas no son sugerencias. Son la forma en que trabajamos.

1. **Un PASO a la vez.** No comenzar el PASO N+1 sin que el N esté marcado `[x]` y la verificación sea verde.
2. **TDD en pasos 2–6.** Primero el test (rojo), luego el código (verde). El test rojo confirma que es real.
3. **Un commit atómico por PASO.** El mensaje es el predefinido abajo — usarlo textualmente.
4. **Suite completa antes de cada commit.** `pytest tests/ -q --tb=no` debe mostrar "N passed, 0 failed".
5. **Si algo falla, parar.** Diagnosticar y resolver en el mismo PASO. No avanzar con tests rojos.

---

## Mapa de dependencias

```
PASO 1  (Excel manual)
  └─► PASO 2  (config.py)              ← TDD
        └─► PASO 3  (etapa2.py)        ← TDD — mayor riesgo de regresión
              ├─► PASO 4  (run_pipeline.py)   ← TDD
              └─► PASO 5  (lanzador GUI)      ← TDD + verificación visual
                    └─► PASO 6  (verificador_entorno.py)  ← TDD
                          └─► PASO 7  (validación final + merge)
```

---

## PASO 1 — Migrar PIVOT_MAESTRO.xlsx *(trabajo manual en Excel)*

**Precondición:** Ninguna.  
**Estado:** ⬜ Pendiente  
**Tipo:** Manual — no requiere cambios de código.

### Checklist

- [ ] **1.0** Backup: copiar `config_pivot/PIVOT_MAESTRO.xlsx` → `config_pivot/PIVOT_MAESTRO_backup_20260323.xlsx`
- [ ] **1.1** Renombrar hoja `06-FILTROS` → `06-FILTROS-TI`
- [ ] **1.2** Crear hoja `06-EXCL-GLOBALES`
  - Misma estructura de columnas que `06-FILTROS-TI` (encabezado en fila 5)
  - Trasladar desde `06-FILTROS-TI` (cols E–L) solo las exclusiones **universales**
  - Criterio: *"¿Existe algún área de MP que querría licitaciones de ese tipo?"*
    - Respuesta **NO** → va a `06-EXCL-GLOBALES`: pavimentacion, demolicion, medicamentos, vestuario, juegos infantiles, fertilizantes, etc.
    - Respuesta **SÍ o DUDA** → queda en `06-FILTROS-TI`
  - Las columnas A–D (inclusión) y M (bypass) quedan **vacías** en esta hoja
- [ ] **1.3** Crear hoja `06-FILTROS-TEMPLATE`
  - Misma estructura de encabezados (fila 5)
  - Instrucciones en filas 1–4 (texto en gris, solo lectura)
  - Sin datos a partir de fila 6
- [ ] **1.4** Crear hoja `07-AREAS`
  - Columnas: `ID_AREA | NOMBRE_DISPLAY | DESCRIPCION | ACTIVA`
  - Primera fila de datos: `TI | TI / Tecnología | Sistemas, software, telecomunicaciones | S`
- [ ] **1.5** Guardar el Excel y cerrar

### ⚠️ Advertencia esperada

Después de renombrar `06-FILTROS` → `06-FILTROS-TI`, `etapa2.py` todavía busca la hoja con el nombre viejo. Puede que **algunos tests fallen** — eso es normal y se resuelve en PASO 3. Anotarlo antes de continuar.

### Verificación

```bash
python -m pytest tests/ -q --tb=no
```

| Resultado | Significado | Acción |
|-----------|-------------|--------|
| 545 passed | Nada se rompió | ✅ Continuar |
| Fallos solo en `test_etapa2*` | Renombrado rompió validación de hoja — **esperado** | Anotar, continuar |
| Fallos en otro test | Error inesperado | Parar y diagnosticar antes de continuar |

### Commit

```bash
git add config_pivot/PIVOT_MAESTRO.xlsx
git commit -m "chore(pivot): migrar 06-FILTROS a arquitectura multi-área (PASO 1)"
```

---

## PASO 2 — `config.py`: propiedad `AREAS_DISPONIBLES` *(TDD)*

**Precondición:** PASO 1 ✅  
**Estado:** ⬜ Pendiente  
**Markers en código:** `PASO 2.1`, `PASO 2.2` (buscar en `src/utils/config.py`)

### 2a — Escribir los tests primero

Crear (o abrir si ya existe) `tests/unit/test_multi_area.py` y agregar:

```python
# ── Grupo 1: Config ────────────────────────────────────
def test_areas_disponibles_detecta_hoja_06_filtros_ti()
    # Mock: PIVOT con hoja '06-FILTROS-TI' → retorna {"TI": ...}

def test_areas_disponibles_usa_hoja_07_areas_para_nombre_display()
    # Mock: PIVOT con '07-AREAS' → retorna {"TI": "TI / Tecnología"}

def test_areas_disponibles_fallback_sin_pivot()
    # PIVOT no existe → retorna {"TI": "TI / Tecnología"} sin lanzar excepción

def test_validar_estructura_falla_si_no_hay_hoja_06_filtros_asterisco()
    # PIVOT existe pero sin hojas '06-FILTROS-*' → validar_estructura() retorna False
```

Ejecutar → **deben fallar** (el método no existe):

```bash
python -m pytest tests/unit/test_multi_area.py -v --tb=short
# → 4 FAILED (expected)
```

### 2b — Implementar

Ver marker `PASO 2.1` en `src/utils/config.py`:
- Añadir `@property AREAS_DISPONIBLES(self) -> dict[str, str]`
- Lee `07-AREAS` para nombres display; fallback al ID de hoja si esa hoja no existe
- Fallback final: `{"TI": "TI / Tecnología"}` si el PIVOT no existe (no lanzar excepción)

Ver marker `PASO 2.2` en `src/utils/config.py`:
- Actualizar `validar_estructura()` para verificar que exista al menos una hoja `06-FILTROS-*`

### Verificación

```bash
python -m pytest tests/unit/test_multi_area.py -v --tb=short
# → 4 passed

python -m pytest tests/ -q --tb=no
# → ~549 passed (base 545 + 4 nuevos)
```

### Commit

```bash
git add src/utils/config.py tests/unit/test_multi_area.py
git commit -m "feat(config): AREAS_DISPONIBLES escanea hojas PIVOT dinámicamente (PASO 2)"
```

---

## PASO 3 — `etapa2.py`: refactor multi-área *(TDD)*

**Precondición:** PASO 2 ✅  
**Estado:** ⬜ Pendiente  
**Markers en código:** `PASO 3.0` a `PASO 3.5` (buscar en `src/etapas/etapa2.py`)  
**⚠️ Riesgo:** Mayor superficie de cambio del sprint. Leer el código existente antes de modificar.

### 3a — Agregar tests a `test_multi_area.py`

```python
# ── Grupo 2: etapa2 — carga de filtros ────────────────
def test_cargar_filtros_globales_lee_hoja_EXCL_GLOBALES()
    # Mock PIVOT con hoja '06-EXCL-GLOBALES' → retorna dict con clave "excluir"

def test_cargar_filtros_funde_globales_con_filtros_del_area()
    # Globales: excluir=["X"] / Área TI: excluir=["Y"] → fusión: ["X","Y"]

def test_cargar_filtros_area_inexistente_lanza_error()
    # Pedir área "INEXISTENTE" → FileNotFoundError o ValueError claro

# ── Grupo 3: etapa2 — ejecución multi-área ────────────
def test_run_agrega_columna_AREA_al_dataframe_resultado()
    # Resultado de run() con area="TI" → df tiene columna "ÁREA" con valor "TI"

def test_run_procesa_multiples_areas_independientemente()
    # areas=["TI","HIDRAULICA"] → dos dataframes separados sin mezclar resultados

def test_generar_outputs_produce_excel_con_hoja_RESUMEN_y_por_area()
    # Verificar que el Excel generado tiene Sheet "RESUMEN" + "TI"
```

Ejecutar → **deben fallar**:

```bash
python -m pytest tests/unit/test_multi_area.py -v --tb=short
# → 6 nuevos FAILED
```

### 3b — Implementar (en este orden estricto)

| N° | Marker | Qué hacer |
|----|--------|-----------|
| 3.0 | `PASO 3.0` en `_validar_prerequisitos()` | Cambiar `hojas_requeridas=['06-FILTROS']` → `['06-FILTROS-TI']` |
| 3.1 | `PASO 3.1` | Extraer lógica de lectura en `_leer_hoja_filtros(self, hoja: str) -> dict` |
| 3.2 | `PASO 3.2` | Añadir `_cargar_filtros_globales(self) -> dict` — lee `06-EXCL-GLOBALES` |
| 3.3 | `PASO 3.3` | Modificar `_cargar_filtros(self, area: str = "TI")` — lee `06-FILTROS-{area}`, fusiona globales |
| 3.4 | `PASO 3.4` | Modificar `run()` — loop por `areas_seleccionadas`, añadir `df["ÁREA"] = area` |
| 3.5 | `PASO 3.5` | Modificar `_generar_outputs()` — acepta `dict[str, DataFrame]`, escribe multi-hoja |

Ejecutar tests parciales después de cada sub-paso:

```bash
python -m pytest tests/unit/test_multi_area.py -v -k "filtros" --tb=short  # tras 3.3
python -m pytest tests/unit/test_multi_area.py -v --tb=short                # tras 3.5
```

### Verificación

```bash
python -m pytest tests/unit/test_multi_area.py -v --tb=short
# → 10 passed (4 config + 6 etapa2)

python -m pytest tests/ -q --tb=no
# → ~555 passed — cero regresiones
```

### Commit

```bash
git add src/etapas/etapa2.py tests/unit/test_multi_area.py
git commit -m "feat(etapa2): refactor multi-área con filtros globales y loop por áreas (PASO 3)"
```

---

## PASO 4 — `run_pipeline.py`: argumento `--areas` *(TDD)*

**Precondición:** PASO 3 ✅  
**Estado:** ⬜ Pendiente  
**Marker en código:** `PASO 4.1` (buscar en `run_pipeline.py`)

### 4a — Agregar tests a `test_multi_area.py`

```python
# ── Grupo 4: CLI ────────────────────────────────────────
def test_argparse_acepta_flag_areas_con_multiples_valores()
    # parse_args(["--areas","TI","HIDRAULICA"]) → args.areas == ["TI","HIDRAULICA"]

def test_argparse_areas_default_es_TI()
    # parse_args([]) → args.areas == ["TI"]
```

### 4b — Implementar

Ver marker `PASO 4.1` en `run_pipeline.py`:
- Añadir argumento `--areas` justo antes de `args = parser.parse_args()`
- Tipo: `str`, `nargs='+'`, `default=["TI"]`
- Antes de ejecutar el pipeline: `context.flags["areas_seleccionadas"] = args.areas`

### 4c — Prueba manual de integración

```bash
python run_pipeline.py --areas TI --no-descargar --etapas 2
# → Debe ejecutar etapa 2 sin error, generando Excel con hoja TI y RESUMEN
```

### Verificación

```bash
python -m pytest tests/ -q --tb=no
# → ~557 passed
```

### Commit

```bash
git add run_pipeline.py tests/unit/test_multi_area.py
git commit -m "feat(pipeline): argumento --areas para seleccionar áreas por CLI (PASO 4)"
```

---

## PASO 5 — `lanzador_licitaciones.py`: GUI *(TDD + verificación visual)*

**Precondición:** PASO 4 ✅  
**Estado:** ⬜ Pendiente  
**Markers en código:** `PASO 5.1` a `PASO 5.5` (buscar en `lanzador_licitaciones.py`)

### 5a — Agregar tests a `test_multi_area.py`

```python
# ── Grupo 5: GUI ────────────────────────────────────────
def test_cargar_areas_disponibles_retorna_dict_desde_config()
    # Mock config.AREAS_DISPONIBLES → método crea BooleanVar por área

def test_get_areas_seleccionadas_retorna_lista_de_marcados()
    # vars_areas = {"TI": BooleanVar(True), "HIDRAULICA": BooleanVar(False)}
    # → _get_areas_seleccionadas() == ["TI"]

def test_crear_area_en_pivot_crea_hoja_desde_template()
    # Mock PIVOT → verifica que se llama openpyxl y se copia '06-FILTROS-TEMPLATE'

def test_crear_area_valida_id_vacio()
    # ID vacío → retorna error sin modificar el PIVOT
```

### 5b — Implementar (en este orden)

| N° | Marker | Qué hacer |
|----|--------|-----------|
| 5.1 | `PASO 5.1` | `self.vars_areas: dict[str, tk.BooleanVar] = {}` en `__init__` |
| 5.2 | `PASO 5.2` | Método `_cargar_areas_disponibles()` — llama a `Config().AREAS_DISPONIBLES`, crea BooleanVars |
| 5.3 | `PASO 5.3` | Método `_get_areas_seleccionadas() -> list[str]` |
| 5.4 | `PASO 5.4` | Sección de checkboxes en `setup_ui()` (solo visible si hay 2+ áreas) + botón "➕ Gestionar" |
| 5.5 | `PASO 5.5` | Método `_crear_area_en_pivot()` — `Toplevel` dialog + openpyxl copia plantilla |

### 5c — Verificación visual obligatoria

```bash
python lanzador_licitaciones.py
```

- [ ] Sección "Áreas a analizar" aparece con TI marcado por defecto
- [ ] Botón "➕ Gestionar" presente y funcional
- [ ] El wizard abre sin error
- [ ] "EJECUTAR" lanza el pipeline con `areas=["TI"]` en los flags del contexto

### Verificación

```bash
python -m pytest tests/ -q --tb=no
# → ~561 passed
```

### Commit

```bash
git add lanzador_licitaciones.py tests/unit/test_multi_area.py
git commit -m "feat(gui): checkboxes dinámicos de áreas + asistente nueva área (PASO 5)"
```

---

## PASO 6 — `verificador_entorno.py` *(TDD)*

**Precondición:** PASO 5 ✅  
**Estado:** ⬜ Pendiente  
**Marker en código:** `PASO 6.1` (buscar en `src/utils/verificador_entorno.py`)

### 6a — Agregar tests al archivo existente

En `tests/unit/test_verificador_entorno.py` (archivo ya existente con 21 tests):

```python
def test_check_pivot_falla_si_no_hay_hoja_06_filtros_area()
    # PIVOT existe pero sin '06-FILTROS-TI' → ResultadoCheck.ok == False

def test_check_pivot_ok_con_hoja_06_filtros_ti()
    # PIVOT existe y tiene '06-FILTROS-TI' → ResultadoCheck.ok == True
```

### 6b — Implementar

Ver marker `PASO 6.1` en `src/utils/verificador_entorno.py`:
- En `_check_pivot()`: si el archivo existe, abrir con `openpyxl.load_workbook(read_only=True)` y verificar que haya al menos una hoja `06-FILTROS-*`
- Actualizar `mensaje` para decir qué hoja falta si aplica

### Verificación

```bash
python -m pytest tests/unit/test_verificador_entorno.py -v --tb=short
# → 23 passed (21 base + 2 nuevos)

python -m pytest tests/ -q --tb=no
# → ~563 passed
```

### Commit

```bash
git add src/utils/verificador_entorno.py tests/unit/test_verificador_entorno.py
git commit -m "fix(verificador): validar hojas 06-FILTROS-* en PIVOT multi-área (PASO 6)"
```

---

## PASO 7 — Validación final y merge a master

**Precondición:** PASO 6 ✅ — toda la suite en verde.  
**Estado:** ⬜ Pendiente

### Suite completa con coverage

```bash
python -m pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=xml
```

**Criterios de aceptación:**

- [ ] Tests: ≥ 559 passed, **0 failed, 0 errors**
- [ ] Coverage global `src/`: ≥ 80%
- [ ] Sin nuevos warnings de `pytest`
- [ ] `python lanzador_licitaciones.py` abre sin error

### Merge

```bash
git checkout master
git merge feature/multi-area --no-ff -m "feat: multi-área completo — PIVOT único con hojas por área (Sprint multi-area)"
git push origin master
```

### Verificación post-merge

```bash
git log --oneline -6
python -m pytest tests/ -q --tb=no
# → ≥ 559 passed en master
```

---

## Registro de progreso

Actualizar esta tabla a medida que se completan los pasos.

| PASO | Descripción | Tests antes | Tests (+nuevos) | Commit SHA | Estado |
|------|-------------|-------------|-----------------|------------|--------|
| 1 | Migrar PIVOT | 545 | 545 (sin código) | — | ⬜ |
| 2 | `config.py` AREAS_DISPONIBLES | 545 | +4 | — | ⬜ |
| 3 | `etapa2.py` refactor multi-área | 549 | +6 | — | ⬜ |
| 4 | `run_pipeline.py` `--areas` | 555 | +2 | — | ⬜ |
| 5 | GUI checkboxes + wizard | 557 | +4 | — | ⬜ |
| 6 | `verificador_entorno.py` | 561 | +2 | — | ⬜ |
| 7 | Validación final + merge | 563 | ≥0 | merge | ⬜ |

---

## Referencia rápida de markers en código

Abrir **Todo Tree** en VS Code (`Ctrl+Shift+P` → "Todo Tree: Focus on Tree View") y filtrar por `PASO` para ver todos los puntos de implementación en contexto.

| Tag | Archivo | Descripción |
|-----|---------|-------------|
| `PASO 2.1` | `src/utils/config.py` | Propiedad `AREAS_DISPONIBLES` |
| `PASO 2.2` | `src/utils/config.py` | Actualizar `validar_estructura()` |
| `PASO 3.0` | `src/etapas/etapa2.py` | Cambiar nombre de hoja en `_validar_prerequisitos()` |
| `PASO 3.1` | `src/etapas/etapa2.py` | Extraer `_leer_hoja_filtros()` |
| `PASO 3.2` | `src/etapas/etapa2.py` | Añadir `_cargar_filtros_globales()` |
| `PASO 3.3` | `src/etapas/etapa2.py` | Modificar `_cargar_filtros(area)` |
| `PASO 3.4` | `src/etapas/etapa2.py` | Loop por áreas en `run()` |
| `PASO 3.5` | `src/etapas/etapa2.py` | Multi-hoja en `_generar_outputs()` |
| `PASO 4.1` | `run_pipeline.py` | Argumento `--areas` en argparse |
| `PASO 5.1` | `lanzador_licitaciones.py` | Atributo `vars_areas` |
| `PASO 5.2` | `lanzador_licitaciones.py` | Método `_cargar_areas_disponibles()` |
| `PASO 5.3` | `lanzador_licitaciones.py` | Método `_get_areas_seleccionadas()` |
| `PASO 5.4` | `lanzador_licitaciones.py` | UI checkboxes en `setup_ui()` |
| `PASO 5.5` | `lanzador_licitaciones.py` | Wizard `_crear_area_en_pivot()` |
| `PASO 6.1` | `src/utils/verificador_entorno.py` | Verificar hojas `06-FILTROS-*` |
