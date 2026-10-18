"""Dashboard de la Tarea 1: clasificador de titulares peruanos.

Para ejecutarla (desde la carpeta tarea_1/):  streamlit run app.py
"""

import json
import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

BASE = Path(__file__).parent
DATOS = BASE / "datos"
MODELO_DIR = BASE / "modelo"
NOTEBOOK_CLASIF = BASE / "02_clasificacion.ipynb"

ETIQUETAS = ["politica", "economia", "deportes", "ciencia_tecnologia"]
NOMBRES = {"politica": "Política", "economia": "Economía",
           "deportes": "Deportes", "ciencia_tecnologia": "Ciencia y tecnología"}
COLORES = {"Política": "#4C72B0", "Economía": "#DD8452",
           "Deportes": "#55A868", "Ciencia y tecnología": "#8172B3"}

# Valores de respaldo, tomados de las salidas de 02_clasificacion.ipynb:
#   - F1 macro en test: celda "6. Evaluación final en test" -> "Fine-tuned (test, n=61) ... F1 macro=0.920"
#   - Concordancia LLM vs humano: celda "Resultado de la revisión manual" -> "Acuerdo humano-LLM: 19/20 = 95%"
# Solo se usan si no se puede leer el notebook.
F1_RESPALDO = 0.920
ACUERDO_RESPALDO = (19, 20)

st.set_page_config(page_title="Clasificador de titulares peruanos", page_icon="📊", layout="wide")


# ------------------------------------------------------------------ carga de datos
@st.cache_data
def cargar_noticias():
    df = pd.read_csv(DATOS / "noticias.csv")
    llm = pd.read_csv(DATOS / "etiquetas_llm.csv")  # mismo orden de filas que noticias.csv
    df["etiqueta_llm"] = llm["etiqueta_llm"].values
    df["confianza"] = llm["confianza"].values
    df["categoria"] = df["etiqueta"].map(NOMBRES)
    return df


@st.cache_data
def leer_metricas_notebook():
    """Lee el F1 macro del fine-tuned y el acuerdo LLM-humano desde las salidas del notebook (sin modificarlo)."""
    f1, acuerdo = F1_RESPALDO, ACUERDO_RESPALDO
    try:
        nb = json.loads(NOTEBOOK_CLASIF.read_text(encoding="utf-8"))
        textos = ["".join(o.get("text", "")) for c in nb["cells"] if c["cell_type"] == "code"
                  for o in c.get("outputs", [])]
        salida = "\n".join(textos)
        m = re.search(r"Fine-tuned \(test.*?F1 macro=([0-9.]+)", salida)
        if m:
            f1 = float(m.group(1))
        m = re.search(r"Acuerdo humano-LLM: (\d+)/(\d+)", salida)
        if m:
            acuerdo = (int(m.group(1)), int(m.group(2)))
    except (OSError, ValueError, KeyError):
        pass
    return f1, acuerdo


@st.cache_resource
def cargar_modelo():
    """Carga el DistilBERT fine-tuned guardado en modelo/. Devuelve None si faltan los pesos."""
    if not (MODELO_DIR / "model.safetensors").exists():
        return None
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(MODELO_DIR)
    modelo = AutoModelForSequenceClassification.from_pretrained(MODELO_DIR)
    modelo.eval()
    return tokenizer, modelo


def clasificar(texto, tokenizer, modelo):
    import torch

    entradas = tokenizer(texto, return_tensors="pt", truncation=True, max_length=64)
    with torch.no_grad():
        probs = torch.softmax(modelo(**entradas).logits, dim=-1)[0].tolist()
    return {modelo.config.id2label[i]: p for i, p in enumerate(probs)}


df = cargar_noticias()
f1_test, (aciertos, auditados) = leer_metricas_notebook()

# ------------------------------------------------------------------ encabezado
st.markdown("<h1 style='text-align:center'>📊 ¿Pueden convertir titulares peruanos en un clasificador de noticias?</h1>",
            unsafe_allow_html=True)
st.markdown("### *¿Cómo se hizo?*")
st.markdown(
    """
1. **Recolección:** 401 noticias de **La República** (Perú): 44 de sus RSS oficiales y 357 de páginas de artículo,
   alcanzadas con un recorrido que partió de los enlaces del RSS y de las portadas de sección y siguió los enlaces
   internos entre artículos, verificando `robots.txt` antes de cada solicitud.
2. **Etiquetado con Gemini:** `gemini-3.8-flash` asignó una de 4 categorías (política, economía, deportes,
   ciencia y tecnología) a cada noticia con un prompt estructurado (*supervisión débil*).
3. **Auditoría humana:** se revisaron a mano 20 etiquetas del LLM al azar.
4. **Fine-tuning:** se entrenó **DistilBERT multilingüe** con las etiquetas de Gemini.
5. **Evaluación:** en un conjunto de test aislado, contra la etiqueta original, comparado con un baseline zero-shot.
"""
)

c1, c2, c3 = st.columns(3)
c1.metric("Noticias recolectadas", f"{len(df)}")
c2.metric("F1 macro del modelo en test", f"{f1_test:.3f}", help="DistilBERT fine-tuned, 61 noticias de test")
c3.metric("Concordancia LLM vs auditoría humana", f"{aciertos / auditados:.0%}",
          help=f"{aciertos} de {auditados} etiquetas de Gemini revisadas a mano fueron correctas")
st.caption(f"Concordancia: {aciertos}/{auditados} etiquetas correctas en la auditoría humana.")

# ------------------------------------------------------------------ filtros
st.sidebar.header("Filtros")
medios = sorted(df["medio"].unique())
sel_medios = st.sidebar.multiselect("Medio", medios, default=medios)
categorias = [NOMBRES[e] for e in ETIQUETAS]
sel_cats = st.sidebar.multiselect("Categoría", categorias, default=categorias)

filtrado = df[df["medio"].isin(sel_medios) & df["categoria"].isin(sel_cats)]
st.sidebar.markdown(f"**{len(filtrado)}** de {len(df)} noticias seleccionadas")

# ------------------------------------------------------------------ gráfico y tabla
st.subheader("Distribución de categorías")
if filtrado.empty:
    st.info("No hay noticias con los filtros elegidos. Selecciona al menos un medio y una categoría.")
else:
    conteo = (filtrado["categoria"].value_counts().reindex([c for c in categorias if c in sel_cats])
              .fillna(0).astype(int).rename_axis("categoría").reset_index(name="noticias"))
    fig = px.bar(conteo, x="categoría", y="noticias", color="categoría", text="noticias",
                 color_discrete_map=COLORES)
    fig.update_layout(showlegend=False, height=380, margin=dict(t=20, b=10))
    st.plotly_chart(fig, width="stretch")

st.subheader("Noticias")
# mismo orden que noticias.csv, seguido de las columnas del LLM (el CSV descargado usa este orden)
COLUMNAS_TABLA = ["titular", "bajada", "medio", "seccion_original", "url", "fecha", "etiqueta",
                  "etiqueta_llm", "confianza"]
tabla = filtrado[COLUMNAS_TABLA]
st.dataframe(
    tabla, width="stretch", hide_index=True,
    column_config={
        "confianza": st.column_config.NumberColumn("confianza", format="%.2f"),
        "url": st.column_config.LinkColumn("url"),
    },
)
st.download_button("⬇️ Descargar CSV filtrado", tabla.to_csv(index=False).encode("utf-8-sig"),
                   file_name="noticias_filtradas.csv", mime="text/csv", disabled=filtrado.empty)

# ------------------------------------------------------------------ probador en vivo
st.subheader("Probador en vivo")
recursos = cargar_modelo()
if recursos is None:
    st.warning(
        "No se encontraron los pesos del modelo (`modelo/model.safetensors`). Por su tamaño (~540 MB) no están "
        "en GitHub. Ejecuta primero **`02_clasificacion.ipynb`** para entrenar y guardar el modelo en `modelo/`, "
        "y luego recarga esta página."
    )
else:
    texto = st.text_input("Escribe un titular nuevo:",
                          placeholder="Ej.: Universitario venció 2-0 a Sporting Cristal en el Estadio Nacional")
    if st.button("Clasificar", type="primary"):
        if not texto.strip():
            st.warning("Primero escribe un titular.")
        else:
            probs = clasificar(texto, *recursos)
            ganadora = max(probs, key=probs.get)
            st.success(f"Categoría predicha: **{NOMBRES[ganadora]}** — probabilidad {probs[ganadora]:.1%}")
            if probs[ganadora] < 0.80:
                st.warning("Confianza baja: este titular podría no pertenecer claramente a ninguna de las 4 categorías")
            dfp = pd.DataFrame({"categoría": [NOMBRES[e] for e in ETIQUETAS],
                                "probabilidad": [probs[e] for e in ETIQUETAS]})
            figp = px.bar(dfp, x="probabilidad", y="categoría", orientation="h", color="categoría",
                          color_discrete_map=COLORES, text=dfp["probabilidad"].map("{:.1%}".format))
            figp.update_layout(showlegend=False, height=260, margin=dict(t=10, b=10), xaxis_range=[0, 1])
            st.plotly_chart(figp, width="stretch")
