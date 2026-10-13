# Fase 1 — Adquisición

> Estado: **cerrada** (2026-10-13).

## Qué se descarga

| Conjunto (MININTER) | Archivo que usa el proyecto | Tamaño | Destino |
|---|---|---|---|
| [Denuncias policiales registradas a nivel nacional](https://www.datosabiertos.gob.pe/dataset/denuncias-policiales-registradas-nivel-nacional-mininter) | `DATASET_Denuncias_Policiales_Ene 2018 a Julio 2026.csv` | 27,4 MB | `data/raw/denuncias.csv` |
| [Violencia contra la mujer y los integrantes del grupo familiar](https://www.datosabiertos.gob.pe/dataset/violencia-contra-la-mujer-y-los-integrantes-del-grupo-familiar-registrada-por-la-pnp) | `DATASET_Viol_Cont_Muj_Ene 2018 a Jul 2026.csv` | 4,3 MB | `data/raw/violencia_mujer.csv` |
| [Indicadores de seguridad ciudadana y tendencias territoriales](https://www.datosabiertos.gob.pe/dataset/indicadores-de-seguridad-ciudadana-y-tendencias-territoriales-mininter) | CSV `2009 a Jul 2026`, dentro de un zip anidado | 5,8 MB (9,8 MB comprimido) | `data/raw/indicadores.csv` |
| Los tres conjuntos | 3 diccionarios de datos y 3 metadatos oficiales | < 0,5 MB | [`docs/fuentes/`](fuentes/) |

El conjunto de indicadores publica una versión mensual acumulativa (de enero a julio de 2026).
Se usa solo la más reciente, que contiene a las anteriores.

## Por qué la descarga se hace en el navegador

El portal responde **418** a cualquier cliente que no sea un navegador (curl, `requests`,
`urllib`). Es un control deliberado y **no se intenta evadirlo**: no se cambian cabeceras ni se
simula un navegador.

La salida es una descarga única y trazable. La página de cada conjunto tiene un botón que arma un
zip con todos sus recursos; se baja una vez desde el navegador y se deja en `data/raw/descarga/`.
Los tres zip pesan 2,7 MB, 1,1 MB y 10,7 MB. A partir de ahí todo es automático y verificable.

## Cómo se ejecuta

1. Abrir en el navegador el botón de descarga de cada conjunto:
   - `https://www.datosabiertos.gob.pe/node/22156/dataset/download` (denuncias)
   - `https://www.datosabiertos.gob.pe/node/21199/dataset/download` (violencia contra la mujer)
   - `https://www.datosabiertos.gob.pe/node/23663/dataset/download` (indicadores)
2. Guardar los zip en `data/raw/descarga/` con los nombres que espera `src/config.py`
   (`sidpol_denuncias_*.zip`, `sidpol_violencia_mujer_*.zip`, `mininter_indicadores_*.zip`).
3. Ejecutar:

```bash
python -m src.extract              # extrae, compara con el inventario y registra en el manifiesto
python -m src.extract --verificar  # solo comprueba que lo extraído no cambió
```

El script:

- **Extrae cada archivo sin modificar un solo byte,** incluso el que está en un zip dentro de otro
  zip.
- **Compara con el inventario del portal**
  ([`data/reference/inventario_portal.csv`](../data/reference/inventario_portal.csv)): nombre,
  tamaño y fecha de publicación que el portal listaba el 2026-10-13. Si MININTER reemplaza un
  archivo, el tamaño deja de coincidir y el registro queda marcado `distinto_al_inventario`.
- **Falla si falta un archivo** y, en ese caso, imprime los enlaces de descarga.
- **Es idempotente.** Ejecutarlo dos veces deja el manifiesto idéntico, byte por byte.

## Manifiesto

[`data/raw/manifest.csv`](../data/raw/manifest.csv) es el único archivo de `data/raw` que se
versiona. Tiene una fila por archivo:

| Campo | Para qué sirve |
|---|---|
| `clave`, `archivo_portal`, `url` | Trazabilidad hasta el archivo oficial, con su nombre original |
| `publicado_en` | Fecha de la última modificación del archivo en el portal |
| `bytes_portal` | Tamaño que lista el portal para el recurso (el del zip anidado, si lo hay) |
| `archivo`, `bytes`, `sha256` | Dónde quedó y su huella: un solo byte distinto cambia el hash |
| `origen`, `estado`, `registrado_en` | De qué zip salió, si coincide con el inventario y cuándo se registró |

## Resultado

- **9 de 9 archivos** registrados con estado `ok`: el tamaño de cada uno coincide con el que
  lista el portal.
- **7 pruebas automáticas** ([`tests/test_extract.py`](../tests/test_extract.py)): extracción sin
  alterar bytes, zip anidado, idempotencia, archivo con tamaño distinto, archivo alterado o
  ausente, zip faltante e inventario completo.

## Lo que la adquisición ya reveló

1. **Los conjuntos se actualizan a ritmos distintos.** El de denuncias se publicó el 2026-08-13 con
   datos a julio; el de violencia contra la mujer, el 2026-08-21; el de indicadores, el
   2026-08-26. Los tres llegan a julio de 2026, pero no se publicaron el mismo día.
2. **Los diccionarios no siempre están al día.** El de denuncias es de abril de 2026 y el
   metadato, de julio; el diccionario de violencia contra la mujer, de julio de 2025. La
   [Fase 2](02_calidad.md) contrasta cada diccionario con los archivos reales.
3. **El diccionario de indicadores explica los códigos.** El código 7 es la tasa de denuncias por
   extorsión por cada mil habitantes y el 2, la de delitos contra el patrimonio. Eso permite
   validar el archivo principal contra cifras oficiales.
