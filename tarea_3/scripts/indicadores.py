import re
import pandas as pd
from openpyxl import load_workbook
from openpyxl.utils import column_index_from_string

libro = load_workbook("datos/originales/Cap_12_ENDES_2025.xlsx", data_only=True)

# Qué leer: (hoja, columna donde empieza el bloque, nombre corto del indicador)
BLOQUES = [
    ("12.1", "B", "cualquiera"),
    ("12.1", "AR", "psicologica"),
    ("12.1", "CH", "fisica"),
    ("12.1", "DX", "sexual"),
    ("12.4", "B", "fis_sex_12m"),
]


def a_numero(valor):
    """54.86 -> 54.86 ;  "(16,9)" -> 16.9 ;  "¬" o vacío -> None"""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip().strip("()").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def leer_bloque(hoja, letra_inicio, indicador):
    inicio = column_index_from_string(letra_inicio)
    # columnas de cada año dentro de este bloque (cada bloque mide 42 columnas)
    columna_anio = {}
    for col in range(inicio, inicio + 42):
        texto = str(hoja.cell(7, col).value).strip()
        if texto.isdigit():
            columna_anio[int(texto)] = col

    filas = []
    seccion = None
    for fila in range(11, hoja.max_row + 1):
        etiqueta = hoja.cell(fila, 1).value
        if etiqueta is None:
            continue
        etiqueta = str(etiqueta).strip()
        if etiqueta.startswith("Nota"):
            break
        if etiqueta == "Departamento":
            seccion = "departamento"
            continue
        if etiqueta != "Total" and seccion != "departamento":
            continue                      # por ahora solo Perú y departamentos
        nombre = "Perú" if etiqueta == "Total" else re.sub(r"\s+\d+/$", "", etiqueta)
        for anio, col in columna_anio.items():
            valor = a_numero(hoja.cell(fila, col).value)
            if valor is None:
                continue
            fila_nueva = {"anio": anio, "categoria": nombre, "indicador": indicador, "valor": round(valor, 1)}
            if anio >= 2022:              # desde 2022 hay intervalo de confianza
                fila_nueva["ic_inf"] = round(a_numero(hoja.cell(fila, col + 2).value), 1)
                fila_nueva["ic_sup"] = round(a_numero(hoja.cell(fila, col + 3).value), 1)
            filas.append(fila_nueva)
    return filas


todas = []
for nombre_hoja, letra, indicador in BLOQUES:
    filas = leer_bloque(libro[nombre_hoja], letra, indicador)
    print(f"{nombre_hoja} {indicador}: {len(filas)} valores")
    todas += filas

tabla = pd.DataFrame(todas)
print(tabla.head())
print(tabla[tabla.categoria == "Perú"].pivot(index="indicador", columns="anio", values="valor"))
tabla.to_csv("datos/procesados/indicadores_mi_version.csv", index=False)