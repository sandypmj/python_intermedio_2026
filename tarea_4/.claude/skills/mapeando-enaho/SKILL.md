---
name: mapeando-enaho
description: Genera un mapa coroplético de la pobreza monetaria por departamento del Perú con la ENAHO 2024 del INEI, uniendo por código de ubigeo, y lo compara con la referencia de la Sesión 16. Se usa cuando piden un mapa de pobreza por departamento o región, o validar sus cifras.
---

# Mapear la pobreza de la ENAHO 2024

Si no existe salidas/personas_2024.parquet, usa primero la skill limpiando-enaho.

1. Desde la raíz del proyecto, corre el script tal cual:

   ```bash
   uv run python ${CLAUDE_SKILL_DIR}/scripts/mapear.py
   ```

   Si faltan, descarga `datos/peru_departamental_simple.geojson` y `referencias/pobreza_departamento_2024.csv`.

2. Actúa según el resultado:
   - **Termina con error:** no hay mapa ni comparación. Informa qué falló y busca la causa. No uses resultados parciales.
   - **Termina con ADVERTENCIA:** el mapa se generó, pero hay diferencias sin explicar o sin verificar. Avisa al usuario de forma visible.
3. Abre `mapas/pobreza_departamento.png` y revisa que no haya etiquetas cortadas o encimadas.
4. Lee `salidas/comparacion_mapa.csv` y reporta las diferencias con su columna `estado`:
   - `coincide`: el cálculo por personas está a 0.1 puntos o menos de la referencia.
   - `explicada_por_metodo`: difiere por personas, pero el cálculo por hogares está a 0.1 puntos o menos.
   - `no_explicada`: difiere con ambos métodos.
   - `sin_verificar`: difiere por personas y falta `datos/966-Modulo34.zip` para calcular por hogares.

## Reglas

- **Une por código, nunca por nombre:** `ubigeo[:2]` con `FIRST_IDDP`, ambos como texto de 2 dígitos. No rellenes ceros: un código sin su cero es un error de lectura.
- **Exige 25 departamentos con dato**, con Lima (15) y Callao (07) separados. No los fusiones.
- El mapa pondera con `facpob07`. El cálculo por hogares (`factor07 × mieperho`) solo sirve para la comparación y nunca alimenta el mapa.
- **Nunca ajustes cifras, factores ni tolerancias** para acercarte a la referencia. Reporta las diferencias tal como salen.
- La escala usa un solo color y empieza en 0. La leyenda dice «% de personas en pobreza monetaria». El pie dice «Fuente: INEI, ENAHO 2024».

## Al interpretar

- El área de un departamento no representa su población: un color intenso en Loreto no equivale a más personas pobres que en Lima.
- El color resume todo el departamento: oculta diferencias internas y no describe a provincias, distritos ni personas.
- La ENAHO es una muestra y el mapa no muestra márgenes de error: dos colores distintos no prueban una diferencia significativa.
- El mapa describe dónde es alta la tasa, no por qué.
