import json

# 1. Leer los dos archivos de límites
with open("datos/originales/limites/peru_departamental_simple.geojson", encoding="utf-8") as f:
    departamental = json.load(f)
with open("datos/originales/limites/peru_provincial_simple.geojson", encoding="utf-8") as f:
    provincial = json.load(f)

# 2. Nombres del GeoJSON (en mayúsculas y sin tildes) -> nombres de tus datos de la ENDES
NOMBRES = {
    "AMAZONAS": "Amazonas", "ANCASH": "Áncash", "APURIMAC": "Apurímac", "AREQUIPA": "Arequipa",
    "AYACUCHO": "Ayacucho", "CAJAMARCA": "Cajamarca", "CALLAO": "Prov. Const. del Callao",
    "CUSCO": "Cusco", "HUANCAVELICA": "Huancavelica", "HUANUCO": "Huánuco", "ICA": "Ica",
    "JUNIN": "Junín", "LA LIBERTAD": "La Libertad", "LAMBAYEQUE": "Lambayeque",
    "LIMA": "Departamento de Lima", "LORETO": "Loreto", "MADRE DE DIOS": "Madre de Dios",
    "MOQUEGUA": "Moquegua", "PASCO": "Pasco", "PIURA": "Piura", "PUNO": "Puno",
    "SAN MARTIN": "San Martín", "TACNA": "Tacna", "TUMBES": "Tumbes", "UCAYALI": "Ucayali",
}


def redondear(coords):
    """3 decimales (unos 100 m) bastan para un mapa del país y hacen el archivo más liviano."""
    if isinstance(coords[0], (int, float)):
        return [round(coords[0], 3), round(coords[1], 3)]
    return [redondear(c) for c in coords]


# 3. Un territorio por departamento, con el nombre que usan tus datos
territorios = []
for f in departamental["features"]:
    nombre = NOMBRES[f["properties"]["NOMBDEP"]]
    territorios.append({"nombre": nombre, "tipo": f["geometry"]["type"],
                        "coords": redondear(f["geometry"]["coordinates"])})

# 4. La provincia de Lima (código 1501) se dibuja encima como "Lima Metropolitana"
for f in provincial["features"]:
    if f["properties"]["FIRST_IDPR"] == "1501":
        territorios.append({"nombre": "Lima Metropolitana", "tipo": f["geometry"]["type"],
                            "coords": redondear(f["geometry"]["coordinates"])})

# 5. Guardarlo para la web, igual que hiciste con datos.js
with open("web/geo.js", "w", encoding="utf-8") as f:
    f.write("const GEO = " + json.dumps(territorios, ensure_ascii=False) + ";")
print("Territorios en el mapa:", len(territorios))