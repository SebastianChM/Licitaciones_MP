# 🚀 Licitaciones Mercado Público - Pipeline Automatizado

Sistema automatizado para filtrar y enriquecer licitaciones del Mercado Público de Chile, reduciendo ~12,000 licitaciones diarias a ~200 relevantes para Sebastian Chirino.

**Versión**: 4.0.0 - Sistema Incremental  
**Última actualización**: 25 Octubre 2025

---

## ⚡ INICIO RÁPIDO

```bash
# 0. IMPORTANTE: Configurar API Key de Mercado Público primero
#    Ver: docs/NOTAS_API_MERCADO_PUBLICO.md
#    Agregar en: config_pivot/PIVOT_MAESTRO.xlsx -> Hoja 01-PARAMETROS

# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Pipeline completo (primera vez)
python run_pipeline.py

# 3. 🆕 Análisis incremental (uso diario)
python src/sistema_incremental.py

# 4. 🆕 Actualizar reportes preservando trabajo manual
python src/reporte_incremental.py "ruta/archivo.xlsx"

# 5. Ver resultados en:
data/2. OUTPUT/5. PRESENTACION/Reporte_Licitaciones_*.xlsx
```

---

## 📁 ESTRUCTURA DEL PROYECTO

```
Licitaciones_MP/
│
├── run_pipeline.py          ⭐ Script principal
├── requirements.txt         📦 Dependencias
├── README.md               📖 Esta documentación
│
├── src/                    🔧 Código fuente
│   ├── etapas/            
│   │   ├── etapa1.py      # Auditoría taxonomía (450 líneas)
│   │   ├── etapa2.py      # Filtrado inteligente (620 líneas)
│   │   ├── etapa3.py      # Enriquecimiento API (550 líneas)
│   │   └── etapa4.py      # Reporte ejecutivo (650 líneas)
│   ├── sistema_incremental.py    🆕 # Sistema de análisis incremental
│   ├── reporte_incremental.py    🆕 # Generador reportes preservando formato
│   └── utils/
│       ├── config.py      # Configuración centralizada
│       ├── logger.py      # Sistema de logging
│       ├── analizador_incremental.py  🆕 # Núcleo análisis inteligente
│       ├── text_processing.py
│       └── file_ops.py
│
├── config_pivot/          ⚙️ Configuración
│   └── PIVOT_MAESTRO.xlsx # Cerebro del sistema
│
├── data/                  🗄️ Datos
│   ├── 1. INPUT/         # Entrada: Licitacion_Publicada.xlsx
│   └── 2. OUTPUT/        # Salidas del pipeline
│
├── docs/                  📚 Documentación
│   ├── QUICKSTART.md     # Guía inicio rápido
│   ├── CHANGELOG.md      # Historial cambios
│   ├── PROXIMOS_PASOS.md # Roadmap futuro
│   └── NOTAS_API_MERCADO_PUBLICO.md  # ⚠️ Comportamiento API
│       ├── 1. LOGS/
│       ├── 2. HALLAZGOS/
│       ├── 3. FILTRADO/
│       ├── 4. ENRIQUECIDO/
│       └── 5. PRESENTACION/
│
├── docs/                  📚 Documentación adicional
├── scripts/               🔧 Scripts auxiliares
├── tests/                 🧪 Tests unitarios
└── _OLD/                  🗑️ Archivos legacy
```

---

## 🎯 LAS 4 ETAPAS DEL PIPELINE

### **Etapa 1: Auditoría de Taxonomía**
Detecta valores nuevos que no existen en PIVOT_MAESTRO.

- **Entrada**: `data/1. INPUT/Licitacion_Publicada.xlsx`
- **Proceso**: Compara contra valores conocidos en PIVOT_MAESTRO
- **Salida**: `data/2. OUTPUT/2. HALLAZGOS/HALLAZGOS_*.xlsx`

### **Etapa 2: Filtrado Inteligente**
Reduce 12,000 licitaciones a ~200 relevantes.

- **Entrada**: `Licitacion_Publicada.xlsx`
- **Proceso**: Aplica filtros de inclusión/exclusión desde PIVOT_MAESTRO (Hoja 06)
- **Salida**: `data/2. OUTPUT/3. FILTRADO/Licitaciones_Filtradas_*.xlsx`

### **Etapa 3: Enriquecimiento API**
Consulta API de Mercado Público para obtener 40+ campos adicionales.

- **Entrada**: `Licitaciones_Filtradas_*.xlsx`
- **Proceso**: Rate limiting 2 req/segundo, reintentos automáticos, caché
- **Salida**: `data/2. OUTPUT/4. ENRIQUECIDO/Licitaciones_Enriquecidas_*.xlsx`

### **Etapa 4: Reporte Ejecutivo**
Genera Excel final con formateo profesional.

- **Entrada**: `Licitaciones_Enriquecidas_*.xlsx`
- **Proceso**: Convierte UTM/USD→CLP, calcula días para cierre, formatea colores
- **Salida**: `data/2. OUTPUT/5. PRESENTACION/Reporte_Licitaciones_*.xlsx`

---

## 🆕 SISTEMA INCREMENTAL (v4.0)

### 🎯 **¿Qué es?**
Sistema inteligente que preserva el trabajo manual de tus compañeros (colores, filtros, ordenamientos) mientras actualiza solo los datos nuevos.

### ✨ **Funcionalidades Clave**
- **🔍 Detección Automática**: Identifica nuevos valores en taxonomía vs PIVOT_MAESTRO
- **👥 Preserva Trabajo Manual**: Mantiene colores, filtros y ordenamientos aplicados por compañeros
- **➕ Solo Datos Nuevos**: Agrega únicamente licitaciones que no existían previamente
- **🎯 Sugerencias Inteligentes**: Propone mejoras a filtros basadas en patrones detectados
- **📊 Reportes Detallados**: Genera análisis JSON completos de todos los cambios

### 🚀 **Comandos Principales**
```bash
# Análisis completo de cambios
python src/sistema_incremental.py

# Actualizar Excel preservando formato
python src/reporte_incremental.py "archivo.xlsx"

# Validar sistema completo
python test_sistema_completo.py
```

### 📋 **Casos de Uso**
1. **Colaboración Diaria**: Compañeros aplican colores/filtros → Sistema los preserva automáticamente
2. **Actualización Inteligente**: Solo nuevas licitaciones se agregan, existentes se actualizan mínimamente
3. **Mejora Continua**: Sistema detecta nuevos patrones y sugiere filtros mejorados
4. **Auditoria Completa**: Logs detallados de todos los cambios para trazabilidad

**📖 Documentación completa**: `SISTEMA_INCREMENTAL_COMPLETADO.md`

---

## ⚙️ CONFIGURACIÓN

Todo se controla desde:
```
config_pivot/PIVOT_MAESTRO.xlsx
```

**Hojas importantes**:
- **Hoja 01-05**: Valores permitidos (Región, Organismo, ONU, Niveles, Genérico)
- **Hoja 06**: FILTROS (palabras de inclusión/exclusión/bypass)

Para modificar comportamiento:
1. Abrir `PIVOT_MAESTRO.xlsx`
2. Editar filtros en Hoja 06
3. Guardar
4. Ejecutar `python run_pipeline.py`

---

## 🛠️ OPCIONES DE EJECUCIÓN

### Pipeline Completo
```bash
python run_pipeline.py
```

### Etapas Específicas
```bash
# Solo auditoría y filtrado
python run_pipeline.py --etapas 1 2

# Solo enriquecimiento y reporte
python run_pipeline.py --etapas 3 4
```

### Con Archivo Custom
```bash
python run_pipeline.py --entrada "ruta/archivo.xlsx"
```

### Etapas Individuales
```bash
python -m src.etapas.etapa1
python -m src.etapas.etapa2
python -m src.etapas.etapa3
python -m src.etapas.etapa4
```

---

## 📊 ESTADÍSTICAS DEL PROYECTO

| Métrica | Valor |
|---------|-------|
| Líneas de código | 3,570 |
| Duplicación | <5% |
| Módulos Python | 9 |
| Cobertura tests | Pendiente |
| Versión | 3.0.0 |

---

## 🐛 SOLUCIÓN DE PROBLEMAS

### 🔑 Etapa 3 con 0% de éxito - FALTA API KEY
**SÍNTOMA**: Todos los requests fallan con HTTP 500, mensaje "peticiones simultáneas"

**CAUSA**: No está configurada la API Key de Mercado Público

**SOLUCIÓN**:
1. Obtener API Key en https://www.mercadopublico.cl/Home/Ayuda
2. Abrir `config_pivot/PIVOT_MAESTRO.xlsx`
3. Ir a hoja `01-PARAMETROS`
4. Agregar fila: `API Key` | `<tu_clave>`
5. Guardar y ejecutar de nuevo

Ver guía completa: [docs/NOTAS_API_MERCADO_PUBLICO.md](docs/NOTAS_API_MERCADO_PUBLICO.md)

### ⚠️ Muchos errores HTTP 500 en Etapa 3 (CON API Key configurada)
**ESTO ES NORMAL**. Ver documentación completa: [docs/NOTAS_API_MERCADO_PUBLICO.md](docs/NOTAS_API_MERCADO_PUBLICO.md)

- 10-30% de errores HTTP 500 es comportamiento esperado del API de Mercado Público
- El sistema reintenta 3 veces con delays
- Tasa de éxito real: 50-80% es normal, >80% es excelente
- Solución: Ejecutar en horarios de baja demanda (2am-6am, fines de semana)

### Error: "No se encuentra PIVOT_MAESTRO.xlsx"
```bash
python -c "from src.utils import Config; c = Config(); print(c.PIVOT_MAESTRO)"
```

### Error: "ModuleNotFoundError: No module named 'src'"
```bash
# Ejecutar desde la raíz del proyecto
cd C:\Users\Sebastian\Desktop\SCRIPTS\Licitaciones_MP
python run_pipeline.py
```

### Error: "No se encontró archivo de entrada"
```bash
# Verificar que existe
dir "data\1. INPUT\Licitacion_Publicada.xlsx"
```

### Ver logs detallados
```bash
type "data\2. OUTPUT\1. LOGS\pipeline_completo_*.log"
```

---

## 📈 MÉTRICAS DE RENDIMIENTO

- **Etapa 1** (Auditoría): ~5 segundos para 12,000 registros
- **Etapa 2** (Filtrado): ~10 segundos (reduce 12k → 200)
- **Etapa 3** (Enriquecimiento): ~2 minutos (200 licitaciones × 2 req/seg)
- **Etapa 4** (Reporte): ~5 segundos
- **TOTAL**: ~3 minutos para pipeline completo

---

## 🔄 CHANGELOG v3.0 (24 Oct 2025)

### ✅ Cambios Mayores
- ✅ Refactorización completa a arquitectura modular
- ✅ Eliminación de 40% de duplicación de código
- ✅ Configuración centralizada en `config.py`
- ✅ Sistema de logging profesional
- ✅ Pipeline orquestado con `run_pipeline.py`
- ✅ Estructura super limpia (4 archivos raíz, 7 carpetas)

### 🗂️ Organización
- ✅ Carpetas renombradas: `2. PIVOT/` → `config_pivot/`, `4. DATA/` → `data/`
- ✅ Documentación consolidada en README.md único
- ✅ 50+ archivos legacy movidos a `_OLD/`
- ✅ 38 carpetas OUTPUT antiguas eliminadas
- ✅ Carpetas vacías eliminadas

### 📦 Dependencias
```
pandas>=2.0.0
openpyxl>=3.1.0
requests>=2.31.0
python-Levenshtein>=0.21.0
pytz>=2023.3
```

---

## 📞 SOPORTE

- **Documentación adicional**: Ver carpeta `docs/`
- **Código legacy**: Ver carpeta `_OLD/` (referencia)
- **Issues**: Contactar equipo MP

---

## 🎓 PARA DESARROLLADORES

### Agregar Nueva Etapa
1. Crear `src/etapas/etapaN.py`
2. Seguir patrón de etapas existentes
3. Usar utilidades de `src/utils/`
4. Agregar al orquestador `run_pipeline.py`

### Modificar Filtros
1. Editar `config_pivot/PIVOT_MAESTRO.xlsx` (Hoja 06)
2. No tocar código Python
3. Ejecutar pipeline

### Ejecutar Tests
```bash
pytest tests/ -v
```

---

## 📜 LICENCIA

Propietario - Sebastian Chirino  
© 2025 Todos los derechos reservados

---

**¡Pipeline listo para producción!** 🚀

Para empezar: `python run_pipeline.py`
