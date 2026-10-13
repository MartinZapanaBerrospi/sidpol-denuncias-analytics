# Fase 5 — Análisis

> Estado: **cerrada** (2026-10-13). Datos hasta julio de 2026. Todas las cifras salen de
> `python -m src.analysis` y se guardan en [`reports/analisis/`](../reports/analisis/); el tablero
> las cita desde ahí.

## Cómo leer este documento

Cada respuesta trae su cifra, **qué dice**, **qué no dice** y la advertencia que hay que repetir en
cualquier presentación. Una denuncia no es un delito: es un hecho que alguien decidió reportar. El
análisis es descriptivo y no estima causas. Las tasas son denuncias por 100 mil habitantes en un
año; el 2026, que llega a julio, se anualiza (ver [Fase 4](04_modelado.md#4-cómo-se-calcula-la-tasa-por-100-mil)).

## P1. ¿Cómo evolucionaron las denuncias?

**Subieron hasta 2023 y bajan desde entonces, pero la historia no es una sola curva.**

| Año | Denuncias | Por 100 mil hab. |
|---|---|---|
| 2018 | 774 804 | 2 462 |
| 2023 (máximo) | 1 044 843 | 3 107 |
| 2025 | 895 260 | 2 614 |
| 2026 (enero–julio, anualizada) | 494 268 | 2 452 |

- De 2023 a 2025 las denuncias cayeron 14,3 %, pero siguen 15,5 % sobre 2018 en
  cifras y por encima en tasa (2 614 contra 2 462).
- En enero–julio de 2026 hay 494 268 denuncias, 7,7 % menos que en el
  mismo periodo de 2025.
- La pandemia hundió 2020 (ver P5) y en 2022 las denuncias ya superaban a las de 2019 en 2,7 %.

**Qué no dice.** Que el delito bajó. El robo explica el 56 % de la caída de 2023 a 2025 y su serie tiene
saltos de registro (P2). Además, «Otros» agrupa el 36 % de las
denuncias y la fuente no la abre, así que ninguna cifra total puede leerse por tipo de delito.

## P2. ¿Qué modalidades crecen, cuáles caen y qué tan fiable es la lectura?

Cuadro completo en [`p2_modalidades.csv`](../reports/analisis/p2_modalidades.csv).

| Modalidad | 2018 | 2023 | 2025 | 2018→2025 | Ene–jul 2026 vs 2025 | Saltos |
|---|---|---|---|---|---|---|
| Otros | 252 950 | 357 440 | 370 065 | +46 % | −8,8 % | 0 |
| Violencia contra la mujer e integrantes | 250 543 | 256 282 | 219 417 | −12 % | −4,4 % | 0 |
| Hurto | 161 503 | 231 464 | 180 604 | +12 % | −5,0 % | 1 |
| Robo | 96 091 | 141 708 | 57 200 | −40 % | −13,8 % | 5 |
| Estafa | 9 574 | 34 304 | 40 068 | +319 % | −7,0 % | 4 |
| Extorsión | 3 072 | 22 320 | 26 730 | +770 % | −24,9 % | 9 |
| Secuestro | 1 071 | 1 325 | 1 176 | +10 % | −10,6 % | 0 |

- **Extorsión: se multiplicó por 8,7** (3 072 en 2018, 26 730 en
  2025). Es la mayor alza relativa. En enero–julio de 2026 baja 24,9 % frente a 2025.
- **Estafa: se multiplicó por 4,2** (9 574 → 40 068). Su serie incluye un
  salto de +41,8 % en octubre de 2025 y de −30,4 % al mes siguiente.
- **Robo: cayó 60 % de 2023 a 2025** (141 708 → 57 200) y explica el
  56 % de la caída total. Tiene 5 saltos de nivel: +51,7 % en diciembre de
  2022, −26,8 % en abril de 2024 y −28,1 % en noviembre de 2024.
- **Hurto** baja 22 % de 2023 a 2025 y **violencia contra la mujer** baja
  12 % desde 2018. La violencia contra la mujer no tiene ningún salto de serie y el hurto, uno (marzo de 2021).

**¿Qué tan fiable es la lectura?** Se detectaron **19 saltos de serie** de más de 20 % de un mes
a otro fuera de la pandemia, en cuatro modalidades ([`rupturas.csv`](../reports/calidad/rupturas.csv)). Un salto
de ese tamaño en un mes rara vez es un cambio del delito: suele ser un cambio de cómo se registra, se
tipifica o se carga. Por eso:

- Las **tendencias de largo plazo** de extorsión y estafa son sólidas en dirección (cualquier tramo de la serie
  lo muestra), pero su tamaño exacto depende de cómo se registró cada año.
- La **caída del robo** mezcla una baja posible con varios escalones de registro. No se debe citar
  «−60 %» como si fuera una reducción del delito.
- La validación contra el indicador oficial de extorsión del Ministerio ([V2](02_calidad.md)) coincide
  dentro de −1,6 % a −5,3 %: el archivo es consistente con la cifra oficial, aunque ambos son registros.

## P3. ¿Qué territorios tienen más denuncias por habitante?

Año de referencia: **2025** (último año completo). Tasa nacional: **2 614** por 100 mil.

| Departamento | Tasa por 100 mil | Veces la nacional | Cambio de la tasa 2018→2025 |
|---|---|---|---|
| Lambayeque | 4 410 | 1,69 | +28 % |
| Madre de Dios | 4 123 | 1,58 | +11 % |
| Arequipa | 3 461 | 1,32 | −14 % |
| Moquegua | 3 141 | 1,20 | +18 % |
| Lima Metropolitana | 3 112 | 1,19 | −2 % |
| Ucayali | 1 337 | 0,51 | −30 % |
| Puno | 1 322 | 0,51 | +66 % |
| Huancavelica | 1 226 | 0,47 | +128 % |

- **Lambayeque** tiene la mayor tasa (4 410, 1,69 veces la nacional), seguido de
  Madre de Dios (4 123). El de menor tasa es Huancavelica (1 226): hay
  3,6 veces entre el primero y el último.
- **Lima Metropolitana** concentra el 36 % de las denuncias con el 30 % de la
  población: tasa 3 112, 1,19 veces la nacional. Pesa mucho en el conteo, pero por
  habitante no es la más alta.
- Solo 11 de 26 departamentos superan la tasa nacional.
- **Extorsión:** las mayores tasas de 2025 son las de Tumbes (230) y
  La Libertad (201); en conteo, Lima Metropolitana reúne el 42 %.
- **Concentración en distritos:** los 10 distritos con más denuncias suman el 22,6 % del total
  (eran 23,7 % en 2018) y bastan 41 de 1 758
  distritos para llegar a la mitad. Encabezan Lima (33 669) y San Juan de Lurigancho
  (30 622).
- **Convergencia:** los cinco departamentos con menor tasa en 2018 (Huancavelica, Puno, Cajamarca, Loreto, San Martín) la subieron
  50 % en conjunto, mientras la nacional subió 6 %. La correlación de rangos entre la tasa
  inicial y su cambio es −0,71.

**Qué no dice.** Que Lambayeque o Arequipa sean más inseguros. Una tasa de denuncias mezcla cuánto delito hay, cuánto
se denuncia y cuán fácil es denunciar. Que los de menor tasa suban más es coherente con un sistema que
llega a más lugares (problema 17 de la Fase 2: de 1 518 a 1 758 distritos con denuncias entre 2018 y 2025) y
también con la regresión a la media; los datos no separan las dos cosas.

**Advertencia de los distritos.** Las denuncias se registran donde se presenta la denuncia, no donde vive la persona,
y la población es la residente. Por eso los distritos comerciales o de paso tienen tasas enormes (Arequipa, 13 203;
Lima, 12 681; Miraflores, 7 857) y no deben leerse como «más peligrosos». El ranking de
[`p3_distritos_tasa.csv`](../reports/analisis/p3_distritos_tasa.csv) se limita a distritos de 5 mil habitantes o más;
aun así, San Antonio (Huarochirí, 6 140 habitantes) sale en 23 795 por 100 mil, un caso de población pequeña con
mucho movimiento.

## P4. ¿Qué distritos se salen de su propia historia?

De 1 526 combinaciones distrito–modalidad con al menos 30 denuncias en los 12 meses previos,
**5 se salen del patrón** (cambio de los últimos 12 meses ≥ 3 desviaciones robustas por encima del resto de
distritos de su modalidad, con al menos 20 denuncias más):

| Distrito | Modalidad | 12 meses previos | Últimos 12 meses | Cambio | Mes del escalón | Antes → después (mensual) |
|---|---|---|---|---|---|---|
| Punchana (Loreto) | Estafa | 60 | 172 | +187 % | 2026-01 | 8,5 → 20,8 |
| Querecotillo (Piura) | Violencia (mujer e integrantes) | 53 | 115 | +117 % | 2025-06 | 3,8 → 8,3 |
| Pocollay (Tacna) | Violencia (mujer e integrantes) | 90 | 185 | +106 % | 2025-09 | 4,5 → 18,7 |
| Santa Maria (Región Lima) | Extorsión | 55 | 209 | +280 % | 2026-01 | 4,5 → 30,0 |
| Santa Anita (Lima Metropolitana) | Hurto | 2 438 | 5 418 | +122 % | 2025-06 | 131,5 → 465,7 |

**Los cinco son escalones, no picos.** En todos el nivel mensual se multiplica por 2 o más entre un semestre y el siguiente y
se mantiene alto. El caso más grande es **Santa Anita (Lima), hurto:** de 132 denuncias mensuales a
466 desde 2025-06, sostenido por catorce meses. Esa forma se parece más a un cambio de registro
(una comisaría que empieza a cargar en el sistema, un criterio nuevo) que a un brote, pero **los datos no permiten
distinguirlo**. La alerta sirve para preguntar a la comisaría, no para concluir.

## P5. ¿Cuándo se denuncia más y cómo afectó la pandemia?

- **Casi no hay estacionalidad.** Excluyendo 2020, cada mes tiene entre 7,9 % (febrero) y
  8,8 % (marzo) de las denuncias del año; un año parejo daría 8,3 %. La diferencia es de
  0,9 puntos. Febrero es corto, así que no se interpreta.
- Por modalidad hay matices: la **violencia contra la mujer** es más alta de enero a marzo, y **hurto y estafa** tienen
  su mejor trimestre en octubre–diciembre. La extorsión parece subir hacia fin de año, pero es su tendencia (crece
  durante el año), no una estación.
- **Pandemia:** en abril de 2020 hubo 21 570 denuncias contra 69 641 en abril de 2019
  (−69 %). El año 2020 cerró −24 % frente a 2019 y diciembre todavía quedó
  −18 %. Es la caída más grande de la serie y no se corrige: es un hecho real, aunque mezcla menos delito
  y menos posibilidad de denunciar.

## Lo que se pasa al tablero

Una página por pregunta, con la respuesta en el subtítulo y esta advertencia en la lectura. Las cifras de los
textos se leen de `cifras_clave.csv`: ningún número del tablero está escrito a mano.
