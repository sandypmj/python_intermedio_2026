"""Servidor MCP del BCRP. Empiecen aquí: buscar_series ya funciona; completen los TODO hasta que pasen las pruebas.

    uv run pytest                                           # el contrato: las 10 pruebas deben pasar
    uv run server.py                                        # el servidor, por stdio
    claude mcp add --scope project bcrp -- uv run server.py # conectarlo a Claude Code

Las cuentas las hace Python, no el modelo: así cada cifra sale de una llamada que se puede repetir.
"""
import json
import re
import time
import unicodedata
from datetime import date
from functools import cache
from pathlib import Path
from statistics import StatisticsError, correlation

import httpx
import pandas as pd
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

AQUI = Path(__file__).parent
CATALOGO = AQUI / "datos" / "catalogo_bcrp.csv"
URL_CATALOGO = "https://estadisticas.bcrp.gob.pe/estadisticas/series/metadata"
API = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"
SOLO_LECTURA = {"readOnlyHint": True, "openWorldHint": True}
# la API escribe setiembre como "Set" en las series diarias y como "Sep" en las mensuales
MESES = {"Ene": "01", "Feb": "02", "Mar": "03", "Abr": "04", "May": "05", "Jun": "06", "Jul": "07", "Ago": "08",
         "Sep": "09", "Set": "09", "Oct": "10", "Nov": "11", "Dic": "12"}
FECHAS = {"Mensual": r"(\d{4})-(\d{1,2})", "Trimestral": r"(\d{4})-T?(\d)", "Diaria": r"\d{4}-\d{2}-\d{2}", "Anual": r"\d{4}"}

mcp = FastMCP("bcrp", instructions=(
    "Series oficiales del Banco Central de Reserva del Perú (BCRP). Primero busca el código con buscar_series; "
    "luego usa resumen para variaciones, promedios y extremos, y serie para los datos. No calcules a mano: "
    "cita siempre el código de la serie y el periodo."))


def _sin_tildes(s):
    return unicodedata.normalize("NFD", str(s).lower()).encode("ascii", "ignore").decode()


@cache
def catalogo():
    """El catálogo oficial: 17 mil series en unos 7 MB. Se baja una vez y queda en datos/."""
    if not CATALOGO.exists():
        CATALOGO.parent.mkdir(exist_ok=True)
        r = httpx.get(URL_CATALOGO, timeout=120)
        r.raise_for_status()
        CATALOGO.write_text(r.content.decode("latin-1"), encoding="utf-8")
    df = pd.read_csv(CATALOGO, sep=";", dtype=str).fillna("")
    df = df.rename(columns={"Código de serie": "codigo", "Categoría de serie": "categoria", "Grupo de serie": "grupo",
                            "Nombre de serie": "nombre", "Frecuencia": "frecuencia",
                            "Fecha de actualización": "actualizada", "Fecha de inicio": "inicio"})
    df["texto"] = (df.categoria + " " + df.grupo + " " + df.nombre).map(_sin_tildes)
    return df


def _ficha(codigo):
    fila = catalogo().query("codigo == @codigo")
    if fila.empty:
        raise ToolError(f"No existe el código de serie {codigo!r}. Búsquenlo con buscar_series.")
    f = fila.iloc[0]
    return {"codigo": f.codigo, "nombre": f"{f.grupo} - {f.nombre}", "categoria": f.categoria,
            "frecuencia": f.frecuencia, "inicio": f.inicio, "actualizada": f.actualizada}


@mcp.tool(annotations=SOLO_LECTURA)
def buscar_series(texto: str, frecuencia: str | None = None, limite: int = 10) -> list[dict]:
    """Busca series del BCRP por palabras: todas deben aparecer en la categoría, el grupo o el nombre.

    Ejemplos: "ipc 12 meses", "tipo de cambio interbancario venta", "reservas internacionales netas",
    "tasa de referencia", "cobre precio". frecuencia: "Diaria", "Mensual", "Trimestral" o "Anual".
    Devuelve el código, el nombre completo, la frecuencia y desde cuándo hay datos. Si no hay resultados,
    prueben con menos palabras.
    """
    df = catalogo()
    m = pd.Series(True, index=df.index)
    for palabra in _sin_tildes(texto).split():
        m &= df.texto.str.contains(re.escape(palabra))
    if frecuencia:
        m &= df.frecuencia.str.lower() == frecuencia.lower()
    # primero las series vigentes y, entre ellas, las de nombre más corto (las más generales)
    sel = df[m]
    orden = sel.assign(vieja=sel.actualizada < "2025", largo=(sel.grupo + sel.nombre).str.len())
    return [_ficha(c) for c in orden.sort_values(["vieja", "largo"]).head(limite).codigo]


def _fecha_api(fecha, frecuencia):
    """Pasa una fecha al formato que pide la API: "2025-01" y "2025-T1" se piden como 2025-1."""
    m = re.fullmatch(FECHAS[frecuencia], fecha)
    if not m:
        raise ToolError(f"La fecha {fecha!r} no sirve para una serie {frecuencia.lower()}. Formatos: 2025-01 (mensual), "
                        "2025-T1 (trimestral), 2025-01-15 (diaria), 2025 (anual).")
    return f"{m[1]}-{int(m[2])}" if m.groups() else fecha


def _anio(yy):
    """Completa un año de dos dígitos: "26" es 2026, pero "97" es 1997 porque 2097 todavía no llega."""
    anio = 2000 + int(yy)
    return anio if anio <= date.today().year else anio - 100


def _periodo(nombre, frecuencia):
    """Pasa el nombre que devuelve la API a un periodo uniforme: "2025-01", "2026-10-01", "2025-T1" o "2025"."""
    partes = nombre.split(".")
    if frecuencia == "Mensual":
        return f"{partes[1]}-{MESES[partes[0]]}"
    if frecuencia == "Diaria":
        return f"{_anio(partes[2])}-{MESES[partes[1]]}-{partes[0]}"
    if frecuencia == "Trimestral":
        return f"{_anio(partes[1])}-{partes[0]}"
    return nombre


@cache
def _periodos(url, codigo):
    """Baja los periodos de la API. Si está saturada responde HTML en vez de JSON: se espera y se reintenta."""
    for espera in (0, 5, 10, 20):
        time.sleep(espera)
        try:
            return httpx.get(url, timeout=60, follow_redirects=True).json()["periods"]
        except (ValueError, httpx.HTTPError):  # ValueError: lo que llegó no era JSON
            continue
    raise ToolError(f"La API del BCRP no respondió con datos para {codigo}. Prueben de nuevo en un minuto.")


@mcp.tool(annotations=SOLO_LECTURA)
def serie(codigo: str, desde: str, hasta: str) -> dict:
    """Devuelve los datos oficiales de una serie del BCRP entre dos fechas, ambas incluidas.

    Primero busquen el código con buscar_series, que también dice la frecuencia. Las fechas dependen de ella:
    "2025-01" (mensual), "2025-T1" (trimestral), "2025-01-15" (diaria) o "2025" (anual). Los periodos vuelven en ese
    mismo formato y sin los días que no tienen dato; datos viene vacío si no hay nada en ese rango.
    """
    ficha = _ficha(codigo)
    frecuencia = ficha["frecuencia"]
    url = f"{API}/{codigo}/json/{_fecha_api(desde, frecuencia)}/{_fecha_api(hasta, frecuencia)}"
    datos = [{"periodo": _periodo(p["name"], frecuencia), "valor": float(p["values"][0])}
             for p in _periodos(url, codigo) if p["values"][0] != "n.d."]
    return {"codigo": codigo, "nombre": ficha["nombre"], "frecuencia": frecuencia, "datos": datos, "fuente": url}


@mcp.tool(annotations=SOLO_LECTURA)
def resumen(codigo: str, desde: str, hasta: str) -> dict:
    """Calcula primero, último, cambio, variación, promedio, máximo y mínimo de una serie. No hagan estas cuentas a mano.

    Las fechas van como en serie. cambio está en las unidades de la serie; variacion_pct es ese cambio como porcentaje
    del primer valor (None si ese valor es 0). Si la serie ya es un porcentaje, como el IPC a 12 meses, para hablar de
    puntos porcentuales usen cambio. Da un error si no hay datos en el rango.
    """
    s = serie(codigo, desde, hasta)
    datos = s["datos"]
    if not datos:
        raise ToolError(f"La serie {codigo} no tiene datos entre {desde} y {hasta}. Su ficha dice que empieza en "
                        f"{_ficha(codigo)['inicio']}: prueben con otro rango.")
    primero, ultimo = datos[0], datos[-1]
    cambio = ultimo["valor"] - primero["valor"]
    return {"codigo": codigo, "nombre": s["nombre"], "frecuencia": s["frecuencia"],
            "primero": primero, "ultimo": ultimo, "cambio": cambio,
            # con abs() el signo sigue al del cambio aunque la serie empiece en negativo
            "variacion_pct": cambio / abs(primero["valor"]) * 100 if primero["valor"] else None,
            "promedio": {"periodo": f"{primero['periodo']} a {ultimo['periodo']}",
                         "valor": sum(d["valor"] for d in datos) / len(datos)},
            "maximo": max(datos, key=lambda d: d["valor"]), "minimo": min(datos, key=lambda d: d["valor"]),
            "fuente": s["fuente"]}

def _lado(s, periodos, valores):
    """Lo que comparar_series informa de cada serie, ya recortada a los periodos que coinciden."""
    return {"codigo": s["codigo"], "nombre": s["nombre"], "primero": {"periodo": periodos[0], "valor": valores[0]},
            "ultimo": {"periodo": periodos[-1], "valor": valores[-1]}, "promedio": sum(valores) / len(valores)}


@mcp.tool(annotations=SOLO_LECTURA)
def comparar_series(codigo_a: str, codigo_b: str, desde: str, hasta: str) -> dict:
    """Compara dos series del BCRP de la misma frecuencia y calcula su correlación de Pearson.

    Úsenla para preguntas como "¿el tipo de cambio y las reservas se mueven juntos?"; para una sola serie usen resumen.
    Las fechas van como en serie. Solo se usan los periodos con dato en ambas series, y sobre ellos se calculan la
    correlación, el promedio y el primer y último valor. correlacion va de -1 a 1 y es None si una serie no varía.

    Una correlación no prueba causalidad: dos series pueden moverse juntas por azar o por un tercer factor. No afirmen
    que una causa la otra basándose solo en este resultado. Da un error si las frecuencias son distintas o si hay
    menos de 2 periodos en común.
    """
    frecuencia_a, frecuencia_b = _ficha(codigo_a)["frecuencia"], _ficha(codigo_b)["frecuencia"]
    if frecuencia_a != frecuencia_b:
        raise ToolError(f"No se pueden comparar: {codigo_a} es {frecuencia_a.lower()} y {codigo_b} es "
                        f"{frecuencia_b.lower()}. Elijan dos series de la misma frecuencia.")
    a, b = serie(codigo_a, desde, hasta), serie(codigo_b, desde, hasta)
    valores_b = {d["periodo"]: d["valor"] for d in b["datos"]}
    comunes = [d for d in a["datos"] if d["periodo"] in valores_b]
    if len(comunes) < 2:
        raise ToolError(f"{codigo_a} y {codigo_b} tienen {len(comunes)} periodos con dato en ambas entre {desde} y "
                        f"{hasta}, y se necesitan al menos 2. Prueben con un rango más amplio.")
    periodos = [d["periodo"] for d in comunes]
    xs, ys = [d["valor"] for d in comunes], [valores_b[p] for p in periodos]
    try:
        r = correlation(xs, ys)
    except StatisticsError:  # una de las series no varía
        r = None
    return {"frecuencia": frecuencia_a, "periodos_coincidentes": len(comunes), "correlacion": r,
            "a": _lado(a, periodos, xs), "b": _lado(b, periodos, ys), "fuentes": [a["fuente"], b["fuente"]]}

@mcp.resource("bcrp://serie/{codigo}", mime_type="application/json")
def ficha_serie(codigo: str) -> str:
    """La ficha de una serie del BCRP: nombre, categoría, frecuencia, inicio y última actualización."""
    return json.dumps(_ficha(codigo), ensure_ascii=False)


@mcp.prompt
def informe(tema: str) -> str:
    """Pide un informe breve sobre un tema con cifras del BCRP, cada una con su código de serie y periodo."""
    return (f"Escribe un informe breve sobre {tema} con datos oficiales del BCRP.\n\n"
            "1. Busca los códigos de las series con buscar_series.\n"
            "2. Obtén las cifras con resumen o serie. No hagas cuentas a mano: si necesitas una variación, un promedio "
            "o un extremo, usa resumen.\n"
            "3. Cita junto a cada cifra el código de la serie y el periodo, por ejemplo: "
            "4.55 % (PN01273PM, 2026-09).\n"
            "4. Si relacionas dos series, usa comparar_series y describe solo cómo se mueven juntas. No afirmes que una "
            "causa la otra: una correlación no prueba causalidad.\n"
            "5. Si no encuentras un dato, dilo en vez de estimarlo.")


if __name__ == "__main__":
    mcp.run()
