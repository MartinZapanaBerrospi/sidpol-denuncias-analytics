# Fase 3 — Transformación

> Estado: **cerrada** (2026-10-13)

## 1. Qué se hizo

`python -m src.transform` convierte los tres CSV del portal en un modelo en estrella que Power BI
lee sin ejecutar nada:

```
raw (data/raw)  →  staging (parquet)  →  curated (data/curated/*.csv)
7 359 931 denuncias   7 359 931           7 359 931
369 100 filas         369 100 filas       369 099 filas
```

Ninguna denuncia se excluye. Lo que la Fase 2 marcó como raro queda como **columna de marca**, no
como filas borradas. El script falla si un paso pierde o duplica una denuncia, si alguna clave se
repite, si una clave foránea queda huérfana o si una tabla trae nulos.

## 2. El modelo

| Tabla | Filas | Clave | Para qué sirve |
|---|---|---|---|
| `fact_denuncia` | 369 099 | mes × distrito × modalidad | Denuncias (`cantidad`) y marca `celda_atipica` |
| `fact_poblacion` | 16 542 | distrito × año | Población para las tasas |
| `fact_alerta_distrito` | 1 526 | distrito × modalidad | Cambio de los últimos 12 meses frente a los 12 anteriores y su puntaje `z` |
| `fact_salto_serie` | 19 | mes × modalidad | Saltos de nivel de la serie (marcan el robo, la extorsión, la estafa y el hurto) |
| `dim_distrito` | 1 839 | `ubigeo` | Distrito, provincia, departamento y zona (Lima y Callao / Resto del país) |
| `dim_modalidad` | 7 | `modalidad_id` | Hurto, robo, extorsión, secuestro, estafa, violencia y otros |
| `dim_fecha` | 103 | `mes_inicio` | Enero de 2018 a julio de 2026, con `es_ene_jul` y `es_pandemia` |
| `dim_anio` | 9 | `anio` | Año y si está completo |

Los nombres vienen de la fuente en mayúsculas y sin tildes; `dim_distrito` los pasa a formato
normal (`San Jose de Sisa`) y agrega `distrito_unico` con la provincia entre paréntesis cuando el
nombre se repite en el país (problema 9). La tabla `data/reference/departamentos.csv` pone las
tildes de los 26 departamentos y define la zona.

## 3. Decisiones

| Tema | Decisión | Por qué |
|---|---|---|
| Tabla dispersa (problema 8) | **No** se rellena con ceros | Una grilla completa serían 1,33 millones de filas; el 72 % sería cero. Power BI trata la celda vacía como cero y el modelo pesa 9 MB en vez de 30 |
| UBIGEO sin cero inicial (1) | Se rellena a 6 dígitos | Lo hace `parse.pad_ubigeo`; con eso el 100 % de las filas se une a la dimensión |
| Clave repetida (2) | Se suman las dos filas | Una fila menos, mismas denuncias |
| Lima partida en dos (3) | Se conserva: ids `1501` y `1599` | Es la misma división que usa el padrón de población |
| Distrito sin población (4) | Sin fila en `fact_poblacion` | Se muestra el conteo, no la tasa |
| Población repetida (5) | Un valor por territorio y año | Antes de unirla |
| Población faltante (6) | Se arrastra el último año conocido y se marca `poblacion_imputada` | Pasa en 323 filas de 2026, 16 de 2025 y 8 de 2024 |
| Población distrital baja (19) | Se reparte el total provincial oficial; se marca `poblacion_ajustada` | Ver abajo |
| Saltos de serie (10) | Se calculan y se guardan en `fact_salto_serie`; no se corrigen | El tablero los muestra y cada hallazgo los advierte |
| Alertas por distrito | Mediana y desviación absoluta de todos los distritos de la modalidad, descontando el cambio nacional | Así un salto del sistema (como el del robo) no marca a todos |

### Problema 19: la población distrital no suma su provincia

Al validar las tasas apareció algo que la suma nacional escondía. La fuente publica población por
país, departamento, provincia y distrito. Las tres primeras cuadran **exactamente** entre sí todos
los años. Los distritos también, hasta 2019, pero desde 2020 algunas provincias quedan cortas.
Ejemplo, provincia de Trujillo en 2025: 1 223 977 habitantes oficiales y 1 136 345 sumando sus 11
distritos (−7,2 %). En 2025 son 21 de 196 provincias, con brechas de hasta −30 %.

Si se usara la población distrital tal cual, la tasa de denuncias por 100 mil habitantes saldría
más alta de lo real justo en las provincias más pobladas. La decisión fue repartir cada total
provincial oficial entre sus distritos **en proporción a la población que la fuente publica** para
cada uno. Se marca `poblacion_ajustada = 1` cuando el cambio supera 0,1 %, y `poblacion_fuente`
guarda el valor original. Afecta a 109 distritos en 2025 y 778 en 2026.

### Validación 4: departamentos frente a la cifra oficial

[`reports/validacion_poblacion.csv`](../reports/validacion_poblacion.csv) compara la población del
modelo con la oficial de cada uno de los 26 departamentos y 9 años (234 comparaciones):

- Nunca supera la cifra oficial (máximo +0,001 %, por redondeo).
- La suma nacional queda **−0,3 % en todos los años**, constante.
- Las mayores brechas son Huancavelica (−4,4 %), Huánuco (−4,0 %), Ayacucho (−2,6 %) y
  Apurímac (−2,6 % en 2025).

La brecha no es un error del reparto. Es la gente de los **36 distritos del padrón que no
registran ninguna denuncia** en ningún mes (95 mil habitantes, casi todos en la sierra): cuentan
en la cifra oficial pero el modelo no tiene fila para ellos. Siete están en Huancavelica
(14 009 habitantes, que explican su brecha). Las tasas de esos departamentos pueden quedar hasta
4,4 % más altas de lo real; se avisa en las notas del tablero.

## 4. Linaje

[`reports/linaje.csv`](../reports/linaje.csv):

| Paso | Filas | Denuncias | Nota |
|---|---|---|---|
| 1. raw | 369 100 | 7 359 931 | Tal como se publica |
| 2. staging | 369 100 | 7 359 931 | UBIGEO de 6 dígitos, 0 filas excluidas |
| 3. curated | 369 099 | 7 359 931 | Suma la clave repetida (problema 2) |
| 3a. marca | 3 | 150 | Celdas atípicas; son un subconjunto |

## 5. Alertas por distrito

Hay 1 526 combinaciones distrito × modalidad con al menos 30 denuncias en los 12 meses previos
(agosto 2024 a julio 2025). Se marca alerta si el cambio en los últimos 12 meses supera en 3
desviaciones al del resto de distritos y suma al menos 20 denuncias más. Resultan **5 alertas**:

| Distrito | Modalidad | 12 meses previos | Últimos 12 meses | Cambio |
|---|---|---|---|---|
| Santa Anita (Lima) | Hurto | 2 438 | 5 418 | +122 % |
| Santa María (Región Lima) | Extorsión | 55 | 209 | +280 % |
| Punchana (Loreto) | Estafa | 60 | 172 | +187 % |
| Querecotillo (Piura) | Violencia contra la mujer | 53 | 115 | +117 % |
| Pocollay (Tacna) | Violencia contra la mujer | 90 | 185 | +106 % |

Que el sistema los marque no prueba que el delito haya subido: puede ser una comisaría que empezó
a registrar en el sistema (problema 17). El análisis de la Fase 5 revisa cada caso.

## 6. Pruebas

`tests/test_curated.py` (11 pruebas) comprueba claves únicas, claves foráneas, UBIGEO de 6 dígitos,
linaje, la partición de Lima, la población frente a la oficial, las alertas y el calendario. Se
ejecutan sobre los CSV versionados, así que pasan en GitHub Actions sin los archivos originales.

## 7. Lo que pasa a la Fase 4

- Relaciones: `fact_denuncia` → `dim_distrito`, `dim_modalidad`, `dim_fecha`; `fact_poblacion` →
  `dim_distrito` y `dim_anio`; `dim_fecha[anio]` → `dim_anio[anio]`.
- La población es anual y la denuncia mensual: la medida usa `TREATAS` para llevar los años
  elegidos a `dim_anio`.
- La **tasa por 100 mil** de un periodo incompleto (2026 llega a julio) se anualiza con
  12 / meses cubiertos; solo así es comparable con un año completo.
- Cada medida se valida contra el mismo cálculo en Python (Fase 4).
