"""Mapa coroplético de la pobreza por departamento, ENAHO 2024.

Uso, desde la raíz del proyecto:
    uv run python .claude/skills/mapeando-enaho/scripts/mapear.py

Salidas, solo si la unión pasa todas las validaciones:
    mapas/pobreza_departamento.png
    salidas/comparacion_mapa.csv

El mapa pondera con facpob07. La referencia y el cálculo por hogares solo se
comparan: nunca modifican las cifras. Devuelve código 1 si falla una validación.
"""

import argparse
import io
import math
import sys
import urllib.request
import zipfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import patheffects
from matplotlib.cm import ScalarMappable
from matplotlib.colors import LinearSegmentedColormap, Normalize

RAIZ = Path(__file__).resolve().parents[4]

ANIO = 2024
DPI = 200
LEYENDA = "% de personas en pobreza monetaria"
FUENTE = f"Fuente: INEI, ENAHO {ANIO}. Tasas ponderadas con facpob07."
TOLERANCIA_PUNTOS = 0.1

URL_BASE = "https://raw.githubusercontent.com/d2cml-ai/Data-Science-Python/main/sessions"
URL_GEOJSON = f"{URL_BASE}/06-geoespacial/lab/Data/peru_departamental_simple.geojson"
URL_REFERENCIA = f"{URL_BASE}/16-skills-enaho/referencias/pobreza_departamento_2024.csv"

ZIP_SUMARIA = "966-Modulo34.zip"
DTA_SUMARIA = "966-Modulo34/sumaria-2024.dta"

CODIGOS = {f"{i:02d}" for i in range(1, 26)}
LIMA, CALLAO = "15", "07"

# Solo para mostrar: la unión nunca usa estos nombres.
NOMBRES = {
    "01": "Amazonas", "02": "Áncash", "03": "Apurímac", "04": "Arequipa",
    "05": "Ayacucho", "06": "Cajamarca", "07": "Callao", "08": "Cusco",
    "09": "Huancavelica", "10": "Huánuco", "11": "Ica", "12": "Junín",
    "13": "La Libertad", "14": "Lambayeque", "15": "Lima", "16": "Loreto",
    "17": "Madre de Dios", "18": "Moquegua", "19": "Pasco", "20": "Piura",
    "21": "Puno", "22": "San Martín", "23": "Tacna", "24": "Tumbes",
    "25": "Ucayali",
}

# Un solo tono de claro a oscuro; el tono más claro corresponde a 0.
RAMPA = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
COLOR_TEXTO = "#1f1f1d"
COLOR_SECUNDARIO = "#5f5f5a"

# Etiquetas (longitud, latitud) que no caben en el punto interior de su polígono.
POSICIONES = {"15": (-76.3, -11.55), "24": (-81.75, -3.45), "14": (-81.45, -6.85)}
ETIQUETAS_EN_EL_MAR = {"14", "24"}


class ErrorValidacion(Exception):
    """La unión o sus insumos no son confiables: no se genera el mapa."""


def asegurar_archivo(ruta, url):
    if ruta.is_file():
        return
    print(f"Descargando {ruta.name}...")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=60) as respuesta:
        ruta.write_bytes(respuesta.read())


def exigir_texto(serie, ancho, nombre):
    """Un código numérico ya perdió sus ceros: se rechaza, no se repara."""
    ok = pd.api.types.is_string_dtype(serie) and serie.str.fullmatch(rf"\d{{{ancho}}}").all()
    if not ok:
        raise ErrorValidacion(f"{nombre} debe ser texto de {ancho} dígitos.")


def tasas_personas(ruta):
    """Pobreza por departamento: suma(facpob07 de los pobres) / suma(facpob07)."""
    if not ruta.is_file():
        raise ErrorValidacion(f"No existe {ruta}. Usa primero la skill limpiando-enaho.")
    df = pd.read_parquet(ruta, columns=["ubigeo", "pobre", "facpob07"])
    exigir_texto(df["ubigeo"], 6, "ubigeo")
    factor = df["facpob07"]
    if df["pobre"].isna().any() or not (np.isfinite(factor) & (factor > 0)).all():
        raise ErrorValidacion("La base tiene vacíos en pobre o factores inválidos.")

    codigo = df["ubigeo"].str[:2]
    pobres = factor.where(df["pobre"], 0.0).groupby(codigo).sum()
    return (100 * pobres / factor.groupby(codigo).sum()).rename("pobreza_pct")


def unir_por_codigo(ruta_geojson, tasas):
    geo = gpd.read_file(ruta_geojson)
    exigir_texto(geo["FIRST_IDDP"], 2, "FIRST_IDDP")
    if not geo.geometry.is_valid.all() or geo.geometry.is_empty.any():
        raise ErrorValidacion("El GeoJSON tiene geometrías inválidas o vacías.")

    datos = tasas.rename_axis("FIRST_IDDP").reset_index()
    try:
        mapa = geo.merge(datos, on="FIRST_IDDP", how="outer", validate="1:1", indicator=True)
    except pd.errors.MergeError as error:
        raise ErrorValidacion(f"Hay códigos repetidos en la unión: {error}") from error

    sin_par = mapa.loc[mapa["_merge"] != "both", "FIRST_IDDP"].tolist()
    if sin_par:
        raise ErrorValidacion(f"Códigos sin par entre la base y el GeoJSON: {sin_par}")
    con_dato = int(mapa["pobreza_pct"].notna().sum())
    if set(mapa["FIRST_IDDP"]) != CODIGOS or con_dato != len(CODIGOS):
        raise ErrorValidacion(f"Se exigen 25 departamentos con dato; hay {con_dato}.")
    geometrias = mapa.set_index("FIRST_IDDP").geometry
    if geometrias[LIMA].equals(geometrias[CALLAO]):
        raise ErrorValidacion("Lima (15) y Callao (07) deben ser geometrías separadas.")
    return mapa.drop(columns="_merge")


def tasas_hogares(ruta_zip):
    """Mismo cálculo con la sumaria y factor07 x mieperho. Solo para comparar."""
    with zipfile.ZipFile(ruta_zip) as z, z.open(DTA_SUMARIA) as f:
        sumaria = pd.read_stata(io.BytesIO(f.read()), convert_categoricals=False)
    sumaria.columns = sumaria.columns.str.lower()
    exigir_texto(sumaria["ubigeo"], 6, "ubigeo de la sumaria")
    codigo = sumaria["ubigeo"].str[:2]
    peso = sumaria["factor07"].astype("float64") * sumaria["mieperho"]
    pobres = peso.where(sumaria["pobreza"] <= 2, 0.0).groupby(codigo).sum()
    return 100 * pobres / peso.groupby(codigo).sum()


def clasificar(fila):
    if abs(fila["dif_personas"]) <= TOLERANCIA_PUNTOS:
        return "coincide"
    if pd.isna(fila["dif_hogares"]):
        return "sin_verificar"
    if abs(fila["dif_hogares"]) <= TOLERANCIA_PUNTOS:
        return "explicada_por_metodo"
    return "no_explicada"


def comparar(tasas, ruta_referencia, ruta_zip):
    ref = pd.read_csv(ruta_referencia, dtype={"ccdd": str})
    exigir_texto(ref["ccdd"], 2, "ccdd de la referencia")
    if set(ref["ccdd"]) != CODIGOS or ref["ccdd"].duplicated().any():
        raise ErrorValidacion("La referencia debe tener los 25 códigos, sin repetir.")

    tabla = ref.rename(columns={"pobreza_pct": "referencia_pct"}).set_index("ccdd")
    tabla["personas_pct"] = tasas.reindex(tabla.index)
    tabla["dif_personas"] = (tabla["personas_pct"] - tabla["referencia_pct"]).round(2) + 0.0

    # Se calcula por hogares solo si hay diferencias que explicar.
    tabla["hogares_pct"] = np.nan
    hay_diferencias = (tabla["dif_personas"].abs() > TOLERANCIA_PUNTOS).any()
    if hay_diferencias and ruta_zip.is_file():
        tabla["hogares_pct"] = tasas_hogares(ruta_zip).reindex(tabla.index)
    tabla["dif_hogares"] = (tabla["hogares_pct"] - tabla["referencia_pct"]).round(2) + 0.0
    tabla["estado"] = tabla.apply(clasificar, axis=1)

    tabla["personas_pct"] = tabla["personas_pct"].round(2)
    tabla["hogares_pct"] = tabla["hogares_pct"].round(2)
    columnas = ["departamento", "referencia_pct", "personas_pct", "dif_personas",
                "hogares_pct", "dif_hogares", "estado"]
    return tabla[columnas].reset_index()


def dibujar(mapa, ruta):
    cmap = LinearSegmentedColormap.from_list("azules", RAMPA)
    tope = math.ceil(mapa["pobreza_pct"].max() / 10) * 10
    norm = Normalize(vmin=0, vmax=tope)
    colores = [cmap(norm(v)) for v in mapa["pobreza_pct"]]
    indice = mapa.set_index("FIRST_IDDP")

    fig, ax = plt.subplots(figsize=(8.5, 10.5))
    fig.patch.set_facecolor("white")
    mapa.plot(ax=ax, color=colores, edgecolor="white", linewidth=0.7)
    x_min, x_max = ax.get_xlim()
    ax.set_xlim(x_min - 1.0, x_max)  # Espacio para las etiquetas en el mar.
    ax.set_axis_off()

    # El halo blanco mantiene el texto legible sobre cualquier tono.
    halo = [patheffects.withStroke(linewidth=2, foreground="white")]
    linea_guia = {"arrowstyle": "-", "color": COLOR_SECUNDARIO, "linewidth": 0.6}
    for codigo, fila in indice.iterrows():
        if codigo == CALLAO:  # Demasiado pequeño: se rotula en el recuadro.
            continue
        punto = fila.geometry.representative_point()
        ax.annotate(
            f"{NOMBRES[codigo]}\n{fila['pobreza_pct']:.1f}",
            xy=(punto.x, punto.y), xytext=POSICIONES.get(codigo, (punto.x, punto.y)),
            ha="center", va="center", fontsize=7.5, linespacing=1.05,
            color=COLOR_TEXTO, path_effects=halo,
            arrowprops=linea_guia if codigo in ETIQUETAS_EN_EL_MAR else None,
        )

    # Recuadro: Callao no se distingue a escala nacional.
    callao = indice.loc[CALLAO, "geometry"]
    x0, y0, x1, y1 = callao.bounds
    margen = 0.12
    recuadro = ax.inset_axes([0.0, 0.05, 0.3, 0.27])
    mapa.plot(ax=recuadro, color=colores, edgecolor="white", linewidth=1)
    recuadro.set_xlim(x0 - margen, x1 + margen * 2)
    recuadro.set_ylim(y0 - margen, y1 + margen)
    recuadro.set_xticks([])
    recuadro.set_yticks([])
    recuadro.set_xlabel("")
    recuadro.set_ylabel("")
    recuadro.set_title("Lima y Callao", fontsize=9, color=COLOR_TEXTO)
    for lado in recuadro.spines.values():
        lado.set_color(COLOR_SECUNDARIO)
        lado.set_linewidth(0.6)
    recuadro.text(
        0.72, 0.5, f"Lima\n{indice.loc[LIMA, 'pobreza_pct']:.1f}", transform=recuadro.transAxes,
        ha="center", va="center", fontsize=9, color=COLOR_TEXTO, path_effects=halo,
    )
    punto_callao = callao.representative_point()
    recuadro.annotate(
        f"Callao\n{indice.loc[CALLAO, 'pobreza_pct']:.1f}",
        xy=(punto_callao.x, punto_callao.y), xytext=(0.15, 0.5), textcoords="axes fraction",
        ha="center", va="center", fontsize=9, color=COLOR_TEXTO, arrowprops=linea_guia,
    )
    ax.indicate_inset_zoom(recuadro, edgecolor=COLOR_SECUNDARIO, alpha=0.8)

    barra = fig.colorbar(
        ScalarMappable(norm=norm, cmap=cmap), ax=ax, shrink=0.45, pad=0.02, aspect=28,
    )
    barra.set_label(LEYENDA, color=COLOR_TEXTO, fontsize=10)
    barra.outline.set_visible(False)
    barra.ax.tick_params(colors=COLOR_SECUNDARIO, length=0)

    alto, bajo = indice["pobreza_pct"].idxmax(), indice["pobreza_pct"].idxmin()
    fig.suptitle(
        f"En {ANIO}, la pobreza fue más alta en {NOMBRES[alto]} "
        f"({indice.loc[alto, 'pobreza_pct']:.1f} %)\n"
        f"y más baja en {NOMBRES[bajo]} ({indice.loc[bajo, 'pobreza_pct']:.1f} %)",
        x=0.04, y=0.975, ha="left", fontsize=14, fontweight="bold", color=COLOR_TEXTO,
    )
    fig.text(0.04, 0.02, FUENTE, fontsize=9, color=COLOR_SECUNDARIO)
    fig.subplots_adjust(left=0.02, right=0.98, top=0.91, bottom=0.05)
    fig.savefig(ruta, dpi=DPI, facecolor="white")
    plt.close(fig)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Mapea la pobreza de la ENAHO 2024.")
    parser.add_argument("--personas", type=Path, default=RAIZ / "salidas" / "personas_2024.parquet")
    parser.add_argument("--datos", type=Path, default=RAIZ / "datos")
    parser.add_argument("--referencias", type=Path, default=RAIZ / "referencias")
    parser.add_argument("--salidas", type=Path, default=RAIZ / "salidas")
    parser.add_argument("--mapas", type=Path, default=RAIZ / "mapas")
    args = parser.parse_args(argv)

    ruta_mapa = args.mapas / "pobreza_departamento.png"
    ruta_comparacion = args.salidas / "comparacion_mapa.csv"
    ruta_geojson = args.datos / "peru_departamental_simple.geojson"
    ruta_referencia = args.referencias / "pobreza_departamento_2024.csv"

    # Si esta corrida falla, no deben quedar productos de una corrida anterior.
    ruta_mapa.unlink(missing_ok=True)
    ruta_comparacion.unlink(missing_ok=True)

    try:
        asegurar_archivo(ruta_geojson, URL_GEOJSON)
        asegurar_archivo(ruta_referencia, URL_REFERENCIA)
        tasas = tasas_personas(args.personas)
        mapa = unir_por_codigo(ruta_geojson, tasas)
        comparacion = comparar(tasas, ruta_referencia, args.datos / ZIP_SUMARIA)
    except (ErrorValidacion, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        print("No se generaron el mapa ni la comparación.", file=sys.stderr)
        return 1

    args.mapas.mkdir(parents=True, exist_ok=True)
    args.salidas.mkdir(parents=True, exist_ok=True)
    dibujar(mapa, ruta_mapa)
    comparacion.to_csv(ruta_comparacion, index=False, encoding="utf-8")

    print(f"Unión por código: {mapa['pobreza_pct'].notna().sum()} departamentos con dato")
    print(f"Lima (15): {tasas[LIMA]:.2f} %   Callao (07): {tasas[CALLAO]:.2f} %")
    print(f"Guardado: {ruta_mapa}")
    print(f"Guardado: {ruta_comparacion}\n")
    print(comparacion.to_string(index=False))
    print("\nEstados:", comparacion["estado"].value_counts().to_dict())

    pendientes = comparacion[comparacion["estado"].isin(["no_explicada", "sin_verificar"])]
    if not pendientes.empty:
        print(
            "ADVERTENCIA: diferencias sin explicar o sin verificar en: "
            + ", ".join(pendientes["ccdd"]),
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
