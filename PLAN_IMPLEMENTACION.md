# Plan de Implementación v7.0 — Mejoras Pipeline Licitaciones MP

> **Fecha:** 25 de mayo de 2026  
> **Branch base:** `feature/scoring`  
> **Estado actual:** 752 tests passing, ruff clean, scoring implementado

---

## PASO 0: Consolidar trabajo actual

**Objetivo:** Commit + push del scoring + monto fix antes de tocar más código.

| Sub-paso | Comando/Acción | Archivos |
|---|---|---|
| 0.1 | `git add` archivos modificados | `src/etapas/etapa4.py`, `tests/unit/test_etapa4_convertir_monto.py` |
| 0.2 | `git commit -m "fix: estimar monto desde rango UTM en Tipo Adquisición"` | |
| 0.3 | `git push origin feature/scoring` | Sube los 5 commits a GitHub |
| 0.4 | Crear PR `feature/scoring → main` | |

---

## FASE 1: Integración de Compra Ágil

### 1.1 — Nuevo cliente HTTP para API v2

**Archivo:** `src/utils/http.py` (modificar)

- Añadir método `get_v2(url, headers, params)` al `HTTPClient` existente
- Diferencia clave: ticket va en `headers={'ticket': api_key}`, NO en query params
- Paginación automática: loop `numero_pagina=1..total_paginas`, `tamano_pagina=50`
- Manejo de 429: leer header `Retry-After`, esperar hasta nuevo día calendario
- Manejo de respuesta: verificar `success == "OK"`, extraer `payload.items[]`

```python
# Estructura de respuesta esperada:
{
    "success": "OK",
    "payload": {
        "items": [...],
        "paginacion": {
            "total_paginas": 5,
            "numero_pagina": 1,
            "tamano_pagina": 50,
            "total_resultados": 230
        }
    }
}
```

### 1.2 — Config: nuevas variables

**Archivo:** `src/utils/config.py` (modificar)

| Variable | Valor default | Descripción |
|---|---|---|
| `COMPRA_AGIL_API_BASE_URL` | `https://api2.mercadopublico.cl` | Base URL API v2 |
| `COMPRA_AGIL_ENDPOINT` | `/v2/compra-agil` | Endpoint listado |
| `COMPRA_AGIL_TAMANO_PAGINA` | `50` | Items por página (max API) |
| `COMPRA_AGIL_ENABLED` | `True` | Feature flag para habilitar/deshabilitar |
| `COMPRA_AGIL_ESTADOS` | `"publicada"` | Estados a consultar |
| `COMPRA_AGIL_TTL_CAMBIO_MS` | `86400000` | Ventana de cambios (24h default) |

### 1.3 — Nueva etapa: Descarga Compra Ágil

**Archivo nuevo:** `src/etapas/etapa0b_compra_agil.py`

**Clase:** `DescargadorCompraAgil(BaseStage)`

- `name` = `"compra_agil"`
- `_execute(context)`:
  1. Verificar `COMPRA_AGIL_ENABLED` → skip si False
  2. Leer ticket de `LICIT_MERCADO_PUBLICO_TICKET` (mismo env var)
  3. `GET /v2/compra-agil?estado=publicada&ttl_cambio_ms=86400000&tamano_pagina=50`
  4. Paginar automáticamente hasta `total_paginas`
  5. Para cada item del listado → `GET /v2/compra-agil/{codigo}` (detalle)
  6. Guardar como DataFrame con columnas normalizadas
  7. Output: `data/1. INPUT/CompraAgil_Publicada.xlsx`

**Mapeo de campos (normalización):**

| Campo Compra Ágil | → Columna normalizada | Notas |
|---|---|---|
| `codigo` | `Código` | Ej: `1057539-228-COT26` |
| `nombre` | `Nombre` | |
| `descripcion` (detalle) | `Descripción` | Solo en endpoint detalle |
| `estado.glosa` | `Estado` | |
| `institucion.organismo_comprador` | `Organismo` / `Cliente` | |
| `institucion.nombre_region` | `Región` | |
| `montos.monto_disponible_clp` | `Monto Estimado (CLP)` | Ya normalizado a CLP |
| `montos.moneda` | `Moneda` | |
| `fechas.fecha_publicacion` | `Fecha Publicación` | ISO-8601 → dd/mm/yyyy |
| `fechas.fecha_cierre` | `Fecha Cierre Licitación` | ISO-8601 → dd/mm/yyyy |
| `presupuesto.tipo_presupuesto` | `Tipo Presupuesto` | "Disponible" / "Estimado" |
| `productos_solicitados[].nombre` | `API_ItemsProductos` | Join con `;` |
| `resumen.total_ofertas_recibidas` | `Total Ofertas` | Info competitiva |
| — (constante) | `Origen` | `"Compra Ágil"` |
| — (constante) | `Tipo Adquisición` | `"Compra Ágil (COT)"` |

**Rate limiting:**

- Listado: 1 llamada por página (pocas llamadas)
- Detalle: 1 llamada por COT. Delay 2-3s (la API v2 es más rápida que v1)
- Checkpoint: `temp/checkpoints/compra_agil_{hash}.jsonl`

### 1.4 — Merge en Etapa 2 (pre-filtrado)

**Archivo:** `src/etapas/etapa2.py` (modificar)

- En `_execute()`, después de cargar `Licitacion_Publicada.xlsx`:
  1. Verificar si existe `CompraAgil_Publicada.xlsx`
  2. Si existe → `pd.concat([df_licitaciones, df_compra_agil], ignore_index=True)`
  3. Añadir columna `Origen` = `"Licitación"` a las existentes si no la tienen
  4. Log: `"[IN] {n_licit} licitaciones + {n_ca} compras ágiles = {total}"`
  5. El filtrado inteligente (keywords, exclusiones) aplica igual sobre ambos tipos

**Impacto en etapas posteriores:**

- **Etapa 3:** Las Compra Ágil NO necesitan enriquecimiento (ya vienen completas del detalle v2). Añadir guard: `if row.get('Origen') == 'Compra Ágil': skip`
- **Etapa 4:** Funciona sin cambios (ya recibe DataFrame normalizado)
- **Etapa 5:** Funciona sin cambios (incremental sobre el reporte)

### 1.5 — Registro en pipeline

**Archivo:** `run_pipeline.py` (modificar)

```python
_STAGE_REGISTRY = [
    (0,   Etapa0Descarga,               "DESCARGA DIARIA",         False),
    (0.5, DescargadorCompraAgil,        "COMPRA ÁGIL",             False),  # NUEVO
    (1,   AuditorTaxonomia,             "AUDITORIA DE TAXONOMIA",  True),
    (2,   FiltradorLicitaciones,        "FILTRADO INTELIGENTE",    True),
    (3,   EnriquecedorAPI,              "ENRIQUECIMIENTO API",     True),
    (4,   GeneradorReporte,             "REPORTE EJECUTIVO",       True),
    (5,   GeneradorReporteIncremental,  "ANÁLISIS INCREMENTAL",    False),
]
```

### 1.6 — Tests

**Archivos nuevos:**

- `tests/unit/test_compra_agil.py` — Tests unitarios del normalizador de campos
- `tests/unit/test_http_v2.py` — Tests del cliente HTTP con header auth
- `tests/integration/test_compra_agil_contrato.py` — Test de contrato con mock API

**Tests clave:**

- Normalización de campos COT → formato estándar
- Paginación: 3 páginas → todos los items recolectados
- Error 429: respeta Retry-After
- Feature flag OFF → skip sin error
- Merge con licitaciones: DataFrame final tiene ambos orígenes
- Etapa 3 skip: filas con `Origen="Compra Ágil"` no llaman a API v1

---

## FASE 2: Mejoras de Enriquecimiento Etapa 3

### 2.1 — Extraer campos adicionales de API v1

**Archivo:** `src/etapas/etapa3.py` (modificar método de extracción)

| Campo API | Columna nueva | Tipo | Uso |
|---|---|---|---|
| `Tipo` | `API_TipoCodigo` | `string` | Código corto: L1, LE, LP, LS, CO, etc. |
| `VisibilidadMonto` | `API_VisibilidadMonto` | `int` | 1=público, 0=oculto |
| `TipoMontoEstimado` | `API_TipoMonto` | `int` | 1=Presupuesto, 2=Referencial |
| `Obras` | `API_EsObra` | `int` | 2=Sí, 1=No (ya existe parcialmente) |
| `SubContratacion` | `API_SubContratacion` | `int` | 1=permite |
| `Adjudicacion` | `API_Adjudicacion` | `dict` | Proveedor ganador, monto real |

**Modificación en `_extraer_datos()`:** Añadir las 5 líneas de extracción al dict de campos simples.

### 2.2 — Usar VisibilidadMonto en Etapa 4

**Archivo:** `src/etapas/etapa4.py` (modificar)

- En `_convertir_monto()`: si `API_VisibilidadMonto == 0` → registrar stat `'monto_oculto'` (reemplaza el heurístico actual)
- En el reporte: la columna ya muestra "No publicado", pero ahora con certeza

### 2.3 — Manejar moneda EUR

**Archivo:** `src/etapas/etapa4.py` (modificar `_convertir_monto`)

- Añadir rama `elif moneda in ['EUR', 'EURO']:`
- Nuevo config: `ETAPA4_VALOR_EUR_CLP: int = 1000` (default conservador)
- Actualizar `_actualizar_tasas()` para obtener EUR/CLP de frankfurter.app
- Añadir stat `'eur'`
- Tests: conversión EUR básica, EUR con NaN

### 2.4 — Tests

- Ampliar `tests/unit/test_etapa4_convertir_monto.py` con clase `TestConvertirMontoEUR`
- Ampliar `tests/unit/test_etapa3_contrato.py` con validación de campos nuevos

---

## FASE 3: Inteligencia Competitiva

### 3.1 — Obtener código MP

**Archivo nuevo:** `src/utils/competencia.py`

**Clase:** `ProveedorLookup`

- `buscar_proveedor(rut: str) -> dict`: `GET /Empresas/BuscarProveedor?rutempresaproveedor={rut}&ticket={ticket}`
- Cache local: `temp/proveedor_mp.json` con TTL 30 días
- RUT MP: `59.171.740-5` (ya configurado)
- Retorna: `{'codigo': 17793, 'nombre': 'MP...'}`

### 3.2 — Consultar historial adjudicaciones MP

**Archivo nuevo:** `src/utils/competencia.py` (misma clase)

- `historial_adjudicaciones(codigo_proveedor: int, dias: int = 365) -> DataFrame`
- Loop por los últimos N días: `GET /licitaciones.json?CodigoProveedor={codigo}&fecha={ddmmaaaa}&ticket={ticket}`
- Campos extraídos: código licitación, organismo, monto, fecha adjudicación
- Cache: `temp/historial_mp_{mes}.json`

### 3.3 — Enriquecer reporte con info competitiva

**Archivo:** `src/etapas/etapa4.py` (modificar `_preparar_reporte`)

| Columna nueva | Lógica | Fuente |
|---|---|---|
| `MP Historial` | "Sí" si MP ganó licitación del mismo organismo en últimos 12 meses | Historial adjudicaciones |
| `Competidores` | Nombres de proveedores adjudicados en licitaciones similares del mismo organismo | Adjudicación en API v1 |
| `Org. Recurrente` | Count de licitaciones del mismo organismo en el dataset actual | DataFrame actual |

### 3.4 — Ranking de organismos

**Archivo nuevo:** `src/utils/competencia.py`

- `ranking_organismos(df: DataFrame) -> DataFrame`: agrupa por organismo, cuenta licitaciones relevantes, ordena por frecuencia
- Se guarda como hoja adicional "Organismos" en el Excel de Etapa 4

### 3.5 — Tests

- `tests/unit/test_competencia.py` — Mock API, lookup, cache
- `tests/unit/test_competencia_ranking.py` — Ranking con DataFrame de prueba

---

## FASE 4: Órdenes de Compra

### 4.1 — Cliente OC

**Archivo:** `src/utils/http.py` (modificar) o `src/utils/ordenes_compra.py` (nuevo)

- `consultar_oc(codigo_licitacion: str) -> dict | None`
- `GET /ordenesdecompra.json?codigo={codigo}&ticket={ticket}`
- Solo para licitaciones con `API_CodigoEstado == 8` (adjudicada)
- Extraer: código OC, estado OC, monto total, proveedor adjudicado

### 4.2 — Integrar en Etapa 3

**Archivo:** `src/etapas/etapa3.py` (modificar)

- Después de enriquecer con API licitaciones:
  - Si `API_CodigoEstado == '8'` → consultar OC
  - Campos nuevos: `API_OC_Codigo`, `API_OC_Estado`, `API_OC_MontoTotal`, `API_OC_Proveedor`
- Rate limit: mismo delay de 7s (comparte cuota con licitaciones v1)

### 4.3 — Columnas en reporte

**Archivo:** `src/etapas/etapa4.py` (modificar)

| Columna | Contenido |
|---|---|
| `Monto Adjudicado (CLP)` | Monto real de la OC (vs estimado) |
| `Adjudicado a` | Nombre del proveedor ganador |
| `Estado OC` | Aceptada / Enviada / etc. |

### 4.4 — Tests

- `tests/unit/test_ordenes_compra.py` — Mock API OC
- Integración: licitación adjudicada → enriquecida con OC

---

## FASE 5: Scoring v2 — Dimensiones Nuevas ⏸️ PAUSADO

> **⚠️ CHECKPOINT:** Antes de implementar esta fase, **preguntar al usuario** si desea continuar.

### Propuestas en espera

#### 5.1 — Dimensión "Historial Organismo" (10%)

- Si MP ha ganado licitaciones del mismo organismo antes → +10% al score
- Fuente: datos de FASE 3
- Redistribución de pesos: Relevancia 30%, Monto 20%, Urgencia 20%, Limpieza 10%, Historial 10%, Complejidad 5%, Extra 5%

#### 5.2 — Dimensión "Complejidad" (5%)

- TipoMonto == 1 (Presupuesto) → más confiable → bonus +1 punto
- SubContratacion permitida → +0.5 puntos
- Obras == Sí → -1 punto (MP no es constructora)

#### 5.3 — Ajustar "Monto" con TipoMontoEstimado

- Si TipoMonto == 2 (Referencial) → penalizar ligeramente la dimensión monto (-0.5)
- Si VisibilidadMonto == 0 → usar score neutro (5.0) en vez de penalizar

#### 5.4 — Bonus Compra Ágil en urgencia

- Compra Ágil tiene plazos más cortos → bonus +1 en urgencia
- Licitaciones LE/LP (100+ UTM) → bonus +0.5 en monto (más atractivas)

---

## FASE 6: Infraestructura y Calidad

### 6.1 — Cache inteligente de tasas

**Archivo:** `src/etapas/etapa4.py` (modificar `_actualizar_tasas`)

- Guardar tasas en `temp/tasas_cache.json`:

```json
{
    "utm": 65000,
    "usd": 950,
    "eur": 1020,
    "fecha": "2026-05-25"
}
```

- TTL: 24 horas. Si cache < 24h → usar cache sin llamar API
- Fallback: si API falla → usar cache anterior (cualquier edad) + warning

### 6.2 — Modo API-first (sin Excel diario)

**Archivo:** `src/etapas/etapa0.py` (modificar)

- Nuevo flag: `--modo-api` en `run_pipeline.py`
- Si activado: `GET /licitaciones.json?estado=activas&ticket={ticket}` en vez de descargar Excel
- Beneficio: datos más frescos, no depende del portal web
- Implementación: paginar por fecha (`fecha=ddmmaaaa`) los últimos 7 días

### 6.3 — Dashboard HTML

**Archivo nuevo:** `src/utils/dashboard.py`

- Genera `data/2. OUTPUT/5. PRESENTACION/dashboard.html`
- Tabla sorteable con DataTables.js (embebido, sin CDN)
- Gráficos: distribución por Score, por Región, por Monto (Chart.js embebido)
- Filtros: por Origen (Licitación/Compra Ágil), por Score mínimo
- Se genera al final de Etapa 4

### 6.4 — Alertas por scoring alto

**Archivo:** `src/utils/alerts.py` (ya existe, ampliar)

- Si Score ≥ 8.0 → alerta especial
- Canal: log destacado + opción de webhook (Teams/Slack)
- Config: `ALERTA_SCORE_UMBRAL: float = 8.0`
- Config: `ALERTA_WEBHOOK_URL: str = ""` (vacío = solo log)

### 6.5 — Tests

- `tests/unit/test_cache_tasas.py`
- `tests/unit/test_dashboard.py`
- `tests/unit/test_alertas_scoring.py`

---

## Resumen de archivos

### Archivos nuevos

| Archivo | Fase |
|---|---|
| `src/etapas/etapa0b_compra_agil.py` | 1 |
| `src/utils/competencia.py` | 3 |
| `src/utils/ordenes_compra.py` | 4 |
| `src/utils/dashboard.py` | 6 |
| `tests/unit/test_compra_agil.py` | 1 |
| `tests/unit/test_http_v2.py` | 1 |
| `tests/integration/test_compra_agil_contrato.py` | 1 |
| `tests/unit/test_competencia.py` | 3 |
| `tests/unit/test_competencia_ranking.py` | 3 |
| `tests/unit/test_ordenes_compra.py` | 4 |
| `tests/unit/test_cache_tasas.py` | 6 |
| `tests/unit/test_dashboard.py` | 6 |
| `tests/unit/test_alertas_scoring.py` | 6 |

### Archivos modificados

| Archivo | Fases |
|---|---|
| `src/utils/http.py` | 1, 4 |
| `src/utils/config.py` | 1, 2, 6 |
| `src/etapas/etapa2.py` | 1 |
| `src/etapas/etapa3.py` | 2, 4 |
| `src/etapas/etapa4.py` | 2, 3 |
| `src/utils/alerts.py` | 6 |
| `run_pipeline.py` | 1 |

---

## Cronograma por fase

```
PASO 0: Commit + Push          ▓░░░░░░░░░  (inmediato)
FASE 1: Compra Ágil            ▓▓▓▓▓▓░░░░  (más trabajo, mayor impacto)
FASE 2: Enriquecimiento        ▓▓░░░░░░░░  (cambios puntuales)
FASE 3: Inteligencia           ▓▓▓▓░░░░░░  (módulo nuevo + integración)
FASE 4: Órdenes de Compra      ▓▓▓░░░░░░░  (similar a Etapa 3)
FASE 5: Scoring v2             ⏸️ PAUSA — preguntar al usuario
FASE 6: Infraestructura        ▓▓▓░░░░░░░  (mejoras incrementales)
```

---

## Notas técnicas importantes

### APIs disponibles

| API | Base URL | Auth | Formato fechas | Paginación |
|---|---|---|---|---|
| Licitaciones v1 (USADA) | `api.mercadopublico.cl/servicios/v1/publico/` | `?ticket=KEY` | `ddmmaaaa` | Por fecha |
| Compra Ágil v2 (POR USAR) | `api2.mercadopublico.cl/v2/` | `headers: {ticket: KEY}` | ISO-8601 | `numero_pagina` + `tamano_pagina` (max 50) |
| Órdenes de Compra v1 (POR USAR) | `api.mercadopublico.cl/servicios/v1/publico/` | `?ticket=KEY` | `ddmmaaaa` | Por fecha |
| Proveedores v1 (POR USAR) | `api.mercadopublico.cl/servicios/v1/Publico/Empresas/` | `?ticket=KEY` | — | — |

### Códigos de tipo de licitación

| Código | Descripción | Rango UTM |
|---|---|---|
| L1 | Licitación Pública <100 UTM | 0-100 |
| LE | Licitación Pública 100-1000 UTM | 100-1,000 |
| LP | Licitación Pública >1000 UTM | >1,000 |
| LS | Licitación de Servicios Personales | — |
| CO | Compra directa y trato directo | — |
| A1/B1/J1/F1/E1 | Otros tipos especiales | — |

### Estados Compra Ágil

| Estado | Descripción |
|---|---|
| `publicada` | Abierta a cotizaciones |
| `cerrada` | Plazo vencido |
| `desierta` | Sin ofertas |
| `cancelada` | Anulada |
| `proveedor_seleccionado` | Adjudicada |
| `oc_emitida` | Orden de compra generada |

### RUT MP

- **RUT:** `59.171.740-5`
- Se usa para consultar historial de adjudicaciones en FASE 3
