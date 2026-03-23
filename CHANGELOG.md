# Changelog

Todos los cambios notables del proyecto se documentan en este archivo.

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/),
con versionado semántico [SemVer](https://semver.org/lang/es/).

---

## [5.0.0] — 2026-03-22 (Sprint 8 — Estado final)

### Añadido
- `.venv` como entorno virtual estándar del proyecto
- `.vscode/settings.json` y `pyrightconfig.json` para resolución de imports en VS Code/Pylance
- Tests unitarios Etapa 0 (`test_etapa0_descarga.py`, 20 tests) — cobertura 30% → 91%
- Tests unitarios Etapa 1 (`test_etapa1_auditoria.py`, 23 tests) — cobertura 38% → 89%
- Tests unitarios Etapa 4 `run()` (`test_etapa4_run.py`, 15 tests) — cobertura 55% → 80%
- `--cov-fail-under=80` en CI para impedir regresión de cobertura
- Python 3.13 añadido a la matriz de CI (3.11 / 3.12 / 3.13)
- `[tool.coverage]` en `pyproject.toml` (fuente, omisiones, umbral)
- `pre-commit>=3.0.0` y `pytest-cov>=4.1.0` en dependencias dev
- `.pre-commit-config.yaml` con hooks Ruff (lint + format)
- Badges de CI y cobertura en README
- `CHANGELOG.md` (este archivo)

### Corregido
- 32 errores de Pylance por intérprete sin entorno virtual configurado
- `test_mode`/`test_limit` → `TEST_MODE`/`TEST_LIMIT` (nombres de campo Pydantic)
- `Optional[str/dict/list]` en firmas de funciones faltantes
- `wb.active` puede ser `None` según stubs de openpyxl — añadidos `assert ws is not None`
- `__dict__` mutation en objeto Pydantic frozen — eliminada
- `error_message` puede ser `None` en `StageResult` — añadida comprobación previa
- `truncar_texto()` — tipo de parámetro `Optional[str]`
- Caracteres de encoding corruptos en step name de `ci.yml`

### Eliminado
- Clase `GeneradorReporteIncremental` legacy en `reporte_incremental.py` (~265 líneas de dead code)
- `_main_legacy()` y segundo `if __name__ == "__main__"` redundante
- Imports no usados (`shutil`, `pd`, `datetime`, `load_workbook`, `AnalizadorIncremental`, `obtener_timestamp`) en `reporte_incremental.py`

---

## [4.2.0] — 2026-03-22 (Sprint 7 — Cobertura ≥65%)

### Añadido
- `tests/unit/test_etapa5_incremental.py` (22 tests): `_mover_licitaciones_vencidas`, `_calcular_dias_cierre`, `_generar_link_licitacion`, `_actualizar_reporte_existente`
- `tests/unit/test_sistema_incremental.py` (12 tests): constructor, análisis, sugerencias, I/O
- `tests/unit/test_reporte_incremental_entry.py` (6 tests): `main()` éxito/fallo/excepción/flags
- `tests/unit/test_etapa3_api_key.py` (8 tests): env var → PIVOT fallback → excepción
- `tests/unit/test_alerts.py` (16 tests): `AlertSeverity`, `Alert`, sinks, `AlertManager` — 98%
- `tests/unit/test_observability.py` (25 tests): 6 reglas + `RunSummaryReporter` — 99%
- 13 tests adicionales a `test_analizador.py`: métodos públicos de análisis

### Corregido
- `reporte_incremental.py` — imports `pd`, `shutil`, `load_workbook`, `datetime` faltaban
- `reporte_incremental.main()` solapada por segunda `main()` legacy → renombrada a `_main_legacy()`

### Métricas
- Tests totales: **281** ✅ | Cobertura: **65%**

---

## [4.1.0] — 2026-03-22 (Sprint 6 — Bugs producción + CI/CD)

### Añadido
- `tests/unit/test_analizador.py` (28 tests): lógica de negocio `AnalizadorIncremental`
- `tests/unit/test_etapa4_convertir_monto.py` (35 tests): CLP/UTM/USD edge cases, `_calcular_dias`, `_separar`
- `.github/workflows/ci.yml` — CI/CD con matriz Python 3.11+3.12, pytest + Codecov

### Corregido
- `etapa4._convertir_monto` — `[^\d.]` conservaba puntos → `float('5.000.000')` lanzaba `ValueError`. Fix: `re.sub(r'[^\d]', '', ...)` para CLP/PESO
- `etapa3._cargar_api_key` — doble mecanismo sin prioridad. Fix: env var primero, PIVOT como fallback con deprecation warning
- `analizador_incremental._generar_sugerencias_filtros` — keywords en lowercase vs. texto normalizado UPPERCASE → nunca coincidían. Fix: keywords uppercase

### Métricas
- Tests totales: **173** ✅ | Cobertura: **47%**

---

## [4.0.0] — 2026-03-22 (Sprint 5 — Tests e infraestructura)

### Añadido
- `pyproject.toml` — `pythonpath = [".", "src"]`, markers `unit/integration/slow`, `addopts`
- `tests/conftest.py` — 7 fixtures reutilizables: `config`, `context`, `df_licitaciones_minimo`, `logger_mock`, etc.
- `tests/unit/test_filtrado.py` (17 tests): `_aplicar_inclusion/exclusion/bypass`, regex escapado
- `tests/integration/test_pipeline_smoke.py` (11 tests): contratos `BaseStage`, artefactos, Etapas 1–2 con mocks

### Corregido
- `etapa2` filtrado — `str.contains()` sin `case=False` → 0 resultados con filtros nuevos
- `text_processing.truncar_texto(None)` → retornaba `None` en lugar de `""`

### Métricas
- Tests totales: **124** ✅ | Cobertura: **~30%**

---

## [3.0.0] — 2026-03-22 (Sprint 4 — Documentación)

### Añadido
- `README.md` reescrito completamente: arquitectura v5, 6 etapas, env vars, opciones CLI, observabilidad, tests, troubleshooting

---

## [2.1.0] — 2026-03-22 (Sprint 3 — Calidad)

### Añadido
- `tests/unit/test_text_processing.py` (108 tests): todas las funciones de normalización
- `tests/unit/test_monto_conversion.py` (16 tests): conversión de monedas
- Limpieza automática de checkpoints: `_limpiar_checkpoints_antiguos()` en etapa3
- `ETAPA3_CHECKPOINT_RETENTION_DAYS` en config (default 7 días)

### Cambiado
- Filtrado Etapa 2 vectorizado: `str.contains(pattern, regex=True)` por columna en lugar de `apply(..., axis=1)`

---

## [2.0.0] — 2026-03-22 (Sprint 2 — Deuda técnica)

### Añadido
- `cargar_desde_pivot()` detecta columnas 'Parámetro'/'Valor' por nombre (robusto ante cambios de estructura)
- `sistema_incremental.py` acepta `PipelineContext` opcional

### Eliminado
- Dead code en `etapa5.py`: `_actualizar_hoja_vigentes`, `_insertar_fila_licitacion`, `_actualizar_licitaciones_existentes` (~70 líneas)

### Cambiado
- `reporte_incremental.py` reescrito: 250 líneas → 70 líneas limpiamente delegando en Etapa 5

---

## [1.0.0] — 2026-03-22 (Sprint 1 — Foundation)

### Añadido
- Arquitectura completa de pipeline: `BaseStage`, `StageResult`, `PipelineContext` en `src/core/`
- Etapas 0–5 migradas a `BaseStage`, comunicación vía artefactos en contexto
- `HTTPClient` con retry/backoff exponencial, respeto de `Retry-After`, códigos 429/500–504
- `AlertManager` con `ConsoleAlertSink` y `FileAlertSink`
- `ObservabilityRules` (6 reglas de negocio) + `RunSummaryReporter`
- `Config` con pydantic-settings, prefijo `LICIT_`, patrón 12-factor
- `requirements.txt` completo (9 dependencias)
- `.env.example` documentado (15+ variables)
- `etapa5._mover_licitaciones_vencidas()` completamente implementado
- `etapa5._generar_link_licitacion()` URL corregida (`?idlicitacion=`)
- `src/core/__init__.py` exportando los tres símbolos públicos
