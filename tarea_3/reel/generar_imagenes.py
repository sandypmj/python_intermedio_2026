"""Paso 3a · Imágenes del reel (gráficos y mapa) a partir de los datos procesados.

Uso (desde tarea_3/):  python reel/generar_imagenes.py
Guarda reel/recursos/escena_1.png ... escena_6.png (900 × 620 px, fondo oscuro como el video).
Cada imagen corresponde a una escena de reel/guion.json (campo "imagen").
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Polygon

RAIZ = Path(__file__).resolve().parents[1]
REC = RAIZ / "reel" / "recursos"
REC.mkdir(parents=True, exist_ok=True)
t = pd.read_csv(RAIZ / "datos" / "procesados" / "indicadores.csv")
serie = pd.read_csv(RAIZ / "datos" / "procesados" / "serie_nacional.csv")
geo = json.loads((RAIZ / "web" / "data" / "territorios.geojson").read_text(encoding="utf-8"))

FONDO, TEXTO, SUAVE, ACENTO, CAJA, AZUL = "#1C1A17", "#F7F3EC", "#B8AE9F", "#F08A4B", "#2A2723", "#6DA7EC"
plt.rcParams.update({"figure.facecolor": FONDO, "axes.facecolor": FONDO, "text.color": TEXTO,
                     "axes.labelcolor": SUAVE, "xtick.color": SUAVE, "ytick.color": SUAVE,
                     "axes.edgecolor": CAJA, "font.size": 15, "font.family": "DejaVu Sans"})
W, H, DPI = 9, 6.2, 100   # 900 × 620 px


def fig():
    f, ax = plt.subplots(figsize=(W, H), dpi=DPI)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    return f, ax


def guardar(f, n):
    f.savefig(REC / f"escena_{n}.png", dpi=DPI, facecolor=FONDO)
    plt.close(f)
    print(f"   recursos/escena_{n}.png")


def dep(ind, anio):
    return t[(t.nivel == "departamento") & (t.indicador == ind) & (t.anio == anio)].set_index("categoria").valor


# 1 · De cada 100 mujeres alguna vez unidas, 49 sufrieron violencia (pictograma)
v = t[(t.categoria == "Perú") & (t.indicador == "cualquiera") & (t.anio == 2025)].valor.iloc[0]
f, ax = plt.subplots(figsize=(W, H), dpi=DPI)
ax.axis("off")
for i in range(100):
    x, y = i % 10, 9 - i // 10
    ax.add_patch(plt.Circle((x, y), .36, color=ACENTO if i < round(v) else CAJA))
ax.set_xlim(-.6, 9.6); ax.set_ylim(-1.6, 9.6); ax.set_aspect("equal")
ax.text(4.5, -1.2, f"De cada 100 mujeres alguna vez unidas, {round(v)} sufrieron violencia de su pareja",
        ha="center", fontsize=15, color=SUAVE)
guardar(f, 1)

# 2 · Serie nacional 2009-2025
s = serie[serie.indicador == "cualquiera"]
f, ax = fig()
ax.plot(s.anio, s.valor, color=ACENTO, lw=4, marker="o", ms=7)
for a in (2009, 2025):
    val = s[s.anio == a].valor.iloc[0]
    ax.annotate(f"{val:.1f} %".replace(".", ","), (a, val), xytext=(0, 16), textcoords="offset points",
                ha="center", fontsize=24, fontweight="bold", color=TEXTO)
ax.set_ylim(40, 85); ax.set_yticks([]); ax.set_xticks([2009, 2013, 2017, 2021, 2025])
ax.set_title("Perú: violencia de pareja alguna vez (%)", loc="left", color=SUAVE, fontsize=16, pad=14)
f.tight_layout(); guardar(f, 2)

# 3 · Mapa 2025
vals = dep("cualquiera", 2025)
cmap = LinearSegmentedColormap.from_list("v", ["#3A3530", ACENTO])
lo, hi = vals.min(), vals.max()
f, ax = plt.subplots(figsize=(W, H), dpi=DPI)
ax.axis("off")
orden = sorted(geo["features"], key=lambda x: x["properties"]["departamento"] == "Lima Metropolitana")
for ft in orden:
    nombre = ft["properties"]["departamento"]
    g = ft["geometry"]
    polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
    color = cmap((vals[nombre] - lo) / (hi - lo))
    for p in polys:
        ax.add_patch(Polygon(p[0], closed=True, fc=color, ec=FONDO, lw=.8))
ax.set_xlim(-81.5, -68.5); ax.set_ylim(-18.5, 0.2); ax.set_aspect("equal")
for nombre, (x, y) in {"Apurímac": (-71.2, -14.2), "Cajamarca": (-80.6, -6.6)}.items():
    ax.annotate(f"{nombre}\n{vals[nombre]:.1f} %".replace(".", ","), xy=(x, y), fontsize=17, fontweight="bold",
                color=TEXTO, ha="left" if nombre == "Apurímac" else "right")
ax.annotate("", xy=(-73.0, -14.0), xytext=(-71.3, -14.0), arrowprops=dict(arrowstyle="-", color=TEXTO, lw=1.5))
ax.annotate("", xy=(-78.6, -6.6), xytext=(-80.5, -6.6), arrowprops=dict(arrowstyle="-", color=TEXTO, lw=1.5))
f.subplots_adjust(0, 0, 1, 1); guardar(f, 3)

# 4 · Territorios con caída significativa 2022-2025
c = pd.read_csv(RAIZ / "datos" / "procesados" / "cambios_departamentales.csv", index_col=0)
b = c[c.significativo].sort_values("cambio_pp", ascending=False)
f, ax = fig()
y = range(len(b))
ax.hlines(y, b.hasta, b.desde, color=SUAVE, lw=2, alpha=.5)
ax.scatter(b.desde, y, s=110, color=SUAVE, zorder=3, label="2022")
ax.scatter(b.hasta, y, s=110, color=ACENTO, zorder=3, label="2025")
ax.set_yticks(list(y), b.index, fontsize=15, color=TEXTO)
for i, (_, r) in enumerate(b.iterrows()):
    ax.text(r.desde + 1, i, f"{r.cambio_pp:+.1f}".replace(".", ",").replace("-", "−"), va="center", fontsize=14, color=SUAVE)
ax.set_xlim(34, 76); ax.set_xticks([40, 50, 60, 70], ["40 %", "50 %", "60 %", "70 %"])
ax.legend(frameon=False, loc="lower right", fontsize=14, labelcolor=TEXTO)
ax.set_title("Bajaron de forma significativa, 2022 → 2025", loc="left", color=SUAVE, fontsize=16, pad=12)
f.tight_layout(); guardar(f, 4)

# 5 · Estancados en niveles altos
sel = ["Apurímac", "Huancavelica", "Tumbes"]
f, ax = fig()
d22, d25 = dep("cualquiera", 2022)[sel], dep("cualquiera", 2025)[sel]
x = range(len(sel))
ax.bar([i - .2 for i in x], d22, .38, color=SUAVE, label="2022")
ax.bar([i + .2 for i in x], d25, .38, color=ACENTO, label="2025")
for i in x:
    ax.text(i - .2, d22.iloc[i] + 1, f"{d22.iloc[i]:.1f}".replace(".", ","), ha="center", fontsize=15, color=SUAVE)
    ax.text(i + .2, d25.iloc[i] + 1, f"{d25.iloc[i]:.1f}".replace(".", ","), ha="center", fontsize=17, color=TEXTO, fontweight="bold")
ax.axhline(49.1, color=TEXTO, ls="--", lw=1.2)
ax.text(2.55, 50.2, "Perú 49,1 %", ha="right", fontsize=13, color=TEXTO)
ax.set_xticks(list(x), sel, fontsize=17, color=TEXTO); ax.set_yticks([]); ax.set_ylim(0, 78)
ax.legend(frameon=False, loc="upper right", fontsize=14, labelcolor=TEXTO, ncol=2, bbox_to_anchor=(1, 1.02))
ax.set_title("Sin cambios significativos (%)", loc="left", color=SUAVE, fontsize=16, pad=12)
f.tight_layout(); guardar(f, 5)

# 6 · Identidad: autoidentificación étnica y lengua materna
grupos = [("etnia", "Origen nativo"), ("etnia", "Mestizo"), ("lengua", "Lengua nativa"), ("lengua", "Castellano")]
etiq = ["Origen nativo", "Mestiza", "Lengua materna\nnativa", "Lengua materna\ncastellano"]
vals = [t[(t.nivel == n) & (t.categoria == c) & (t.indicador == "cualquiera") & (t.anio == 2025)].valor.iloc[0] for n, c in grupos]
f, ax = fig()
ax.barh(etiq[::-1], vals[::-1], color=[SUAVE, ACENTO, SUAVE, ACENTO], height=.55)
for i, v in enumerate(vals[::-1]):
    ax.text(v + 1, i, f"{v:.1f} %".replace(".", ","), va="center", fontsize=22, fontweight="bold", color=TEXTO)
ax.axvline(49.1, color=TEXTO, ls="--", lw=1.2)
ax.text(49.6, 3.45, "Perú 49,1 %", fontsize=13, color=TEXTO)
ax.set_xticks([]); ax.set_xlim(0, 68); ax.tick_params(axis="y", labelsize=17, labelcolor=TEXTO, length=0)
ax.spines["bottom"].set_visible(False)
ax.set_title("Perú 2025: violencia de pareja según identidad (%)", loc="left", color=SUAVE, fontsize=16, pad=12)
f.tight_layout(); guardar(f, 6)
