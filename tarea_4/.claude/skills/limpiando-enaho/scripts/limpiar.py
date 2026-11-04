"""Limpia la ENAHO 2024 del INEI: une miembros (módulo 02) y sumaria (módulo 34).

Uso, desde la raíz del proyecto:
    uv run python .claude/skills/limpiando-enaho/scripts/limpiar.py

Salidas en salidas/:
    validacion.txt         siempre, con APROBADA o FALLÓ en cada verificación
    personas_2024.parquet  solo si pasan las validaciones esenciales
    indicadores.csv        solo si pasan las validaciones esenciales

Las cifras de referencia solo se comparan. Este script nunca las usa para
modificar datos ni resultados. Devuelve código 1 si falla algo esencial.
"""

import argparse
import io
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[4]

ZIP_SUMARIA = "966-Modulo34.zip"
DTA_SUMARIA = "966-Modulo34/sumaria-2024.dta"
ZIP_MIEMBROS = "966-Modulo02.zip"
DTA_MIEMBROS = "966-Modulo02/enaho01-2024-200.dta"

LLAVES_HOGAR = ["conglome", "vivienda", "hogar"]
LLAVES_PERSONA = LLAVES_HOGAR + ["codperso"]
ANCHOS_TEXTO = {"conglome": 6, "vivienda": 3, "hogar": 2, "codperso": 2, "ubigeo": 6}

REF_POBREZA_NACIONAL = 27.6
REF_RESIDENTES = 108_664
REF_URBANA = 24.8
REF_RURAL = 39.3
TOLERANCIA_PUNTOS = 0.1

NOTA_METODOS = (
    "NOTA: El método por personas pondera a los residentes habituales del módulo 02 con facpob07; el método por hogares pondera cada hogar de la sumaria con factor07 x mieperho.",
    "Sus tasas difieren porque no cuentan exactamente a las mismas personas: mieperho no coincide con el número de residentes filtrados en todos los hogares.",
    "Las referencias corresponden al método por hogares; por eso un FALLÓ por personas puede reflejar esta diferencia de método, y no se ajusta ninguna cifra.",
)

DEPARTAMENTOS = {
    "01": "AMAZONAS", "02": "ANCASH", "03": "APURIMAC", "04": "AREQUIPA",
    "05": "AYACUCHO", "06": "CAJAMARCA", "07": "CALLAO", "08": "CUSCO",
    "09": "HUANCAVELICA", "10": "HUANUCO", "11": "ICA", "12": "JUNIN",
    "13": "LA LIBERTAD", "14": "LAMBAYEQUE", "15": "LIMA", "16": "LORETO",
    "17": "MADRE DE DIOS", "18": "MOQUEGUA", "19": "PASCO", "20": "PIURA",
    "21": "PUNO", "22": "SAN MARTIN", "23": "TACNA", "24": "TUMBES",
    "25": "UCAYALI",
}


class ErrorValidacion(Exception):
    """Falló una validación esencial: el pipeline debe detenerse."""


class Bitacora:
    """Acumula las verificaciones y las escribe en validacion.txt."""

    def __init__(self):
        self.filas = []
        self.completa = False

    def verificar(self, nombre, aprobada, detalle, esencial=True):
        self.filas.append((nombre, bool(aprobada), detalle, esencial))

    def fallos(self, esencial):
        return [f for f in self.filas if not f[1] and f[3] == esencial]

    def detener_si_falla(self):
        fallos = self.fallos(esencial=True)
        if fallos:
            lista = "; ".join(f"{f[0]} ({f[2]})" for f in fallos)
            raise ErrorValidacion(f"Falló una validación esencial: {lista}")

    def escribir(self, ruta):
        aprobada = self.completa and not self.fallos(esencial=True)
        lineas = [
            "VALIDACIÓN ENAHO 2024 - skill limpiando-enaho",
            f"RESULTADO DE LAS ESENCIALES: {'APROBADA' if aprobada else 'FALLÓ'}",
            f"CONTROLES CON FALLÓ: {len(self.fallos(esencial=False))}",
        ]
        if not self.completa:
            lineas.append("El pipeline se detuvo antes de completar las verificaciones.")
        for titulo, esencial in (("ESENCIALES", True), ("CONTROLES", False)):
            filas = [f for f in self.filas if f[3] == esencial]
            if filas:
                lineas += ["", f"{titulo}:"]
            for nombre, ok, detalle, _ in filas:
                lineas.append(f"[{'APROBADA' if ok else 'FALLÓ'}] {nombre}: {detalle}")
        lineas += ["", *NOTA_METODOS]
        ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def leer_modulo(ruta_zip, miembro, llaves, bitacora):
    """Paso 1 y 2: lee el .dta sin descomprimir a disco y normaliza columnas."""
    with zipfile.ZipFile(ruta_zip) as z, z.open(miembro) as f:
        df = pd.read_stata(io.BytesIO(f.read()), convert_categoricals=False)
    df.columns = df.columns.str.lower()

    # Un código leído como número ya perdió sus ceros: no se puede reparar aquí.
    for col in llaves:
        ancho = ANCHOS_TEXTO[col]
        es_texto = pd.api.types.is_string_dtype(df[col])
        ok = es_texto and df[col].str.fullmatch(rf"\d{{{ancho}}}").all()
        bitacora.verificar(
            f"Llave {col} como texto en {ruta_zip.name}",
            ok,
            f"se exige texto de {ancho} dígitos en todas las filas",
        )
    return df


def filtrar_residentes(miembros):
    """Paso 3: residentes habituales, con la condición oficial exacta."""
    p204, p205, p206 = miembros["p204"], miembros["p205"], miembros["p206"]
    return miembros[((p204 == 1) & (p205 == 2)) | ((p204 == 2) & (p206 == 1))].copy()


def unir(residentes, sumaria, bitacora):
    """Paso 4: cada persona recibe la pobreza de su único hogar."""
    hogares = sumaria[LLAVES_HOGAR + ["pobreza"]]
    try:
        unida = residentes.merge(
            hogares, on=LLAVES_HOGAR, how="left", validate="m:1", indicator=True
        )
    except pd.errors.MergeError as error:
        bitacora.verificar("Unión m:1 personas-hogares", False, str(error))
        raise ErrorValidacion(f"La unión no es m:1: {error}") from error

    sin_hogar = int((unida["_merge"] != "both").sum())
    bitacora.verificar("Unión m:1 personas-hogares", True, "validate='m:1' superado")
    bitacora.verificar(
        "Unión sin duplicar ni perder filas",
        len(unida) == len(residentes) and sin_hogar == 0,
        f"{len(residentes):,} filas antes, {len(unida):,} después, "
        f"{sin_hogar:,} personas sin hogar",
    )
    return unida.drop(columns="_merge")


def construir(df):
    """Paso 5: variables de análisis. float64 evita errores al sumar el factor."""
    df = df.copy()
    df["facpob07"] = df["facpob07"].astype("float64")
    df["departamento"] = df["ubigeo"].str[:2]
    df["departamento_nombre"] = df["departamento"].map(DEPARTAMENTOS)
    df["urbano"] = df["estrato"] <= 5
    df["area"] = np.where(df["urbano"], "Urbana", "Rural")
    df["sexo"] = df["p207"].map({1: "Hombre", 2: "Mujer"})
    df["pobre"] = df["pobreza"] <= 2
    return df


def tasa_ponderada(df):
    """Pobreza en %: suma(facpob07 de los pobres) / suma(facpob07)."""
    return 100 * df.loc[df["pobre"], "facpob07"].sum() / df["facpob07"].sum()


def validar(personas, sumaria, bitacora):
    """Paso 6: compara contra la referencia sin modificar ningún resultado."""
    # Un vacío en pobreza <= 2 daría False: se contaría como "no pobre".
    codigos_ok = (
        personas["pobreza"].isin([1, 2, 3]).all()
        and personas["estrato"].isin(range(1, 9)).all()
        and personas["p207"].isin([1, 2]).all()
    )
    bitacora.verificar(
        "Códigos válidos sin vacíos",
        codigos_ok,
        "pobreza en 1-3, estrato en 1-8, p207 en 1-2",
    )

    nacional = tasa_ponderada(personas)
    bitacora.verificar(
        "Pobreza nacional",
        abs(nacional - REF_POBREZA_NACIONAL) <= TOLERANCIA_PUNTOS,
        f"obtenido {nacional:.2f} %, referencia {REF_POBREZA_NACIONAL} % "
        f"+/- {TOLERANCIA_PUNTOS} puntos",
    )
    bitacora.verificar(
        "Residentes habituales",
        len(personas) == REF_RESIDENTES,
        f"obtenido {len(personas):,}, referencia {REF_RESIDENTES:,}",
    )

    codigos = set(personas["departamento"])
    bitacora.verificar(
        "Códigos de departamento",
        codigos == set(DEPARTAMENTOS),
        f"obtenido {len(codigos)} códigos, referencia 25 (01 a 25)",
    )

    dup_personas = int(personas.duplicated(LLAVES_PERSONA).sum())
    dup_hogares = int(sumaria.duplicated(LLAVES_HOGAR).sum())
    bitacora.verificar(
        "Sin duplicados",
        dup_personas == 0 and dup_hogares == 0,
        f"{dup_personas:,} personas y {dup_hogares:,} hogares repetidos",
    )

    factor = personas["facpob07"]
    invalidos = int((~np.isfinite(factor) | (factor <= 0)).sum())
    bitacora.verificar(
        "Factores válidos",
        invalidos == 0,
        f"{invalidos:,} valores vacíos, infinitos o <= 0 en facpob07",
    )

    for area, referencia in (("Urbana", REF_URBANA), ("Rural", REF_RURAL)):
        obtenido = tasa_ponderada(personas[personas["area"] == area])
        bitacora.verificar(
            f"Pobreza {area.lower()} por personas (facpob07)",
            abs(obtenido - referencia) <= TOLERANCIA_PUNTOS,
            f"obtenido {obtenido:.2f} %, referencia {referencia} % "
            f"+/- {TOLERANCIA_PUNTOS} puntos",
            esencial=False,
        )

    # Mismo método de la referencia: solo informa, no alimenta la base ni los indicadores.
    peso = sumaria["factor07"].astype("float64") * sumaria["mieperho"]
    pobre = sumaria["pobreza"] <= 2
    urbano = sumaria["estrato"] <= 5
    for area, en_area, referencia in (
        ("urbana", urbano, REF_URBANA),
        ("rural", ~urbano, REF_RURAL),
    ):
        obtenido = 100 * peso[en_area & pobre].sum() / peso[en_area].sum()
        bitacora.verificar(
            f"Pobreza {area} por hogares (factor07 x mieperho)",
            abs(obtenido - referencia) <= TOLERANCIA_PUNTOS,
            f"obtenido {obtenido:.2f} %, referencia {referencia} % "
            f"+/- {TOLERANCIA_PUNTOS} puntos",
            esencial=False,
        )


def calcular_indicadores(personas):
    """Paso 8: pobreza ponderada nacional, por área, sexo y departamento."""
    grupos = [
        ("Nacional", pd.Series("Nacional", index=personas.index)),
        ("Área", personas["area"]),
        ("Sexo", personas["sexo"]),
        ("Departamento", personas["departamento"]),
    ]
    filas = []
    for nivel, claves in grupos:
        for categoria, grupo in personas.groupby(claves, sort=True):
            filas.append(
                {
                    "nivel": nivel,
                    "codigo": categoria if nivel == "Departamento" else "",
                    "categoria": DEPARTAMENTOS[categoria]
                    if nivel == "Departamento"
                    else categoria,
                    "pobreza_pct": round(tasa_ponderada(grupo), 2),
                    "personas_muestra": len(grupo),
                    "poblacion_expandida": round(grupo["facpob07"].sum()),
                }
            )
    return pd.DataFrame(filas)


def ejecutar(datos, salidas, bitacora):
    zip_sumaria, zip_miembros = datos / ZIP_SUMARIA, datos / ZIP_MIEMBROS
    for ruta in (zip_sumaria, zip_miembros):
        existe = ruta.is_file()
        bitacora.verificar(
            f"Archivo {ruta.name}", existe, "encontrado" if existe else f"falta en {datos}"
        )
    bitacora.detener_si_falla()

    print("1-2. Leyendo módulos y normalizando columnas...")
    sumaria = leer_modulo(zip_sumaria, DTA_SUMARIA, LLAVES_HOGAR, bitacora)
    miembros = leer_modulo(
        zip_miembros, DTA_MIEMBROS, LLAVES_PERSONA + ["ubigeo"], bitacora
    )
    bitacora.detener_si_falla()

    print("3. Filtrando residentes habituales...")
    residentes = filtrar_residentes(miembros)

    print("4. Uniendo personas y hogares...")
    unida = unir(residentes, sumaria, bitacora)
    bitacora.detener_si_falla()

    print("5. Construyendo variables...")
    personas = construir(unida)

    print("6. Validando...")
    validar(personas, sumaria, bitacora)
    bitacora.completa = True
    bitacora.detener_si_falla()

    print("8. Guardando salidas...")
    personas.to_parquet(salidas / "personas_2024.parquet", index=False)
    calcular_indicadores(personas).to_csv(
        salidas / "indicadores.csv", index=False, encoding="utf-8"
    )


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Limpia la ENAHO 2024.")
    parser.add_argument("--datos", type=Path, default=RAIZ / "datos")
    parser.add_argument("--salidas", type=Path, default=RAIZ / "salidas")
    args = parser.parse_args(argv)
    args.salidas.mkdir(parents=True, exist_ok=True)

    # Si esta corrida falla, no deben quedar productos de una corrida anterior.
    for nombre in ("personas_2024.parquet", "indicadores.csv"):
        (args.salidas / nombre).unlink(missing_ok=True)

    bitacora = Bitacora()
    try:
        ejecutar(args.datos, args.salidas, bitacora)
    except ErrorValidacion as error:
        print(f"ERROR: {error}", file=sys.stderr)
        print("No se generaron personas_2024.parquet ni indicadores.csv.", file=sys.stderr)
        return 1
    finally:
        bitacora.escribir(args.salidas / "validacion.txt")

    controles = bitacora.fallos(esencial=False)
    if controles:
        nombres = ", ".join(f[0] for f in controles)
        print(f"ADVERTENCIA: falló un control no esencial: {nombres}", file=sys.stderr)
    print(f"Listo. Revisa {args.salidas / 'validacion.txt'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
