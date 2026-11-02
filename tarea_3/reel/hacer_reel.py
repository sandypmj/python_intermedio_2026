"""Paso 3b · guion.json + imágenes + tu voz + música -> reel vertical 1080 × 1920.

Extiende el flujo de la Sesión 15 (reel.py, sin cambios) con dos cosas que pide la Tarea 3:
    · una imagen por escena (gráfico, mapa o captura del dashboard) con un zoom lento, y
    · una pista de música de fondo, por debajo de la narración.

Uso (desde la carpeta tarea_3/reel/):
    python hacer_reel.py --voz mi_voz.m4a --autor "Nombre Apellido" \
        --musica recursos/musica.mp3 --credito-musica "Música: <título> · <autor> (Pixabay)"

    # Solo para probar el diseño sin voz ni modelos (usa una voz sintética muda y tiempos fijos):
    python hacer_reel.py --prueba --autor "Nombre Apellido"

Salidas en salidas/: reel.mp4 (final con música), reel_sin_musica.mp4, reel.srt, portada.png, posts.md
"""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import reel
from reel import ALTO, ANCHO, MARGEN, SUAVE, TEXTO, FFMPEG

AQUI = Path(__file__).parent
FUENTE = "INEI, ENDES 2025"
IMG_W, IMG_Y = ANCHO - 2 * MARGEN, 640          # caja de la imagen: 900 px de ancho desde y = 640
IMG_H = 590

p = argparse.ArgumentParser()
p.add_argument("--voz", help="15 a 25 s de tu voz: wav, m4a, ogg u opus")
p.add_argument("--autor", required=True)
p.add_argument("--fuente", default=FUENTE)
p.add_argument("--musica", help="mp3/wav con licencia de uso; si falta, el reel sale sin música")
p.add_argument("--credito-musica", default="", help="aparece al pie, junto a la fuente")
p.add_argument("--volumen-musica", type=float, default=0.12, help="0.12 ≈ -18 dB bajo la voz")
p.add_argument("--device", default="cpu", help="cpu, mps (Mac) o cuda")
p.add_argument("--motor", default="qwen", choices=["qwen", "voxcpm"])
p.add_argument("--tts", default="Qwen/Qwen3-TTS-12Hz-0.6B-Base")
p.add_argument("--velocidad", type=float, default=1.0)
p.add_argument("--prueba", action="store_true", help="sin voz ni Whisper: para revisar el diseño")
a = p.parse_args()

salidas = AQUI / "salidas"
salidas.mkdir(exist_ok=True)
guion = json.loads((AQUI / "guion.json").read_text(encoding="utf-8"))
imagenes = []
for e in guion["escenas"]:
    ruta = AQUI / e["imagen"] if e.get("imagen") else None
    imagenes.append(Image.open(ruta).convert("RGB") if ruta and ruta.exists() else None)


# --- diseño de escena: cifra y etiqueta arriba, imagen abajo ----------------------------------------
def escena_con_imagen(e):
    capa = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    y = 430
    if e.get("cifra"):
        f = reel._ajustar(d, e["cifra"], "Oswald", 700, IMG_W, 150)
        y += -d.textbbox((0, 0), e["cifra"], font=f, anchor="ls")[1]
        d.text((MARGEN, y), e["cifra"], font=f, fill=TEXTO, anchor="ls")
        y += 22
    fe = reel._fuente("PublicSans", 42, 600)
    for linea in reel._envolver(d, e["etiqueta"], fe, IMG_W):
        y += 48
        d.text((MARGEN, y), linea, font=fe, fill=SUAVE if e.get("cifra") else TEXTO, anchor="ls")
    return capa


reel._escena = escena_con_imagen
_cuadro_original = reel._cuadro


def cuadro_con_imagen(base, capas, narracion, t, bloques, fuente_sub):
    """Pega la imagen de la escena (con zoom lento de 100 % a 106 %) y luego dibuja lo de la clase encima."""
    i = max([k for k, (ini, _) in enumerate(narracion.escenas) if ini - reel.PAUSA <= t] or [0])
    img = imagenes[i] if i < len(imagenes) else None
    if img is not None:
        ini, fin = narracion.escenas[i]
        avance = min(1, max(0, (t - ini) / max(fin - ini, .1)))
        alfa = min(1.0, max(0.0, (t - ini + reel.PAUSA) / 0.35))
        z = 1 + 0.06 * avance
        w, h = int(IMG_W * z), int(IMG_W * z * img.height / img.width)
        grande = img.resize((w, h), Image.BILINEAR)
        recorte = grande.crop(((w - IMG_W) // 2, (h - IMG_H) // 2, (w - IMG_W) // 2 + IMG_W, (h - IMG_H) // 2 + IMG_H))
        base = base.copy()
        fondo = base.crop((MARGEN, IMG_Y, MARGEN + IMG_W, IMG_Y + IMG_H))
        base.paste(Image.blend(fondo, recorte, alfa), (MARGEN, IMG_Y))
    return _cuadro_original(base, capas, narracion, t, bloques, fuente_sub)


reel._cuadro = cuadro_con_imagen

# --- voz -------------------------------------------------------------------------------------------
pie = a.fuente + (f" · {a.credito_musica}" if a.credito_musica else "")
if a.prueba:
    # Narración muda con 2.5 palabras por segundo, para ver tiempos y diseño sin descargar modelos
    sr, partes, escenas, t = 24000, [np.zeros(int(reel.INICIO * 24000), np.float32)], [], reel.INICIO
    palabras = []
    for e in guion["escenas"]:
        ws = e["frase"].split()
        dur = len(ws) / 2.5
        for k, w in enumerate(ws):
            palabras.append((t + k * dur / len(ws), t + (k + 1) * dur / len(ws), w))
        escenas.append((t, t + dur))
        partes += [np.zeros(int((dur + reel.PAUSA) * sr), np.float32)]
        t += dur + reel.PAUSA
    partes.append(np.zeros(int(reel.FINAL * sr), np.float32))
    narracion = reel.Narracion(np.concatenate(partes), sr, escenas, palabras)
else:
    voz = (reel.VozExpresiva(a.voz, device=a.device) if a.motor == "voxcpm"
           else reel.Voz(a.voz, modelo=a.tts, device=a.device))
    print(f"Referencia transcrita: «{voz.texto_ref}»")
    narracion = reel.narrar(voz, guion, velocidad=a.velocidad)
    print("WER por escena:", ", ".join(f"{e['wer']:.2f}" for e in guion["escenas"]), "(revisen las que pasen de 0.15)")
    reel.subtitulos(narracion, guion)
print(f"Duración: {narracion.duracion:.1f} s (objetivo 45-75 s)")

reel.a_srt(narracion, salidas / "reel.srt")
reel.portada(guion, narracion, salidas / "portada.png", pie, a.autor)
sin_musica = reel.video(guion, narracion, salidas / "reel_sin_musica.mp4", pie, a.autor)

# --- música ----------------------------------------------------------------------------------------
final = salidas / "reel.mp4"
if a.musica:
    d = narracion.duracion
    filtro = (f"[1:a]aloop=loop=-1:size=2e9,atrim=0:{d:.2f},volume={a.volumen_musica},"
              f"afade=t=in:d=1.5,afade=t=out:st={max(d - 2.5, 0):.2f}:d=2.5[m];"
              f"[0:a][m]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]")
    subprocess.run([FFMPEG, "-y", "-v", "error", "-i", str(sin_musica), "-i", a.musica, "-filter_complex", filtro,
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", str(final)], check=True)
else:
    print("Sin --musica: el reel queda sin pista de fondo (la tarea la pide).")
    shutil.copy(sin_musica, final)
reel.posts(guion, salidas / "posts.md")
print(f"Listo: {final}")
