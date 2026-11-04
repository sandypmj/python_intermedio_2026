"""Grafica la pobreza monetaria de la ENAHO 2024, ponderada con facpob07.

Uso, desde la raíz del proyecto:
    uv run python .claude/skills/graficando-enaho/scripts/graficar.py

Salidas en figuras/ (PNG a 200 dpi):
    pobreza_area.png  pobreza_sexo.png  pobreza_departamento.png

Devuelve código 1, sin generar figuras, si la base falta o no es válida.
"""

import argparse
import sys
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[4]

ANIO = 2024
DPI = 200
FUENTE = f"Fuente: INEI, ENAHO {ANIO}. Tasas ponderadas con facpob07."
UNIDAD = "% de personas en pobreza monetaria"
DIFERENCIA_MINIMA = 1.0  # Puntos: por debajo, el título no presenta una brecha.

COLOR_BARRA = "#2a78d6"
COLOR_TEXTO = "#1f1f1d"
COLOR_SECUNDARIO = "#5f5f5a"
COLOR_GUIA = "#d9d8d3"

COLUMNAS = ["ubigeo", "area", "sexo", "pobre", "facpob07"]

# Solo para mostrar: el grupo sigue siendo el código.
NOMBRES = {
    "01": "Amazonas", "02": "Áncash", "03": "Apurímac", "04": "Arequipa",
    "05": "Ayacucho", "06": "Cajamarca", "07": "Callao", "08": "Cusco",
    "09": "Huancavelica", "10": "Huánuco", "11": "Ica", "12": "Junín",
    "13": "La Libertad", "14": "Lambayeque", "15": "Lima", "16": "Loreto",
    "17": "Madre de Dios", "18": "Moquegua", "19": "Pasco", "20": "Piura",
    "21": "Puno", "22": "San Martín", "23": "Tacna", "24": "Tumbes",
    "25": "Ucayali",
}


class ErrorDatos(Exception):
    """La base no permite calcular tasas confiables."""


def cargar(ruta):
    if not ruta.is_file():
        raise ErrorDatos(f"No existe {ruta}. Usa primero la skill limpiando-enaho.")
    df = pd.read_parquet(ruta, columns=COLUMNAS)

    factor = df["facpob07"]
    if df[COLUMNAS].isna().any().any() or not (np.isfinite(factor) & (factor > 0)).all():
        raise ErrorDatos("La base tiene vacíos o factores inválidos en las columnas usadas.")
    if not df["ubigeo"].str.fullmatch(r"\d{6}").all():
        raise ErrorDatos("ubigeo debe ser texto de 6 dígitos.")

    df["codigo"] = df["ubigeo"].str[:2]
    grupos = (
        ("area", {"Urbana", "Rural"}),
        ("sexo", {"Hombre", "Mujer"}),
        ("codigo", set(NOMBRES)),
    )
    for columna, esperados in grupos:
        if set(df[columna]) != esperados:
            raise ErrorDatos(f"Valores inesperados en {columna}: {sorted(set(df[columna]))}")
    return df


def tasa(df):
    """Pobreza en %: suma(facpob07 de los pobres) / suma(facpob07)."""
    return 100 * df.loc[df["pobre"], "facpob07"].sum() / df["facpob07"].sum()


def tasas_por(df, columna):
    """Tasa ponderada de cada grupo, de mayor a menor."""
    tasas = {grupo: tasa(parte) for grupo, parte in df.groupby(columna)}
    return pd.Series(tasas).sort_values(ascending=False)


def pct(valor):
    return f"{valor:.1f} %"  # Espacio duro: el % no se separa de su cifra.


def rotular(ax, barras, etiquetas, **formato):
    """Valores con fondo blanco, para que la línea nacional no los cruce."""
    textos = ax.bar_label(barras, labels=etiquetas, padding=4, color=COLOR_TEXTO, **formato)
    for texto in textos:
        texto.set_bbox({"facecolor": "white", "edgecolor": "none", "pad": 1})
        texto.set_zorder(5)


def titulo_brecha(tasas, frases):
    """Título que afirma una brecha solo si alcanza DIFERENCIA_MINIMA."""
    a, b = frases[tasas.index[0]], frases[tasas.index[1]]
    valor_a, valor_b = pct(tasas.iloc[0]), pct(tasas.iloc[1])
    if tasas.iloc[0] - tasas.iloc[1] < DIFERENCIA_MINIMA:
        return f"En {ANIO}, la pobreza {a} ({valor_a}) fue casi igual a la {b} ({valor_b})"
    return f"En {ANIO}, la pobreza {a} ({valor_a}) superó a la {b} ({valor_b})"


def preparar_figura(tamano, titulo, ancho_titulo):
    fig, ax = plt.subplots(figsize=tamano)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(COLOR_GUIA)
    ax.tick_params(colors=COLOR_SECUNDARIO, length=0)
    ax.set_axisbelow(True)
    fig.suptitle(
        textwrap.fill(titulo, ancho_titulo),
        x=0.03, y=0.98, ha="left", va="top",
        fontsize=14, fontweight="bold", color=COLOR_TEXTO,
    )
    fig.text(0.03, 0.02, FUENTE, fontsize=9, color=COLOR_SECUNDARIO)
    return fig, ax


def guardar(fig, ruta):
    fig.savefig(ruta, dpi=DPI, facecolor="white")
    plt.close(fig)
    print(f"Guardado: {ruta}")


def barras_verticales(tasas, nacional, titulo, ruta):
    fig, ax = preparar_figura((7, 5.2), titulo, 60)
    posiciones = list(range(len(tasas)))
    barras = ax.bar(posiciones, tasas.values, width=0.5, color=COLOR_BARRA)
    rotular(ax, barras, [pct(v) for v in tasas.values], fontsize=12, fontweight="bold")
    ax.set_xticks(posiciones, list(tasas.index), fontsize=12)
    ax.set_ylim(0, 50)
    ax.set_ylabel(UNIDAD, color=COLOR_SECUNDARIO)
    ax.yaxis.grid(True, color=COLOR_GUIA, linewidth=0.6)
    ax.axhline(nacional, color=COLOR_SECUNDARIO, linewidth=1, linestyle="--")
    ax.text(
        0.5, nacional + 0.6, f"Nacional {pct(nacional)}",
        ha="center", va="bottom", fontsize=9, color=COLOR_SECUNDARIO,
    )
    fig.subplots_adjust(left=0.11, right=0.97, bottom=0.13, top=0.84)
    guardar(fig, ruta)


def barras_departamentos(tasas, nacional, titulo, ruta):
    fig, ax = preparar_figura((8, 9), titulo, 68)
    ordenadas = tasas.iloc[::-1]
    barras = ax.barh(
        [NOMBRES[c] for c in ordenadas.index], ordenadas.values,
        height=0.72, color=COLOR_BARRA,
    )
    rotular(ax, barras, [f"{v:.1f}" for v in ordenadas.values], fontsize=9)
    ax.set_xlim(0, 50)
    ax.set_ylim(-0.6, len(ordenadas) + 0.3)
    ax.set_xlabel(UNIDAD, color=COLOR_SECUNDARIO)
    ax.xaxis.grid(True, color=COLOR_GUIA, linewidth=0.6)
    ax.axvline(nacional, color=COLOR_SECUNDARIO, linewidth=1, linestyle="--")
    ax.text(
        nacional + 0.5, len(ordenadas) - 0.1, f"Nacional {pct(nacional)}",
        va="center", fontsize=9, color=COLOR_SECUNDARIO,
    )
    fig.subplots_adjust(left=0.17, right=0.97, bottom=0.1, top=0.92)
    guardar(fig, ruta)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Grafica la pobreza de la ENAHO 2024.")
    parser.add_argument("--personas", type=Path, default=RAIZ / "salidas" / "personas_2024.parquet")
    parser.add_argument("--figuras", type=Path, default=RAIZ / "figuras")
    args = parser.parse_args(argv)

    try:
        df = cargar(args.personas)
    except ErrorDatos as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    args.figuras.mkdir(parents=True, exist_ok=True)
    nacional = tasa(df)
    area = tasas_por(df, "area")
    sexo = tasas_por(df, "sexo")
    departamento = tasas_por(df, "codigo")

    barras_verticales(
        area, nacional,
        titulo_brecha(area, {"Urbana": "urbana", "Rural": "rural"}),
        args.figuras / "pobreza_area.png",
    )
    barras_verticales(
        sexo, nacional,
        titulo_brecha(sexo, {"Hombre": "de los hombres", "Mujer": "de las mujeres"}),
        args.figuras / "pobreza_sexo.png",
    )
    alto, bajo = departamento.index[0], departamento.index[-1]
    barras_departamentos(
        departamento, nacional,
        f"En {ANIO}, la pobreza varió de {pct(departamento[bajo])} en {NOMBRES[bajo]} "
        f"a {pct(departamento[alto])} en {NOMBRES[alto]}",
        args.figuras / "pobreza_departamento.png",
    )

    print(f"\nNacional: {nacional:.2f} %")
    print("Área:", ", ".join(f"{g} {v:.2f} %" for g, v in area.items()))
    print("Sexo:", ", ".join(f"{g} {v:.2f} %" for g, v in sexo.items()))
    print("Departamento:", ", ".join(f"{NOMBRES[c]} {v:.2f} %" for c, v in departamento.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
