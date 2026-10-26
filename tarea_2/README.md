# Tarea 2 · Del papel y la voz al texto estructurado (OCR + ASR + LLM)

**Estudiante:** Sandy Patricia Martinez Jara (@sandypmj) · Curso Data Science con Python (d2cml-ai), 2026

**Dashboard:** https://tarea2-sandy.streamlit.app

## Pregunta del proyecto

> ¿Pueden convertir documentos escaneados y entrevistas en audio en un archivo de texto estructurado y buscable?

## Corpus y fuentes

Fecha de extracción: **2026-10-24**. La licencia, el autor y la URL de cada archivo están en [`datos/fuentes.csv`](datos/fuentes.csv); las licencias de Commons se leyeron de su API, no se escribieron a mano.

| Modalidad | Fuente | Cantidad | Licencia |
|---|---|---|---|
| Documentos | Wikimedia Commons (resolución municipal, *Mercurio Peruano*, billetes, fotos de placa y pizarra, manuscritos históricos) | 13 | CC0 (6), dominio público (4), CC BY 4.0 (1), CC BY 3.0 (1), CC BY-SA 3.0 (1) |
| Documentos | Capturas propias con celular, sin datos personales (no se publican las imágenes) | 12 | CC BY 4.0, autora: la estudiante |
| Audio | [OpenSLR 73](https://www.openslr.org/73/), Crowdsourced Peruvian Spanish (lectura en estudio) | 23 clips | CC BY-SA 4.0 |
| Audio | Entrevistas de Wikimedia Commons (El Agustino, Lima; Fenmucarinap) | 8 clips | CC BY-SA 4.0 |

- **25 documentos:** 8 impresos, 8 fotos y 9 manuscritos.
- **31 clips:** 34,1 minutos en total; 8 son entrevistas en exteriores con ruido y 2 o más hablantes, y 23 son lecturas en estudio (limpio).

## Proceso

1. **Descarga y limpieza** (`01_extraccion.ipynb`): descarga desde la API de Commons y OpenSLR. Los duplicados se detectan con una huella MD5 del contenido.
2. **OCR:** PaddleOCR 3.7.0 (`lang=es`, sin corrección de orientación ni *unwarping*).
3. **ASR:** faster-whisper `small` (int8, CPU, beam 5, VAD activado). La diarización se hizo con huellas de voz WeSpeaker ResNet34 y agrupamiento jerárquico, y marca `[HABLANTE_n]` en el texto.
4. **Descartes:** 1 documento ilegible (0 caracteres reconocidos) se descartó y se **reemplazó** por una foto nueva. El motivo está en [`datos/descartes.csv`](datos/descartes.csv).
5. **Seudonimización:** se reemplazaron **10 entidades** (2 DNI y 8 nombres de personas) por marcas como `[DNI]` y `[PERSONA_n]`. Se usaron patrones y comparación difusa, con revisión humana. El conteo está en [`datos/seudonimizacion_reporte.csv`](datos/seudonimizacion_reporte.csv).
6. **Evaluación** (`02_evaluacion.ipynb`):
   - Se sorteó una muestra de 10 documentos y 10 clips (semilla 2026), y la estudiante los transcribió a mano como referencia.
   - Se midió el **CER** en documentos y el **WER** en audio, con la misma normalización para referencia y salida.
   - Se compararon contra modelos alternativos y se midió la latencia: segundos por página en OCR y RTF en ASR.
7. **Extracción estructurada:** Gemini 3.5 Flash-Lite (temperatura 0; reemplazó, antes de ver resultados, a 2.5 Flash —no disponible para claves nuevas— y a 3.8 Flash —saturado: 503 y cuota diaria agotada—; respuesta JSON con esquema fijo, `null` si el dato no aparece). Se auditaron a mano 20 extracciones.

## Resultados

| Modalidad | Modelo | Rol | Métrica | Error global | Latencia |
|---|---|---|---|---|---|
| Documentos | PaddleOCR 3.7.0 | línea base | CER | 0.42 | 121.4 s/página |
| Documentos | EasyOCR | alternativo | CER | 0.61 | 26.7 s/página |
| Audio | faster-whisper small | línea base | WER | 0.16 | RTF 0.29 |
| Audio | Qwen3-ASR 0.6B | alternativo | WER | 0.18 | RTF 0.76 |
| Extracción | Gemini 3.5 Flash-Lite | — | acuerdo con humano | 15/20 | — |

**Casos difíciles:** los manuscritos (apuntes de otra persona, cursiva) y la página de periódico fotografiada con inclinación concentran el mayor CER; incluso en la transcripción manual hubo palabras ilegibles. En audio, las entrevistas en la calle (ruido y voces superpuestas) tienen más WER que la lectura limpia de OpenSLR 73.

**Decisión:** elegiría PaddleOCR (CER 0.42 vs 0.61 de EasyOCR) y faster-whisper small (WER 0.16 vs 0.18 de Qwen3-ASR): son más precisos y corren en CPU sin GPU.

Las tablas completas están en [`datos/metricas.csv`](datos/metricas.csv), [`datos/resultados_evaluacion.csv`](datos/resultados_evaluacion.csv) y [`datos/resumen_resultados.json`](datos/resumen_resultados.json).

### Hallazgos

1. PaddleOCR supera a EasyOCR en todos los tipos, pero ambos fallan en manuscritos.
2. El ruido de calle aumenta el WER frente a la lectura en estudio.

### Limitaciones

1. Parakeet no cargó (falta librosa) y Gemini 2.5/3.8 Flash no estuvieron disponibles: se usaron Qwen3-ASR y Gemini 3.5 Flash-Lite, decididos antes de ver resultados.
2. Solo 10 casos por modalidad y la diarización sobreestima hablantes en clips cortos.
3. **Problemas de entorno en Windows/CPU:**
   - Escribir audio en OGG/Vorbis con `soundfile` hacía caer el kernel, así que los ejemplos publicados son **WAV recortados a 30 s**.
   - PaddleOCR 3.x solo funcionó con `enable_mkldnn=False`, lo que lo hace más lento en CPU.

## Cómo ejecutar el dashboard en local

Desde la raíz del repositorio, con Python 3.12:

```bash
cd tarea_2
uv venv --python 3.12                # opcional: entorno nuevo
uv pip install -r requirements.txt   # o bien: pip install -r requirements.txt
streamlit run app.py
```

En Streamlit Community Cloud: *Main file path* = `tarea_2/app.py` (toma `tarea_2/requirements.txt`).

El dashboard **solo lee** los CSV/JSON de `datos/` y los ejemplos de `datos/ejemplos/`; no carga ningún modelo. Los notebooks necesitan además PaddleOCR, faster-whisper, EasyOCR, Qwen3-ASR y `google-genai`, que no están en este `requirements.txt`. `datos/raw/`, `datos/referencias/` (transcripciones manuales, pueden tener nombres reales) y `.env` (clave de Gemini) **no se suben** a GitHub.

## Uso de IA

- **Claude** (claude.ai): consultas para planificar la tarea y resolver dudas de conceptos (CER/WER, diarización, seudonimización).
- **Claude Code** (extensión de VS Code), sobre código y decisiones de la estudiante:
  - corrigió `utiles.mostrar()` para que los gráficos Plotly se vean en GitHub;
  - cambió la exportación de ejemplos de OGG a WAV de 30 s;
  - escribió las celdas de evaluación, extracción con LLM y auditoría de `02_evaluacion.ipynb`;
  - escribió `app.py` y la estructura de este README.
- **Qué no hizo la IA:** las transcripciones de referencia son manuales y no se copiaron de ningún modelo; la auditoría de las 20 extracciones, los hallazgos y la elección de modelos son de la estudiante.
- Capturas de las conversaciones: [`evidencias_ia/`](evidencias_ia/) [COMPLETAR: agregar las capturas].
