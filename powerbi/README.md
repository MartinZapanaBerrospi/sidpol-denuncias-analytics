# Tablero de Power BI (PBIP)

> Fase 6 · Estado: **cerrada** (2026-10-13). **[Ver el tablero publicado](https://app.powerbi.com/view?r=eyJrIjoiODYyYzdjYTItOTc2My00Zjg5LTlhYTUtYzM3OGViZjQ0Mzk1IiwidCI6IjFlYmE0NDNmLTIzZTUtNDUzNC05MGQxLTA5NzZhYWJlODZhYyIsImMiOjR9&pageName=p1_resumen)**

El informe se guarda como **Power BI Project**: el modelo en TMDL y el informe en PBIR (JSON),
todo en texto, revisable en GitHub sin abrir Power BI. **Ninguno de los dos se armó a mano.** Los
generan dos scripts, así que cada visual, medida y relación está en el historial de cambios:

```bash
python tools/build_model.py    # modelo: 8 tablas, 10 relaciones y 37 medidas DAX
python tools/build_report.py   # informe: 7 páginas, 60 visuales, tema propio
```

## Cómo abrirlo

1. Clona el repositorio. Los datos que lee el tablero (`data/curated/*.csv`) vienen incluidos: no
   hace falta ejecutar el pipeline.
2. Abre `sidpol.pbip` con **Power BI Desktop** (se construyó con la versión 2.157; necesita
   soporte para el formato de informe PBIR).
3. Si clonaste en otra carpeta: *Inicio → Transformar datos → Editar parámetros* y cambia
   **`RutaDatos`** por la ruta de tu copia de `data/curated/`, con la barra final.
4. *Inicio → Actualizar*. El repositorio no guarda la caché de datos (`.pbi/cache.abf`), así que
   el primer refresco es obligatorio. Carga 369 099 filas de denuncias en segundos.

## Páginas

Cada página tiene el mismo esquema:
- **título:** la pregunta;
- **subtítulo:** la respuesta;
- **visuales:** la evidencia;
- **"Lectura":** qué significa para gerencia, con su advertencia;
- **pie:** la fuente.

Los textos toman sus cifras de [`reports/analisis/cifras_clave.csv`](../reports/analisis/cifras_clave.csv).
Ninguna cifra se escribió a mano, así que el tablero no puede contradecir al análisis.

| Página | Pregunta | Qué tiene |
|---|---|---|
| ![](../docs/img/01_resumen.png) **1. Resumen** | Resumen ejecutivo | 5 indicadores, denuncias por mes y por modalidad, "qué está pasando" y "qué conviene hacer" |
| ![](../docs/img/02_modalidades.png) **2. Modalidades** (P1, P2) | ¿Qué modalidades crecen y cuáles caen? | Matriz modalidad × año, serie mensual (de la modalidad que se elija) y los 19 saltos de serie |
| ![](../docs/img/03_territorio.png) **3. Territorio** (P3) | ¿Qué territorios tienen más denuncias por habitante? | Tasa por 100 mil de los 26 departamentos (Lima partida en dos) y su evolución |
| ![](../docs/img/04_distritos.png) **4. Distritos** (P3) | ¿Qué distritos concentran las denuncias? | Concentración en los 10 mayores, distritos con más denuncias y con mayor tasa |
| ![](../docs/img/05_alertas.png) **5. Alertas** (P4) | ¿Qué distritos se salen de su propia historia? | Los 1 526 casos ordenados por puntaje; al elegir uno se ve su serie mensual |
| ![](../docs/img/06_calendario.png) **6. Calendario** (P5) | ¿Cuándo se denuncia más? | Parte del año por mes, promedio y por año; la pandemia |
| ![](../docs/img/07_notas.png) **7. Notas** | | Definiciones, fuentes, validación y límites |

**Segmentadores.** Modalidad en las páginas de modalidades, territorio, distritos, alertas y calendario;
año en el resumen, el territorio y los distritos (en estas dos últimas abre en **2025**, el último año
completo); departamento en distritos. Vacío significa todo el periodo.

## Decisiones de diseño

- **Una pregunta por página**, con la respuesta en el subtítulo. Un gerente entiende la página sin
  mirar los gráficos.
- **Comparaciones justas con 2026.** Como 2026 llega hasta julio:
  - la tasa por 100 mil se **anualiza** (habitantes-año, ver [Fase 4](../docs/04_modelado.md));
  - el indicador del resumen compara enero–julio de 2026 con enero–julio de 2025;
  - la página *Calendario* solo usa años completos, y sin 2020 en el promedio;
  - la variación interanual aparece solo al elegir un año.
- **Territorio abre en 2025.** Al elegir un año, el segmentador de año no filtra la serie anual
  de la derecha: así se ve el año de referencia y toda la trayectoria a la vez
  (`visualInteractions` en `page.json`).
- **Filtrar con un clic.** En *Modalidades* y *Alertas*, elegir una fila de la tabla cambia la
  serie mensual de abajo o de la derecha.
- **Distritos con cuidado.** Las tasas de distrito solo se muestran con 5 mil habitantes o más, y
  la página advierte que las denuncias se registran donde se presentan, no donde vive la persona.
- **Números sin abreviar.** Power BI abrevia por defecto ("895 mil"). Se desactivó en etiquetas,
  ejes y tarjetas.
- **Nombres repetidos con provincia.** Las tablas usan `distrito_unico`, así que los dos *San
  Antonio* o los tres *Acobamba* aparecen por separado.
- **Tema propio** ([`Sidpol.json`](sidpol.Report/StaticResources/RegisteredResources/Sidpol.json)):
  un color de acento, fondo gris claro y tarjetas blancas, sin sombras ni bordes. Nada compite
  con los datos.

## Cómo se verificó

1. **Pruebas automáticas** ([`tests/test_powerbi.py`](../tests/test_powerbi.py)), en GitHub
   Actions:
   - ningún visual se sale del lienzo de 1280 × 720 ni se encima con otro;
   - cada medida y columna que usa un visual existe en el modelo;
   - cada página tiene título y pie;
   - los archivos versionados son exactamente los que producen los generadores.
2. **Medidas contra Python.** 1 530 comparaciones en Power BI Desktop, cero diferencias (ver la
   [Fase 4](../docs/04_modelado.md)).
3. **Revisión de cada captura a ojo** antes de cerrar la fase. Detectó cosas que las pruebas no ven:
   valores de tarjeta cortados por una etiqueta de dos líneas, un segmentador que no abría con el
   año elegido (el estado se guarda en `objects.general.filter` y no en `filterConfig`), y una
   tarjeta de variación en blanco cuando no hay un año elegido (se cambió por una medida que no
   depende del segmentador).

## Regenerar las capturas

```bash
powershell -ExecutionPolicy Bypass -File tools/capturas.ps1 -Salida <carpeta>
python tools/recortar_capturas.py <carpeta>
```

`capturas.ps1` cambia de página y captura la ventana de Power BI Desktop sin mover el mouse ni
tomar el foco.
