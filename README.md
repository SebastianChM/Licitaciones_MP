# Licitaciones Mercado Público

> Sistema automatizado que filtra y enriquece las licitaciones publicadas en el Mercado Público de Chile, reduciendo aproximadamente 12 000 licitaciones diarias a las 300 relevantes para Sebastian Chirino.

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Tests 501 passing](https://img.shields.io/badge/tests-501%20passing-22C55E?style=for-the-badge)](#tests)
[![Coverage 95%](https://img.shields.io/badge/coverage-95%25-22C55E?style=for-the-badge)](#tests)
[![Version v6.0.0](https://img.shields.io/badge/version-v6.0.0-3776AB?style=for-the-badge)](#)
[![License Proprietary](https://img.shields.io/badge/license-proprietary-A8C95A?style=for-the-badge)](#licencia)

**Plataforma:** Windows 10 / 11 con interfaz gráfica
**Última versión:** v6.0.0

---

## Qué hace

El sistema descarga cada día el listado completo de licitaciones publicadas en el Mercado Público de Chile (alrededor de 12 000 registros), aplica un pipeline de filtrado en tres fases para quedarse con los 300 contratos potencialmente relevantes para MP, enriquece esos registros con datos detallados desde la API oficial, y genera un reporte Excel ejecutivo con conversión automática de moneda (CLP, UTM, USD) y un análisis incremental que distingue qué licitaciones son nuevas respecto al histórico.

El sistema reemplaza un proceso manual que tomaba varias horas al día del equipo comercial y que era propenso a perder oportunidades por fatiga. Hoy cada ejecución del pipeline completo termina en aproximadamente cuatro minutos.

Está pensado para ser usado por personas no técnicas: tiene una interfaz gráfica con panel de estado, botones explícitos y un sistema de configuración por planilla Excel. Los filtros se ajustan editando un único archivo `PIVOT_MAESTRO.xlsx` sin tocar código.

## Arquitectura

```
+------------------------------------------------------+
|   Interfaz gráfica (Tkinter / customtkinter)         |
|   - Panel de estado del entorno                      |
|   - Botones: pipeline completo / solo incremental    |
+----------------------+-------------------------------+
                       |
                       v
+----------------------+-------------------------------+
|   Orquestador (run_pipeline.py)                      |
|   - Resuelve qué etapas correr                       |
|   - Mantiene PipelineContext compartido              |
+----------------------+-------------------------------+
                       |
       +---------------+----------------+
       |                                |
       v                                v
+------+-------+ +---+--------+ +-------+----+ +--------+---+ +---------+--+ +---------+
| 0. Descarga  | | 1. Audit.  | | 2. Filtrado | | 3. Enriq.  | | 4. Reporte | | 5. Inc. |
| API MP       | | Taxonomía  | | 3 fases     | | API MP     | | Excel      | | Histor. |
+--------------+ +------------+ +-------------+ +------------+ +------------+ +---------+
       |                                                                          |
       v                                                                          v
+------+-----+                                                            +-------+----+
| 1. INPUT/  |                                                            | 5. PRES./  |
| Excel raw  |                                                            | Reporte    |
+------------+                                                            +------------+
```

Cada etapa hereda `BaseStage` (`src/core/contracts.py`) y se comunica con las demás a través de `PipelineContext` (`src/core/context.py`), lo cual desacopla la lógica de cada etapa del orquestador.

## Las 6 etapas del pipeline

| # | Nombre | Qué hace | Entrada → Salida |
|---|---|---|---|
| 0 | Descarga | Obtiene el Excel diario con todas las licitaciones publicadas | API Mercado Público → `1. INPUT/Licitacion_Publicada.xlsx` |
| 1 | Auditoría | Detecta valores de taxonomía nuevos no contemplados en el pivot | Publicada.xlsx → `2. HALLAZGOS/HALLAZGOS_*.xlsx` |
| 2 | Filtrado | Reduce 12 000 licitaciones a 300 relevantes en tres fases | Publicada.xlsx → `3. FILTRADO/Filtradas_*.xlsx` |
| 3 | Enriquecimiento | Consulta la API por cada licitación filtrada y trae los detalles | Filtradas.xlsx → `4. ENRIQUECIDO/Enriquecidas_*.xlsx` |
| 4 | Reporte | Genera el Excel ejecutivo con formato, colores y conversión de moneda | Enriquecidas.xlsx → `5. PRESENTACION/ORIGINALES/Reporte_*.xlsx` |
| 5 | Incremental | Compara con el histórico y aísla solo las licitaciones nuevas | Reporte.xlsx → `5. PRESENTACION/INCREMENTALES/Incremental_*.xlsx` |

## Cómo funciona el filtrado

La etapa 2 es el núcleo del sistema. Aplica tres fases sucesivas sobre las 12 000 licitaciones publicadas:

```
12 000 licitaciones
        |
        v   FASE 1 - INCLUSIÓN
        |   ¿El nombre o categoría contiene alguna palabra clave de inclusión?
        |   (software, consultoría, sistema, BIM, etc.)
        |
        v   ~600 licitaciones pasan
        |
        v   FASE 2 - EXCLUSIÓN
        |   ¿El nombre, organismo o descripción contiene una palabra de exclusión?
        |   (pavimentación, medicamentos, alimentación, etc.)
        |
        v   ~200 candidatas pasan a la fase de bypass
        |
        v   FASE 3 - BYPASS
        |   ¿Algún campo contiene una palabra de bypass?
        |   (ITO, AIF, MP, etc.)
        |   Si sí, la licitación se recupera aunque la exclusión la haya bloqueado.
        |
        v   ~300 licitaciones finales
```

Los tres conjuntos de palabras clave se configuran en `config_pivot/PIVOT_MAESTRO.xlsx`, hoja `06-FILTROS`. **No se necesita tocar el código para ajustar los filtros.**

## Tech stack

| Capa | Herramienta |
|---|---|
| Lenguaje | Python 3.11+ |
| Procesamiento de datos | pandas |
| Excel I/O | openpyxl |
| HTTP | requests |
| Configuración | pydantic-settings + python-dotenv |
| Interfaz gráfica | customtkinter (Tkinter modernizado) |
| Empaquetado | setuptools |
| Lint | ruff con reglas E, F, I, UP, B, SIM, DTZ, RUF, C4, PTH, PERF, S, TCH, ANN |
| Type checking | pyright (basic) |
| Tests | pytest con marcadores unit / integration / slow |
| Cobertura | coverage con gate al 90% |
| Calidad de commits | pre-commit |

## Instalación

### Opción A — instalación automática (recomendada)

1. Abrir la carpeta del proyecto en el Explorador de Windows.
2. Doble clic en `instalar.bat`.
3. Seguir las instrucciones en pantalla.

El script verifica que Python esté instalado, crea el entorno virtual `.venv`, instala todas las dependencias y crea el archivo `.env` desde la plantilla.

### Opción B — instalación manual

```bash
cd C:\Licitaciones_MP

python -m venv .venv
.venv\Scripts\activate

pip install -e ".[dev]"

copy .env.example .env
```

## Configuración

Editar el archivo `.env` con un editor de texto y rellenar las credenciales:

```env
# API Key de Mercado Público — necesaria para la etapa 3 (enriquecimiento)
LICIT_MERCADO_PUBLICO_TICKET=...

# API Key del SIF de CMF Chile — necesaria para el valor UTM actualizado
LICIT_CMF_API_KEY=...
```

El sistema funciona sin estas claves, pero la etapa 3 opera con límites reducidos y la etapa 4 cae al valor UTM estático.

### Variables opcionales

| Variable | Valor por defecto | Descripción |
|---|---|---|
| `LICIT_LOG_LEVEL` | `INFO` | Nivel de log (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `LICIT_ETAPA2_MIN_AMOUNT` | `1000000` | Monto mínimo en CLP para incluir una licitación |
| `LICIT_ETAPA3_DELAY_SEGUNDOS` | `1.5` | Pausa entre llamadas a la API |
| `LICIT_ETAPA3_MAX_REINTENTOS` | `3` | Reintentos por llamada fallida |
| `LICIT_ETAPA4_VALOR_UTM` | `65000` | Valor UTM en CLP de respaldo |
| `LICIT_TEST_MODE` | `false` | Si `true`, limita a 100 registros para pruebas |

## Uso diario

### Interfaz gráfica

Doble clic en `Lanzador_MP.bat` desde la carpeta del proyecto.

La ventana muestra un panel de estado del entorno que verifica automáticamente:

- Entorno virtual presente
- `PIVOT_MAESTRO.xlsx` accesible
- API keys configuradas
- Archivo de entrada disponible

Cuando el panel está en verde aparecen tres botones principales:

- **Ejecutar pipeline completo** — corre las seis etapas en orden, ~4 minutos.
- **Solo análisis incremental** — corre solo la etapa 5 sobre el reporte del día, ~15 segundos.
- **Abrir carpeta de resultados** — atajo al directorio de presentación.

### Línea de comandos

Para usuarios técnicos:

```bash
cd C:\Licitaciones_MP
.venv\Scripts\activate

# Pipeline completo
python run_pipeline.py

# Solo ciertas etapas
python run_pipeline.py --etapas 2 3 4

# Sin descargar (usa el archivo que ya está en data/1. INPUT/)
python run_pipeline.py --no-descargar

# Archivo de entrada alternativo
python run_pipeline.py --archivo "C:\ruta\alternativa.xlsx"

# Solo etapa 5
python run_pipeline.py --etapas 5

# Ayuda
python run_pipeline.py --help
```

## Estructura del proyecto

```
Licitaciones_MP/
├── instalar.bat                       # Instalación inicial (correr una vez)
├── Lanzador_MP.bat                  # Abre la interfaz gráfica
├── lanzador_licitaciones.py           # Código de la interfaz (Tkinter)
├── run_pipeline.py                    # Orquestador CLI
├── pyproject.toml
├── .env.example
│
├── config_pivot/
│   └── PIVOT_MAESTRO.xlsx             # Configuración de filtros editable
│
├── src/
│   ├── core/
│   │   ├── contracts.py               # BaseStage, StageResult
│   │   └── context.py                 # PipelineContext compartido
│   ├── etapas/
│   │   ├── etapa0.py                  # Descarga
│   │   ├── etapa1.py                  # Auditoría de taxonomía
│   │   ├── etapa2.py                  # Filtrado en 3 fases
│   │   ├── etapa3.py                  # Enriquecimiento por API
│   │   ├── etapa4.py                  # Reporte ejecutivo
│   │   └── etapa5.py                  # Análisis incremental
│   └── utils/
│       ├── config.py                  # Configuración centralizada
│       ├── logger.py                  # Logging estructurado
│       ├── file_ops.py                # Lectura y escritura de Excel
│       ├── text_processing.py         # Normalización y búsqueda de texto
│       ├── analizador_incremental.py  # Detección de cambios
│       └── verificador_entorno.py     # Checks del panel de estado
│
├── data/
│   ├── 1. INPUT/                      # Excel descargado por la etapa 0
│   └── 2. OUTPUT/
│       ├── 1. LOGS/                   # Registro por ejecución
│       ├── 2. HALLAZGOS/              # Taxonomía nueva detectada
│       ├── 2. HISTORICO/              # Histórico de ejecuciones
│       ├── 3. FILTRADO/               # Salida de la etapa 2
│       ├── 4. ENRIQUECIDO/            # Salida de la etapa 3
│       └── 5. PRESENTACION/
│           ├── ORIGINALES/            # Reporte completo del día
│           └── INCREMENTALES/         # Solo lo nuevo
│
└── tests/                             # 501 tests (unit, integration, slow)
```

## Configuración de filtros — `PIVOT_MAESTRO.xlsx`

El archivo `config_pivot/PIVOT_MAESTRO.xlsx` es el panel de control del sistema. Se edita directamente en Excel sin tocar código.

### Hojas principales

| Hoja | Descripción |
|---|---|
| `02-CONFIG` | Parámetros del sistema (valor UTM, API key alternativa) |
| `04-BASE` | Tabla maestra de taxonomía de Mercado Público |
| `06-FILTROS` | Palabras clave de inclusión, exclusión y bypass |

### Estructura de `06-FILTROS`

Encabezados en la fila 5, datos desde la fila 6:

| Columna | Contenido | Cuándo usar |
|---|---|---|
| A | Inclusión por nombre | Palabras que deben aparecer en el nombre |
| B–D | Inclusión por nivel 1, 2, 3 | Categorías de taxonomía a incluir |
| E | Exclusión por nombre | Palabras en el nombre que descartan |
| F–L | Exclusión por nivel, organismo, tipo | Exclusión por otros campos |
| M | Bypass | Palabras que rescatan licitaciones excluidas |

### Cómo modificar los filtros

1. Abrir `config_pivot/PIVOT_MAESTRO.xlsx` en Excel.
2. Ir a la hoja `06-FILTROS`.
3. Agregar o quitar palabras en la columna correspondiente.
4. Guardar.
5. La próxima ejecución usa los cambios automáticamente.

Las palabras no distinguen mayúsculas ni acentos. "Consultoría", "consultoria" y "CONSULTORIA" se consideran equivalentes.

## Archivos de salida

Tras el pipeline completo, en `data/2. OUTPUT/5. PRESENTACION/`:

```
ORIGINALES/
  Reporte_20260323_143022.xlsx
    [Hoja] Licitaciones    300 licitaciones filtradas y enriquecidas
    [Hoja] Resumen         métricas y estadísticas del proceso

INCREMENTALES/
  Incremental_20260323_143022.xlsx
    [Hoja] Nuevas          licitaciones que no estaban en el reporte anterior
```

Para cada licitación el reporte incluye código, nombre, organismo, monto en CLP (con conversión desde UTM o USD), días al cierre, fecha de cierre, estado, región, tipo, categoría y descripción del servicio.

## Tests

El proyecto tiene **501 tests automatizados** con un gate de cobertura del 90%.

```bash
cd C:\Licitaciones_MP
.venv\Scripts\activate

# Suite completa
python -m pytest tests/ -v

# Con reporte de cobertura
python -m pytest tests/ -v --cov=src --cov-report=term-missing

# Tests de una etapa específica
python -m pytest tests/unit/test_etapa2_cobertura.py -v

# Tests de calidad del filtrado
python -m pytest tests/unit/test_calidad_filtrado.py -v
```

Los tests están organizados con marcadores: `unit` (sin I/O), `integration` (con archivos reales) y `slow` (más de 5 segundos).

## Solución de problemas

### El botón Ejecutar está deshabilitado

El panel de estado indica la causa. Casos típicos:

- **Entorno virtual no encontrado** → correr `instalar.bat` de nuevo.
- **PIVOT_MAESTRO.xlsx no encontrado** → verificar que existe `config_pivot/PIVOT_MAESTRO.xlsx`.
- **Archivo de entrada no encontrado** → ejecutar primero el pipeline completo para que la etapa 0 descargue el archivo, o copiar manualmente `Licitacion_Publicada.xlsx` a `data/1. INPUT/`.

### Python no está en el PATH

1. Descargar Python desde [python.org/downloads](https://www.python.org/downloads/).
2. Durante la instalación marcar **"Add Python to PATH"**.
3. Reiniciar la terminal y reintentar.

### La etapa 3 tarda o da errores

La API de Mercado Público tiene límites de velocidad e inestabilidad en horario pico. El sistema reintenta tres veces por registro y mantiene checkpoints para reanudar sin perder progreso. Ejecutar en madrugada o fin de semana reduce los errores.

### Resultados inesperados en el filtrado

El filtrado se controla por el `PIVOT_MAESTRO.xlsx`:

- **Demasiadas irrelevantes** → agregar palabras en las exclusiones (columnas E–L).
- **Faltan relevantes** → agregar palabras en inclusión (col A) o bypass (col M).
- **Una específica que debería aparecer** → identificar qué término la excluye y añadirlo al bypass.

### `ModuleNotFoundError`

Ejecutar siempre desde la raíz del proyecto:

```bash
cd C:\Licitaciones_MP
python run_pipeline.py
```

## Para desarrolladores

### Agregar una etapa nueva

Crear `src/etapas/etapaN.py` heredando `BaseStage`:

```python
from core.contracts import BaseStage, StageResult
from core.context import PipelineContext

class MiEtapa(BaseStage):
    @property
    def name(self) -> str:
        return "mi_etapa"

    def validate_inputs(self, context: PipelineContext) -> bool:
        return True

    def run(self, context: PipelineContext) -> StageResult:
        self.bind(context)
        # lógica de la etapa
        return StageResult(success=True, stage_name=self.name)
```

Y registrarla en `run_pipeline.py` dentro de `_construir_etapas()`.

### Comunicación entre etapas vía artifacts

```python
# Producir un artifact
context.add_artifact("etapa2_output", ruta_archivo)

# Consumirlo en la etapa siguiente
archivo = context.get_artifact("etapa2_output")
```

### Configuración desde código

```python
from utils.config import Config

config = Config()
print(config.PIVOT_MAESTRO)
config.validar_estructura()
```

## Licencia

Propietario. Sebastian Chirino
Copyright (c) 2025–2026 MP. Todos los derechos reservados.
