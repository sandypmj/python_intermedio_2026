---
name: graficando-enaho
description: Genera gráficos de barras de la pobreza monetaria ponderada con facpob07, por área urbana y rural, por sexo y por departamento, a partir de la ENAHO 2024 del INEI. Se usa cuando piden graficar, comparar o visualizar la pobreza del Perú con la ENAHO.
---

# Graficar la pobreza de la ENAHO 2024

Si no existe salidas/personas_2024.parquet, usa primero la skill limpiando-enaho.

1. Desde la raíz del proyecto, corre el script tal cual:

   ```bash
   uv run python ${CLAUDE_SKILL_DIR}/scripts/graficar.py
   ```

2. Si termina con error, detente e informa qué falló. No uses figuras parciales.
3. Abre cada PNG de `figuras/` y revisa que no haya textos cortados ni encimados:
   - `pobreza_area.png`
   - `pobreza_sexo.png`
   - `pobreza_departamento.png`
4. Muestra las figuras al usuario con las cifras que imprimió el script.

## Reglas

- Toda tasa va ponderada con `facpob07`. No uses promedios simples, conteos sin ponderar ni `factor07`.
- Las barras empiezan en cero y usan un solo color. Se ordenan de mayor a menor y llevan su valor escrito.
- El título dice qué se observa y el año, y se calcula desde los datos. No escribas cifras a mano.
- Cada figura indica la unidad (% de personas) y lleva al pie «Fuente: INEI, ENAHO 2024».
- Guarda PNG a 200 dpi en `figuras/`.
- No ajustes cifras para acercarte a una referencia. Si otra fuente da un valor distinto, repórtalo.
- Para una figura nueva, edita `scripts/graficar.py` en lugar de escribir otro código.

## Al interpretar

La ENAHO es una muestra y estas figuras no muestran márgenes de error. No afirmes que una diferencia pequeña, como la de hombres y mujeres, es estadísticamente significativa.
