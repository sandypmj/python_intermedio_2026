import pandas as pd

t = pd.read_csv("datos/procesados/indicadores_mi_version.csv")
texto = t.to_json(orient="records", force_ascii=False)   # los vacíos se vuelven null
with open("web/datos.js", "w", encoding="utf-8") as f:
    f.write("const DATOS = " + texto + ";")
print("Filas exportadas:", len(t))