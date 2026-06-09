# Sistema MP — Esquema General para Dirección

> Documento orientado a perfiles no técnicos.
> Describe qué hace el sistema, cómo lo hace paso a paso, y cómo podría incorporarse Inteligencia Artificial.

---

## ¿Qué problema resuelve este sistema?

Cada día, el Estado de Chile publica en el portal **Mercado Público** aproximadamente **12.000 licitaciones** de todo tipo: desde lápices hasta infraestructura de telecomunicaciones. Una consultora del sector tecnológico sólo puede ofertar en un pequeño subconjunto de esas licitaciones — las que corresponden a su área de negocio.

**Sin el sistema:** una persona tendría que revisar manualmente esas 12.000 fichas todos los días para encontrar las ~50-100 relevantes. Eso tomaría varios días de trabajo.

**Con el sistema:** el proceso completo se ejecuta en unos 45-60 minutos con un solo clic, y entrega un informe Excel listo para que el equipo comercial lo analice.

---

## Visión general — El "embudo" de datos

```
 INTERNET                                                 MP
 Mercado Público
 ~12.000 licitaciones                                     ~60 licitaciones
 publicadas por día                                       relevantes + detalle
        │                                                      │
        ▼                                                      ▼
 ┌─────────────────────────────────────────────────────────────────┐
 │                                                                 │
 │   DESCARGA   ──►   FILTRADO   ──►   ENRIQUECIMIENTO   ──►   REPORTE   │
 │                                                                 │
 └─────────────────────────────────────────────────────────────────┘
```

---

## Las 6 etapas del pipeline — explicadas sin tecnicismos

### Etapa 0 — Descarga automática

**¿Qué hace?**
El sistema se conecta a la página web de Mercado Público y descarga automáticamente el listado completo del día en formato de planilla Excel.

**Analogía:**
Es como ir al kiosco, comprar todos los diarios del día y traerlos a la oficina para revisarlos.

**Resultado:** Una planilla con ~12.000 filas.

---

### Etapa 1 — Auditoría de categorías

**¿Qué hace?**
Revisa que las categorías de producto que usa Mercado Público no hayan cambiado desde la última vez. Si aparece una categoría nueva que el sistema no conoce, genera una alerta para que el equipo la evalúe.

**Analogía:**
Es como verificar que el índice del diario sigue siendo el mismo antes de buscar en secciones específicas. Si hay una sección nueva, se avisa.

**Resultado:** Reporte de categorías nuevas (si las hay), para que el equipo decida si son relevantes.

---

### Etapa 2 — Filtrado inteligente

**¿Qué hace?**
Aplica las reglas de negocio de MP para quedarse solo con las licitaciones que interesan. Esas reglas están configuradas en un archivo Excel llamado `PIVOT_MAESTRO.xlsx`, que el equipo puede editar sin tocar el código.

Los filtros funcionan en tres niveles:
1. **Palabras clave de inclusión** — si la licitación menciona términos como "consultoría", "vialidad", "agua potable", se considera candidata.
2. **Palabras clave de exclusión** — si menciona "alimentación escolar" o "materiales de oficina", se descarta.
3. **Categorías prioritarias** — ciertas categorías del portal pasan directamente sin revisión de palabras clave.

**Analogía:**
Es como tener un asistente que lee los titulares de los 12.000 artículos del diario y separa solo los que tienen que ver con infraestructura, agua o energía — descartando los de deportes, cocina y entretenimiento.

**Resultado:** Planilla reducida de ~50-100 licitaciones relevantes.

---

### Etapa 3 — Enriquecimiento con la API

**¿Qué hace?**
Para cada licitación filtrada, el sistema consulta automáticamente la API oficial de Mercado Público para obtener la ficha técnica completa: monto estimado, organismo comprador, región, plazo, descripción detallada, etc.

**¿Por qué no viene todo en la descarga inicial?**
El listado inicial tiene solo el título y la categoría. El detalle completo se obtiene consultando una por una. Por eso esta etapa tarda más (la API pública tiene un límite de velocidad de ~10 consultas por minuto).

**Analogía:**
Es como haber separado los artículos interesantes del diario y ahora buscar en internet el artículo completo de cada uno para tener todos los detalles.

**Resultado:** Planilla enriquecida con toda la información disponible de cada licitación.

---

### Etapa 4 — Generación del reporte ejecutivo

**¿Qué hace?**
Transforma la planilla técnica en un informe formateado, con columnas relevantes para el equipo comercial: nombre del proyecto, región, monto estimado en UF/USD, días restantes para postular, organismo licitante, etc.

**Analogía:**
Es como tomar los artículos seleccionados y crear un resumen ejecutivo de una página con los puntos más importantes de cada uno, ordenado por urgencia (fecha de cierre).

**Resultado:** Excel formateado `Reporte_Licitaciones_FECHA.xlsx` listo para el equipo.

---

### Etapa 5 — Actualización incremental (modo diario)

**¿Qué hace?**
En lugar de generar un informe nuevo cada día (perdiendo las anotaciones manuales del equipo), esta etapa actualiza el informe existente de forma inteligente:

- **Licitaciones nuevas:** se agregan al final.
- **Licitaciones ya conocidas:** solo se actualiza el contador de días restantes; el resto (colores, comentarios manuales) se preserva.
- **Licitaciones vencidas:** se archivan automáticamente en una hoja histórica.

**Analogía:**
Es como tener un cuaderno de seguimiento donde el sistema agrega las oportunidades nuevas, tach las vencidas, y actualiza los plazos — pero sin borrar las notas que el equipo ya escribió a mano.

**Resultado:** El informe del equipo siempre está actualizado sin perder el trabajo manual.

---

## La interfaz gráfica (la ventana de la aplicación)

El sistema tiene una ventana de escritorio con tres partes principales:

```
┌──────────────────────────────────────────────────┐
│  MP                │  ESTADO DEL ENTORNO        │
│  CONSULTING          │  ✓ Python  ✓ Excel  ✓ API  │
├──────────────────────┼───────────────────────────┤
│  ACCIONES            │  PROGRESO                  │
│  > Pipeline Completo │  0──1──2──3──4──5          │
│  > Solo Incremental  │  (barra de avance)         │
│  > Detener           │                            │
├──────────────────────┼───────────────────────────┤
│  UTILIDADES          │  CONSOLA                   │
│  > Abrir Resultados  │  (log en tiempo real)      │
│  > Último Log        │                            │
└──────────────────────┴───────────────────────────┘
```

El usuario solo necesita hacer clic en "Pipeline Completo" y esperar. No necesita conocer ningún detalle técnico.

---

## Dónde vive cada dato

```
Carpeta del proyecto/
│
├── data/
│   ├── 1. INPUT/              ← La planilla descargada de Mercado Público
│   └── 2. OUTPUT/
│       ├── 3. FILTRADO/       ← Resultado de Etapa 2 (~60 licitaciones)
│       ├── 4. ENRIQUECIDO/    ← Resultado de Etapa 3 (con todos los detalles)
│       └── 5. PRESENTACION/   ← ★ El informe final que usa el equipo
│
├── config_pivot/
│   └── PIVOT_MAESTRO.xlsx     ← ★ Aquí el equipo configura los filtros
│
└── MP_Licitaciones.vbs      ← ★ Doble clic para abrir la aplicación
```

---

## Flujo de uso diario (para el usuario final)

```
Cada mañana:

  1. Doble clic en MP_Licitaciones.vbs
        │
        ▼
  2. Clic en "Pipeline Completo"
        │
        ▼
  3. Esperar ~45-60 minutos (el sistema trabaja solo)
        │
        ▼
  4. Clic en "Abrir Resultados"
        │
        ▼
  5. Se abre el informe Excel actualizado
```

---

---

# Parte II — Incorporación de Inteligencia Artificial

> Esta sección describe teóricamente cómo podría mejorarse el sistema con IA, sin requerir cambios en la infraestructura actual.

---

## ¿Qué puede aportar la IA a este sistema?

El sistema actual es muy bueno filtrando por palabras clave y categorías. Su limitación es que esas reglas son **rígidas y manuales**: si aparece una licitación de "Mejoramiento de Conectividad Vial" usando términos que no estaban en el diccionario, el sistema la descarta aunque sea relevante.

La IA puede resolver ese problema y agregar capacidades nuevas.

---

## Mejoras posibles con IA — De menor a mayor complejidad

### Nivel 1 — Clasificador semántico (el más inmediato)

**¿Qué hace?**
Un modelo de IA entrenado con licitaciones históricas aprendería a distinguir "relevante para MP" de "no relevante" leyendo la descripción completa, no solo palabras clave.

**¿Cómo encaja en el sistema actual?**
Se inserta entre la Etapa 2 y la Etapa 3: los casos "dudosos" que el sistema actual descartaría son revisados por el modelo antes de continuar.

```
Etapa 2 (filtrado por palabras clave)
        │
        ├──► Claramente relevante ──────────────────► Etapa 3
        │
        ├──► Zona gris (dudoso) ──► IA clasifica ──► Etapa 3 o descarte
        │
        └──► Claramente irrelevante ─────────────────► Descarte
```

**Beneficio estimado:** Recuperar un 2-5% de licitaciones relevantes que hoy se pierden por no tener las palabras exactas.

---

### Nivel 2 — Resumen automático por licitación

**¿Qué hace?**
Un modelo de lenguaje (como el que usa ChatGPT) lee la ficha técnica de cada licitación y genera automáticamente una columna adicional en el informe con un resumen ejecutivo en 2-3 oraciones:

> "Licitación de consultoría en diseño de infraestructura hídrica para la región de Atacama. Monto estimado: $450M. Plazo para postular: 18 días. Experiencia mínima requerida: 10 años en proyectos similares."

**¿Cómo encaja?**
Se agrega como un paso adicional en la Etapa 4 (generación de reporte).

**Beneficio:** El equipo comercial tarda segundos en evaluar cada oportunidad en lugar de entrar al portal a leer la ficha completa.

---

### Nivel 3 — Agente de scoring y priorización

**¿Qué hace?**
Un agente de IA evalúa cada licitación en base a criterios de negocio de MP y le asigna una puntuación de 1 a 100:

- ¿Coincide con proyectos en los que MP ha ganado antes?
- ¿El monto es competitivo para el tamaño de la empresa?
- ¿La región es donde MP tiene presencia?
- ¿El plazo es suficiente para preparar una buena propuesta?

El informe sale ordenado de mayor a menor puntuación, permitiendo al equipo enfocarse primero en las mejores oportunidades.

**¿Cómo encaja?**
Se añade como Etapa 3.5 (entre enriquecimiento y reporte). El PIVOT_MAESTRO.xlsx se extiende con una hoja de "criterios de scoring" que el equipo puede calibrar sin tocar código.

---

### Nivel 4 — Agente autónomo de monitoreo

**¿Qué hace?**
Un agente inteligente que opera de forma completamente autónoma:

1. Ejecuta el pipeline diariamente a una hora programada.
2. Detecta licitaciones de alta relevancia y envía alertas por correo o Teams.
3. Monitorea licitaciones activas y avisa cuando se acerca la fecha límite.
4. Aprende de las decisiones del equipo (si una licitación fue marcada como "no aplica", no la vuelve a presentar de forma prominente).

**Arquitectura conceptual:**

```
┌─────────────────────────────────────────────────────────────┐
│                    AGENTE IA (orquestador)                  │
│                                                             │
│  Planificador ──► Pipeline MP ──► Analizador ──► Notificador │
│       │                                   │            │    │
│  (agenda)                           (scoring)    (Teams/email) │
│                                                             │
│            ◄── Retroalimentación del equipo ──────────────  │
└─────────────────────────────────────────────────────────────┘
```

---

## Comparativa de opciones de IA

| Opción | Complejidad | Costo estimado | Beneficio | Tiempo de implementación |
|--------|-------------|----------------|-----------|--------------------------|
| Clasificador semántico | Baja | Bajo (modelo local) | Medio | 2-4 semanas |
| Resumen automático | Baja-Media | Bajo (API OpenAI ~$5/mes) | Alto | 1-2 semanas |
| Scoring y priorización | Media | Medio | Alto | 4-6 semanas |
| Agente autónomo | Alta | Medio-Alto | Muy alto | 2-3 meses |

---

## Recomendación de ruta de implementación

```
HOY                    +2 SEMANAS              +2 MESES              +4 MESES
  │                        │                       │                     │
  ▼                        ▼                       ▼                     ▼
Sistema              Resumen               Clasificador           Scoring +
actual               automático            semántico              Agente
(funcional)          por licitación        (zona gris)            autónomo
                     (impacto inmediato)   (menos pérdidas)       (full IA)
```

La recomendación es empezar por el **resumen automático** porque:
- Es la mejora más visible para el usuario final.
- No requiere entrenamiento ni datos históricos.
- El costo es mínimo (se paga por uso, no por instalación).
- Se puede activar/desactivar sin afectar el resto del sistema.

---

## Infraestructura necesaria para la IA

El sistema actual ya tiene la arquitectura preparada para incorporar IA sin reescribirlo:

| Lo que ya existe | Lo que se necesitaría agregar |
|------------------|-------------------------------|
| Pipeline modular con etapas independientes | Clave de API de OpenAI o Azure OpenAI |
| Sistema de configuración via Excel (PIVOT_MAESTRO) | Nueva hoja en PIVOT_MAESTRO con parámetros de IA |
| Logs y métricas por ejecución | (ninguno adicional) |
| Manejo de errores y reintentos | (ninguno adicional) |
| Interfaz gráfica con consola en tiempo real | (ninguno adicional) |

El diseño actual del sistema fue construido específicamente para que agregar nuevas etapas sea tan simple como escribir una clase nueva con el método `run()`. Una nueva etapa de IA no requeriría modificar ninguna parte del código existente.

---

*Documento generado: Mayo 2026 — Sistema MP v6.0.0*
