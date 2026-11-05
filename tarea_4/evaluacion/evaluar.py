"""Parte 4: ¿mejora Claude con el MCP del BCRP y las skills de la ENAHO? Mismas preguntas, con y sin herramientas.

Adaptado de sessions/04-mcp-claude-code/proyecto/evaluar.py (d2cml-ai/Data-Science-Python).

    uv run evaluacion/evaluar.py                      # las 10 preguntas, modos sin y con, con Haiku
    uv run evaluacion/evaluar.py --solo bcrp_pbi_2025 # repite una pregunta y actualiza sus filas
    uv run evaluacion/evaluar.py --modelo sonnet --modos con

Modo «sin»: claude -p sin herramientas (--tools "") ni MCP (--strict-mcp-config), desde una carpeta temporal
vacía, para que no cargue CLAUDE.md, las skills, la memoria ni el estado git de tarea_4.
Modo «con»: desde la raíz de tarea_4, con el MCP bcrp, Skill, Bash, Read, Glob y Grep. Las rutas que contienen
las respuestas (evaluacion/, informes/, evidencias_ia/, notas_proceso.md, referencias/) quedan bloqueadas,
y cualquier lectura de ellas o de los valores de referencia de las skills se marca en «acceso_indebido»
sin cambiar la calificación.

Escribe evaluacion/resultados.csv, los registros crudos en evaluacion/registros/ y evaluacion/comparacion.md.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import pandas as pd

AQUI = Path(__file__).resolve().parent          # tarea_4/evaluacion
RAIZ = AQUI.parent                              # tarea_4
REGISTROS = AQUI / "registros"
MARCA_ANALISIS = "<!-- ANALISIS: todo lo que escribas debajo de esta línea se conserva al regenerar el archivo -->"

ESQUEMA = {
    "type": "object",
    "required": ["valor", "valor_2", "fuente", "interpretacion"],
    "properties": {
        "valor": {"type": ["number", "null"]},
        "valor_2": {"type": ["number", "null"]},
        "fuente": {"type": "string"},
        "interpretacion": {"type": "string"},
    },
}
INSTRUCCION = (
    "Responde en JSON. En «valor» pon un solo número, en la unidad que pide la pregunta. Si la pregunta pide una "
    "segunda cifra (valor_2), ponla en «valor_2»; si no la pide, pon valor_2 null. Si no puedes saber una cifra "
    "con certeza, pon null: no estimes. En «fuente» di de dónde sale cada cifra (institución, serie o archivo y "
    "periodo). En «interpretacion» escribe 1 a 3 frases; si la pregunta pide una explicación, va ahí.\n\n"
)

# Rutas con las respuestas o con cifras de referencia: el modo «con» no debe leerlas.
BLOQUEADAS = ["evaluacion", "informes", "evidencias_ia", "notas_proceso.md", "referencias"]
DENEGAR = [f"Read(./{r}/**)" for r in BLOQUEADAS if not r.endswith(".md")] + ["Read(./notas_proceso.md)"]
DENEGAR += [f"Bash(*{r.removesuffix('.md')}*)" for r in BLOQUEADAS]
HERRAMIENTAS_CON = "Skill,Bash,Read,Glob,Grep"
SKILLS_PROYECTO = {d.name for d in (RAIZ / ".claude" / "skills").iterdir() if d.is_dir()}

MODOS = {
    "sin": ["--tools", "", "--strict-mcp-config"],
    "con": ["--tools", HERRAMIENTAS_CON, "--strict-mcp-config", "--mcp-config", str(RAIZ / ".mcp.json"),
            "--allowedTools", "mcp__bcrp," + HERRAMIENTAS_CON, "--disallowedTools", *DENEGAR],
}

# Detección de accesos indebidos (no cambia la calificación).
RE_RUTA = re.compile(r"(?:^|[/\s'\"=(:-])(evaluacion|informes|evidencias_ia|referencias|notas_proceso)(?=[/\s'\")*.]|$)")
RE_RUTA_EN_SALIDA = re.compile(r"(?:evaluacion|informes|evidencias_ia|referencias)[/\\][^\s:]+:\S|notas_proceso\.md:\S")
RE_EJECUTA_LIMPIAR = re.compile(r"(?:uv\s+run|python[\w.]*)\s+(?:\S+\s+)*?\S*limpiar\.py")
RE_FUENTE_REF = re.compile(r"REF_[A-Z_]+\s*=\s*\d|fuente_verdad|tolerancia_2")
RE_REF_VISIBLE = re.compile(r"referencia_pct|referencia\s*[:=]?\s*\d+(?:[.,]\d+)?\s*%")
NIVELES = ["no", "intento bloqueado", "referencia visible", "sí"]   # de menor a mayor gravedad

RESULTADOS = ["correcta", "parcial", "incorrecta", "no contesta", "error"]
PUNTAJE = {"correcta": 3, "parcial": 2, "no contesta": 1, "incorrecta": 0}   # «error» no se compara


# --------------------------------------------------------------------------- llamada a claude -p

def texto_de(contenido):
    if isinstance(contenido, str):
        return contenido
    if isinstance(contenido, list):
        return "\n".join(texto_de(c.get("text", c.get("content", ""))) if isinstance(c, dict) else str(c)
                         for c in contenido)
    return "" if contenido is None else str(contenido)


def relativa(texto):
    """Quita la ruta absoluta de tarea_4 para que el registro sea legible."""
    for base in {str(RAIZ), RAIZ.as_posix()}:
        texto = re.sub(re.escape(base) + r"[\\/]?", "", texto, flags=re.IGNORECASE)
    return texto


def describir(nombre, entrada):
    e = entrada or {}
    if nombre.startswith("mcp__"):
        args = ", ".join(f"{k}={v}" for k, v in e.items())
        corto = nombre.replace("mcp__", "").replace("__", ".")
        return f"{corto}({args})"
    clave = {"Read": "file_path", "Bash": "command", "Skill": "skill", "Glob": "pattern"}.get(nombre)
    if nombre == "Grep":
        detalle = f"{e.get('pattern', '')} en {e.get('path', '.')}"
    else:
        detalle = str(e.get(clave, json.dumps(e, ensure_ascii=False)))
    detalle = relativa(detalle).replace("\n", " ")
    return f"{nombre}({detalle[:160]})"


def leer_eventos(lineas):
    """De stream-json saca la respuesta final, el evento init y cada herramienta con su resultado."""
    init, final, usos, por_id = {}, {}, [], {}
    for linea in lineas:
        try:
            ev = json.loads(linea)
        except json.JSONDecodeError:
            continue
        tipo = ev.get("type")
        if tipo == "system" and ev.get("subtype") == "init":
            init = ev
        elif tipo == "assistant":
            for c in ev.get("message", {}).get("content", []):
                if c.get("type") == "tool_use" and c.get("name") != "StructuredOutput":   # es la respuesta final
                    uso = {"nombre": c.get("name", ""), "entrada": c.get("input", {}), "salida": "", "error": False}
                    usos.append(uso)
                    por_id[c.get("id")] = uso
        elif tipo == "user":
            contenido = ev.get("message", {}).get("content", [])
            for c in contenido if isinstance(contenido, list) else []:
                if c.get("type") == "tool_result" and c.get("tool_use_id") in por_id:
                    por_id[c["tool_use_id"]].update(salida=texto_de(c.get("content")), error=bool(c.get("is_error")))
        elif tipo == "result":
            final = ev
    return init, final, usos


def detectar(usos):
    """Devuelve (nivel, detalles) de acceso indebido según lo que pidió y lo que recibió cada herramienta."""
    hallazgos = []
    for u in usos:
        entrada = json.dumps(u["entrada"], ensure_ascii=False).replace("\\\\", "/").replace("\\", "/").lower()
        etiqueta = describir(u["nombre"], u["entrada"])
        denegado = u["error"] and re.search(r"permission|denied|not allowed|deny|permiso", u["salida"], re.I)
        motivos = []
        if RE_RUTA.search(entrada):
            motivos.append("ruta bloqueada")
        if "reference.md" in entrada:
            motivos.append("lee reference.md (cifras de referencia)")
        if "limpiar.py" in entrada and not (u["nombre"] == "Bash" and RE_EJECUTA_LIMPIAR.search(entrada)):
            motivos.append("lee limpiar.py (constantes REF_*)")
        if motivos:
            hallazgos.append(("intento bloqueado" if denegado else "sí", f"{etiqueta}: {', '.join(motivos)}"))
        if u["salida"] and not denegado:
            if RE_RUTA_EN_SALIDA.search(u["salida"]) or RE_FUENTE_REF.search(u["salida"]):
                hallazgos.append(("sí", f"{etiqueta}: la salida muestra contenido de una ruta bloqueada o REF_*"))
            elif RE_REF_VISIBLE.search(u["salida"]):
                hallazgos.append(("referencia visible", f"{etiqueta}: la salida muestra un valor de referencia"))
    if not hallazgos:
        return "no", ""
    nivel = max((h[0] for h in hallazgos), key=NIVELES.index)
    return nivel, " | ".join(h[1] for h in hallazgos)


def extraer_json(texto):
    m = re.search(r"\{.*\}", texto or "", re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


def numero(x):
    if x is None or isinstance(x, bool):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def preguntar(q, modo, modelo, timeout):
    cmd = ["claude", "-p", INSTRUCCION + q.pregunta, "--output-format", "stream-json", "--verbose",
           "--json-schema", json.dumps(ESQUEMA), "--no-session-persistence", "--model", modelo, *MODOS[modo]]
    carpeta = Path(tempfile.mkdtemp(prefix="eval_sin_")) if modo == "sin" else RAIZ
    t = time.time()
    error, stdout = "", ""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=timeout, cwd=carpeta)
        stdout = proc.stdout
        if proc.returncode != 0:
            error = f"código {proc.returncode}: {(proc.stderr or proc.stdout)[-300:]}"
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        error = f"tiempo agotado ({timeout} s)"
    finally:
        if modo == "sin":
            shutil.rmtree(carpeta, ignore_errors=True)
    segundos = round(time.time() - t, 1)

    REGISTROS.mkdir(exist_ok=True)
    (REGISTROS / f"{q.id}__{modo}.jsonl").write_text(stdout, encoding="utf-8")

    init, final, usos = leer_eventos(stdout.splitlines())
    r = final.get("structured_output") or extraer_json(final.get("result", ""))
    if final.get("is_error") and not error:
        error = f"{final.get('subtype', 'error')}: {str(final.get('result', ''))[:300]}"
    if not final and not error:
        error = "sin evento result en stream-json"
    if not r and not error:
        error = "la respuesta no trae el JSON pedido"
    if modo == "sin" and init:
        # StructuredOutput es la herramienta interna con la que --json-schema devuelve el JSON.
        herramientas = [h for h in init.get("tools", []) if h != "StructuredOutput"]
        del_proyecto = sorted(set(init.get("skills", [])) & SKILLS_PROYECTO)
        if herramientas or init.get("mcp_servers") or del_proyecto:
            error = (error + " | " if error else "") + (f"aislamiento roto: tools={herramientas}, "
                                                        f"mcp={init.get('mcp_servers')}, skills={del_proyecto}")
    nivel, detalle = detectar(usos)
    return {
        "valor": numero(r.get("valor")), "valor_2": numero(r.get("valor_2")),
        "fuente": str(r.get("fuente", "")), "interpretacion": str(r.get("interpretacion", "")),
        "herramientas": " ; ".join(describir(u["nombre"], u["entrada"]) + (" [denegado]" if u["error"] else "")
                                   for u in usos),
        "acceso_indebido": nivel, "detalle_acceso": detalle,
        "segundos": segundos, "error": error,
    }


# --------------------------------------------------------------------------- calificación

def dentro(valor, verdad, tolerancia):
    return valor is not None and abs(valor - verdad) <= tolerancia + 1e-9


def calificar(q, r):
    if r["error"] and r["valor"] is None and r["valor_2"] is None:
        return "error"
    if q.tipo != "mixta" or pd.isna(q.verdad_2):
        if r["valor"] is None:
            return "no contesta"
        return "correcta" if dentro(r["valor"], q.verdad, q.tolerancia) else "incorrecta"
    aciertos = dentro(r["valor"], q.verdad, q.tolerancia) + dentro(r["valor_2"], q.verdad_2, q.tolerancia_2)
    if aciertos == 2:
        return "correcta"
    if aciertos == 1:
        return "parcial"
    return "no contesta" if r["valor"] is None and r["valor_2"] is None else "incorrecta"


def cifras(*valores):
    return "; ".join("null" if v is None or pd.isna(v) else f"{v:g}" for v in valores)


# --------------------------------------------------------------------------- comparacion.md

def tabla_md(df):
    df = df.reset_index() if df.index.name or isinstance(df.index, pd.MultiIndex) else df
    limpiar = lambda x: str(x).replace("|", "\\|").replace("\n", " ")
    filas = ["| " + " | ".join(limpiar(c) for c in df.columns) + " |", "|" + "---|" * len(df.columns)]
    filas += ["| " + " | ".join(limpiar(v) for v in fila) + " |" for fila in df.itertuples(index=False)]
    return "\n".join(filas)


def conteo(res, por):
    t = res.groupby(por).resultado.value_counts().unstack(fill_value=0)
    t = t.reindex(columns=RESULTADOS, fill_value=0)
    t["total"] = t.sum(axis=1)
    t["% correctas"] = (100 * t["correcta"] / t["total"]).round(0).astype(int).astype(str) + " %"
    return t


def tiempos(res):
    t = res.pivot_table(index="tipo", columns="modo", values="segundos", aggfunc="mean")
    t.loc["todas"] = res.groupby("modo").segundos.mean()
    t = t.round(1).reindex(columns=[m for m in MODOS if m in t.columns])
    t.columns.name = None
    return t.rename_axis("tipo")


def escribir_comparacion(res, preguntas):
    destino = AQUI / "comparacion.md"
    analisis_previo = ""
    if destino.exists():
        previo = destino.read_text(encoding="utf-8")
        if MARCA_ANALISIS in previo:
            analisis_previo = previo.split(MARCA_ANALISIS, 1)[1].strip("\n")
    if not analisis_previo:
        analisis_previo = PLANTILLA_ANALISIS

    orden = {i: n for n, i in enumerate(preguntas.id)}
    modelos = ", ".join(sorted(res.modelo.dropna().unique()))
    partes = [
        "# Parte 4: evaluación con y sin herramientas",
        "",
        f"Generado por `evaluacion/evaluar.py` el {datetime.now():%Y-%m-%d %H:%M}. Modelo: **{modelos}**. "
        f"Preguntas evaluadas: {res.id.nunique()} de {len(preguntas)}. Filas: {len(res)}.",
        "",
        "Cada pregunta se hizo en una sesión nueva de `claude -p` (`--no-session-persistence`), con el mismo modelo "
        "en ambos modos. Las respuestas esperadas y sus tolerancias se fijaron en `preguntas.csv` antes de correr "
        "el experimento y no se modificaron después.",
        "",
        BARRERAS,
        "",
        "## Aciertos por modo",
        "",
        tabla_md(conteo(res, "modo")),
        "",
        "## Aciertos por tipo de pregunta y modo",
        "",
        tabla_md(conteo(res, ["tipo", "modo"])),
        "",
        "## Tiempo promedio por respuesta (segundos)",
        "",
        tabla_md(tiempos(res)),
        "",
    ]

    if {"sin", "con"} <= set(res.modo):
        ancho = res.pivot_table(index="id", columns="modo", values=["resultado", "generada"], aggfunc="first")
        ancho.columns = [f"{v}_{m}" for v, m in ancho.columns]
        ancho = ancho.dropna(subset=["resultado_sin", "resultado_con"])
        ancho = ancho.loc[sorted(ancho.index, key=orden.get)]

        def cambio(f):
            a, b = f.resultado_sin, f.resultado_con
            if "error" in (a, b):
                return "con error"
            return "mejoró" if PUNTAJE[b] > PUNTAJE[a] else "empeoró" if PUNTAJE[b] < PUNTAJE[a] else "igual"

        ancho["cambio"] = ancho.apply(cambio, axis=1)
        esperadas = res.drop_duplicates("id").set_index("id").esperada
        detalle = pd.DataFrame({
            "id": ancho.index, "esperada": esperadas.reindex(ancho.index).values,
            "sin: cifra": ancho.generada_sin.values, "sin: resultado": ancho.resultado_sin.values,
            "con: cifra": ancho.generada_con.values, "con: resultado": ancho.resultado_con.values,
            "cambio": ancho.cambio.values})
        partes += [
            "## Preguntas que mejoraron o empeoraron",
            "",
            "Orden usado: correcta > parcial > no contesta > incorrecta. Responder `null` (reconocer que no sabe) "
            "se considera mejor que dar una cifra equivocada. Las filas con «error» no se comparan.",
            "",
            tabla_md(detalle),
            "",
            "Resumen: " + ", ".join(f"{k}: {v}" for k, v in detalle.cambio.value_counts().items()) + ".",
            "",
        ]

    con = res[res.modo == "con"]
    if len(con):
        partes += [
            "## Herramientas usadas en el modo «con»",
            "",
            tabla_md(con[["id", "herramientas"]].assign(herramientas=con.herramientas.fillna("").replace("", "(ninguna)"))),
            "",
        ]
    accesos = res[res.acceso_indebido.fillna("no") != "no"]
    partes += ["## Accesos indebidos detectados", ""]
    partes += [tabla_md(accesos[["id", "modo", "acceso_indebido", "resultado", "detalle_acceso"]]) if len(accesos)
               else "Ninguno: ninguna respuesta leyó rutas bloqueadas ni valores de referencia de las skills.", ""]
    errores = res[res.error.fillna("") != ""]
    if len(errores):
        partes += ["## Errores de ejecución", "", tabla_md(errores[["id", "modo", "error"]]), ""]

    partes += [MARCA_ANALISIS, "", analisis_previo, ""]
    destino.write_text("\n".join(partes), encoding="utf-8")


BARRERAS = """## Barreras del experimento

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
- La configuración del usuario (`~/.claude`) se carga en ambos modos por igual."""

PLANTILLA_ANALISIS = """## Mi análisis

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

_(Pendiente)_"""


# --------------------------------------------------------------------------- principal

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--modos", nargs="+", default=["sin", "con"], choices=list(MODOS))
    p.add_argument("--modelo", default="haiku")
    p.add_argument("--preguntas", default=str(AQUI / "preguntas.csv"))
    p.add_argument("--solo", help="id de una pregunta: la repite y reemplaza solo sus filas en resultados.csv")
    p.add_argument("--paralelo", type=int, default=1,
                   help="llamadas simultáneas (1 por defecto: las skills escriben en salidas/)")
    p.add_argument("--timeout", type=int, default=900, help="segundos máximos por llamada")
    a = p.parse_args()
    if "con" in a.modos and not (RAIZ / ".mcp.json").exists():
        raise SystemExit(f"Falta {RAIZ / '.mcp.json'}.")

    preguntas = pd.read_csv(a.preguntas, encoding="utf-8")
    seleccion = preguntas[preguntas.id == a.solo] if a.solo else preguntas
    if seleccion.empty:
        raise SystemExit(f"No existe la pregunta «{a.solo}». Ids: {', '.join(preguntas.id)}")

    casos = [(q, m) for q in seleccion.itertuples() for m in a.modos]
    print(f"{len(casos)} llamadas a claude -p con {a.modelo}...")

    def correr(caso):
        q, m = caso
        r = preguntar(q, m, a.modelo, a.timeout)
        resultado = calificar(q, r)
        print(f"  {q.id:<26} {m:<4} {resultado:<12} {r['segundos']:>6} s  acceso: {r['acceso_indebido']}"
              + (f"  ERROR: {r['error'][:80]}" if r["error"] else ""), flush=True)
        mixta = q.tipo == "mixta" and not pd.isna(q.verdad_2)
        return {
            "id": q.id, "tipo": q.tipo, "modo": m, "modelo": a.modelo, "pregunta": q.pregunta,
            "esperada": cifras(q.verdad, q.verdad_2) if mixta else cifras(q.verdad),
            "generada": cifras(r["valor"], r["valor_2"]) if mixta else cifras(r["valor"]),
            "fuente": r["fuente"], "herramientas": r["herramientas"], "resultado": resultado,
            "segundos": r["segundos"], "error": r["error"], "interpretacion": r["interpretacion"],
            "acceso_indebido": r["acceso_indebido"], "detalle_acceso": r["detalle_acceso"],
        }

    with ThreadPoolExecutor(a.paralelo) as ex:
        nuevas = pd.DataFrame(list(ex.map(correr, casos)))

    archivo = AQUI / "resultados.csv"
    if archivo.exists():
        previas = pd.read_csv(archivo, encoding="utf-8-sig", keep_default_na=False, na_values=[""])
        clave = set(zip(nuevas.id, nuevas.modo))
        previas = previas[[(i, m) not in clave for i, m in zip(previas.id, previas.modo)]]
        res = pd.concat([previas, nuevas], ignore_index=True)
    else:
        res = nuevas
    orden = {i: n for n, i in enumerate(preguntas.id)}
    res = res.sort_values(["id", "modo"], key=lambda s: s.map(orden) if s.name == "id" else s.map({"sin": 0, "con": 1}))
    res.to_csv(archivo, index=False, encoding="utf-8-sig")
    escribir_comparacion(res, preguntas)

    print("\n" + conteo(res, "modo").to_string())
    print(f"\nGuardado: {archivo.relative_to(RAIZ)}, evaluacion/comparacion.md y evaluacion/registros/")
