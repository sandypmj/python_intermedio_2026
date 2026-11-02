"""Música de fondo original: un fondo suave de acordes generado con numpy (ya incluida como recursos/musica_propia.mp3).

Uso:  python generar_musica.py   ->  recursos/musica_propia.wav (75 s; la versión .mp3 incluida es la misma pista comprimida)

Sirve si no encuentras una pista con licencia adecuada: al generarla tú, no depende de licencias de terceros.
Si prefieres música "de verdad", descarga una pista de Pixabay Music (licencia libre para uso en redes) o de la
Biblioteca de audio de YouTube, guárdala en recursos/ y anota título y autor en --credito-musica.
"""
from pathlib import Path

import numpy as np
import wave

SR, DUR = 44100, 75
t = np.arange(SR * DUR) / SR
# Progresión lenta y serena (la menor - fa - do - sol), 8 segundos por acorde
ACORDES = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [196.0, 261.63, 329.63], [196.0, 246.94, 293.66]]
audio = np.zeros_like(t)
for k, inicio in enumerate(np.arange(0, DUR, 8.0)):
    m = (t >= inicio) & (t < inicio + 9.0)                          # 1 s de solapamiento entre acordes
    tt = t[m] - inicio
    envolvente = np.minimum(1, tt / 2.5) * np.minimum(1, (9.0 - tt) / 2.5)
    for f in ACORDES[k % 4]:
        for detune in (0.997, 1.003):                               # dos osciladores un poco desafinados = textura de "pad"
            audio[m] += envolvente * np.sin(2 * np.pi * f * detune * tt) * 0.06
            audio[m] += envolvente * np.sin(2 * np.pi * f * 2 * detune * tt) * 0.015
    bajo = ACORDES[k % 4][0] / 2
    audio[m] += envolvente * np.sin(2 * np.pi * bajo * tt) * 0.05
audio *= 0.8 / np.abs(audio).max()
salida = Path(__file__).parent / "recursos" / "musica_propia.wav"
with wave.open(str(salida), "wb") as w:            # WAV estéreo de 16 bits, sin librerías extra
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((np.repeat(audio[:, None], 2, axis=1) * 32767).astype("<i2").tobytes())
print(f"Guardado {salida} ({DUR} s)")
