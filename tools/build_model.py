"""Genera el modelo semántico de Power BI (TMDL) a partir de data/curated.

Escribe powerbi/sidpol.SemanticModel/: tablas con su consulta de Power Query, relaciones y
medidas DAX. Los identificadores (lineageTag) se derivan del nombre de cada objeto, así que
regenerar el modelo produce exactamente los mismos archivos.

Las medidas están documentadas en docs/04_modelado.md y validadas contra Python en
tools/validate_measures.py.

Uso:
    python tools/build_model.py
"""

import re
import shutil
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config  # noqa: E402

NAME = "sidpol"
CUTOFF_MONTH = config.END[1]                                    # último mes con datos (7 = julio)
LAST_FULL_YEAR = config.END[0] if config.END[1] == 12 else config.END[0] - 1
PANDEMIC_YEAR = 2020                                            # sale del índice estacional
MIN_POPULATION_FOR_RATE = 5000                                  # habitantes mínimos para comparar tasas de distritos
MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "setiembre",
             "octubre", "noviembre", "diciembre"]
MODEL = ROOT / "powerbi" / f"{NAME}.SemanticModel"
NS = uuid.UUID("b3d0f4c8-5a21-4e6b-8f47-9d2c1a7e6b30")


def tag(*parts: str) -> str:
    return str(uuid.uuid5(NS, "/".join(parts)))


# ---------------------------------------------------------------------------------------------
# Tablas: (columna, tipo TMDL, opciones). El orden es el del CSV de data/curated.
# ---------------------------------------------------------------------------------------------

M_TYPES = {"string": "type text", "int64": "Int64.Type", "double": "type number", "dateTime": "type date"}

TABLES = {
    "dim_fecha": {
        "description": "Calendario mensual de 2018-01 a 2026-07, en español.",
        "data_category": "Time",
        "columns": [
            ("mes_inicio", "dateTime", {"key": True, "format": "mmm yyyy", "description": "Primer día del mes"}),
            ("anio", "int64", {"format": "0", "description": "Año"}),
            ("mes", "int64", {"hidden": True}),
            ("mes_nombre", "string", {"sort_by": "mes"}),
            ("trimestre", "string", {}),
            ("anio_mes", "string", {}),
            ("es_ene_jul", "int64", {"hidden": True}),
            ("es_pandemia", "int64", {"hidden": True}),
        ],
    },
    "dim_anio": {
        "description": "Año de la población. Se une a los hechos de población; la tasa lo alcanza con TREATAS.",
        "columns": [
            ("anio", "int64", {"key": True, "format": "0"}),
            ("periodo", "string", {"description": "Año completo o enero–julio"}),
        ],
    },
    "dim_distrito": {
        "description": "Distrito identificado por su UBIGEO de 6 dígitos. Lima está partida en Lima Metropolitana "
                       "y Región Lima. distrito_unico agrega la provincia cuando el nombre se repite en el país.",
        "columns": [
            ("ubigeo", "string", {"key": True}),
            ("distrito", "string", {}),
            ("distrito_unico", "string", {"description": "Nombre para mostrar; único en todo el modelo"}),
            ("provincia", "string", {}),
            ("departamento_id", "string", {"hidden": True}),
            ("departamento", "string", {}),
            ("zona", "string", {"description": "Lima y Callao, o resto del país"}),
        ],
    },
    "dim_modalidad": {
        "description": "Las siete modalidades que publica la fuente.",
        "columns": [
            ("modalidad_id", "int64", {"key": True, "hidden": True}),
            ("modalidad", "string", {}),
            ("grupo", "string", {}),
        ],
    },
    "fact_denuncia": {
        "description": "Denuncias por mes, distrito y modalidad (2018-01 a 2026-07). Solo hay fila si hubo al "
                       "menos una denuncia: la celda vacía equivale a cero.",
        "columns": [
            ("mes_inicio", "dateTime", {"hidden": True, "format": "mmm yyyy"}),
            ("ubigeo", "string", {"hidden": True}),
            ("modalidad_id", "int64", {"hidden": True}),
            ("cantidad", "int64", {"hidden": True}),
            ("celda_atipica", "int64", {"hidden": True}),
        ],
    },
    "fact_poblacion": {
        "description": "Población proyectada por distrito y año, ajustada al total oficial de cada provincia.",
        "columns": [
            ("ubigeo", "string", {"hidden": True}),
            ("anio", "int64", {"hidden": True}),
            ("poblacion_fuente", "int64", {"hidden": True}),
            ("poblacion_imputada", "int64", {"hidden": True}),
            ("poblacion", "int64", {"hidden": True}),
            ("poblacion_ajustada", "int64", {"hidden": True}),
        ],
    },
    "fact_alerta_distrito": {
        "description": "Cambio de las denuncias de los últimos 12 meses frente a los 12 anteriores, por distrito "
                       "y modalidad, y su puntaje frente al resto de distritos.",
        "columns": [
            ("ubigeo", "string", {"hidden": True}),
            ("modalidad_id", "int64", {"hidden": True}),
            ("denuncias_ultimos_12m", "int64", {"hidden": True}),
            ("denuncias_12m_previos", "int64", {"hidden": True}),
            ("variacion_pct", "double", {"hidden": True}),
            ("variacion_nacional_pct", "double", {"hidden": True}),
            ("z", "double", {"hidden": True, "format": "0.0"}),
            ("en_alerta", "int64", {"hidden": True}),
        ],
    },
    "fact_salto_serie": {
        "description": "Meses en que una modalidad grande cambia más de 20 % frente al mes anterior (fuera de la pandemia).",
        "columns": [
            ("mes_inicio", "dateTime", {"hidden": True, "format": "mmm yyyy"}),
            ("modalidad_id", "int64", {"hidden": True}),
            ("denuncias", "int64", {"hidden": True}),
            ("mes_anterior", "int64", {"hidden": True}),
            ("variacion_pct", "double", {"hidden": True}),
        ],
    },
}

RELATIONSHIPS = [
    ("fact_denuncia", "mes_inicio", "dim_fecha", "mes_inicio"),
    ("fact_denuncia", "ubigeo", "dim_distrito", "ubigeo"),
    ("fact_denuncia", "modalidad_id", "dim_modalidad", "modalidad_id"),
    ("fact_poblacion", "ubigeo", "dim_distrito", "ubigeo"),
    ("fact_poblacion", "anio", "dim_anio", "anio"),
    ("dim_fecha", "anio", "dim_anio", "anio"),
    ("fact_alerta_distrito", "ubigeo", "dim_distrito", "ubigeo"),
    ("fact_alerta_distrito", "modalidad_id", "dim_modalidad", "modalidad_id"),
    ("fact_salto_serie", "mes_inicio", "dim_fecha", "mes_inicio"),
    ("fact_salto_serie", "modalidad_id", "dim_modalidad", "modalidad_id"),
]

# ---------------------------------------------------------------------------------------------
# Medidas: (carpeta, nombre, expresión DAX, formato, descripción)
# ---------------------------------------------------------------------------------------------

MEASURES = [
    # 1. Denuncias (P1, P2)
    ("1. Denuncias", "Denuncias", "SUM ( fact_denuncia[cantidad] )", "#,##0",
     "Denuncias registradas por la Policía Nacional en el SIDPOL."),
    ("1. Denuncias", "Denuncias (miles)", "DIVIDE ( [Denuncias], 1000 )", "#,##0.0", "Denuncias en miles."),
    ("1. Denuncias", "Distritos con denuncias", "DISTINCTCOUNT ( fact_denuncia[ubigeo] )", "#,##0",
     "Distritos con al menos una denuncia en el contexto."),
    ("1. Denuncias", "Denuncias mismo periodo año anterior",
     "CALCULATE ( [Denuncias], DATEADD ( dim_fecha[mes_inicio], -1, YEAR ) )", "#,##0",
     "Denuncias de los mismos meses un año antes. En 2026 compara enero–julio con enero–julio de 2025."),
    ("1. Denuncias", "Var. interanual",
     "VAR antes = [Denuncias mismo periodo año anterior]\nRETURN\n"
     "    IF ( HASONEVALUE ( dim_fecha[anio] ) && NOT ISBLANK ( antes ), DIVIDE ( [Denuncias] - antes, antes ) )",
     "+0.0%;-0.0%;0.0%",
     "Variación frente a los mismos meses del año anterior. Solo con un año elegido: sobre varios años no tiene sentido."),
    ("1. Denuncias", f"Denuncias ene–jul",
     f"CALCULATE ( [Denuncias], dim_fecha[es_ene_jul] = 1 )", "#,##0",
     f"Denuncias de enero a {MONTHS_ES[CUTOFF_MONTH - 1]} de cada año: compara los años completos con el último, "
     "que llega hasta el corte."),
    ("1. Denuncias", "Var. último periodo vs año anterior",
     "VAR ultimo = CALCULATE ( MAX ( dim_fecha[anio] ), REMOVEFILTERS ( dim_fecha ) )\n"
     "VAR actual = CALCULATE ( [Denuncias ene–jul], REMOVEFILTERS ( dim_fecha ), dim_fecha[anio] = ultimo )\n"
     "VAR antes = CALCULATE ( [Denuncias ene–jul], REMOVEFILTERS ( dim_fecha ), dim_fecha[anio] = ultimo - 1 )\n"
     "RETURN\n    DIVIDE ( actual - antes, antes )",
     "+0.0%;-0.0%;0.0%",
     f"Variación del último periodo (enero–{MONTHS_ES[CUTOFF_MONTH - 1]} de {config.END[0]}) frente al mismo periodo del año anterior. "
     "No depende del año que se elija en el segmentador; sí respeta modalidad y territorio."),
    ("1. Denuncias", "Participación de la modalidad",
     "DIVIDE ( [Denuncias], CALCULATE ( [Denuncias], REMOVEFILTERS ( dim_modalidad ) ) )", "0.0%",
     "Parte de las denuncias que corresponde a la modalidad dentro del contexto (año, territorio)."),

    # 2. Tasas por 100 mil habitantes (P3)
    ("2. Tasas", "Población del año",
     "CALCULATE ( SUM ( fact_poblacion[poblacion] ), TREATAS ( VALUES ( dim_fecha[anio] ), dim_anio[anio] ) )", "#,##0",
     "Población proyectada del territorio en el año del contexto. Con varios años los suma: úsela dentro de Habitantes-año."),
    ("2. Tasas", "Población (último año)",
     "VAR y = MAX ( dim_fecha[anio] )\nRETURN\n    CALCULATE ( SUM ( fact_poblacion[poblacion] ), dim_anio[anio] = y )",
     "#,##0", "Población proyectada del último año elegido (2026 si no se elige ninguno)."),
    ("2. Tasas", "Meses cubiertos", "DISTINCTCOUNT ( dim_fecha[mes_inicio] )", "0",
     "Meses del calendario dentro del contexto. Dentro de una iteración por año se evalúa año por año."),
    ("2. Tasas", "Habitantes-año",
     "SUMX (\n    VALUES ( dim_fecha[anio] ),\n    [Población del año] * [Meses cubiertos] / 12\n)",
     "#,##0",
     "Población expuesta: cada año suma su población por la fracción del año que cubre el periodo (2026 cubre 7 de 12 meses)."),
    ("2. Tasas", "Tasa por 100 mil (anual)",
     "DIVIDE ( [Denuncias], [Habitantes-año] ) * 100000", "#,##0",
     "Denuncias por 100 mil habitantes en un año. Si el periodo no es un año completo (2026 llega a julio) queda "
     "anualizada, así que es comparable con los demás años. Se calcula como suma entre suma, nunca promediando tasas."),
    ("2. Tasas", "Tasa nacional",
     "CALCULATE ( [Tasa por 100 mil (anual)], REMOVEFILTERS ( dim_distrito ) )", "#,##0",
     "La misma tasa para todo el país, con el mismo periodo y modalidad."),
    ("2. Tasas", "Veces la tasa nacional",
     "DIVIDE ( [Tasa por 100 mil (anual)], [Tasa nacional] )", "0.00",
     "Tasa del territorio dividida por la nacional: 2 significa el doble."),
    ("2. Tasas", "Tasa (distritos de 5 mil hab. o más)",
     f"IF ( [Población (último año)] >= {MIN_POPULATION_FOR_RATE}, [Tasa por 100 mil (anual)] )", "#,##0",
     f"Tasa en blanco para distritos de menos de {MIN_POPULATION_FOR_RATE // 1000} mil habitantes, donde pocas "
     "denuncias mueven mucho la tasa."),

    # 3. Concentración territorial (P3)
    ("3. Concentración", "Participación top 10 distritos",
     "VAR mayores = TOPN ( 10, VALUES ( fact_denuncia[ubigeo] ), CALCULATE ( [Denuncias] ), DESC )\nRETURN\n"
     "    DIVIDE ( CALCULATE ( [Denuncias], mayores ), [Denuncias] )",
     "0.0%", "Parte de las denuncias que suman los 10 distritos con más denuncias del contexto."),
    ("3. Concentración", "Distritos para el 50 %",
     "VAR t = ADDCOLUMNS ( VALUES ( fact_denuncia[ubigeo] ), \"@m\", CALCULATE ( [Denuncias] ) )\n"
     "VAR total = SUMX ( t, [@m] )\n"
     "VAR conAcumulado =\n    ADDCOLUMNS ( t, \"@antes\", VAR m = [@m] RETURN SUMX ( FILTER ( t, [@m] > m ), [@m] ) )\n"
     "RETURN\n    COUNTROWS ( FILTER ( conAcumulado, [@antes] < 0.5 * total ) )",
     "#,##0", "Menor número de distritos que, ordenados de mayor a menor, acumulan la mitad de las denuncias."),
    ("3. Concentración", "Distrito líder",
     "VAR t = ADDCOLUMNS ( VALUES ( dim_distrito[distrito_unico] ), \"@m\", CALCULATE ( [Denuncias] ) )\n"
     "RETURN\n    MAXX ( TOPN ( 1, t, [@m], DESC ), dim_distrito[distrito_unico] )",
     None, "Distrito con más denuncias en el contexto."),
    ("3. Concentración", "Participación del distrito líder",
     "VAR t = ADDCOLUMNS ( VALUES ( fact_denuncia[ubigeo] ), \"@m\", CALCULATE ( [Denuncias] ) )\n"
     "RETURN\n    DIVIDE ( MAXX ( t, [@m] ), [Denuncias] )",
     "0.0%", "Parte de las denuncias que tiene el distrito con más denuncias del contexto."),

    # 4. Alertas por distrito (P4)
    ("4. Alertas", "Distritos en alerta",
     "COALESCE ( CALCULATE ( COUNTROWS ( fact_alerta_distrito ), fact_alerta_distrito[en_alerta] = 1 ), 0 )", "#,##0",
     "Combinaciones distrito–modalidad cuyo cambio de los últimos 12 meses se sale 3 o más desviaciones robustas del resto."),
    ("4. Alertas", "Combinaciones evaluadas",
     "COUNTROWS ( fact_alerta_distrito )", "#,##0",
     "Combinaciones distrito–modalidad con al menos 30 denuncias en los 12 meses previos."),
    ("4. Alertas", "Denuncias últimos 12 m", "SUM ( fact_alerta_distrito[denuncias_ultimos_12m] )", "#,##0",
     "Denuncias de agosto de 2025 a julio de 2026."),
    ("4. Alertas", "Denuncias 12 m previos", "SUM ( fact_alerta_distrito[denuncias_12m_previos] )", "#,##0",
     "Denuncias de agosto de 2024 a julio de 2025."),
    ("4. Alertas", "Cambio 12 meses",
     "DIVIDE ( [Denuncias últimos 12 m] - [Denuncias 12 m previos], [Denuncias 12 m previos] )", "+0.0%;-0.0%;0.0%",
     "Variación de los últimos 12 meses frente a los 12 anteriores."),
    ("4. Alertas", "Cambio nacional de la modalidad",
     "IF ( HASONEVALUE ( dim_modalidad[modalidad] ), AVERAGE ( fact_alerta_distrito[variacion_nacional_pct] ) / 100 )",
     "+0.0%;-0.0%;0.0%", "Variación nacional de la modalidad en la misma ventana: lo que cambió el sistema entero."),
    ("4. Alertas", "Estado de alerta",
     "IF ( [Distritos en alerta] > 0, \"En alerta\", \"Normal\" )", None,
     "Marca la fila como En alerta cuando el puntaje z es 3 o más."),
    ("4. Alertas", "Puntaje z", "MAX ( fact_alerta_distrito[z] )", "0.0",
     "Cuántas desviaciones robustas se aparta el distrito del cambio típico de su modalidad (3 o más = alerta)."),

    # 5. Calendario (P5)
    ("5. Calendario", "Participación del mes en el año",
     "DIVIDE ( [Denuncias], CALCULATE ( [Denuncias], ALLEXCEPT ( dim_fecha, dim_fecha[anio] ) ) )", "0.0%",
     "Parte de las denuncias del año que cae en el mes. Solo tiene sentido en años completos."),
    ("5. Calendario", "Índice estacional",
     f"AVERAGEX (\n    FILTER ( VALUES ( dim_fecha[anio] ), dim_fecha[anio] <= {LAST_FULL_YEAR} && dim_fecha[anio] <> {PANDEMIC_YEAR} ),\n"
     "    [Participación del mes en el año]\n)",
     "0.0%", f"Promedio de la parte del año que cae en el mes, de 2018 a {LAST_FULL_YEAR} sin {PANDEMIC_YEAR} "
             "(la pandemia deforma sus meses). Un mes parejo tendría 8,3 %."),
    ("5. Calendario", "Participación del mes (años completos)",
     f"IF ( MAX ( dim_fecha[anio] ) <= {LAST_FULL_YEAR}, [Participación del mes en el año] )", "0.0%",
     f"Igual que Participación del mes en el año, pero en blanco para {LAST_FULL_YEAR + 1}, que aún no termina."),

    # 6. Saltos de serie y calidad (limitaciones)
    ("6. Calidad de datos", "Saltos de serie", "COUNTROWS ( fact_salto_serie )", "#,##0",
     "Meses en que una modalidad grande cambió más de 20 % frente al mes anterior, sin contar la pandemia."),
    ("6. Calidad de datos", "Denuncias en el mes del salto", "SUM ( fact_salto_serie[denuncias] )", "#,##0",
     "Denuncias de la modalidad en el mes del salto."),
    ("6. Calidad de datos", "Variación del salto", "SUM ( fact_salto_serie[variacion_pct] ) / 100", "+0.0%;-0.0%;0.0%",
     "Cambio de la modalidad frente al mes anterior."),
    ("6. Calidad de datos", "Denuncias en celdas atípicas",
     "CALCULATE ( [Denuncias], fact_denuncia[celda_atipica] = 1 )", "#,##0",
     "Denuncias en celdas mes–distrito–modalidad marcadas como atípicas en la Fase 2 (no se excluyen)."),

    # 7. Textos para el tablero
    ("7. Textos", "Corte de datos",
     "VAR f = CALCULATE ( MAX ( fact_denuncia[mes_inicio] ), REMOVEFILTERS () )\nRETURN\n"
     "    \"Denuncias registradas hasta \" & LOWER ( FORMAT ( f, \"mmmm\", \"es-PE\" ) ) & \" de \" & YEAR ( f )",
     None, "Último mes con datos."),
    ("7. Textos", "Fuente",
     "\"Fuente: Ministerio del Interior, denuncias policiales del SIDPOL y población proyectada "
     "(datosabiertos.gob.pe). Elaboración propia.\"",
     None, "Pie de fuente para cada página."),
]


# ---------------------------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------------------------

def indent(text: str, tabs: int) -> str:
    return "\n".join("\t" * tabs + line if line else "" for line in text.splitlines())


def quote(name: str) -> str:
    """Nombres con espacios, tildes o signos van entre comillas simples en TMDL."""
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        return name
    return "'" + name.replace("'", "''") + "'"


def table_tmdl(name: str, spec: dict) -> str:
    out = [f"/// {spec['description']}", f"table {name}", f"\tlineageTag: {tag('table', name)}"]
    if spec.get("data_category"):
        out.append(f"\tdataCategory: {spec['data_category']}")
    out.append("")
    m_types = []
    for col, dtype, opts in spec["columns"]:
        if opts.get("description"):
            out.append(f"\t/// {opts['description']}")
        if opts.get("expression"):            # columna calculada en DAX
            out.append(f"\tcolumn {col} =")
            out.append(indent(opts["expression"], 3))
        else:
            out.append(f"\tcolumn {col}")
        out.append(f"\t\tdataType: {dtype}")
        if opts.get("key"):
            out.append("\t\tisKey")
        if opts.get("hidden"):
            out.append("\t\tisHidden")
        if opts.get("format"):
            out.append(f"\t\tformatString: {opts['format']}")
        out.append(f"\t\tlineageTag: {tag('column', name, col)}")
        out.append("\t\tsummarizeBy: none")
        if not opts.get("expression"):
            out.append(f"\t\tsourceColumn: {col}")
        if opts.get("sort_by"):
            out.append(f"\t\tsortByColumn: {opts['sort_by']}")
        out.append("")
        out.append("\t\tannotation SummarizationSetBy = Automatic")
        out.append("")
        if not opts.get("expression"):
            m_types.append(f'{{"{col}", {M_TYPES[dtype]}}}')
    m = (
        "let\n"
        f'    Origen = Csv.Document(File.Contents(RutaDatos & "{name}.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),\n'
        "    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars=true]),\n"
        f'    Tipos = Table.TransformColumnTypes(Encabezados, {{{", ".join(m_types)}}}, "en-US")\n'
        "in\n"
        "    Tipos"
    )
    out.append(f"\tpartition {name} = m")
    out.append("\t\tmode: import")
    out.append("\t\tsource =")
    out.append(indent(m, 4))
    out.append("")
    out.append("\tannotation PBI_ResultType = Table")
    out.append("")
    return "\n".join(out)


def measures_tmdl() -> str:
    out = ["table _Medidas", f"\tlineageTag: {tag('table', '_Medidas')}", ""]
    for folder, name, expr, fmt, desc in MEASURES:
        out.append(f"\t/// {desc}")
        if "\n" in expr:
            out.append(f"\tmeasure {quote(name)} =")
            out.append(indent(expr, 3))
        else:
            out.append(f"\tmeasure {quote(name)} = {expr}")
        if fmt:
            out.append(f"\t\tformatString: {fmt}")
        out.append(f"\t\tdisplayFolder: {folder}")
        out.append(f"\t\tlineageTag: {tag('measure', name)}")
        out.append("")
    out += ["\tcolumn Columna", "\t\tdataType: string", "\t\tisHidden",
            f"\t\tlineageTag: {tag('column', '_Medidas', 'Columna')}", "\t\tsummarizeBy: none",
            "\t\tisNameInferred", "\t\tsourceColumn: [Columna]", "",
            "\t\tannotation SummarizationSetBy = Automatic", "",
            "\tpartition _Medidas = calculated", "\t\tmode: import",
            '\t\tsource = ROW ( "Columna", BLANK () )', ""]
    return "\n".join(out)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    definition = MODEL / "definition"
    if definition.exists():
        shutil.rmtree(definition)
    names = list(TABLES)

    write(MODEL / ".platform", (
        '{\n  "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",\n'
        f'  "metadata": {{\n    "type": "SemanticModel",\n    "displayName": "{NAME}"\n  }},\n'
        f'  "config": {{\n    "version": "2.0",\n    "logicalId": "{tag("logical", "model")}"\n  }}\n}}\n'))
    write(MODEL / "definition.pbism", (
        '{\n  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",\n'
        '  "version": "4.2",\n  "settings": {}\n}\n'))
    write(definition / "database.tmdl", "database\n\tcompatibilityLevel: 1606\n\n")
    query_order = ", ".join(f'"{n}"' for n in ["RutaDatos", *names])
    write(definition / "model.tmdl", (
        "model Model\n\tculture: es-PE\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
        "\tdiscourageImplicitMeasures\n\tsourceQueryCulture: en-US\n\tdataAccessOptions\n"
        "\t\tlegacyRedirects\n\t\treturnErrorValuesAsNull\n\n"
        "annotation __PBI_TimeIntelligenceEnabled = 0\n\n"
        f"annotation PBI_QueryOrder = [{query_order}]\n\n"
        'annotation PBI_ProTooling = ["DevMode"]\n\n'
        + "".join(f"ref table {n}\n" for n in [*names, "_Medidas"]) + "\n"))
    curated = str(config.CURATED).replace("/", "\\") + "\\"
    write(definition / "expressions.tmdl", (
        "/// Carpeta data/curated del repositorio, con barra final. Cámbiala al clonar el proyecto en otra ruta.\n"
        f'expression RutaDatos = "{curated}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
        f"\tlineageTag: {tag('expression', 'RutaDatos')}\n\n\tannotation PBI_ResultType = Text\n\n"))
    write(definition / "relationships.tmdl", "".join(
        f"relationship {tag('relationship', f, fc, t, tc)}\n\tfromColumn: {f}.{fc}\n\ttoColumn: {t}.{tc}\n\n"
        for f, fc, t, tc in RELATIONSHIPS))
    for name, spec in TABLES.items():
        write(definition / "tables" / f"{name}.tmdl", table_tmdl(name, spec))
    write(definition / "tables" / "_Medidas.tmdl", measures_tmdl())
    print(f"Modelo: {len(TABLES)} tablas, {len(RELATIONSHIPS)} relaciones, {len(MEASURES)} medidas -> "
          f"{MODEL}")


if __name__ == "__main__":
    main()
