# Tarea 4: agente de investigación con MCP del BCRP y skills de la ENAHO

**Estudiante:** Sandy Patricia Martinez Jara (@sandypmj)
**Curso:** Python Intermedio 2026

**Pregunta de investigación:** ¿Cómo evolucionó la inflación de Lima y la tasa de referencia del BCRP entre 2020 y 2024, y qué diferencias territoriales y entre áreas urbana y rural presentaba la pobreza monetaria al cierre de ese periodo (ENAHO 2024)?

---

## 1. Objetivo del proyecto

Construir un agente de investigación sobre Claude Code que responda preguntas económicas del Perú con cifras verificables, sin que el modelo haga cuentas a mano. El agente tiene dos fuentes:

- un **servidor MCP propio** ([mcp/server.py](mcp/server.py)) que consulta la API oficial del BCRP;
- tres **skills** ([.claude/skills/](.claude/skills/)) que limpian, grafican y mapean la ENAHO 2024 del INEI.

Con ellas se escribió el [informe final](informes/informe_final.md) y se evaluó si el modelo responde mejor con estas herramientas que sin ellas ([evaluacion/comparacion.md](evaluacion/comparacion.md)).

## 2. Arquitectura general del agente

```text
                 Pregunta del usuario
                          │
                          ▼
                 ┌─────────────────┐
                 │   Claude Code   │  decide qué herramienta usar
                 └────────┬────────┘
             ┌────────────┴─────────────┐
             ▼                          ▼
   ┌───────────────────┐      ┌──────────────────────┐
   │   MCP bcrp        │      │   Skills ENAHO       │
   │ (mcp/server.py)   │      │ (.claude/skills/)    │
   │ buscar_series     │      │ limpiando-enaho      │
   │ serie / resumen   │      │ graficando-enaho     │
   │ comparar_series   │      │ mapeando-enaho       │
   └────────┬──────────┘      └──────────┬───────────┘
            ▼                            ▼
   API del BCRP (JSON)          datos/ (módulos 34 y 02, GeoJSON)
            │                            │
            └────────────┬───────────────┘
                         ▼
     Informe (informes/informe_final.md) + figuras/ + mapas/ + salidas/
```

Las cuentas las hace Python, no el modelo: cada cifra sale de una llamada a una herramienta o de un script que se puede repetir.

## 3. Herramientas MCP

Servidor `bcrp` hecho con FastMCP en [mcp/server.py](mcp/server.py). Todas las herramientas son de solo lectura.

| Elemento | Tipo | Qué hace |
|---|---|---|
| `buscar_series(texto, frecuencia=None, limite=10)` | herramienta | Busca series en el catálogo oficial del BCRP (unas 17 mil series). Todas las palabras deben aparecer en la categoría, el grupo o el nombre; no distingue tildes. |
| `serie(codigo, desde, hasta)` | herramienta | Devuelve los datos oficiales entre dos fechas. Acepta `2025-01` (mensual), `2025-T1` (trimestral), `2025-01-15` (diaria) o `2025` (anual) y devuelve los periodos en ese mismo formato, junto con la URL de la fuente. |
| `resumen(codigo, desde, hasta)` | herramienta | Calcula primero, último, cambio, variación %, promedio, máximo y mínimo, para que el modelo no haga cuentas a mano. |
| `comparar_series(codigo_a, codigo_b, desde, hasta)` | herramienta **propia** | Alinea dos series de la misma frecuencia en sus periodos comunes y calcula la correlación de Pearson. Da error si las frecuencias son distintas o hay menos de 2 periodos en común, y advierte que una correlación no prueba causalidad. |
| `bcrp://serie/{codigo}` | recurso | Ficha de la serie en JSON: nombre, categoría, frecuencia, inicio y última actualización. |
| `informe(tema)` | prompt | Pide un informe breve con cifras del BCRP, cada una con su código de serie y periodo, usando `buscar_series`, `resumen`/`serie` y `comparar_series`. |

El contrato del servidor son las 10 pruebas de [mcp/test_server.py](mcp/test_server.py).

## 4. Las tres skills

| Skill | Qué entra | Qué hace | Qué produce |
|---|---|---|---|
| [limpiando-enaho](.claude/skills/limpiando-enaho/SKILL.md) | `datos/966-Modulo34.zip` (sumaria) y `datos/966-Modulo02.zip` (miembros) | Une personas y hogares (`validate='m:1'`), deja a los residentes habituales, conserva las llaves como texto y ejecuta 18 validaciones esenciales y 4 controles contra cifras de referencia. Nunca ajusta datos ni tolerancias. Ver [reference.md](.claude/skills/limpiando-enaho/reference.md). | `salidas/validacion.txt` (siempre); `salidas/personas_2024.parquet` y `salidas/indicadores.csv` (solo si pasan las esenciales) |
| [graficando-enaho](.claude/skills/graficando-enaho/SKILL.md) | `salidas/personas_2024.parquet` | Grafica barras de la pobreza ponderada con `facpob07`, desde cero, ordenadas y con su valor escrito. | `figuras/pobreza_area.png`, `figuras/pobreza_sexo.png`, `figuras/pobreza_departamento.png` (200 dpi) |
| [mapeando-enaho](.claude/skills/mapeando-enaho/SKILL.md) | `salidas/personas_2024.parquet`, `datos/peru_departamental_simple.geojson`, `referencias/pobreza_departamento_2024.csv` y, para la comparación por hogares, `datos/966-Modulo34.zip` | Une por código (`ubigeo[:2]` con `FIRST_IDDP`), exige 25 departamentos con Lima y Callao separados, dibuja el mapa coroplético y compara cada departamento con la referencia de la Sesión 16. | `mapas/pobreza_departamento.png` y `salidas/comparacion_mapa.csv` (columna `estado`: `coincide`, `explicada_por_metodo`, `no_explicada`, `sin_verificar`) |

Si falta la base de personas, `graficando-enaho` y `mapeando-enaho` piden ejecutar primero `limpiando-enaho`.

## 5. Fuentes y enlaces para descargar los datos

La carpeta `datos/` no se versiona (está en [.gitignore](.gitignore)): hay que descargar los archivos y guardarlos ahí.

| Dato | Dónde se obtiene | Dónde guardarlo |
|---|---|---|
| ENAHO 2024, módulo 34 (sumaria) | Portal de microdatos del INEI (<https://proyectos.inei.gob.pe/microdatos/>), encuesta ENAHO, código **966** = 2024, formato Stata | `datos/966-Modulo34.zip` (sin descomprimir; dentro está `966-Modulo34/sumaria-2024.dta`) |
| ENAHO 2024, módulo 02 (miembros del hogar) | Mismo portal, código 966 | `datos/966-Modulo02.zip` (sin descomprimir; dentro está `966-Modulo02/enaho01-2024-200.dta`) |
| GeoJSON departamental | <https://raw.githubusercontent.com/d2cml-ai/Data-Science-Python/main/sessions/06-geoespacial/lab/Data/peru_departamental_simple.geojson> | `datos/peru_departamental_simple.geojson` (`mapear.py` lo descarga si falta) |
| Referencia departamental de la Sesión 16 | <https://raw.githubusercontent.com/d2cml-ai/Data-Science-Python/main/sessions/16-skills-enaho/referencias/pobreza_departamento_2024.csv> | `referencias/pobreza_departamento_2024.csv` (`mapear.py` lo descarga si falta) |
| BCRP: API de series | <https://estadisticas.bcrp.gob.pe/estadisticas/series/api> | No se guarda: el servidor MCP la consulta en vivo |
| BCRP: catálogo de series | <https://estadisticas.bcrp.gob.pe/estadisticas/series/metadata> | `mcp/datos/catalogo_bcrp.csv` (el servidor lo baja la primera vez, unos 7 MB) |

## 6. Instalación con uv

Requiere Python 3.12 o superior y [uv](https://docs.astral.sh/uv/). Desde `tarea_4/`:

```bash
uv sync
```

Instala `fastmcp`, `geopandas`, `httpx`, `matplotlib`, `pandas`, `pyarrow` y, en el grupo de desarrollo, `pytest` ([pyproject.toml](pyproject.toml), versiones fijadas en [uv.lock](uv.lock)).

**Si la descarga falla por timeout** (pasó con `pyarrow`, ver [notas_proceso.md](notas_proceso.md)), aumenta los tiempos de espera y los reintentos de uv:

```bash
# Git Bash / Linux / macOS
UV_HTTP_TIMEOUT=300 UV_HTTP_CONNECT_TIMEOUT=60 UV_HTTP_RETRIES=10 uv sync
```

```powershell
# PowerShell
$env:UV_HTTP_TIMEOUT = "300"; $env:UV_HTTP_CONNECT_TIMEOUT = "60"; $env:UV_HTTP_RETRIES = "10"; uv sync
```

## 7. Cómo conectar el MCP a Claude Code

El proyecto ya trae [.mcp.json](.mcp.json), que registra el servidor `bcrp` por stdio:

```json
{
  "mcpServers": {
    "bcrp": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "mcp/server.py"],
      "env": {}
    }
  }
}
```

1. Abre Claude Code desde la carpeta `tarea_4/` (la ruta `mcp/server.py` es relativa a ella).
2. Acepta el servidor `bcrp` cuando Claude Code pregunte si confía en los servidores del proyecto.
3. Escribe `/mcp` y comprueba que `bcrp` aparece como conectado, con sus cuatro herramientas, el recurso y el prompt.

Si prefieres registrarlo desde la terminal, el comando equivalente es:

```bash
claude mcp add --scope project bcrp -- uv run mcp/server.py
```

Las skills no requieren configuración: Claude Code las lee de `.claude/skills/` al abrir el proyecto.

## 8. Comandos para reproducir

Todos se ejecutan desde la raíz `tarea_4/`.

```bash
# Pruebas del servidor MCP (consultan la API real del BCRP)
uv run pytest

# Las tres skills, en este orden
uv run python .claude/skills/limpiando-enaho/scripts/limpiar.py
uv run python .claude/skills/graficando-enaho/scripts/graficar.py
uv run python .claude/skills/mapeando-enaho/scripts/mapear.py

# Gráfico del BCRP del informe y cifras derivadas
uv run python informes/graficar_bcrp.py
uv run python informes/calculos_informe.py

# Evaluación con y sin herramientas (llama a `claude -p`; tarda varios minutos)
uv run evaluacion/evaluar.py                       # 10 preguntas, modos sin y con, con Haiku
uv run evaluacion/evaluar.py --solo bcrp_pbi_2025  # repite una pregunta
uv run evaluacion/evaluar.py --modelo sonnet --modos con
```

`evaluar.py` escribe `evaluacion/resultados.csv`, los registros crudos en [evaluacion/registros/](evaluacion/registros/) y [evaluacion/comparacion.md](evaluacion/comparacion.md). Las preguntas y respuestas esperadas están en [evaluacion/preguntas.csv](evaluacion/preguntas.csv).

## 9. Resultados

### Pruebas del servidor

`uv run pytest` → **10 passed** (10/10 pruebas de [mcp/test_server.py](mcp/test_server.py)).

### Validación de la ENAHO ([salidas/validacion.txt](salidas/validacion.txt))

**Resultado de las esenciales: APROBADA** (18 de 18). Controles con FALLÓ: 1.

| Verificación | Obtenido | Referencia | Resultado |
|---|---|---|---|
| Pobreza nacional | 27.53 % | 27.6 % ± 0.1 puntos | APROBADA |
| Residentes habituales | 108,664 | 108,664 | APROBADA |
| Códigos de departamento | 25 (01 a 25) | 25 | APROBADA |
| Unión personas-hogares | 108,664 filas antes y después, 0 personas sin hogar | — | APROBADA |
| Urbana por personas (`facpob07`) | 24.74 % | 24.8 % ± 0.1 | APROBADA |
| **Rural por personas (`facpob07`)** | **39.44 %** | **39.3 % ± 0.1** | **FALLÓ** |
| Urbana por hogares (`factor07 × mieperho`) | 24.81 % | 24.8 % ± 0.1 | APROBADA |
| Rural por hogares (`factor07 × mieperho`) | 39.30 % | 39.3 % ± 0.1 | APROBADA |

**Nota de método** (de `validacion.txt`): el método por personas pondera a los residentes habituales del módulo 02 con `facpob07`; el método por hogares pondera cada hogar de la sumaria con `factor07 × mieperho`. Sus tasas difieren porque no cuentan exactamente a las mismas personas: `mieperho` no coincide con el número de residentes filtrados en todos los hogares. Las referencias corresponden al método por hogares; por eso un FALLÓ por personas puede reflejar esta diferencia de método, y **no se ajusta ninguna cifra**.

### Evaluación con y sin herramientas ([evaluacion/comparacion.md](evaluacion/comparacion.md))

10 preguntas (4 BCRP, 4 ENAHO, 2 mixtas), modelo Haiku, cada una en una sesión nueva de `claude -p`.

| Modo | Correcta | Parcial | Incorrecta | No contesta | % correctas |
|---|---|---|---|---|---|
| Con MCP y skills | **7** | 0 | 0 | 3 | **70 %** |
| Sin herramientas | **1** | 1 | 0 | 8 | **10 %** |

| Tipo | Con | Sin |
|---|---|---|
| BCRP | 4/4 | 0/4 |
| ENAHO | 1/4 | 1/4 |
| Mixta | 2/2 | 0/2 (1 parcial) |

Mejoraron 6 preguntas, quedaron igual 4 y no empeoró ninguna. Ningún modo dio cifras incorrectas: sin herramientas, el modelo respondió `null` en 8 casos. El modo «con» tardó en promedio 20.3 s por respuesta, frente a 5.9 s.

**Aclaración sobre las filas con acceso indebido.** Tres respuestas correctas del modo «con» vieron información bloqueada y se revisaron a mano:

| Pregunta | Qué vio | Origen de la cifra ENAHO | Validez |
|---|---|---|---|
| `enaho_pobreza_nacional` | `reference.md`, constantes `REF_*` de `limpiar.py` y `validacion.txt` (con Grep) | Copiada del valor de referencia (27.6) | No demuestra uso de skills; además, el modo «sin» ya la sabía |
| `mixta_pbi_pobreza` | `reference.md` (con Grep); sus intentos de leer `evaluacion/registros/` fueron negados | Copiada de `reference.md` (27.6) | Solo la cifra BCRP es válida |
| `mixta_ipc_lima` | `reference.md` completo y el código de `limpiar.py` | Calculada con código propio sobre los microdatos (28.03) | Cifra válida, pero no usó la skill: reimplementó su cálculo |

Si se descuentan las cifras ENAHO copiadas, el modo «con» queda en **5 aciertos limpios y 1 parcial**, que sigue superando al modo «sin» (1 acierto y 1 parcial, ambos con la pobreza nacional recordada de memoria). La mejora clara viene del MCP del BCRP; en este experimento el modelo **nunca usó la herramienta `Skill`**.

## 10. Limitaciones y problemas encontrados

Resumen de [notas_proceso.md](notas_proceso.md) y de los límites de [evaluacion/comparacion.md](evaluacion/comparacion.md).

**Entorno**
- `uv add` falló por timeout al descargar `pyarrow`; se resolvió con `UV_HTTP_TIMEOUT=300`, `UV_HTTP_CONNECT_TIMEOUT=60` y `UV_HTTP_RETRIES=10`.
- `git push` falló por conexión inestable (`RPC failed, curl 55`); se resolvió con `git config http.postBuffer 524288000`.
- Avisos de Git LF/CRLF en Windows, sin efecto sobre el código.

**Servidor MCP (BCRP)**
- La API escribe setiembre como «Set» en series diarias y «Sep» en mensuales; el servidor acepta ambos.
- Pedir `2024-T1` no da error pero devuelve 0 datos; el servidor lo convierte a `2024-1`.
- La API limita pedidos seguidos: las pruebas tardaron entre 20 y 82 segundos, y una consulta en vivo falló; el servidor informó el error y Claude reintentó.

**ENAHO**
- La pobreza rural por personas da 39.44 % frente a 39.3 % de referencia (0.14 puntos); por hogares da 39.30 %. No se ajustó la tolerancia: se documenta la diferencia de método.
- Por personas, 14 de 25 departamentos difieren de la tabla de la Sesión 16 (máximo 0.52 puntos, Puno); por hogares, los 25 coinciden a 0.05 puntos o menos.

**Evaluación**
- Las reglas de Bash comparan texto: un comando que arme la ruta por partes podría evadirlas; por eso existe la detección sobre lo que devuelve cada herramienta.
- La configuración del usuario (`~/.claude`) se carga en ambos modos por igual.
- El modelo conocía los nombres de los archivos de `evaluacion/registros/` (probablemente por el estado git que Claude Code incluye al arrancar). Intentó leerlos, pero todas las lecturas fueron negadas.
- Las búsquedas salieron de `tarea_4` hacia otras tareas del curso, donde no había barreras.
- Las reglas de permisos negaban comandos completos que mezclaban rutas permitidas y bloqueadas, por lo que el modelo no llegó a `datos/` en 3 preguntas ENAHO.
- La detección automática tuvo un falso positivo y un falso negativo, por eso cada fila marcada se revisó a mano.
- La pobreza extrema no la calcula ninguna skill.
- Solo se probó con Haiku y preguntas redactadas como «según el INEI».

**Del análisis** ([informe_final.md, sección 6](informes/informe_final.md#6-limitaciones)): periodos distintos (BCRP 2020-2024 frente a ENAHO solo 2024), IPC de Lima frente a pobreza nacional, sin intervalos de confianza y sin inferencia causal.

## 11. Ejemplo de una ejecución completa

### Activación automática de skills

Evidencia: [evidencias_ia/skills/03_activacion_automatica.txt](evidencias_ia/skills/03_activacion_automatica.txt).

```text
> Haz un mapa de la pobreza monetaria por departamento con ENAHO 2024.
```

1. Claude Code activó **`mapeando-enaho`** sin que se nombrara la skill.
2. Detectó que faltaba `salidas/personas_2024.parquet` y, como indica la skill, activó **`limpiando-enaho`**.
3. La limpieza aprobó las 18 validaciones esenciales y 3 de los 4 controles; el agente avisó del control rural fallido (39.44 % frente a 39.3 %) y explicó que por hogares sí coincide, sin ajustar cifras.
4. Corrió el mapa y revisó la imagen: 25 departamentos unidos por código, con Lima y Callao separados. Tasa más alta: Cajamarca (45.0 %); más baja: Ica (5.9 %).
5. Leyó `salidas/comparacion_mapa.csv`: 11 departamentos coinciden y 14 difieren solo por el método; ninguno queda sin explicar.
6. Entregó `mapas/pobreza_departamento.png`, `salidas/comparacion_mapa.csv` y `salidas/validacion.txt`, con advertencias de lectura (el área no es población, sin márgenes de error, «dónde, no por qué»).

### Investigación de la Parte 3

El [informe final](informes/informe_final.md) responde la pregunta de investigación combinando el MCP y las skills:

- **BCRP** (`PN01273PM`, `PD04722MM`, 2020-01 a 2024-12): la inflación de Lima tuvo su máximo de 8.81 % en 2022-06; la tasa de referencia llegó a 7.75 % en 2023-01, 7 meses después; la correlación entre ambas fue de 0.57 en 60 meses (`comparar_series`).
- **ENAHO 2024**: pobreza rural 39.44 % y urbana 24.74 %, pero el 72.8 % de las personas pobres vivía en el área urbana; Cajamarca tuvo la tasa más alta (44.99 %) y Lima reunió el 32.1 % de las personas pobres.
- Figuras: [figuras/bcrp_inflacion_tasa_2020_2024.png](figuras/bcrp_inflacion_tasa_2020_2024.png), [figuras/pobreza_area.png](figuras/pobreza_area.png) y [mapas/pobreza_departamento.png](mapas/pobreza_departamento.png).
- Tres cifras se verificaron a mano contra la web del BCRP y un recálculo propio (sección «Verificación manual» del informe).

## 12. Evidencias del uso de IA

Carpeta principal: [evidencias_ia/](evidencias_ia/)

| Subcarpeta | Archivos | Contenido |
|---|---|---|
| [evidencias_ia/mcp/](evidencias_ia/mcp/) | [01_desarrollo_servidor.txt](evidencias_ia/mcp/01_desarrollo_servidor.txt), [02_pruebas_en_vivo.txt](evidencias_ia/mcp/02_pruebas_en_vivo.txt) | Desarrollo del servidor MCP y consultas en vivo |
| [evidencias_ia/skills/](evidencias_ia/skills/) | [01_limpiando_enaho.txt](evidencias_ia/skills/01_limpiando_enaho.txt), [02_graficando_y_mapeando.txt](evidencias_ia/skills/02_graficando_y_mapeando.txt), [03_activacion_automatica.txt](evidencias_ia/skills/03_activacion_automatica.txt) | Creación de las skills y su activación automática |
| [evidencias_ia/integracion/](evidencias_ia/integracion/) | [01_investigacion_agente.txt](evidencias_ia/integracion/01_investigacion_agente.txt), [verificacion_bcrp_inflacion.png](evidencias_ia/integracion/verificacion_bcrp_inflacion.png), [verificacion_bcrp_tasa.png](evidencias_ia/integracion/verificacion_bcrp_tasa.png) | Investigación de la Parte 3 y capturas de la verificación manual en la web del BCRP |
| [evidencias_ia/evaluacion/](evidencias_ia/evaluacion/) | [01_diseno_y_analisis.txt](evidencias_ia/evaluacion/01_diseno_y_analisis.txt) | Diseño del experimento con y sin herramientas y su análisis |
