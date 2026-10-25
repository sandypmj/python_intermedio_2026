"""Tablero de la Tarea 2: corpus OCR + ASR, evaluación y extracción con LLM.

Solo lee los CSV/JSON que generan los notebooks (no carga ningún modelo):
    streamlit run tarea_2/app.py
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

BASE = Path(__file__).parent
DATOS = BASE / "datos"
PREGUNTA = "¿Pueden convertir documentos escaneados y entrevistas en audio en un archivo de texto estructurado y buscable?"
COLOR_ROL = {"línea base": "#2a78d6", "alternativo": "#eb6834"}
COLOR_TIPO = {"impreso": "#2a78d6", "foto": "#eb6834", "manuscrito": "#1baf7a"}
COLOR_CONDICION = {"limpio": "#2a78d6", "con ruido": "#eb6834"}

st.set_page_config(page_title="Tarea 2 · OCR + ASR", page_icon="📄", layout="wide")


# ───────────────────────────────────────────── datos
@st.cache_data
def leer_csv(nombre: str) -> pd.DataFrame | None:
    ruta = DATOS / nombre
    return pd.read_csv(ruta) if ruta.exists() else None


@st.cache_data
def leer_json(nombre: str) -> dict | None:
    ruta = DATOS / nombre
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None


def sin_tildes(texto: str) -> str:
    """Minúsculas y sin tildes: buscar 'resolucion' encuentra 'Resolución'."""
    t = unicodedata.normalize("NFD", str(texto).lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def contiene(textos: pd.Series, consulta: str) -> pd.Series:
    """True si el texto tiene TODAS las palabras de la consulta."""
    palabras = sin_tildes(consulta).split()
    base = textos.fillna("").map(sin_tildes)
    return base.map(lambda t: all(p in t for p in palabras))


def fragmento(texto: str, consulta: str, ancho: int = 90) -> str:
    """Trozo del texto alrededor de la primera palabra buscada, resaltada en negrita."""
    texto = str(texto)
    palabras = sin_tildes(consulta).split()
    if not palabras:
        return texto[: 2 * ancho]
    i = sin_tildes(texto).find(palabras[0])
    if i < 0:
        return texto[: 2 * ancho]
    a, b = max(0, i - ancho), i + len(palabras[0]) + ancho
    trozo = texto[a:i] + "**" + texto[i:i + len(palabras[0])] + "**" + texto[i + len(palabras[0]):b]
    return ("…" if a else "") + trozo.replace("\n", " ") + ("…" if b < len(texto) else "")


corto = lambda g: "con ruido" if "ruido" in str(g) else "limpio" if "limpio" in str(g) else g

docs = leer_csv("documentos.csv")
aud = leer_csv("transcripciones.csv")
metricas = leer_csv("metricas.csv")
resultados = leer_csv("resultados_evaluacion.csv")
extraccion = leer_csv("extraccion_llm.csv")
resumen = leer_json("resumen_resultados.json")

if docs is None or aud is None:
    st.error("No encuentro datos/documentos.csv o datos/transcripciones.csv. Ejecuta primero 01_extraccion.ipynb.")
    st.stop()
aud["condicion_corta"] = aud["condicion"].map(corto)
aud["fuente_corta"] = aud["fuente"].str.split(" \\(").str[0]
docs["fuente_corta"] = docs["fuente"].str.split(" \\(").str[0]
campos_llm = {}
if extraccion is not None:
    campos_llm = dict(zip(extraccion["id"], extraccion["campos_json"].map(json.loads)))

# ───────────────────────────────────────────── barra lateral
with st.sidebar:
    st.header("Buscar y filtrar")
    consulta = st.text_input("Palabras en el texto OCR o ASR", placeholder="p. ej. resolución, banco, partido",
                             help="Encuentra los textos que tienen todas las palabras (sin importar mayúsculas ni tildes).")
    tipos = st.multiselect("Tipo de documento", sorted(docs["tipo"].unique()), default=sorted(docs["tipo"].unique()))
    fuentes_todas = sorted(set(docs["fuente_corta"]) | set(aud["fuente_corta"]))
    fuentes = st.multiselect("Fuente", fuentes_todas, default=fuentes_todas)
    d_min, d_max = float(aud["duracion_seg"].min()), float(aud["duracion_seg"].max())
    duracion = st.slider("Duración del audio (s)", d_min, d_max, (d_min, d_max), step=1.0)
    modelos_todos = sorted(metricas["modelo"].unique()) if metricas is not None else []
    modelos = st.multiselect("Modelo (evaluación)", modelos_todos, default=modelos_todos,
                             disabled=not modelos_todos, help="Filtra la pestaña Evaluación.")
    st.caption("Los datos ya están seudonimizados: los nombres de personas aparecen como [PERSONA_n].")

f_docs = docs[docs["tipo"].isin(tipos) & docs["fuente_corta"].isin(fuentes)]
f_aud = aud[aud["fuente_corta"].isin(fuentes) & aud["duracion_seg"].between(*duracion)]
if consulta.strip():
    f_docs = f_docs[contiene(f_docs["texto_ocr"], consulta)]
    f_aud = f_aud[contiene(f_aud["texto_asr"], consulta)]
f_metricas = metricas[metricas["modelo"].isin(modelos)] if metricas is not None else None
f_resultados = resultados[resultados["modelo"].isin(modelos)] if resultados is not None else None

# ───────────────────────────────────────────── encabezado
st.title(PREGUNTA)
st.caption("Tarea 2 · Data Science con Python · Sandy Patricia Martinez Jara (@sandypmj)")

with st.expander("Resumen metodológico", expanded=False):
    st.markdown(f"""
- **Corpus:** {len(docs)} documentos ({", ".join(f"{n} {t}" for t, n in docs["tipo"].value_counts().items())})
  y {len(aud)} clips de audio ({aud["duracion_seg"].sum() / 60:.0f} min) de Wikimedia Commons, OpenSLR 73 y capturas propias,
  con la licencia registrada archivo por archivo (`datos/fuentes.csv`).
- **Extracción (línea base):** OCR con **PaddleOCR 3.7.0** sin ajuste; ASR con **faster-whisper `small`** en CPU con VAD,
  y diarización para marcar `[HABLANTE_n]`. Todo el texto se **seudonimizó** antes de publicarse.
- **Evaluación:** muestra fija de 10 documentos y 10 clips (semilla 2026) con **transcripción manual** como referencia.
  **CER** para documentos y **WER** para audio, con la misma normalización. Se compara con **EasyOCR** y **Qwen3-ASR 0.6B**,
  y se mide la latencia (segundos por página y RTF).
- **Extracción estructurada:** **Gemini 2.5 Flash** (temperatura 0, JSON con esquema) saca tema, resumen, emisor, fecha y monto
  (documentos) o citas y número de hablantes (audios), con `null` si el dato no está. **20 extracciones auditadas a mano.**
""")

# ───────────────────────────────────────────── indicadores
def num(clave):
    return resumen.get(clave) if resumen else None

c = st.columns(5)
c[0].metric("Documentos", f"{len(f_docs)} / {len(docs)}", help="Filtrados / total")
c[1].metric("Minutos de audio", f"{f_aud['duracion_seg'].sum() / 60:.1f}", help=f"{len(f_aud)} de {len(aud)} clips con los filtros")
c[2].metric("CER (OCR elegido)", f"{num('cer'):.2f}" if num("cer") is not None else "—",
            help=f"Modelo: {num('ocr_elegido')}" if resumen else "Pendiente: ejecuta 02_evaluacion.ipynb")
c[3].metric("WER (ASR elegido)", f"{num('wer'):.2f}" if num("wer") is not None else "—",
            help=f"Modelo: {num('asr_elegido')}" if resumen else "Pendiente: ejecuta 02_evaluacion.ipynb")
c[4].metric("Acuerdo LLM-humano",
            f"{num('acuerdo_llm') / num('auditados'):.0%}" if num("auditados") else "—",
            help=f"{num('acuerdo_llm')}/{num('auditados')} extracciones correctas" if num("auditados") else "Pendiente: auditoría")

if consulta.strip():
    st.info(f"Búsqueda «{consulta}»: {len(f_docs)} documentos y {len(f_aud)} audios contienen todas las palabras.")

tab_resumen, tab_docs, tab_aud, tab_eval = st.tabs(["Resumen", "Documentos", "Audios", "Evaluación"])

# ───────────────────────────────────────────── Resumen
with tab_resumen:
    izq, der = st.columns(2)
    por_tipo = f_docs.groupby(["tipo", "fuente_corta"]).size().reset_index(name="documentos")
    fig = px.bar(por_tipo, x="tipo", y="documentos", color="tipo", color_discrete_map=COLOR_TIPO,
                 hover_data=["fuente_corta"], title=f"{len(f_docs)} documentos por tipo",
                 category_orders={"tipo": ["impreso", "foto", "manuscrito"]})
    fig.update_layout(showlegend=False, template="plotly_white", bargap=0.35, xaxis_title="", yaxis_title="Documentos")
    izq.plotly_chart(fig, width="stretch")

    minutos = f_aud.groupby("condicion_corta")["duracion_seg"].sum().div(60).round(1).reset_index(name="minutos")
    fig = px.bar(minutos, x="condicion_corta", y="minutos", color="condicion_corta", color_discrete_map=COLOR_CONDICION,
                 title=f"{minutos['minutos'].sum():.1f} min de audio por condición", text="minutos")
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(showlegend=False, template="plotly_white", bargap=0.35, xaxis_title="", yaxis_title="Minutos")
    der.plotly_chart(fig, width="stretch")

    if consulta.strip():
        st.subheader("Coincidencias")
        for r in f_docs.itertuples():
            st.markdown(f"📄 **{r.id}** · {r.tipo} · {r.descripcion}  \n{fragmento(r.texto_ocr, consulta)}")
        for r in f_aud.itertuples():
            st.markdown(f"🎙️ **{r.id}** · {r.condicion_corta} · {r.descripcion}  \n{fragmento(r.texto_asr, consulta)}")

    if extraccion is not None:
        st.subheader("Extracción estructurada con LLM")
        tabla = pd.json_normalize(extraccion["campos_json"].map(json.loads))
        tabla.insert(0, "id", extraccion["id"])
        if "sospechosos" in extraccion:
            tabla["sospechosos"] = extraccion["sospechosos"].fillna("")
        visibles = set(f_docs["id"]) | set(f_aud["id"])
        st.dataframe(tabla[tabla["id"].isin(visibles)], hide_index=True, width="stretch")
    else:
        st.caption("La extracción con LLM aparecerá aquí cuando exista datos/extraccion_llm.csv.")

# ───────────────────────────────────────────── Documentos
with tab_docs:
    st.dataframe(f_docs[["id", "tipo", "fuente", "descripcion", "n_caracteres", "confianza_media", "segundos_proceso"]],
                 hide_index=True, width="stretch",
                 column_config={"confianza_media": st.column_config.ProgressColumn("confianza OCR", min_value=0, max_value=1),
                                "segundos_proceso": st.column_config.NumberColumn("segundos", format="%.1f")})
    if len(f_docs):
        elegido = st.selectbox("Ver un documento", f_docs["id"], format_func=lambda i: f"{i} · {docs.set_index('id').at[i, 'descripcion']}")
        r = docs.set_index("id").loc[elegido]
        izq, der = st.columns([1, 1])
        imagen = BASE / str(r["ejemplo"]) if isinstance(r["ejemplo"], str) else None
        if r["publicable"] and imagen is not None and imagen.exists():
            izq.image(str(imagen), caption=r["fuente"])
        else:
            izq.caption("Imagen no publicada (captura propia o archivo pesado); solo se muestra el texto.")
        der.text_area("Texto OCR (PaddleOCR)", r["texto_ocr"], height=320)
        if elegido in campos_llm:
            der.json(campos_llm[elegido])

# ───────────────────────────────────────────── Audios
with tab_aud:
    st.dataframe(f_aud[["id", "condicion_corta", "fuente", "descripcion", "duracion_seg", "n_hablantes", "n_palabras", "segundos_proceso"]],
                 hide_index=True, width="stretch",
                 column_config={"condicion_corta": "condición", "duracion_seg": st.column_config.NumberColumn("duración (s)", format="%.0f")})
    fig = px.histogram(f_aud, x="duracion_seg", color="condicion_corta", nbins=15, color_discrete_map=COLOR_CONDICION,
                       title="Duración de los clips", labels={"duracion_seg": "Duración (s)", "condicion_corta": "Condición"})
    fig.update_layout(template="plotly_white", bargap=0.08, yaxis_title="Clips")
    st.plotly_chart(fig, width="stretch")
    if len(f_aud):
        elegido = st.selectbox("Escuchar y leer un clip", f_aud["id"], format_func=lambda i: f"{i} · {aud.set_index('id').at[i, 'descripcion']}")
        r = aud.set_index("id").loc[elegido]
        sonido = BASE / str(r["ejemplo"]) if isinstance(r["ejemplo"], str) else None
        if sonido is not None and sonido.exists():
            st.audio(str(sonido))
            st.caption("Ejemplo recortado a 30 s.")
        texto = re.sub(r"\s*(\[HABLANTE_\d+\])", r"\n\n\1", r["texto_asr"]).strip()
        st.text_area("Transcripción (faster-whisper, con hablantes)", texto, height=320)
        if elegido in campos_llm:
            st.json(campos_llm[elegido])

# ───────────────────────────────────────────── Evaluación
with tab_eval:
    if f_metricas is None or f_resultados is None:
        st.info("Todavía no hay resultados de evaluación: ejecuta 02_evaluacion.ipynb (genera datos/metricas.csv).")
    else:
        st.markdown("**Error global** = errores totales / largo total de las referencias manuales. "
                    "**Promedio por caso** = media del error de cada documento o clip. Menor es mejor.")
        st.dataframe(f_metricas, hide_index=True, width="stretch")

        f_resultados = f_resultados.assign(grupo_corto=f_resultados["grupo"].map(corto))
        izq, der = st.columns(2)
        por_grupo = f_resultados.groupby(["modalidad", "grupo_corto", "rol", "modelo"], as_index=False)["valor"].mean()
        fig = px.bar(por_grupo, x="grupo_corto", y="valor", color="rol", barmode="group", facet_col="modalidad",
                     color_discrete_map=COLOR_ROL, hover_data=["modelo"], text="valor",
                     category_orders={"rol": ["línea base", "alternativo"], "modalidad": ["documento", "audio"]},
                     title="Error medio por tipo de documento y condición del audio",
                     labels={"valor": "CER (documentos) / WER (audio)", "grupo_corto": "", "rol": "Modelo"})
        fig.update_xaxes(matches=None)
        fig.update_traces(texttemplate="%{text:.2f}", textposition="outside", cliponaxis=False)
        fig.update_layout(template="plotly_white", bargap=0.3, legend=dict(orientation="h", y=-0.15))
        izq.plotly_chart(fig, width="stretch")

        fig = px.scatter(f_resultados, x="segundos", y="valor", color="rol", symbol="modalidad", hover_data=["id", "modelo", "grupo"],
                         color_discrete_map=COLOR_ROL, title="Precisión vs latencia: cada punto es un caso",
                         labels={"segundos": "Segundos de proceso (CPU)", "valor": "Error (CER / WER)", "rol": "Modelo"})
        fig.update_traces(marker_size=10, marker_line=dict(width=2, color="white"))
        fig.update_layout(template="plotly_white", legend=dict(orientation="h", y=-0.15))
        der.plotly_chart(fig, width="stretch")

        st.subheader("Caso por caso")
        st.dataframe(f_resultados[["id", "modalidad", "grupo", "modelo", "rol", "metrica", "valor", "segundos", "rtf"]],
                     hide_index=True, width="stretch")
        if resumen:
            st.success(f"Resultados Test: WER: {resumen['wer']:.2f} | CER: {resumen['cer']:.2f} | "
                       f"Acuerdo LLM-Humano: {resumen['acuerdo_llm']}/{resumen['auditados']}")
