import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

t = pd.read_csv("datos/procesados/indicadores_mi_version.csv")
dep = t[(t.indicador == "cualquiera") & (t.nivel == "departamento")]

# Hallazgo 2: ranking y brecha en 2025
d25 = dep[dep.anio == 2025].sort_values("valor", ascending=False)
mayor, menor = d25.iloc[0], d25.iloc[-1]
print(f"Mayor: {mayor.categoria} {mayor.valor} % | Menor: {menor.categoria} {menor.valor} %")
print(f"Brecha: {mayor.valor - menor.valor:.1f} puntos")
print("Territorios por encima de 50 %:", (d25.valor > 50).sum())

# Hallazgo 3: cambio 2022 -> 2025 y prueba de significancia
a = dep[dep.anio == 2022].set_index("categoria")
b = dep[dep.anio == 2025].set_index("categoria")
cambio = pd.DataFrame({"v2022": a.valor, "v2025": b.valor})
cambio["dif"] = (cambio.v2025 - cambio.v2022).round(1)
ee22 = (a.ic_sup - a.ic_inf) / 3.92
ee25 = (b.ic_sup - b.ic_inf) / 3.92
cambio["z"] = (cambio.dif / np.sqrt(ee22**2 + ee25**2)).round(2)
cambio["significativo"] = cambio.z.abs() > 1.96
cambio = cambio.sort_values("dif")
print(cambio)
print("Bajan de forma significativa:", (cambio.significativo & (cambio.dif < 0)).sum())
print("Suben de forma significativa:", (cambio.significativo & (cambio.dif > 0)).sum())

# Un gráfico para sustentar el hallazgo 2
fig, ax = plt.subplots(figsize=(8, 8))
ax.barh(d25.categoria[::-1], d25.valor[::-1], color="#2a78d6")
ax.axvline(49.1, color="black", linestyle="--", linewidth=1)
ax.set_xlabel("% de mujeres alguna vez unidas de 15 a 49 años")
ax.set_title("Violencia de pareja alguna vez, 2025 (ENDES)")
fig.tight_layout()
fig.savefig("datos/procesados/ranking_2025.png", dpi=120)
print("Gráfico guardado")