"""Calcula las cifras derivadas de informe_final.md, para que ninguna se haga a mano.

    uv run python informes/calculos_informe.py

BCRP: usa la función serie de mcp/server.py. ENAHO: usa salidas/personas_2024.parquet y salidas/indicadores.csv.
"""
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "mcp"))
from server import serie  # noqa: E402

DESDE, HASTA = "2020-01", "2024-12"


def tabla(codigo):
    datos = pd.DataFrame(serie(codigo, DESDE, HASTA)["datos"])
    return pd.Series(datos["valor"].values, index=datos["periodo"])


def tramos(mascara):
    """Devuelve los tramos consecutivos en los que se cumple la condición, como (desde, hasta, meses)."""
    grupos = (mascara != mascara.shift()).cumsum()
    return [(g.index[0], g.index[-1], len(g)) for _, g in mascara.groupby(grupos) if g.iloc[0]]


def main():
    inflacion, tasa = tabla("PN01273PM"), tabla("PD04722MM")
    print("== BCRP ==")
    print("Meses con tasa en su mínimo:", tramos(tasa == tasa.min()))
    print("Meses con tasa en su máximo:", tramos(tasa == tasa.max()))
    print("Primer mes con alza de la tasa:", tasa.index[(tasa.diff() > 0).values][0])
    print("Primer mes con baja desde el máximo:",
          tasa.loc[tasa.idxmax():].index[(tasa.loc[tasa.idxmax():].diff() < 0).values][0])
    print("Meses entre máximo de inflación y máximo de tasa:",
          (pd.Period(tasa.idxmax(), "M") - pd.Period(inflacion.idxmax(), "M")).n)
    print("Tramos con inflación mayor que la tasa:", tramos(inflacion > tasa))
    print("Tramos con tasa mayor que la inflación:", tramos(tasa > inflacion))
    print(f"Tasa menos inflación en {HASTA}: {tasa[HASTA] - inflacion[HASTA]:.2f} puntos")

    print("\n== ENAHO ==")
    ind = pd.read_csv(RAIZ / "salidas" / "indicadores.csv", dtype={"codigo": str})
    area = ind[ind.nivel == "Área"].set_index("categoria").pobreza_pct
    print(f"Brecha rural menos urbana: {area['Rural'] - area['Urbana']:.2f} puntos")
    dep = ind[ind.nivel == "Departamento"]
    nacional = ind.loc[ind.nivel == "Nacional", "pobreza_pct"].iloc[0]
    print(f"Departamentos sobre el promedio nacional ({nacional}): {(dep.pobreza_pct > nacional).sum()} de {len(dep)}")
    print(f"Rango departamental: {dep.pobreza_pct.max() - dep.pobreza_pct.min():.2f} puntos")
    menor = dep.loc[dep.personas_muestra.idxmin()]
    print(f"Menor muestra: {menor.categoria}, {menor.personas_muestra} personas")

    df = pd.read_parquet(RAIZ / "salidas" / "personas_2024.parquet", columns=["area", "departamento", "pobre", "facpob07"])
    pobres = df[df.pobre]
    total = pobres.facpob07.sum()
    print(f"Personas pobres (expandido con facpob07): {total:,.0f}")
    for nombre, valor in pobres.groupby("area").facpob07.sum().items():
        print(f"  {nombre}: {valor:,.0f} ({100 * valor / total:.1f} % de los pobres)")
    poblacion = df.groupby("area").facpob07.sum()
    for nombre, valor in poblacion.items():
        print(f"  Población {nombre}: {100 * valor / poblacion.sum():.1f} % del total")
    por_dep = pobres.groupby("departamento").facpob07.sum().sort_values(ascending=False)
    for codigo, valor in por_dep.head(3).items():
        print(f"  Departamento {codigo}: {valor:,.0f} ({100 * valor / total:.1f} % de los pobres)")


if __name__ == "__main__":
    main()
