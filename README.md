# Licitaciones Mercado Público — Sistema MP

![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)
![Tests](https://img.shields.io/badge/tests-545%20passing-brightgreen)
![Version](https://img.shields.io/badge/versión-Sprint--13-blue)

Sistema automatizado para filtrar y enriquecer licitaciones del Mercado Público de Chile, reduciendo ~12 000 licitaciones publicadas a ~300 relevantes para Sebastian Chirino.

**Versión:** Sprint-13
**Última actualización:** Marzo 2026
**Plataforma:** Windows (con interfaz gráfica visual)

---

## Índice

1. [Requisitos previos](#1-requisitos-previos)
2. [Instalación — primera vez](#2-instalación--primera-vez)
3. [Configuración de credenciales](#3-configuración-de-credenciales)
4. [Uso diario — interfaz gráfica](#4-uso-diario--interfaz-gráfica)
5. [Uso avanzado — línea de comandos](#5-uso-avanzado--línea-de-comandos)
6. [Estructura del proyecto](#6-estructura-del-proyecto)
7. [Las 6 etapas del pipeline](#7-las-6-etapas-del-pipeline)
8. [Cómo funciona el filtrado](#8-cómo-funciona-el-filtrado)
9. [Archivos de salida](#9-archivos-de-salida)
10. [PIVOT_MAESTRO.xlsx — configuración de filtros](#10-pivot_maestroxlsx--configuración-de-filtros)
11. [Variables de entorno](#11-variables-de-entorno)
12. [Tests](#12-tests)
13. [Solución de problemas](#13-solución-de-problemas)
14. [Para desarrolladores](#14-para-desarrolladores)

---

## 1. Requisitos previos

| Requisito | Versión mínima | Cómo verificar |
|-----------|---------------|----------------|
| Windows | 10 / 11 | — |
| Python | 3.11 | `python --version` en la terminal |
| Conexión a Internet | — | Para descarga de licitaciones y API |

> **¿Python no instalado?** Descárgalo desde [python.org/downloads](https://www.python.org/downloads/).
> Durante la instalación marca obligatoriamente **"Add Python to PATH"**.

---

## 2. Instalación — primera vez

Este paso solo se hace **una única vez** al configurar el sistema en una máquina nueva.

### Opción A — Instalación automática (recomendada)

1. Abre la carpeta del proyecto en el Explorador de Windows
2. Haz doble clic en **`instalar.bat`**
3. Sigue las instrucciones en pantalla

El script hace automáticamente:
- Verifica que Python esté instalado
- Crea el entorno virtual `.venv` con todas las dependencias
- Crea el archivo `.env` desde la plantilla `.env.example`

Al terminar verás:
```
[OK] Instalacion completada con exito.
Ahora edita el archivo .env con tus credenciales y ejecuta Lanzador_MP.bat
```

### Opción B — Instalación manual

```bash
# 1. Abrir una terminal en la carpeta del proyecto
cd C:\Licitaciones_MP

# 2. Crear entorno virtual
python -m venv .venv

# 3. Activar el entorno virtual
.venv\Scripts\activate

# 4. Instalar dependencias
pip install -r requirements.txt

# 5. Crear archivo de configuración
copy .env.example .env
```

---

## 3. Configuración de credenciales

Después de instalar, abre el archivo **`.env`** con cualquier editor de texto (Bloc de notas, VS Code, etc.) y rellena las credenciales necesarias:

```env
# API Key de Mercado Público — necesaria para enriquecer los datos (Etapa 3)
# Solicitar en: https://api.mercadopublico.cl/
LICIT_MERCADO_PUBLICO_TICKET=pega_tu_clave_aqui

# API Key del SIF de CMF Chile — necesaria para obtener el valor UTM actual (Etapa 4)
# Registro gratuito en: https://api.cmfchile.cl/
LICIT_CMF_API_KEY=pega_tu_clave_aqui
```

> **Sin estas claves el sistema igual funciona**, pero la Etapa 3 usará límites de tasa reducidos y la Etapa 4 usará un valor UTM estático en lugar del valor actualizado.

El resto de las variables en `.env` tienen valores por defecto correctos y **no necesitan modificarse** para el uso normal.

---

## 4. Uso diario — interfaz gráfica

### Iniciar la aplicación

Haz doble clic en **`Lanzador_MP.bat`** en la carpeta del proyecto.

Se abre una ventana como esta:

```
┌─────────────────────────────────────────────────────┐
│  🏛️ MP CONSULTING                                  │
│  Sistema de Licitaciones Mercado Público             │
├─────────────────────────────────────────────────────┤
│  Estado del entorno:                                │
│  ✅ Entorno virtual (.venv): OK                     │
│  ✅ PIVOT_MAESTRO.xlsx: OK                          │
│  ✅ API Key: Configurada                            │
│  ✅ Archivo de entrada: Encontrado                  │
│                              [🔄 Re-verificar]      │
├─────────────────────────────────────────────────────┤
│  [ 🚀 EJECUTAR PIPELINE COMPLETO                  ] │
│  [ 📊 SOLO ANÁLISIS INCREMENTAL                   ] │
│  [ 📂 Abrir carpeta de resultados                 ] │
├─────────────────────────────────────────────────────┤
│  Estado: ✅ Sistema listo para ejecutar             │
│  Log de ejecución:                                  │
│  [10:23:01] 🎯 Sistema iniciado                    │
└─────────────────────────────────────────────────────┘
```

### Panel de estado del entorno

Al abrir la app, verifica automáticamente que todo esté correctamente configurado:

| Indicador | Qué significa |
|-----------|--------------|
| ✅ verde | Todo correcto |
| ⚠️ amarillo | Advertencia — el sistema puede funcionar pero algo no está óptimo |
| ❌ rojo | Error crítico — los botones de ejecución estarán deshabilitados hasta resolverlo |

### Botones principales

#### 🚀 EJECUTAR PIPELINE COMPLETO

Ejecuta las 6 etapas en orden:
1. Descarga las licitaciones actuales desde Mercado Público
2. Audita la taxonomía
3. **Filtra** las ~12.000 licitaciones a ~300 relevantes
4. Enriquece con datos detallados de la API
5. Genera el reporte ejecutivo Excel
6. Actualiza el análisis incremental (novedades respecto al histórico)

**Tiempo estimado:** ~4 minutos con buena conexión a Internet.

El resultado queda en:
```
data/
  2. OUTPUT/
    5. PRESENTACION/
      ORIGINALES/       ← Reporte completo del día
      INCREMENTALES/    ← Solo lo nuevo respecto a la semana anterior
```

#### 📊 SOLO ANÁLISIS INCREMENTAL

Ejecuta únicamente la Etapa 5. Útil si ya tienes el reporte del día y quieres ver solo qué licitaciones son nuevas respecto al histórico.

**Tiempo estimado:** ~15 segundos.

#### 📂 Abrir carpeta de resultados

Abre directamente la carpeta `data/2. OUTPUT/5. PRESENTACION/` en el Explorador de Windows.

---

## 5. Uso avanzado — línea de comandos

Para usuarios con conocimientos técnicos que prefieren la terminal:

```bash
# Activar entorno virtual
cd C:\Licitaciones_MP
.venv\Scripts\activate

# Pipeline completo
python run_pipeline.py

# Solo etapas específicas (por número)
python run_pipeline.py --etapas 2 3 4

# Sin descargar (usar el archivo existente en data/1. INPUT/)
python run_pipeline.py --no-descargar

# Archivo de entrada alternativo
python run_pipeline.py --archivo "C:\ruta\alternativa.xlsx"

# Solo etapa 5 (incremental)
python run_pipeline.py --etapas 5

# Ver todas las opciones disponibles
python run_pipeline.py --help
```

---

## 6. Estructura del proyecto

```
C:\Licitaciones_MP\
│
├── instalar.bat               ← Instalación inicial (ejecutar una vez)
├── Lanzador_MP.bat          ← Abre la interfaz gráfica (uso diario)
├── lanzador_licitaciones.py   ← Código de la interfaz gráfica (Tkinter)
├── run_pipeline.py            ← Orquestador del pipeline (CLI)
├── requirements.txt           ← Dependencias Python
├── .env.example               ← Plantilla de credenciales
├── .env                       ← Tus credenciales (no subir a Git)
│
├── config_pivot/
│   └── PIVOT_MAESTRO.xlsx     ← Configuración de filtros (editable)
│
├── src/
│   ├── core/
│   │   ├── context.py         ← Estado compartido entre etapas
│   │   └── contracts.py       ← Clases base BaseStage, StageResult
│   │
│   ├── etapas/
│   │   ├── etapa0.py          ← Descarga desde Mercado Público
│   │   ├── etapa1.py          ← Auditoría de taxonomía
│   │   ├── etapa2.py          ← Filtrado inteligente
│   │   ├── etapa3.py          ← Enriquecimiento vía API
│   │   ├── etapa4.py          ← Generación del reporte
│   │   └── etapa5.py          ← Análisis incremental
│   │
│   └── utils/
│       ├── config.py          ← Configuración centralizada
│       ├── logger.py          ← Sistema de logging
│       ├── file_ops.py        ← Lectura/escritura de Excel
│       ├── text_processing.py ← Normalización y búsqueda de texto
│       ├── analizador_incremental.py ← Detección de cambios
│       └── verificador_entorno.py    ← Checks del panel de estado
│
├── data/
│   ├── 1. INPUT/
│   │   └── Licitacion_Publicada.xlsx  ← Archivo de entrada (generado por Etapa 0)
│   └── 2. OUTPUT/
│       ├── 1. LOGS/           ← Registro de cada ejecución
│       ├── 2. HALLAZGOS/      ← Taxonomía nueva detectada (Etapa 1)
│       ├── 2. HISTORICO/      ← Histórico de ejecuciones anteriores
│       ├── 3. FILTRADO/       ← Resultado del filtrado (Etapa 2)
│       ├── 4. ENRIQUECIDO/    ← Datos enriquecidos con API (Etapa 3)
│       └── 5. PRESENTACION/   ← Reportes finales para usuarios
│           ├── ORIGINALES/
│           └── INCREMENTALES/
│
└── tests/                     ← 545 tests automatizados
```

---

## 7. Las 6 etapas del pipeline

| # | Nombre | Qué hace | Entrada → Salida |
|---|--------|----------|-----------------|
| 0 | Descarga | Descarga el Excel con todas las licitaciones publicadas hoy | API Mercado Público → `1. INPUT/Licitacion_Publicada.xlsx` |
| 1 | Auditoría | Detecta valores de taxonomía nuevos no contemplados en el PIVOT | Publicada.xlsx → `2. HALLAZGOS/HALLAZGOS_*.xlsx` |
| 2 | Filtrado | Reduce ~12.000 licitaciones a ~300 relevantes usando 3 fases | Publicada.xlsx → `3. FILTRADO/Filtradas_*.xlsx` |
| 3 | Enriquecimiento | Consulta la API para obtener datos detallados de cada licitación filtrada | Filtradas.xlsx → `4. ENRIQUECIDO/Enriquecidas_*.xlsx` |
| 4 | Reporte | Genera el Excel ejecutivo final con formato, colores y conversiones de moneda | Enriquecidas.xlsx → `5. PRESENTACION/ORIGINALES/Reporte_*.xlsx` |
| 5 | Incremental | Compara con el histórico y detecta solo las licitaciones nuevas | Reporte.xlsx → `5. PRESENTACION/INCREMENTALES/Incremental_*.xlsx` |

Cada etapa hereda `BaseStage` (`src/core/contracts.py`) y se comunica con el resto a través de `PipelineContext` (`src/core/context.py`).

---

## 8. Cómo funciona el filtrado

La Etapa 2 es el núcleo del sistema. Aplica 3 fases en secuencia sobre las ~12.000 licitaciones publicadas:

```
~12.000 licitaciones
        │
        ▼  FASE 1 — INCLUSIÓN
        │  ¿El nombre o categoría contiene alguna palabra clave de inclusión?
        │  Solo pasan las que SÍ coinciden (ej: "software", "consultoría", "sistema")
        │
        ▼  ~600 licitaciones pasan
        │
        ▼  FASE 2 — EXCLUSIÓN
        │  ¿El nombre, organismo o descripción contiene una palabra de exclusión?
        │  Se eliminan las que SÍ coinciden (ej: "pavimentación", "medicamentos")
        │
        ▼  ~200 descartadas pero recuperables por bypass
        │
        ▼  FASE 3 — BYPASS
        │  ¿Algún campo contiene una palabra de bypass? (ej: "ITO", "AIF", "MP")
        │  Si sí → se recupera aunque la exclusión la hubiera bloqueado
        │
        ▼  ~300 licitaciones finales
```

Los tres conjuntos de palabras clave se configuran en `config_pivot/PIVOT_MAESTRO.xlsx`, hoja `06-FILTROS`. **No se necesita tocar el código para ajustar los filtros.**

---

## 9. Archivos de salida

Después de ejecutar el pipeline completo encontrarás en `data/2. OUTPUT/5. PRESENTACION/`:

```
ORIGINALES/
  └── Reporte_20260323_143022.xlsx    ← Reporte completo del día
        ├── [Hoja] Licitaciones       ← ~300 licitaciones filtradas y enriquecidas
        └── [Hoja] Resumen            ← Métricas y estadísticas del proceso

INCREMENTALES/
  └── Incremental_20260323_143022.xlsx  ← Solo las licitaciones nuevas
        └── [Hoja] Nuevas             ← Lo que no existía en el reporte anterior
```

El reporte incluye para cada licitación:
- Código, nombre y organismo
- Monto en CLP (con conversión automática desde UTM/USD si aplica)
- Días para el cierre y fecha exacta de cierre
- Estado, región, tipo y categoría
- Descripción del servicio

---

## 10. PIVOT_MAESTRO.xlsx — configuración de filtros

El archivo `config_pivot/PIVOT_MAESTRO.xlsx` es la configuración del sistema. Se puede editar directamente en Excel **sin tocar ningún archivo de código**.

### Hojas principales

| Hoja | Descripción |
|------|-------------|
| `02-CONFIG` | Parámetros del sistema (valor UTM, API key como alternativa al `.env`) |
| `04-BASE` | Tabla maestra de taxonomía de Mercado Público (referencia) |
| `06-FILTROS` | **La más importante** — palabras clave de inclusión, exclusión y bypass |

### Estructura de la hoja `06-FILTROS`

La hoja tiene encabezados en la **fila 5**. Los datos empiezan en la **fila 6**:

| Columna | Contenido | Cuándo usar |
|---------|-----------|-------------|
| A | Inclusión — NOMBRE | Palabras que deben aparecer en el nombre de la licitación |
| B | Inclusión — NIVEL1 | Categorías de nivel 1 que incluir |
| C | Inclusión — NIVEL2 | Categorías de nivel 2 que incluir |
| D | Inclusión — NIVEL3 | Categorías de nivel 3 que incluir |
| E | Exclusión — NOMBRE | Palabras en el nombre que causan descarte |
| F–L | Exclusión — otros campos | Exclusión por nivel, genérico, organismo, tipo |
| M | BYPASS | Palabras que recuperan una licitación aunque haya sido excluida |

### Cómo agregar o quitar palabras clave

1. Abre `config_pivot/PIVOT_MAESTRO.xlsx` en Excel
2. Ve a la hoja `06-FILTROS`
3. Agrega o elimina palabras en la columna correspondiente
4. Guarda el archivo
5. La próxima ejecución del pipeline usará los cambios automáticamente

> **Tip:** Las palabras clave no distinguen mayúsculas/minúsculas ni acentos. "Consultoría", "consultoria" y "CONSULTORIA" son equivalentes.

---

## 11. Variables de entorno

El archivo `.env` en la raíz del proyecto controla el comportamiento del sistema. Es creado automáticamente por `instalar.bat` a partir de `.env.example`.

### Variables obligatorias para funcionalidad completa

| Variable | Descripción | Dónde obtenerla |
|----------|-------------|-----------------|
| `LICIT_MERCADO_PUBLICO_TICKET` | API Key de Mercado Público | [api.mercadopublico.cl](https://api.mercadopublico.cl/) |
| `LICIT_CMF_API_KEY` | API Key del SIF de CMF | [api.cmfchile.cl](https://api.cmfchile.cl/) |

### Variables opcionales (ya tienen valores por defecto)

| Variable | Valor por defecto | Descripción |
|----------|------------------|-------------|
| `LICIT_LOG_LEVEL` | `INFO` | Nivel de detalle del log (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `LICIT_ETAPA2_MIN_AMOUNT` | `1000000` | Monto mínimo en CLP para incluir una licitación |
| `LICIT_ETAPA3_DELAY_SEGUNDOS` | `1.5` | Segundos de espera entre llamadas a la API |
| `LICIT_ETAPA3_MAX_REINTENTOS` | `3` | Reintentos por llamada fallida |
| `LICIT_ETAPA4_VALOR_UTM` | `65000` | Valor UTM en CLP (fallback si la API de CMF no responde) |
| `LICIT_TEST_MODE` | `false` | Si `true`, limita el procesamiento a 100 registros |

---

## 12. Tests

El proyecto tiene **545 tests automatizados** que verifican el correcto funcionamiento de cada componente.

```bash
# Activar entorno virtual primero
cd C:\Licitaciones_MP
.venv\Scripts\activate

# Ejecutar todos los tests
python -m pytest tests/ -v

# Ejecutar con reporte de cobertura de código
python -m pytest tests/ -v --cov=src --cov-report=term-missing

# Ejecutar solo los tests de una etapa específica
python -m pytest tests/unit/test_etapa2_cobertura.py -v

# Ejecutar solo tests de calidad del filtrado
python -m pytest tests/unit/test_calidad_filtrado.py -v
```

---

## 13. Solución de problemas

### El botón "Ejecutar" está deshabilitado (❌ rojo en el panel)

Revisa qué dice el panel de estado. Los errores más comunes:

**❌ Entorno virtual (.venv) no encontrado**
```
Solución: Ejecutar instalar.bat de nuevo
```

**❌ PIVOT_MAESTRO.xlsx no encontrado**
```
Solución: Verificar que existe config_pivot/PIVOT_MAESTRO.xlsx
```

**❌ Archivo de entrada no encontrado**
```
Solución: Ejecutar primero el pipeline completo para que la Etapa 0
          descargue el archivo, o colocar manualmente
          Licitacion_Publicada.xlsx en data/1. INPUT/
```

---

### Error: "Python no está instalado o no está en el PATH"

1. Descargar Python desde [python.org/downloads](https://www.python.org/downloads/)
2. Durante la instalación, marcar **"Add Python to PATH"** (importante)
3. Reiniciar la terminal y volver a intentarlo

---

### La Etapa 3 tarda mucho o tiene muchos errores

La API de Mercado Público tiene límites de velocidad y puede ser inestable en horarios pico. El sistema reintenta automáticamente 3 veces por registro.

- Ejecutar en horarios de baja demanda (madrugada, fines de semana)
- Los checkpoints permiten reanudar sin perder progreso si se interrumpe

---

### Resultados inesperados en el filtrado (demasiadas o muy pocas licitaciones)

El filtrado se controla desde `config_pivot/PIVOT_MAESTRO.xlsx`, hoja `06-FILTROS`:

- **Demasiadas licitaciones irrelevantes:** Agregar más palabras en las columnas de exclusión (E–L)
- **Faltan licitaciones relevantes:** Agregar más palabras en las inclusiones (col A) o en bypass (col M)
- **Una licitación específica que debería aparecer:** Buscar qué término la está excluyendo y añadirlo al bypass (col M)

---

### `ModuleNotFoundError: No module named 'utils'`

Siempre ejecutar desde la raíz del proyecto:
```bash
cd C:\Licitaciones_MP
python run_pipeline.py
```

---

### Error de tipo de cambio USD/CLP

Si la API de tipo de cambio no responde, el sistema continúa usando el último valor conocido y registra una advertencia en el log. No es un error crítico.

---

## 14. Para desarrolladores

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
        return True

    def run(self, context: PipelineContext) -> StageResult:
        self.bind(context)
        # ... lógica de la etapa
        return StageResult(success=True, stage_name=self.name)
```

2. Registrar en `run_pipeline.py` en el método `_construir_etapas()`.

### Convención de artefactos entre etapas

```python
# Guardar un artefacto (ruta a un archivo producido)
context.add_artifact('etapa2_output', ruta_archivo)

# Leer el artefacto de la etapa anterior
archivo = context.get_artifact('etapa2_output')
```

### Estructura de un test unitario

```python
import pytest
from etapas.etapa2 import FiltradorLicitaciones
from core.context import PipelineContext
from utils.config import Config

@pytest.fixture
def contexto(tmp_path):
    ctx = PipelineContext(config=Config())
    ctx.config.FILTRADO_DIR = tmp_path
    return ctx

def test_mi_caso(contexto):
    etapa = FiltradorLicitaciones()
    etapa.bind(contexto)
    # ... assertions
```

### Modificar configuración desde código

```python
from utils.config import Config
config = Config()

# Leer la ruta del PIVOT
print(config.PIVOT_MAESTRO)   # C:\...\config_pivot\PIVOT_MAESTRO.xlsx

# Verificar estructura
config.validar_estructura()
```

---

## Licencia

Propietario — Sebastian Chirino  
© 2025–2026 Todos los derechos reservados
