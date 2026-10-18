"""Aplicación Streamlit de la Tarea 1.

Para ejecutarla:  streamlit run app.py
"""

import streamlit as st

st.set_page_config(page_title="Tarea 1", layout="wide")

st.title("Tarea 1")
st.write("Describe aquí brevemente tu proyecto.")

# Ejemplo de entrada de texto para probar el clasificador más adelante
texto = st.text_area("Escribe un texto para clasificar:")

if st.button("Clasificar"):
    if texto.strip():
        # TODO: cargar el modelo desde la carpeta modelo/ y clasificar el texto
        st.info("Aquí aparecerá el resultado de la clasificación.")
    else:
        st.warning("Primero escribe un texto.")
