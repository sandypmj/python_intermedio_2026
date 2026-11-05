"""Grafica la inflación de Lima y la tasa de referencia del BCRP, 2020-2024.

Los datos salen solo de la función serie de mcp/server.py; aquí no se llama a la API por otro camino.

    uv run python informes/graficar_bcrp.py
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "mcp"))
from server import serie  # noqa: E402

INFLACION = "PN01273PM"
TASA = "PD04722MM"
DESDE, HASTA = "2020-01", "2024-12"
SALIDA = RAIZ / "figuras" / "bcrp_inflacion_tasa_2020_2024.png"

# Mismo estilo que las figuras de la skill graficando-enaho
COLOR_INFLACION = "#2a78d6"
COLOR_TASA = "#eb6834"
COLOR_TEXTO = "#1f1f1d"
COLOR_SECUNDARIO = "#5f5f5a"
COLOR_GUIA = "#d9d8d3"


def tabla(codigo):
    """Pasa los datos de serie a una Serie de pandas indexada por fecha."""
    datos = pd.DataFrame(serie(codigo, DESDE, HASTA)["datos"])
    if datos.empty:
        raise SystemExit(f"La serie {codigo} no trajo datos entre {DESDE} y {HASTA}: no se genera la figura.")
    return pd.Series(datos["valor"].values, index=pd.to_datetime(datos["periodo"]), name=codigo)


def mes(fecha):
    return fecha.strftime("%Y-%m")


def marcar_maximo(ax, s, color, desplazamiento):
    """Marca la primera vez que la serie alcanza su máximo, con su valor y su mes."""
    fecha, valor = s.idxmax(), s.max()
    ax.plot(fecha, valor, "o", color=color, markersize=7, markeredgecolor="white", markeredgewidth=1.5, zorder=4)
    ax.annotate(f"Máximo: {valor:.2f} %\n({mes(fecha)})", (fecha, valor), xytext=desplazamiento,
                textcoords="offset points", ha="center", va="bottom" if desplazamiento[1] > 0 else "top",
                fontsize=9, color=COLOR_TEXTO)


def main():
    inflacion, tasa = tabla(INFLACION), tabla(TASA)

    fig, ax = plt.subplots(figsize=(9, 5.6))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    ax.plot(inflacion.index, inflacion.values, color=COLOR_INFLACION, linewidth=2,
            label=f"Inflación de Lima Metropolitana, var. % a 12 meses ({INFLACION})")
    # La tasa cambia por decisión de política y se mantiene hasta el siguiente cambio: va en escalones.
    ax.step(tasa.index, tasa.values, where="post", color=COLOR_TASA, linewidth=2,
            label=f"Tasa de referencia de la política monetaria, % ({TASA})")

    marcar_maximo(ax, inflacion, COLOR_INFLACION, (-22, 8))
    marcar_maximo(ax, tasa, COLOR_TASA, (3, -34))

    # Último valor de cada serie, a la derecha de la línea
    for s, color in ((inflacion, COLOR_INFLACION), (tasa, COLOR_TASA)):
        ax.plot(s.index[-1], s.iloc[-1], "o", color=color, markersize=7,
                markeredgecolor="white", markeredgewidth=1.5, zorder=4)
        ax.annotate(f"{s.iloc[-1]:.2f} %\n({mes(s.index[-1])})", (s.index[-1], s.iloc[-1]), xytext=(8, 0),
                    textcoords="offset points", ha="left", va="center", fontsize=9, color=COLOR_TEXTO)

    ax.set_ylim(0, 10)
    ax.set_xlim(inflacion.index[0], inflacion.index[-1] + pd.DateOffset(months=1))
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_ylabel("Porcentaje (%)", color=COLOR_SECUNDARIO)
    ax.yaxis.grid(True, color=COLOR_GUIA, linewidth=0.6)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(COLOR_GUIA)
    ax.tick_params(colors=COLOR_SECUNDARIO, length=0)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), frameon=False, fontsize=9, labelcolor=COLOR_TEXTO)

    fig.suptitle(
        "Perú, 2020-2024: la inflación de Lima tocó su máximo en "
        f"{mes(inflacion.idxmax())} ({inflacion.max():.1f} %)\n"
        f"y la tasa de referencia alcanzó el suyo en {mes(tasa.idxmax())} ({tasa.max():.2f} %)",
        x=0.03, ha="left", fontsize=13, fontweight="bold", color=COLOR_TEXTO)
    fig.text(0.03, 0.02,
             f"Fuente: BCRP, series {INFLACION} (IPC de Lima Metropolitana, var. % a 12 meses) y {TASA} "
             "(tasa de referencia),\nmensuales, "
             f"{DESDE} a {HASTA}.", fontsize=8.5, color=COLOR_SECUNDARIO)

    fig.tight_layout(rect=(0, 0.07, 0.96, 1))
    SALIDA.parent.mkdir(exist_ok=True)
    fig.savefig(SALIDA, dpi=200, facecolor="white")
    plt.close(fig)

    print(f"Guardado: {SALIDA}")
    print(f"{INFLACION}: {len(inflacion)} meses, máximo {inflacion.max():.2f} en {mes(inflacion.idxmax())}, "
          f"último {inflacion.iloc[-1]:.2f}")
    print(f"{TASA}: {len(tasa)} meses, máximo {tasa.max():.2f} en {mes(tasa.idxmax())}, último {tasa.iloc[-1]:.2f}")


if __name__ == "__main__":
    main()
