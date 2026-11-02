# La violencia contra las mujeres persiste: territorios e identidad en el Perú

**Autora:** Sandy Patricia Martinez Jara · Tarea 3, Python Intermedio

**Tema:** violencia ejercida por el esposo o compañero contra las mujeres de 15 a 49 años alguna vez unidas en el Perú.

**Pregunta:** ¿Dónde y a quiénes golpea más? ¿Qué ha cambiado?

## Descripción

El proyecto tiene dos productos, construidos con Python a partir de los cuadros oficiales de la ENDES 2025:

- **Dashboard interactivo:** permite elegir indicador, año, año de comparación y territorio. Muestra KPIs, evolución 2021–2025, formas de violencia, diferencias por identidad y área de residencia, mapa y ranking, con descarga en CSV de los datos del ranking.
- **Reel vertical:** video de 52 segundos que resume los hallazgos, con voz clonada, subtítulos y música de fondo.

**Cobertura:** 26 territorios: 23 departamentos, Lima Metropolitana, Departamento de Lima (Lima Provincias) y el Callao (como los publica el INEI) · 2021–2025.

**Grupos analizados:** autoidentificación étnica, lengua materna y área de residencia.

## Enlaces

- **Dashboard:** https://sandypmj.github.io/python_intermedio_2026/tarea_3/web/
- **Video:** [reel/salidas/reel.mp4](reel/salidas/reel.mp4)
- **LinkedIn:** [ENLACE_LINKEDIN]

## Hallazgos

1. **Disminuye, pero sigue siendo alta.** Si bien los porcentajes de violencia hacia las mujeres han disminuido en los últimos años, aún son muy elevados: casi la mitad de las mujeres de 15 a 49 años alguna vez unidas ha sufrido algún tipo de violencia ejercida por el esposo o compañero. En 2025, el 49,1 % de estas mujeres sufrió violencia por parte de su pareja, en comparación con el 76,9 % registrado en 2009. La forma más común es la violencia psicológica y/o verbal, que alcanza el 45,6 %.
2. **Existen disparidades territoriales marcadas.** Apurímac, con 66,1 %, tiene el nivel más alto de violencia por tercer año consecutivo, mientras que Cajamarca, con 36,8 %, presenta la cifra más baja. En 14 de los 26 territorios analizados, más de la mitad de las mujeres alguna vez unidas ha experimentado alguna forma de violencia.
3. **La disminución no ha sido igual en todo el territorio.** Entre 2022 y 2025, 9 de los 26 territorios mostraron una disminución estadísticamente significativa, entre ellos Junín (−14,7 puntos porcentuales), Cajamarca (−14,5) y Loreto (−13,9). Ningún territorio incrementó significativamente sus cifras, aunque Apurímac, Huancavelica y Tumbes continúan con niveles altos y estancados.
4. **La identidad también marca diferencias.** En 2025, las mujeres de origen nativo (54,4 %) y con lengua materna nativa (53,2 %) registran niveles de violencia más altos que las mestizas (48,2 %) y las de lengua castellana (48,3 %). En cambio, el área urbana (49,8 %) supera ligeramente a la rural (46,5 %).

## Fuentes

- INEI, [Perú: Encuesta Demográfica y de Salud Familiar – ENDES 2025](https://www.gob.pe/institucion/inei/informes-publicaciones/8284085-peru-encuesta-demografica-y-de-salud-familiar-endes-2025), capítulo 12.
- Límites territoriales: [juaneladio/peru-geojson](https://github.com/juaneladio/peru-geojson) (cartografía del INEI).

## Metodología

- **Datos:** los datos provienen de los cuadros oficiales del capítulo 12 del informe «Perú: Encuesta Demográfica y de Salud Familiar 2025 – Nacional y departamental», del Instituto Nacional de Estadística e Informática (INEI), en formato Excel.
- **Población:** mujeres de 15 a 49 años que han estado alguna vez casadas o en convivencia, considerando la violencia ejercida por el esposo o compañero.
- **Procesamiento:** se emplearon herramientas de programación en Python (bibliotecas pandas y openpyxl) para leer los cuadros 12.1, 12.4 y 12.1.1 (serie nacional 2009–2025). Se limpiaron los nombres y los valores referenciales, que estaban escritos como texto, y se transformaron todos los datos a formato largo.
- **Prueba de cambio:** a partir del intervalo de confianza al 95 % publicado por el INEI se calculó el error estándar y el estadístico z. Un cambio se considera significativo si |z| > 1,96.

```text
ee = (superior − inferior) / 3,92
z  = (valor 2025 − valor 2022) / √(ee₂₀₂₂² + ee₂₀₂₅²)
```

## Limitaciones

- La muestra de la encuesta se limita a mujeres de 15 a 49 años que han estado alguna vez unidas, y excluye otras poblaciones.
- Los datos reflejan violencia declarada en una encuesta: el miedo o la vergüenza pueden conducir a un subregistro.
- A nivel departamental, la muestra es de unos pocos cientos de mujeres, por lo que las diferencias pequeñas no son concluyentes.
- El análisis es de carácter descriptivo: una disminución en los índices no prueba por sí sola el efecto de una política específica.
- Algunos valores son referenciales: el INEI publica entre paréntesis los estimadores con un coeficiente de variación de 15,0 % a 49,9 %. Este dashboard los muestra sin paréntesis, por lo que deben leerse con cautela; por ejemplo, las cifras de mujeres negras, morenas o zambas y de mujeres blancas en violencia sexual y en los últimos 12 meses (2025). La categoría «Extranjera» de lengua materna se omitió por ser muy imprecisa.

## Cómo reproducirlo

### Dashboard

Desde la carpeta `tarea_3/`, con `pandas`, `openpyxl`, `numpy` y `matplotlib` instalados:

```bash
python scripts/explorar.py        # opcional: revisa las hojas del Excel
python scripts/explorar2.py       # opcional: revisa las columnas de los cuadros
python scripts/departamentos.py   # opcional: primera versión, por departamento (no alimenta el dashboard)
python scripts/indicadores.py     # Excel -> datos/procesados/indicadores_mi_version.csv
python scripts/exportar_web.py    # CSV -> web/datos.js
python scripts/preparar_mapa.py   # límites GeoJSON -> web/geo.js
python scripts/hallazgos.py       # imprime las cifras y la prueba z; guarda datos/procesados/ranking_2025.png
```

Después, abre `web/index.html` en el navegador.

Los scripts de `scripts/` no leen la hoja 12.1.1: el valor de 2009 (76,9 %) se comprobó directamente en esa hoja del Excel.

### Reel

Desde la carpeta `tarea_3/reel/`, con `qwen-tts`, `faster-whisper`, `pillow`, `imageio-ffmpeg`, `soundfile`, `jiwer`, `num2words`, `numpy`, `matplotlib` y `pandas` instalados:

```bash
python hacer_reel.py --voz mi_voz.mp4 --autor "Sandy Patricia Martinez Jara" --musica recursos/musica_propia.mp3 --credito-musica "Música original generada con Python"
```

Para revisar solo el diseño, sin voz ni modelos, se puede usar `--prueba` en lugar de `--voz mi_voz.mp4`.

- **Voz:** `mi_voz.*` no se sube al repositorio porque está en `.gitignore`. Para generar el reel hay que grabar 15 a 25 segundos de voz propia y guardarlos en `reel/` con ese nombre.
- **Salidas:** se guardan en `reel/salidas/`. Volver a generar el reel sobrescribe `posts.md`, y los textos de X y Facebook vuelven a decir `[ENLACE]`, porque así están en `guion.json`.
- **Imágenes:** las escenas ya están en `reel/recursos/`. `generar_imagenes.py` no se puede ejecutar con este repositorio, porque necesita archivos que no están incluidos: `indicadores.csv`, `serie_nacional.csv`, `cambios_departamentales.csv` y `web/data/territorios.geojson`.
- **Música:** `generar_musica.py` genera una pista original con numpy; `recursos/musica_propia.mp3` es esa misma pista comprimida.
- **Código del curso:** `reel.py` es una copia del material del curso (sesión 15), como indica su encabezado.

## Uso de IA

- Usé Claude (chat y Claude Code) para guiarme, escribir y depurar código y mejorar el diseño.
- Revisé las cifras contra los cuadros del INEI.
- La voz del reel es mi propia voz clonada con Qwen3-TTS, y los subtítulos se hicieron con Whisper.

---

Si tú o alguien que conoces vive violencia, llama gratis a la **Línea 100**.
