"""Funciones de apoyo de la Tarea 2 (las usan los dos notebooks).

Aquí está lo que NO viene en voz.py del curso: descargas de Wikimedia Commons con su licencia,
huella (hash) de archivos, seudonimización con conteo de reemplazos y gráficos que se ven en GitHub.
"""
from __future__ import annotations

import hashlib
import re
import time
import urllib.parse
from pathlib import Path

import pandas as pd
import requests

AGENTE = {"User-Agent": "tarea2-ds-python/2026 (proyecto académico; https://github.com/d2cml-ai/Data-Science-Python)"}
API_COMMONS = "https://commons.wikimedia.org/w/api.php"


# ───────────────────────────────────────────── Wikimedia Commons
def info_commons(titulo: str, ancho: int | None = 1600) -> dict:
    """Pregunta a la API de Commons por un archivo: URL de descarga, licencia y autor.

    `titulo` es el nombre del archivo tal como aparece en Commons, sin "File:".
    Así la licencia queda registrada automáticamente (no la escribimos a mano).
    """
    params = {"action": "query", "format": "json", "titles": "File:" + titulo,
              "prop": "imageinfo", "iiprop": "url|extmetadata|mime"}
    if ancho:
        params["iiurlwidth"] = ancho
    r = requests.get(API_COMMONS, params=params, headers=AGENTE, timeout=60)
    r.raise_for_status()
    pagina = next(iter(r.json()["query"]["pages"].values()))
    if "imageinfo" not in pagina:
        raise FileNotFoundError(f"No existe en Commons: {titulo!r} (revisa mayúsculas y extensión)")
    ii = pagina["imageinfo"][0]
    meta = ii.get("extmetadata", {})
    limpiar = lambda s: re.sub(r"<[^>]+>", "", s or "").strip()  # el autor viene con HTML
    return {
        "url_descarga": ii.get("thumburl") or ii["url"],
        "fuente_url": ii["descriptionurl"],
        "licencia": limpiar(meta.get("LicenseShortName", {}).get("value")) or "revisar",
        "autor": limpiar(meta.get("Artist", {}).get("value"))[:120] or "desconocido",
        "mime": ii.get("mime", ""),
    }


def descargar(url: str, destino: Path, pausa: float = 1.5) -> Path:
    """Descarga un archivo si todavía no está en disco. Pausa de cortesía entre pedidos."""
    destino = Path(destino)
    if destino.exists() and destino.stat().st_size > 0:
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, headers=AGENTE, timeout=120)
    r.raise_for_status()
    destino.write_bytes(r.content)
    time.sleep(pausa)
    return destino


def nombre_seguro(titulo: str) -> str:
    """Nombre de archivo corto y sin tildes ni espacios, a partir del título de Commons."""
    base = re.sub(r"[^A-Za-z0-9]+", "_", Path(titulo).stem)[:40].strip("_")
    return f"{base}_{hashlib.md5(titulo.encode()).hexdigest()[:6]}"


def url_commons(titulo: str) -> str:
    return "https://commons.wikimedia.org/wiki/File:" + urllib.parse.quote(titulo.replace(" ", "_"))


# ───────────────────────────────────────────── limpieza
def huella(ruta: Path) -> str:
    """Hash MD5 del contenido: dos archivos idénticos tienen la misma huella aunque se llamen distinto."""
    h = hashlib.md5()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


# ───────────────────────────────────────────── seudonimización
PATRONES = {
    # 8 dígitos seguidos = posible DNI peruano
    "DNI": (re.compile(r"(?<!\d)\d{8}(?!\d)"), "[DNI]"),
    # celular peruano: 9 dígitos que empiezan con 9 (con o sin espacios)
    "TELEFONO": (re.compile(r"(?<!\d)9\d{2}[\s-]?\d{3}[\s-]?\d{3}(?!\d)"), "[TELEFONO]"),
    "CORREO": (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[CORREO]"),
}


def seudonimizar_con_conteo(texto: str, reemplazos: dict[str, str]) -> tuple[str, dict[str, int]]:
    """Aplica voz.seudonimizar (nombres, comparación difusa) + patrones de DNI, teléfono y correo.

    Devuelve el texto limpio y cuántas entidades de cada clase se reemplazaron.
    """
    from voz import seudonimizar

    conteo = {}
    if not isinstance(texto, str) or not texto:
        return texto, conteo
    salida = texto
    for clase, (patron, marca) in PATRONES.items():
        salida, n = patron.subn(marca, salida)
        if n:
            conteo[clase] = n
    if reemplazos:
        antes = salida
        salida = seudonimizar(salida, reemplazos)
        n_nombres = sum(salida.count(s) - antes.count(s) for s in set(reemplazos.values()))
        if n_nombres:
            conteo["NOMBRE"] = n_nombres
    return salida, conteo


def candidatos_a_nombre(texto: str) -> list[str]:
    """Pistas para la revisión humana: dos o más palabras seguidas que empiezan con mayúscula.

    No decide nada: solo te ayuda a encontrar posibles nombres de personas para revisar a mano.
    """
    if not isinstance(texto, str):
        return []
    patron = r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+(?:de\s+|del\s+|la\s+)?[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+"
    return sorted(set(re.findall(patron, texto)))


# ───────────────────────────────────────────── métricas
MARCA_HABLANTE = re.compile(r"\[(?:HABLANTE|H)_?\d+\]\s*:?")


def quitar_marcas(texto: str) -> str:
    """Quita [HABLANTE_1] y similares: no son palabras habladas y no deben contar en el WER."""
    return MARCA_HABLANTE.sub(" ", texto or "").strip()


# ───────────────────────────────────────────── gráficos visibles en GitHub
def mostrar(fig):
    """Muestra el gráfico Plotly interactivo (VS Code) y además una copia PNG estática.

    GitHub no ejecuta JavaScript: la copia PNG es la que se ve en el notebook publicado.
    La imagen necesita el paquete `kaleido`.
    """
    fig.show()  # interactivo
    try:
        from IPython.display import Image, display
        display(Image(fig.to_image(format="png", width=1000, height=500)))  # copia para GitHub
    except Exception as e:
        print(f"(No se pudo generar PNG: {e}. Instala kaleido: pip install -U kaleido)")