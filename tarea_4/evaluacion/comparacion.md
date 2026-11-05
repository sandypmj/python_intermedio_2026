# Parte 4: evaluación con y sin herramientas

Generado por `evaluacion/evaluar.py` el 2026-11-05 15:39. Modelo: **haiku**. Preguntas evaluadas: 1 de 10. Filas: 2.

Cada pregunta se hizo en una sesión nueva de `claude -p` (`--no-session-persistence`), con el mismo modelo en ambos modos. Las respuestas esperadas y sus tolerancias se fijaron en `preguntas.csv` antes de correr el experimento y no se modificaron después.

## Barreras del experimento

**Modo «sin» (solo memoria del modelo).**

- `--tools ""`: no tiene herramientas, así que no puede abrir archivos ni ejecutar comandos.
- `--strict-mcp-config` sin `--mcp-config`: no carga el MCP `bcrp` ni los conectores de la cuenta.
- Se ejecuta desde una carpeta temporal vacía, creada y borrada en cada pregunta. Así no recibe al arrancar
  el `CLAUDE.md`, las descripciones de las skills de `.claude/skills/`, la memoria del proyecto ni la ruta
  y los commits de git de `tarea_4`.
- El script revisa el evento `init` de `stream-json`. Si aparece alguna herramienta, algún servidor MCP
  o alguna skill de `tarea_4`, marca la fila como error («aislamiento roto»). La única herramienta
  permitida es `StructuredOutput`, que `--json-schema` añade solo para devolver el JSON.
- Las skills de usuario y de plugins siguen apareciendo en la lista, pero sin la herramienta `Skill` no
  puede usarlas.

**Modo «con» (MCP y skills).**

- Se ejecuta desde la raíz de `tarea_4` con `--mcp-config .mcp.json` y `--strict-mcp-config`, así que
  solo carga el MCP `bcrp`. Las herramientas permitidas son `mcp__bcrp`, `Skill`, `Bash`, `Read`, `Glob`
  y `Grep`.
- Hay rutas bloqueadas porque contienen las respuestas esperadas o las cifras ya publicadas:
  - `evaluacion/`: las respuestas esperadas y los resultados.
  - `informes/`, `evidencias_ia/` y `notas_proceso.md`: cifras ya obtenidas en las partes anteriores.
  - `referencias/`: la tabla departamental de la Sesión 16, con la respuesta de Cajamarca.
- El bloqueo se hace con reglas `--disallowedTools`: `Read(./ruta/**)`, que también afecta a Grep y Glob,
  y `Bash(*ruta*)`.
- Los scripts de las skills sí pueden leer `referencias/` cuando se ejecutan (por ejemplo `mapear.py`),
  porque las reglas solo controlan las herramientas de Claude, no los programas que este lanza.

**Detección (columna `acceso_indebido`, no cambia la calificación).**

| Nivel | Qué lo provoca |
|---|---|
| `sí` | El modelo pidió leer una ruta bloqueada, `limpiando-enaho/reference.md` o el código de `limpiar.py` (sus constantes `REF_*`), o una salida mostró ese contenido. Ejecutar `limpiar.py` no cuenta como lectura de su código. |
| `referencia visible` | Una salida legítima de las skills mostró un valor de referencia. Por ejemplo, la columna `referencia_pct` de `salidas/comparacion_mapa.csv` o la línea «referencia 27.6 %» de `validacion.txt`. |
| `intento bloqueado` | El modelo intentó una lectura prohibida y la regla la denegó. |
| `no` | Nada de lo anterior. |

El detalle de cada caso está en `detalle_acceso` de `resultados.csv`, y el registro completo de cada respuesta
en `evaluacion/registros/<id>__<modo>.jsonl`.

**Límites.**

- Las reglas de Bash comparan texto, así que un comando que arme la ruta por partes podría evadirlas. Por eso
  existe la detección sobre lo que devuelve cada herramienta.
- La configuración del usuario (`~/.claude`) se carga en ambos modos por igual.

## Aciertos por modo

| modo | correcta | parcial | incorrecta | no contesta | error | total | % correctas |
|---|---|---|---|---|---|---|---|
| con | 1 | 0 | 0 | 0 | 0 | 1 | 100 % |
| sin | 0 | 0 | 0 | 1 | 0 | 1 | 0 % |

## Aciertos por tipo de pregunta y modo

| tipo | modo | correcta | parcial | incorrecta | no contesta | error | total | % correctas |
|---|---|---|---|---|---|---|---|---|
| bcrp | con | 1 | 0 | 0 | 0 | 0 | 1 | 100 % |
| bcrp | sin | 0 | 0 | 0 | 1 | 0 | 1 | 0 % |

## Tiempo promedio por respuesta (segundos)

| tipo | sin | con |
|---|---|---|
| bcrp | 5.5 | 11.8 |
| todas | 5.5 | 11.8 |

## Preguntas que mejoraron o empeoraron

Orden usado: correcta > parcial > no contesta > incorrecta. Responder `null` (reconocer que no sabe) se considera mejor que dar una cifra equivocada. Las filas con «error» no se comparan.

| id | esperada | sin: cifra | sin: resultado | con: cifra | con: resultado | cambio |
|---|---|---|---|---|---|---|
| bcrp_pbi_2025 | 3.4306 | null | no contesta | 3.43 | correcta | mejoró |

Resumen: mejoró: 1.

## Herramientas usadas en el modo «con»

| id | herramientas |
|---|---|
| bcrp_pbi_2025 | bcrp.buscar_series(texto=PBI real variacion, frecuencia=Anual, limite=20) ; bcrp.buscar_series(texto=PBI real, frecuencia=Anual, limite=20) ; bcrp.serie(codigo=PM04923AA, desde=2024, hasta=2025) |

## Accesos indebidos detectados

Ninguno: ninguna respuesta leyó rutas bloqueadas ni valores de referencia de las skills.

<!-- ANALISIS: todo lo que escribas debajo de esta línea se conserva al regenerar el archivo -->

## Mi análisis

### ¿Qué cambió entre el modo «sin» y el modo «con»?

_(Pendiente)_

### Preguntas BCRP frente a preguntas ENAHO

_(Pendiente)_

### Preguntas mixtas: cifras e interpretación

_(Pendiente)_

### ¿Inventó cifras el modelo sin herramientas o reconoció que no sabía?

_(Pendiente)_

### Accesos indebidos y validez de los resultados

_(Pendiente)_

### Costo en tiempo y conclusiones

_(Pendiente)_
