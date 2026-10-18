# Tarea 1 · Clasificador de titulares peruanos

## Pregunta del proyecto

**¿Pueden convertir titulares peruanos en un clasificador de noticias?**

Es decir: a partir de titulares reales de un diario peruano, ¿se puede construir un modelo que clasifique noticias en
4 categorías (`politica`, `economia`, `deportes`, `ciencia_tecnologia`) **sin etiquetar a mano**, usando un LLM como
anotador (*supervisión débil*) y un transformer propio entrenado con esas etiquetas?

| Parte | Archivo | Contenido |
|---|---|---|
| 1. Recolección | `01_recoleccion.ipynb` | RSS y portadas de sección → `datos/noticias.csv` (401 noticias) |
| 2. Clasificación | `02_clasificacion.ipynb` | Split 70/15/15, zero-shot, etiquetado con Gemini, auditoría humana, fine-tuning de DistilBERT, evaluación |
| 3. Dashboard | `app.py` | Streamlit: indicadores, filtros, gráfico, tabla descargable y probador en vivo |

## Medio y fechas de extracción

- **Medio:** La República (Perú) — https://larepublica.pe (RSS oficiales y portadas de sección, respetando `robots.txt`).
- **Fechas de publicación de las noticias:** del **23/09/2026 al 17/10/2026**.
- **Fecha de descarga:** **18/10/2026**.

## Hallazgos

1. **La supervisión débil con un LLM funciona.** Gemini (`gemini-3.8-flash`) coincidió con la sección del diario en
   el 96.7 % de las noticias de test y obtuvo **95 % de acuerdo (19/20)** en la auditoría humana. El DistilBERT
   entrenado solo con esas etiquetas alcanzó **F1 macro = 0.920** en test, frente a **0.577** del baseline zero-shot:
   sin etiquetar a mano se obtiene un clasificador propio, local y ≈6–9 veces más rápido que consultar al LLM.
2. **La dificultad está en la frontera política–economía.** `deportes` es la categoría más fácil (F1 = 1.00) por su
   vocabulario propio (clubes, Liga 1, partidos), mientras que `economia` es la más difícil (F1 = 0.84): en el Perú
   muchas noticias económicas pasan por el Estado (créditos suplementarios en el Congreso, reformas del MEF) y
   comparten vocabulario con política. El zero-shot no acertó ninguna noticia de economía.

## Limitaciones

1. **Ruido en la sección política.** La República publica en "política" algunas notas que no lo son, por ejemplo
   notas religiosas de la edición impresa, como la noticia sobre la salud del papa León XIV detectada en la
   auditoría. Como el esquema de 4 categorías es cerrado, cualquier modelo está obligado a asignarles una etiqueta
   incorrecta. Además, el dataset es pequeño (61 noticias de test: cada error vale ≈1.6 puntos de accuracy) y
   proviene de un solo medio y de un período de menos de un mes.
2. **Los pesos del modelo no están en GitHub.** `modelo/model.safetensors` pesa ≈540 MB (más que el límite de
   100 MB de GitHub), por eso está en `.gitignore`. Solo se suben `config.json` y el tokenizer. Para usar el
   probador del dashboard hay que ejecutar primero `02_clasificacion.ipynb`, que re-entrena el modelo (≈3 min en CPU)
   y lo guarda en `modelo/`.

## Cómo ejecutar en local

Requisitos: [uv](https://docs.astral.sh/uv/) y Git. Los comandos son para **Windows PowerShell**
(en macOS/Linux, activar con `source .venv/bin/activate`).

```powershell
# 1. Clonar el repositorio
git clone https://github.com/sandypmj/python_intermedio_2026.git
cd python_intermedio_2026

# 2. Crear el entorno virtual con Python 3.12 y activarlo
uv venv .venv --python 3.12
.venv\Scripts\Activate.ps1

# 3. Instalar las dependencias
uv pip install -r tarea_1/requirements.txt

# 4. Entrar a la carpeta de la tarea
cd tarea_1
```

5. **Entrenar el modelo (solo la primera vez):** abrir `02_clasificacion.ipynb` en VS Code o Jupyter con el kernel
   de `.venv` y ejecutar todas las celdas (≈5 min en CPU). No hace falta llave de Gemini: las etiquetas del LLM ya
   están en caché en `datos/etiquetas_llm.csv`. Solo para volver a etiquetar desde cero se necesita un archivo
   `tarea_1/.env` con `GEMINI_API_KEY=...` (nunca se sube a GitHub).

6. **Iniciar el dashboard:**

   ```powershell
   streamlit run app.py
   ```

   Se abre en http://localhost:8501. Sin el paso 5 el dashboard funciona igual, pero el probador en vivo muestra un
   aviso pidiendo entrenar el modelo.

## Transparencia sobre el uso de IA

- **Claude Code** (Anthropic) se usó como asistente de programación para escribir y ejecutar el código de los
  notebooks y del dashboard, con revisión humana en cada etapa (las decisiones de método, la auditoría de las etiquetas y la interpretación de
  resultados fueron propias).
- **Gemini** (`gemini-3.8-flash`, Google) se usó como herramienta del método: etiquetó las 401 noticias
  (supervisión débil). Sus etiquetas fueron auditadas manualmente (20 casos) y evaluadas contra la sección original.
