---
name: limpiando-enaho
description: Limpia y valida los módulos 34 (sumaria) y 02 (miembros) de la ENAHO 2024 del INEI, y genera una base de personas con pobreza y factor de expansión más indicadores ponderados. Se usa cuando piden limpiar, unir o analizar la ENAHO, o calcular pobreza nacional, urbana, rural, por sexo o por departamento del Perú.
---

# Limpiar la ENAHO 2024

1. Comprueba que existan `datos/966-Modulo34.zip` y `datos/966-Modulo02.zip`. Si faltan, pide al usuario bajarlos del portal de microdatos del INEI (código 966 = 2024). No los descomprimas.
2. Desde la raíz del proyecto, corre el script tal cual:

   ```bash
   uv run python ${CLAUDE_SKILL_DIR}/scripts/limpiar.py
   ```

3. Lee `salidas/validacion.txt` y muestra su contenido.
4. Actúa según el resultado:
   - **Falló algo esencial** (el script termina con error): detente, informa qué falló y busca la causa en los datos o en el código. No uses resultados parciales.
   - **Falló un control** (urbana o rural, por personas o por hogares): la base se genera, pero avisa al usuario de forma visible.
   - **Todo aprobado:** usa `salidas/personas_2024.parquet` y `salidas/indicadores.csv`.

## Reglas

- **Nunca ajustes datos, filtros, factores ni tolerancias** para acercarte a una cifra de referencia. Si no coincide, repórtalo como fallo.
- Reporta la cifra obtenida en `validacion.txt`, sin reemplazarla por la de referencia.
- Toda cifra de población va ponderada con `facpob07`. No uses promedios simples ni conteos sin ponderar para estimar tasas.
- No reimplementes el pipeline en otro código. Si hay que cambiarlo, edita `scripts/limpiar.py` y vuelve a validar.

## Antes de usar otra variable

Lee [reference.md](reference.md) para ver el significado de las variables, las cifras de referencia y los errores típicos.
