# Fase 2 — Calidad de los datos

> Estado: **cerrada** (2026-10-13).

## 1. Resumen

Se revisaron las **369 100 filas** (7 359 931 denuncias) del archivo principal con **40 reglas de
calidad** en seis dimensiones. **Ninguna regla bloqueante falla.**

- **Los datos son íntegros.** Cero vacíos, cero espacios sobrantes, cantidades enteras de 1 a
  1 303, 103 meses completos y las siete modalidades presentes en todos los meses.
- **Son exactos donde se pueden contrastar.** La violencia contra la mujer coincide con el archivo
  hermano en las **94 940 celdas** año × mes × distrito, sin una diferencia. La extorsión queda
  entre −1,6 % y −5,3 % del indicador oficial, con las mismas variaciones año a año
  (correlación 1,00). La población de los distritos suma la nacional (exacta en 2018).
- **El formato no es uniforme.** Hay 18 problemas documentados. Los que importan:
  - el **UBIGEO pierde el cero inicial** en el 39 % de las filas;
  - un código tiene **dos nombres**;
  - **Lima viene partida** en dos "departamentos";
  - la **población está repetida** por indicador y es **incompleta** según qué fuente se use.
- **Lo más importante para el análisis no es un error de formato.** Las series de **robo** y
  **hurto** tienen **saltos de nivel** (por ejemplo −27 % en abril de 2024 y −28 % en noviembre de
  2024) que también aparecen en el indicador oficial. Cualquier comparación entre años debe
  decirlo.

## 2. Cómo se mide

```bash
python -m src.quality     # perfila, aplica las reglas y compara con otras cifras oficiales
python -m src.validate    # solo las comparaciones con cifras oficiales
```

Las reglas de limpieza de campo viven en [`src/parse.py`](../src/parse.py) y las de calidad en
[`src/quality.py`](../src/quality.py). La Fase 3 reutiliza las mismas funciones. Resultados en
[`reports/calidad/`](../reports/calidad/):

| Archivo | Qué contiene |
|---|---|
| [`perfilado_columnas.csv`](../reports/calidad/perfilado_columnas.csv) | Una fila por columna: vacíos, espacios, valores distintos, longitud, rango y valores frecuentes |
| [`perfilado_mensual.csv`](../reports/calidad/perfilado_mensual.csv) | Una fila por mes: filas, denuncias, distritos con registro y porcentaje de UBIGEO de 5 dígitos |
| [`reglas.csv`](../reports/calidad/reglas.csv) | Las 40 reglas, con filas y denuncias afectadas y su resultado |
| [`rupturas.csv`](../reports/calidad/rupturas.csv) | Los 19 saltos bruscos de las series mensuales |
| [`atipicos.csv`](../reports/calidad/atipicos.csv) | Celdas muy altas frente a la historia de su propio distrito |
| [`ubigeo_problemas.csv`](../reports/calidad/ubigeo_problemas.csv) | Códigos con dos nombres, sin población o repetidos |
| [`cobertura_poblacion.csv`](../reports/calidad/cobertura_poblacion.csv) | Población de los distritos frente a la nacional, por año |
| [`../validaciones.csv`](../reports/validaciones.csv) | Comparaciones con otras cifras oficiales |

Cada regla tiene una **severidad**: *bloqueante* (si falla, el pipeline se detiene), *alerta* (se
documenta y se marca) o *informativa* (describe la fuente sin juzgarla).

## 3. Perfilado

**Por columna** (archivo principal):

| Columna | Distintos | Vacíos | Rango o valores más frecuentes |
|---|---|---|---|
| `ANIO` | 9 | 0 | 2018 a 2026 |
| `MES` | 12 | 0 | 1 a 12 |
| `DPTO_HECHO_NEW` | 26 | 0 | Lima Metropolitana, Arequipa, Cusco |
| `PROV_HECHO` | 196 | 0 | Lima, Arequipa, Chiclayo |
| `DIST_HECHO` | 1 688 | 0 | — |
| `UBIGEO_HECHO` | 1 839 | 0 | Longitud 5 o 6 (problema 1) |
| `P_MODALIDADES` | 7 | 0 | Otros, Violencia contra la mujer e integrantes, Hurto |
| `cantidad` | 918 | 0 | 1 a 1 303 |

**Por mes.** Cada mes trae entre 2 389 y 4 151 filas y entre 853 y 1 336 distritos con al menos
una denuncia. Los distritos con registro en un mes típico (mediana) crecen de 953 en 2018 a 1 290 en 2021 y se
mantienen (problema 17). El porcentaje de filas con UBIGEO de 5 dígitos es estable, entre 37,6 % y 39,4 %
cada año: no es un problema de un mes, sino del formato del archivo.

## 4. Las seis dimensiones

| Dimensión | Pregunta | Reglas | Resultado |
|---|---|---|---|
| **Completitud** | ¿Está todo lo que debería estar? | 12 | 103 de 103 meses, 8 de 8 columnas, 7 de 7 modalidades en cada mes, 0 vacíos. Una regla informativa: la tabla es dispersa |
| **Unicidad** | ¿Algo se cuenta dos veces? | 2 | 0 filas idénticas; 1 clave repetida (alerta, problema 2) |
| **Validez** | ¿Cada valor tiene la forma correcta? | 9 | Años, meses, cantidades, modalidades y códigos de departamento dentro de su dominio. 1 alerta: un distrito sin población. 1 informativa: UBIGEO de 5 dígitos |
| **Consistencia** | ¿Los campos concuerdan entre sí? | 8 | Lima Metropolitana es solo la provincia de Lima y Región Lima no la incluye. 3 alertas (códigos con dos nombres, saltos de series, celdas atípicas) y 1 informativa (nombres de distrito repetidos) |
| **Exactitud** | ¿Coincide con otras cifras oficiales? | 5 | Violencia, extorsión y población cumplen. 2 informativas (patrimonio y secuestro) y 1 alerta (población de 2026) |
| **Oportunidad** | ¿Los datos llegan a tiempo? | 4 | Los tres archivos se publicaron entre 13 y 26 días después de cerrar julio de 2026 |

El detalle de las 40 reglas está en [`reglas.csv`](../reports/calidad/reglas.csv).

## 5. Exactitud: validación contra otras cifras oficiales

Las tres comparaciones usan fuentes de la misma institución. No son un contraste externo
independiente, pero sí detectan cualquier error de lectura, de unión o de agregación.

### V1. Violencia contra la mujer: el archivo principal frente al archivo de violencia

El archivo de violencia es un conjunto distinto, con otro formato, publicado en otra fecha. Se
agrupan los dos por año, mes y distrito y se comparan:

| Año | Denuncias (archivo de violencia) | Denuncias (archivo principal) | Diferencia |
|---|---|---|---|
| 2018 | 250 543 | 250 543 | 0 |
| 2019 | 296 986 | 296 986 | 0 |
| 2020 | 250 385 | 250 385 | 0 |
| 2021 | 258 086 | 258 086 | 0 |
| 2022 | 247 461 | 247 461 | 0 |
| 2023 | 256 282 | 256 282 | 0 |
| 2024 | 244 030 | 244 030 | 0 |
| 2025 | 219 417 | 219 417 | 0 |
| 2026 (a julio) | 125 988 | 125 988 | 0 |

**94 940 de 94 940 celdas idénticas.** El archivo principal no pierde ni agrega nada en esa
modalidad.

### V2. Indicadores oficiales del Plan de Acción de Seguridad Ciudadana

El diccionario oficial del conjunto de indicadores define tres series que se pueden comparar con
las modalidades del archivo principal.

| Año | Extorsión: indicador oficial | Extorsión: archivo principal | Diferencia |
|---|---|---|---|
| 2018 | 3 223 | 3 072 | −4,7 % |
| 2019 | 3 866 | 3 705 | −4,2 % |
| 2020 | 2 839 | 2 689 | −5,3 % |
| 2021 | 4 740 | 4 539 | −4,2 % |
| 2022 | 16 349 | 16 066 | −1,7 % |
| 2023 | 22 688 | 22 320 | −1,6 % |
| 2024 | 22 388 | 21 915 | −2,1 % |
| 2025 | 27 286 | 26 730 | −2,0 % |
| 2026 (a julio) | 12 522 | 12 174 | −2,8 % |

- **Extorsión: cumple (tolerancia ±6 %).** El archivo principal siempre trae un poco menos, con
  una diferencia estable que se achica desde 2022. Las **variaciones año a año coinciden casi
  exactamente** (por ejemplo +244,9 % frente a +254,0 % en 2022; correlación 1,00): la diferencia
  es de nivel, no de forma.
- **Delitos contra el patrimonio (hurto + robo): −6,8 % a −16,7 %.** El indicador usa la
  categoría legal "patrimonio", más amplia que las modalidades hurto y robo del archivo principal.
  Aun así, **ambas series muestran la misma caída: −10,2 % en 2024 y −24,0 % en 2025 el
  indicador, y −12,6 % y −27,1 % el archivo principal.** Es la prueba de que el descenso del robo
  y el hurto está en el sistema de denuncias, no en cómo se armó este archivo.
- **Secuestro: −18,6 % a −28,6 %.** El indicador cuenta más casos que la modalidad del archivo
  principal; no se puede saber por qué. Se informa y no se usa como prueba. Las variaciones
  anuales siguen el mismo rumbo (correlación 0,97).

**Hipótesis de la diferencia de nivel (no verificable).** El indicador se publicó después y puede
usar un corte posterior del sistema o una clasificación más amplia. El metadato de la propia
fuente advierte que son "datos dinámicos" sujetos a variación.

### V3. Población

La suma de la población proyectada de los distritos frente a la población nacional oficial:

| Año | Población nacional | Suma de distritos | Diferencia | Distritos con población |
|---|---|---|---|---|
| 2018 | 31 562 130 | 31 562 130 | 0,00 % | 1 874 |
| 2019 | 32 131 400 | 32 131 400 | 0,00 % | 1 874 |
| 2020 | 32 625 948 | 32 624 315 | −0,01 % | 1 874 |
| 2021 | 33 035 304 | 32 961 764 | −0,22 % | 1 874 |
| 2022 | 33 396 698 | 33 322 520 | −0,22 % | 1 874 |
| 2023 | 33 725 844 | 33 566 742 | −0,47 % | 1 874 |
| 2024 | 34 038 457 | 33 875 022 | −0,48 % | 1 866 |
| 2025 | 34 350 244 | 34 179 939 | −0,50 % | 1 858 |
| 2026 | 34 660 114 | 33 828 083 | **−2,40 %** | 1 515 |

Cumple (±1 %) de 2018 a 2025, pero la suma nacional esconde que **varias provincias quedan cortas** (problema 19). **2026 queda corto:** faltan 359 distritos. La Fase 3 los completa
con la población del último año disponible y marca esas filas.

La cobertura de las denuncias es de 99,95 % a 100 % cada año: solo un distrito (Kumpirushiato,
Cusco) no tiene población en ningún año.

## 6. Catálogo de problemas

| # | Problema | Ejemplo real | Afecta | Decisión |
|---|---|---|---|---|
| 1 | **El UBIGEO pierde el cero inicial** | `10202` en lugar de `010202` (Aramango, Amazonas) | 142 979 filas (38,7 %), 1,84 millones de denuncias | Corregir: se rellena a 6 dígitos; se conserva el original y una marca |
| 2 | **Un UBIGEO con dos nombres de provincia** | `160801`: Loreto / Maynas / Putumayo y Loreto / Putumayo / Putumayo | 106 filas, 258 denuncias; 1 clave repetida en dic-2024 | Corregir: se suman las dos filas y se usa el nombre vigente (provincia Putumayo) |
| 3 | **Lima partida en dos "departamentos"** | `LIMA METROPOLITANA` y `REGION LIMA` comparten el código 15 | 26 527 filas de Lima Metropolitana | Mantener: la clave es 1501 y 1599, como en el padrón de población. Es una distinción útil para el análisis |
| 4 | **Un distrito sin población** | Kumpirushiato (`080915`), La Convención, Cusco | 152 filas, 442 denuncias (0,006 %) | Mantener sin tasa: se muestra el conteo |
| 5 | **La población se repite por indicador** | Aramango trae 3 filas con la misma población de 10 422 | Sumarla directamente da 205 millones en 2018 en lugar de 31,6 | Corregir: un valor por ámbito, territorio y año |
| 6 | **La población distrital está incompleta según la fuente** | Solo con los indicadores SIDPOL hay 1 285 distritos en 2018 (−5,7 %); uniendo todas las fuentes, 1 874 (0,0 %) | Todas las tasas distritales | Corregir: se unen todas las fuentes. 2026 se completa en la Fase 3 |
| 7 | **El archivo de violencia tiene otro formato** | Sin comillas, con marca BOM, columnas `AÑO` y `CANTIDAD` y otro orden | 94 941 filas | Corregir: se lee por nombre de columna, no por posición |
| 8 | **La tabla es dispersa** | Solo hay fila si hubo al menos una denuncia | 72 % de las combinaciones distrito-mes-modalidad no tienen fila | Corregir en la Fase 3: se completa la grilla con ceros |
| 9 | **Nombres de distrito repetidos** | 98 nombres aparecen en provincias distintas (Acobamba en 3) | 51 566 filas (14 %) | Mantener: la identidad es el UBIGEO, nunca el nombre. Las tablas muestran la provincia al lado |
| 10 | **Saltos de nivel en las series** | Robo: +52 % en dic-2022, −27 % en abr-2024, −28 % en nov-2024. Estafa: +42 % en oct-2025 y −30 % al mes siguiente | 19 saltos en 4 modalidades ([`rupturas.csv`](../reports/calidad/rupturas.csv)) | Marcar: no se corrige. Se muestran en el tablero y se advierte en cada hallazgo |
| 11 | **La pandemia rompe las series** | Abril de 2020: 2 845 hurtos frente a 8 897 en marzo | Marzo a diciembre de 2020 | Mantener: es un hecho real. Se excluye de la detección de saltos y se muestra aparte |
| 12 | **El diccionario y el metadato no coinciden con el archivo** | El metadato dice que incluye "homicidios"; el archivo no trae esa modalidad. El diccionario sí nombra el secuestro | Una modalidad | Documentar: el diccionario del proyecto ([sección 8](#8-diccionario-de-datos)) describe lo que el archivo realmente trae |
| 13 | **Metadatos desactualizados y definiciones contradictorias** | El metadato de violencia dice "última actualización 2026-02-28", pero el archivo es de 2026-08-21. El diccionario de denuncias habla del "año del hecho" y el de violencia, del "año de registro", y los dos archivos son idénticos | Los tres conjuntos | Documentar: no se sabe si el mes es el del hecho o el del registro. Se trata como "mes de la denuncia" |
| 14 | **Datos dinámicos** | El metadato dice "información sujeta a variación por ser datos dinámicos" | Meses recientes | Documentar: los últimos meses pueden subir en publicaciones futuras. El manifiesto con hash permite detectar cambios |
| 15 | **Indicadores oficiales con definiciones más amplias** | Patrimonio −6,8 % a −16,7 %; secuestro −18,6 % a −28,6 % | 2 de 3 indicadores | Informar: solo la extorsión se usa como prueba |
| 16 | **Celdas atípicas** | 55 denuncias de estafa en San José de Sisa (San Martín) en octubre de 2025, con z = 22,5 | 3 celdas | Marcar, no excluir: son pocas y no alteran ningún total |
| 17 | **Cobertura del sistema que crece** | Distritos con al menos una denuncia en un mes típico (mediana): 953 en 2018 y 1 290 en 2021; en el año completo, 1 518 y 1 749 | Comparabilidad 2018–2021 | Documentar: parte del aumento 2018–2021 puede ser más comisarías registrando en el sistema, y un mes sin fila puede ser cero o falta de registro |
| 18 | **El último año está incompleto** | 2026 llega a julio | 2026 | Documentar: las comparaciones con 2026 usan enero–julio |
| 19 | **La población por distrito no suma la de su provincia** | Provincia de Trujillo, 2025: 1 223 977 habitantes oficiales y 1 136 345 sumando sus 11 distritos (−7,2 %) | Desde 2020; en 2025, 21 de 196 provincias; hasta −30 % en algunas. Provincias, departamentos y país sí cuadran entre sí | Corregir en la Fase 3: se reparte el total provincial oficial entre sus distritos en proporción a su población publicada, y se marca `poblacion_ajustada` |

## 7. Atípicos y rupturas

**Celdas atípicas.** Una celda (distrito, modalidad, mes) es atípica si es muy alta frente a la
historia de su propio distrito y modalidad: puntaje z robusto mayor que 6 sobre el logaritmo de la
cantidad, con al menos 30 denuncias y 12 meses de historia. **Quedan 3 de 369 100**: Estafa en San
José de Sisa (oct-2025), Estafa en Chongoyape (oct-2019) y violencia en Pacocha (dic-2019). No
alteran ningún total.

**Rupturas.** Un salto es un cambio de más de 20 % de un mes al siguiente en una modalidad con más
de 1 000 denuncias al mes, fuera de la pandemia. Distingue un cambio brusco de una tendencia
gradual, como el crecimiento de la extorsión desde 2021, que no se marca.

| Modalidad | Saltos | Los más grandes |
|---|---|---|
| Robo | 5 | dic-2022 +51,7 %; abr-2024 −26,8 %; nov-2024 −28,1 %; mar-2021 +36,9 % |
| Extorsión | 9 | nov-2022 +42,7 %; mar-2018 +37,9 %; mar-2019 +33,8 % |
| Estafa | 4 | oct-2025 +41,8 %; nov-2025 −30,4 % |
| Hurto | 1 | mar-2021 +28,5 % |

**Qué significa.** Un salto puede ser un cambio en el delito, en la confianza para denunciar, en
la clasificación o en el registro. Los datos no permiten distinguirlo. Pero el indicador oficial
de delitos contra el patrimonio muestra la misma caída, así que el cambio está en el sistema de
denuncias y no en este archivo.

## 8. Diccionario de datos

Diccionario de los archivos reales, contrastado con los
[diccionarios oficiales](fuentes/).

| Columna de origen | Nombre en el proyecto | Tipo | Qué es | Observación |
|---|---|---|---|---|
| `ANIO` / `AÑO` | `anio` | entero | Año de la denuncia | El diccionario dice "año del hecho"; el de violencia, "año de registro" (problema 13) |
| `MES` | `mes` | entero | Mes de la denuncia | Ídem |
| `DPTO_HECHO_NEW` / `DPTO_HECHO` | `departamento_fuente` | texto | Departamento, con Lima partida en dos | Problema 3 |
| `PROV_HECHO` | `provincia` | texto | Provincia | Problema 2 |
| `DIST_HECHO` | `distrito` | texto | Distrito | Problema 9 |
| `UBIGEO_HECHO` | `ubigeo` (y `ubigeo_original`) | texto de 6 | Código del distrito | Problema 1: 39 % sin cero inicial |
| `P_MODALIDADES` | `modalidad` | texto | Una de 7 modalidades | "Otros" pesa el 36 %; problema 12 |
| `cantidad` | `cantidad` | entero | Denuncias de esa fila | 1 a 1 303 |
| `POBLACION_PROYECTADA` | `poblacion` | entero | Población del territorio y año | Problemas 5 y 6 |
| `INDICADOR`, `AMBITO`, `UBIGEO_DASH`, `FUENTE`, `VALORES` | `indicador`, `ambito`, ... | — | Indicadores oficiales | Solo se usan para validar y para la población |

## 9. Lo que pasa a la Fase 3

- Las reglas de campo (problemas 1, 2, 3 y 7) se aplican con las mismas funciones de
  `src/parse.py`.
- **Grilla completa** de distrito × mes × modalidad con ceros explícitos (problema 8).
- **Población:** un valor por territorio y año; 2026 completado con el último año disponible y
  marcado (problema 6).
- **Dimensión de territorio** con UBIGEO como clave, el departamento de Lima partido en dos y la
  provincia al lado de cada nombre repetido (problemas 3 y 9).
- **Marcas, no filtros:** `ubigeo_con_cero_agregado`, `sin_poblacion`, `poblacion_imputada` y las
  rupturas de cada modalidad (problemas 10, 4 y 6).
- **Linaje:** denuncias y filas en cada paso, para demostrar que nada se pierde entre raw y
  curated.
