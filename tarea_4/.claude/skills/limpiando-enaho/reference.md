# Referencia: ENAHO 2024

## Archivos

| Zip | Archivo usado | Una fila por | Filas | Llaves |
|---|---|---|---|---|
| `966-Modulo34.zip` | `sumaria-2024.dta` | hogar | 33,691 | `conglome`, `vivienda`, `hogar` |
| `966-Modulo02.zip` | `enaho01-2024-200.dta` | persona | 117,721 | las tres + `codperso` |

El módulo 34 también trae `sumaria-2024-12g.dta`, con más columnas. Se comprobó que tiene los mismos hogares y los mismos valores de `pobreza`, `estrato`, `ubigeo`, `factor07` y `mieperho`. El script usa siempre `sumaria-2024.dta`.

## Variables

| Variable | Origen | Significado |
|---|---|---|
| `ubigeo` | Módulo 02 | Ubicación, texto de 6 dígitos. Los 2 primeros son el departamento |
| `estrato` | Módulo 02 | 1 a 5 = urbano; 6 a 8 = rural |
| `dominio` | Módulo 02 | Dominio geográfico; 8 = Lima Metropolitana |
| `p204` | Módulo 02 | ¿Es miembro del hogar? 1 = sí, 2 = no |
| `p205` | Módulo 02 | ¿Está ausente 30 días o más? 1 = sí, 2 = no |
| `p206` | Módulo 02 | ¿Está presente 30 días o más? 1 = sí, 2 = no |
| `p207` | Módulo 02 | Sexo: 1 = hombre, 2 = mujer |
| `p208a` | Módulo 02 | Edad en años |
| `facpob07` | Módulo 02 | Factor de expansión de personas |
| `pobreza` | Módulo 34 | 1 = pobre extremo, 2 = pobre no extremo, 3 = no pobre |
| `factor07` | Módulo 34 | Factor de expansión de hogares. No se usa para tasas de personas |

Para otras variables, consulta `Diccionario2024.pdf`, incluido en ambos zip.

## Columnas creadas en `personas_2024.parquet`

| Columna | Regla |
|---|---|
| `departamento` | `ubigeo[:2]`, como texto |
| `departamento_nombre` | Nombre según el código |
| `urbano` | `estrato <= 5` |
| `area` | `Urbana` o `Rural` |
| `sexo` | `Hombre` o `Mujer`, desde `p207` |
| `pobre` | `pobreza <= 2` |

## Fórmula

```python
pobreza_pct = 100 * df.loc[df["pobre"], "facpob07"].sum() / df["facpob07"].sum()
```

## Validaciones de `validacion.txt`

**Esenciales (detienen el proceso):** archivos presentes, llaves como texto, unión m:1 sin duplicar ni perder filas, códigos válidos sin vacíos, pobreza nacional de 27.6 % ± 0.1 puntos, 108,664 residentes, 25 códigos de departamento, sin duplicados y factores válidos.

**Controles (solo avisan):** urbana 24.8 % y rural 39.3 %, ± 0.1 puntos, calculados por personas (`facpob07`) y por hogares (`factor07 × mieperho`). El cálculo por hogares solo se usa en estos controles; la base y los indicadores siguen ponderados con `facpob07`.

## Por qué el control rural da FALLÓ

Las referencias coinciden con un cálculo por hogares, mientras que este pipeline pondera personas, como pide la tarea. Son dos métodos distintos:

| Cifra (%) | Personas residentes y `facpob07` | Sumaria y `factor07 × mieperho` | Referencia |
|---|---|---|---|
| Nacional | 27.53 | 27.58 | 27.6 |
| Urbana | 24.74 | 24.81 | 24.8 |
| Rural | 39.44 | 39.30 | 39.3 |

`mieperho` suma 109,842 personas y el filtro deja 108,664. Sus conteos difieren en 1,846 hogares. La diferencia rural de 0.14 puntos no es un error de limpieza. No la corrijas cambiando el método o la tolerancia para aprobar el control: repórtala.

## Pobreza por departamento según el curso

Cifras de la Sesión 16, para consulta. El script no las valida. Coinciden con el cálculo por hogares (diferencia máxima de 0.05 puntos). `indicadores.csv` pondera personas y puede diferir hasta 0.52 puntos (Puno).

| Código | Departamento | % | Código | Departamento | % |
|---|---|---|---|---|---|
| 01 | Amazonas | 25.7 | 14 | Lambayeque | 14.0 |
| 02 | Áncash | 22.8 | 15 | Lima | 27.1 |
| 03 | Apurímac | 24.0 | 16 | Loreto | 43.0 |
| 04 | Arequipa | 15.8 | 17 | Madre de Dios | 11.1 |
| 05 | Ayacucho | 32.8 | 18 | Moquegua | 11.0 |
| 06 | Cajamarca | 45.0 | 19 | Pasco | 39.0 |
| 07 | Callao | 33.9 | 20 | Piura | 31.9 |
| 08 | Cusco | 18.5 | 21 | Puno | 39.9 |
| 09 | Huancavelica | 33.4 | 22 | San Martín | 22.0 |
| 10 | Huánuco | 39.0 | 23 | Tacna | 24.0 |
| 11 | Ica | 6.0 | 24 | Tumbes | 26.9 |
| 12 | Junín | 18.5 | 25 | Ucayali | 27.1 |
| 13 | La Libertad | 30.2 | | | |

## Errores típicos

| Síntoma | Causa probable |
|---|---|
| La pobreza no da 27.6 % | Falta ponderar o filtrar residentes habituales |
| Hay menos de 25 departamentos o `1` en vez de `01` | El código se leyó como número y perdió el cero |
| `MergeError` en la unión | Hay llaves repetidas en sumaria o las llaves no se leyeron como texto |
| La unión pierde personas | Las llaves no tienen el mismo formato en ambos módulos |
| Cifras demasiado bajas, sin error | Un vacío en `pobreza <= 2` se contó como "no pobre" |
