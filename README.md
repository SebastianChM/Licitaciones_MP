# Licitaciones Mercado Público — Pipeline Automatizado

![CI](https://github.com/MP-Consulting/licitaciones-mp/actions/workflows/ci.yml/badge.svg)
![Coverage](https://codecov.io/gh/MP-Consulting/licitaciones-mp/branch/main/graph/badge.svg)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)
![Version](https://img.shields.io/badge/version-5.0.0-green)

> **Nota:** reemplaza `MP-Consulting/licitaciones-mp` con la ruta real del repositorio en GitHub.

Sistema automatizado para filtrar y enriquecer licitaciones del Mercado Público de Chile, reduciendo ~12 000 licitaciones diarias a ~200 relevantes para Sebastian Chirino.

**Versión**: 5.0.0  
**Última actualización**: Marzo 2026

---

## Inicio rápido

```bash
# 1. Crear y activar entorno virtual
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Copiar la plantilla de variables de entorno y completar los secretos
copy .env.example .env
# Editar .env: agregar LICIT_MERCADO_PUBLICO_TICKET con tu API Key

# 4. Ejecutar el pipeline completo
python run_pipeline.py

# 5. (Uso diario) Solo análisis incremental
python src/sistema_incremental.py

# 6. (Uso diario) Actualizar reporte preservando formato manual
python src/reporte_incremental.py
```

Resultados en `data/2. OUTPUT/5. PRESENTACION/`.

---

## Estructura del proyecto

```
Licitaciones_MP/
├── run_pipeline.py            # Orquestador principal + CLI
├── requirements.txt
├── .env.example               # Plantilla de variables de entorno
│
├── src/
│   ├── core/
│   │   ├── context.py         # PipelineContext — estado compartido entre etapas
│   │   └── contracts.py       # BaseStage, StageResult
│   │
│   ├── etapas/
│   │   ├── etapa0.py          # Descarga automática desde Mercado Público
│   │   ├── etapa1.py          # Auditoría de taxonomía vs PIVOT_MAESTRO
│   │   ├── etapa2.py          # Filtrado inteligente (vectorizado con str.contains)
│   │   ├── etapa3.py          # Enriquecimiento vía API (checkpoint + retry)
│   │   ├── etapa4.py          # Reporte ejecutivo (conversión de monedas)
│   │   └── etapa5.py          # Actualización incremental (preserva formato)
│   │
│   ├── utils/
│   │   ├── config.py          # Configuración pydantic-settings (prefijo LICIT_)
│   │   ├── logger.py          # Sistema de logging con secciones y progreso
│   │   ├── alerts.py          # AlertManager con sinks pluggables (consola + archivo)
│   │   ├── http.py            # HTTPClient con retry/backoff y respeto a Retry-After
│   │   ├── observability.py   # ObservabilityRules + RunSummaryReporter
│   │   ├── analizador_incremental.py  # Detección de cambios y sugerencias de filtros
│   │   ├── text_processing.py # Normalización, similitud, palabras clave
│   │   └── file_ops.py        # Helpers de lectura/escritura de Excel
│   │
│   ├── sistema_incremental.py # Entrada standalone para análisis incremental
│   └── reporte_incremental.py # Entrada standalone para actualización de reportes
│
├── config_pivot/
│   └── PIVOT_MAESTRO.xlsx     # Taxonomía, filtros y parámetros del sistema
│
├── data/
│   ├── 1. INPUT/              # Licitacion_Publicada.xlsx (entrada)
│   └── 2. OUTPUT/
│       ├── 1. LOGS/           # Logs por ejecución
│       ├── 2. HALLAZGOS/      # Nuevos valores detectados por etapa1
│       ├── 2. HISTORICO/      # Reportes históricos
│       ├── 3. FILTRADO/       # Salida de etapa2
│       ├── 4. ENRIQUECIDO/    # Salida de etapa3
│       └── 5. PRESENTACION/   # Reportes finales (etapa4 y etapa5)
│
└── tests/
    └── unit/                  # Tests unitarios (pytest)
```

---

## Las 6 etapas del pipeline

| # | Clase | Descripción | Entrada → Salida |
|---|-------|-------------|------------------|
| 0 | `DescargadorLicitaciones` | Descarga automática desde la API de Mercado Público | API → `INPUT/Licitacion_Publicada.xlsx` |
| 1 | `AuditorTaxonomia` | Detecta valores de taxonomía no contemplados en PIVOT_MAESTRO | Publicada.xlsx → `HALLAZGOS_*.xlsx` |
| 2 | `FiltradorLicitaciones` | Reduce ~12 000 a ~200 usando filtros inclusión/exclusión/bypass vectorizados | Publicada.xlsx → `Filtradas_*.xlsx` |
| 3 | `EnriquecedorAPI` | Consulta la API de Mercado Público (checkpoint automático, retry, rate-limit) | Filtradas.xlsx → `Enriquecidas_*.xlsx` |
| 4 | `GeneradorReporte` | Reporte ejecutivo con conversión UTM/USD→CLP, colores y métricas | Enriquecidas.xlsx → `Reporte_*.xlsx` |
| 5 | `GeneradorReporteIncremental` | Actualiza reporte existente preservando formato y colores manuales | Reporte.xlsx → Reporte actualizado in-place |

Cada etapa hereda `BaseStage` (`src/core/contracts.py`) y se comunica con el resto a través de `PipelineContext` (`src/core/context.py`).

---

## Configuración

### Variables de entorno

La configuración usa `pydantic-settings` con prefijo `LICIT_`. Copia `.env.example` a `.env` y ajusta los valores:

```env
# API Keys (obligatorias para etapa 0 y 3)
LICIT_MERCADO_PUBLICO_TICKET=tu_api_key_aqui

# Límites de filtrado
LICIT_ETAPA2_MIN_AMOUNT=1000000
LICIT_ETAPA2_MAX_AMOUNT=50000000000

# Parámetros API
LICIT_ETAPA3_DELAY_SEGUNDOS=1.5
LICIT_ETAPA3_CHECKPOINT_RETENTION_DAYS=7

# Modo prueba (limita a 100 filas)
LICIT_TEST_MODE=false
```

Consulta `.env.example` para la lista completa documentada.

### PIVOT_MAESTRO.xlsx

La taxonomía y los filtros se gestionan en `config_pivot/PIVOT_MAESTRO.xlsx`:

| Hoja | Contenido |
|------|-----------|
| `01-AUDITORIA` | Referencia para análisis incremental |
| `02-CONFIG` | Parámetros dinámicos (cargados por `cargar_desde_pivot()`) |
| `04-BASE` | Tabla maestra de taxonomía (Nivel 1/2/3, Genérico) |
| `06-FILTROS` | Palabras de inclusión, exclusión y bypass por columna |

Para modificar los filtros sin tocar código: editar la hoja `06-FILTROS` y re-ejecutar el pipeline.

---

## Opciones de ejecución

```bash
# Pipeline completo (todas las etapas)
python run_pipeline.py

# Etapas específicas
python run_pipeline.py --etapas 1 2
python run_pipeline.py --etapas 3 4 5

# Archivo de entrada custom
python run_pipeline.py --archivo "ruta/alternativa.xlsx"

# Sin descarga (usar archivo ya existente)
python run_pipeline.py --no-descargar

# Etapa individual en standalone
python -m src.etapas.etapa2
```

---

## Observabilidad y alertas

Cada ejecución del pipeline genera automáticamente:

- **Log de texto** en `data/2. OUTPUT/1. LOGS/`
- **Resumen JSON** en `temp/logs/runs/run_{uuid}.json` con métricas de cada etapa
- **Archivo de alertas** `temp/logs/alerts_{run_id}.jsonl` con alertas de negocio


Las reglas de negocio evaluadas automáticamente incluyen: tasa de filtrado inusualmente baja, cero registros procesados, errores de API por encima del umbral, entre otras.

---

## Solución de problemas

### Etapa 3 con 0% de éxito — falta API Key
```
# Síntoma: requests fallan con HTTP 500 ("peticiones simultáneas")
# Solución: agregar en .env
LICIT_MERCADO_PUBLICO_TICKET=tu_clave_aqui
```
Obtén la API Key en [mercadopublico.cl](https://www.mercadopublico.cl/Home/Ayuda).

### 10-30% de errores HTTP 500 en etapa 3 (con API Key configurada)
Esto es comportamiento normal de la API de Mercado Público. El sistema reintenta automáticamente 3 veces con backoff. Ejecutar en horarios de baja demanda (madrugada, fines de semana) mejora la tasa de éxito.

### `ModuleNotFoundError: No module named 'utils'`
Ejecutar desde la raíz del proyecto:
```bash
cd C:\Licitaciones_MP
python run_pipeline.py
```

### `FileNotFoundError: PIVOT_MAESTRO.xlsx`
```bash
python -c "from src.utils.config import Config; c = Config(); print(c.PIVOT_MAESTRO)"
```

---

## Tests

```bash
# Todos los tests
pytest tests/ -v

# Con cobertura (umbral mínimo: 80%)
pytest tests/ -v --cov=src --cov-report=term-missing --cov-fail-under=80

# Solo un módulo
pytest tests/unit/test_text_processing.py -v
```

**Cobertura actual: 81%** (339 tests en verde)

---

## Métricas de rendimiento (referencia)

| Etapa | Tiempo estimado | Observaciones |
|-------|----------------|---------------|
| 0 — Descarga | ~30 s | Depende de la red |
| 1 — Auditoría | ~5 s | Para 12 000 registros |
| 2 — Filtrado | ~3 s | Vectorizado con `str.contains` |
| 3 — Enriquecimiento | ~3 min | 200 licitaciones × 1.5 s/req |
| 4 — Reporte | ~5 s | |
| 5 — Incremental | ~10 s | Solo diff sobre reporte existente |
| **Total** | **~4 min** | |

---

## Para desarrolladores

### Añadir una etapa nueva

1. Crear `src/etapas/etapaN.py` heredando `BaseStage`:
   ```python
   from core.contracts import BaseStage, StageResult
   from core.context import PipelineContext

   class MiEtapa(BaseStage):
       @property
       def name(self) -> str:
           return "mi_etapa"

       def validate_inputs(self, context: PipelineContext) -> bool:
           ...

       def run(self, context: PipelineContext) -> StageResult:
           self.bind(context)
           ...
   ```
2. Registrar en `run_pipeline.py` en el método `_construir_etapas()`.

### Agregar una regla de observabilidad

Editar `src/utils/observability.py` añadiendo un método en `ObservabilityRules` con la firma:
```python
def check_mi_regla(self, metrics: dict) -> Optional[Alert]:
```

---

## Licencia

Propietario — Sebastian Chirino  
© 2025 Todos los derechos reservados
