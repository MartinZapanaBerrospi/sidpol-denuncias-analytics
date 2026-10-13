"""Páginas y visuales del informe de Power BI (PBIR), escritos por tools/build_report.py.

Lienzo de 1280 × 720 con márgenes de 24 px. Las cifras de los textos salen de
reports/analisis/cifras_clave.csv (Fase 5): el tablero no repite números escritos a mano.
"""

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEY = {r["cifra"]: r["valor"] for r in csv.DictReader(
    (ROOT / "reports" / "analisis" / "cifras_clave.csv").open(encoding="utf-8"))}

INK, MUTED, PANEL = "#1b1f24", "#4a5058", "#ffffff"
ACCENT = "#1f5f99"


# ---------------------------------------------------------------------------------------------
# Formato de cifras en español del Perú
# ---------------------------------------------------------------------------------------------

def num(value, decimals: int = 0) -> str:
    """1234567.8 -> '1 234 568' ; con decimales usa coma: 2,5."""
    text = f"{float(value):,.{decimals}f}"
    return text.replace(",", " ").replace(".", ",").replace("-", "−")


def pct(value, decimals: int = 1) -> str:
    return f"{num(float(value) * 100, decimals)} %"


def millions(value, decimals: int = 1) -> str:
    return f"S/ {num(float(value) / 1e6, decimals)} millones"


def k(name: str) -> str:
    return KEY[name]


def proper(name: str) -> str:
    """'SAN JUAN' -> 'San Juan' (artículos y preposiciones en minúscula)."""
    small = {"de", "del", "la", "las", "el", "los", "y", "e", "en", "para", "por", "a"}
    words = name.lower().split()
    return " ".join(w if i and w in small else w.capitalize() for i, w in enumerate(words))


# ---------------------------------------------------------------------------------------------
# Piezas PBIR
# ---------------------------------------------------------------------------------------------

def lit(value: str) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


def text(value: str) -> dict:
    return lit("'" + value.replace("'", "''") + "'")


def color(hex_code: str) -> dict:
    return {"solid": {"color": lit(f"'{hex_code}'")}}


def measure(name: str, display: str | None = None) -> dict:
    p = {"field": {"Measure": {"Expression": {"SourceRef": {"Entity": "_Medidas"}}, "Property": name}},
         "queryRef": f"_Medidas.{name}", "nativeQueryRef": name}
    if display:
        p["displayName"] = display
    return p


def column(entity: str, prop: str, display: str | None = None, active: bool = False) -> dict:
    p = {"field": {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
         "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop}
    if display:
        p["displayName"] = display
    if active:
        p["active"] = True
    return p


def sort_by(projection: dict, direction: str = "Descending") -> dict:
    return {"sort": [{"field": projection["field"], "direction": direction}]}


def container(title: str | None = None, background: bool = True) -> dict:
    objects = {
        "background": [{"properties": {"show": lit("true" if background else "false"),
                                       **({"color": color(PANEL), "transparency": lit("0D")} if background else {})}}],
        "border": [{"properties": {"show": lit("false")}}],
        "dropShadow": [{"properties": {"show": lit("false")}}],
        "subTitle": [{"properties": {"show": lit("false")}}],
        "title": [{"properties": {"show": lit("false")}}],
    }
    if title:
        objects["title"] = [{"properties": {
            "show": lit("true"), "text": text(title), "fontSize": lit("11D"),
            "fontColor": color(INK), "bold": lit("false"), "fontFamily": text("Segoe UI Semibold")}}]
    return objects


def position(x, y, w, h) -> dict:
    return {"x": x, "y": y, "z": 0, "height": h, "width": w, "tabOrder": 0}


def visual(name: str, pos: dict, body: dict) -> dict:
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.12.0/schema.json",
        "name": name, "position": pos, "visual": body,
    }


def textbox(name, x, y, w, h, paragraphs, background=False) -> dict:
    """paragraphs: lista de (texto, tamaño en pt, color, negrita)."""
    paras = []
    for content, size, hex_code, bold in paragraphs:
        paras.append({"textRuns": [{"value": content, "textStyle": {
            "fontFamily": "Segoe UI Semibold" if bold else "Segoe UI", "fontSize": f"{size}pt", "color": hex_code}}]})
    return visual(name, position(x, y, w, h), {
        "visualType": "textbox",
        "objects": {"general": [{"properties": {"paragraphs": paras}}]},
        "visualContainerObjects": container(background=background),
    })


def title(page_title: str, answer: str, width: int = 1016) -> dict:
    """Título (la pregunta) y subtítulo (la respuesta). Deja libre la esquina derecha para el segmentador."""
    return textbox("titulo", 24, 8, width, 72, [(page_title, 18, INK, True), (answer, 11, MUTED, False)])


def footer() -> dict:
    return textbox("fuente", 24, 690, 1232, 24, [(
        "Fuente: Ministerio del Interior, denuncias policiales del SIDPOL (datosabiertos.gob.pe), enero 2018 – julio 2026. "
        "Una denuncia no es un delito. Elaboración propia.", 8, MUTED, False)])


def reading(name, x, y, w, h, heading, bullets, extra_heading=None, extra=None) -> dict:
    paras = [(heading, 11, INK, True)] + [("• " + b, 10, INK, False) for b in bullets]
    if extra_heading:
        paras += [(extra_heading, 11, INK, True)] + [("• " + b, 10, INK, False) for b in extra]
    return textbox(name, x, y, w, h, paras, background=True)


def card(name, x, y, w, h, measure_name, label, value_size=22) -> dict:
    return visual(name, position(x, y, w, h), {
        "visualType": "card",
        "query": {"queryState": {"Values": {"projections": [measure(measure_name)]}}},
        "objects": {
            "labels": [{"properties": {"fontSize": lit(f"{value_size}D"), "color": color(ACCENT),
                                       "fontFamily": text("Segoe UI Semibold"), "labelDisplayUnits": lit("1D")}}],
            "categoryLabels": [{"properties": {"show": lit("false")}}],
        },
        "visualContainerObjects": {**container(), "title": [{"properties": {
            "show": lit("true"), "text": text(label), "fontSize": lit("10D"), "fontColor": color(MUTED),
            "bold": lit("false"), "fontFamily": text("Segoe UI")}}]},
    })


def axis_objects(categorical: bool = False, labels: bool = False, legend: bool = False, compact: bool = False) -> dict:
    objects = {
        "categoryAxis": [{"properties": {"showAxisTitle": lit("false"), "gridlineShow": lit("false"),
                                         "labelColor": color(MUTED), "fontSize": lit("8D" if compact else "9D"),
                                         **({"axisType": text("Categorical")} if categorical else {}),
                                         **({"innerPadding": lit("12D")} if compact else {})}}],
        # labelDisplayUnits 1 = sin abreviar: "3 135,8" y no "3,1 mil" (los montos ya están en millones)
        "valueAxis": [{"properties": {"showAxisTitle": lit("false"), "gridlineColor": color("#e9ecef"),
                                      "labelColor": color(MUTED), "fontSize": lit("9D"),
                                      "labelDisplayUnits": lit("1D"),
                                      **({"show": lit("false")} if compact else {})}}],
        "legend": [{"properties": {"show": lit("true" if legend else "false"), "position": text("Top"),
                                   "fontSize": lit("9D"), "labelColor": color(MUTED)}}],
    }
    if labels:
        objects["labels"] = [{"properties": {"show": lit("true"), "fontSize": lit("9D"), "color": color(INK),
                                             "labelDisplayUnits": lit("1D")}}]
    return objects


def chart(name, kind, x, y, w, h, chart_title, category, values, series=None, sort=None,
          categorical=False, labels=False, legend=False, compact=False) -> dict:
    state = {"Category": {"projections": [category]}, "Y": {"projections": values}}
    if series:
        state["Series"] = {"projections": [series]}
    query = {"queryState": state}
    if sort:
        query["sortDefinition"] = sort
    return visual(name, position(x, y, w, h), {
        "visualType": kind, "query": query,
        "objects": axis_objects(categorical, labels, legend, compact),
        "visualContainerObjects": container(chart_title),
    })


def table(name, x, y, w, h, table_title, projections, sort=None, widths=None) -> dict:
    """widths: ancho en píxeles de cada columna, en el orden de projections. Deben sumar menos que w."""
    query = {"queryState": {"Values": {"projections": projections}}}
    if sort:
        query["sortDefinition"] = sort
    objects = {
        "columnHeaders": [{"properties": {"fontSize": lit("9D"), "fontColor": color(INK), "wordWrap": lit("true")}}],
        "values": [{"properties": {"fontSize": lit("9D"), "wordWrap": lit("false")}}],
        "total": [{"properties": {"totals": lit("false")}}],
    }
    if widths:
        assert len(widths) == len(projections) and sum(widths) <= w - 40, name
        objects["columnWidth"] = [{"properties": {"value": lit(f"{width}D")}, "selector": {"metadata": p["queryRef"]}}
                                  for p, width in zip(projections, widths)]
    return visual(name, position(x, y, w, h), {
        "visualType": "tableEx", "query": query, "objects": objects,
        "visualContainerObjects": container(table_title),
    })


def slicer(name, x, y, w, h, entity, prop, header, order_prop=None, selected=None) -> dict:
    """selected: valor numérico que el segmentador trae elegido al abrir el informe (se guarda como filtro)."""
    query = {"queryState": {"Values": {"projections": [column(entity, prop, active=True)]}}}
    if order_prop:
        query["sortDefinition"] = sort_by(column(entity, order_prop), "Ascending")
    out = visual(name, position(x, y, w, h), {
        "visualType": "slicer", "query": query,
        "objects": {
            "data": [{"properties": {"mode": text("Dropdown")}}],
            "selection": [{"properties": {"strictSingleSelect": lit("false"), "singleSelect": lit("false")}}],
            "header": [{"properties": {"show": lit("true"), "text": text(header)}}],
        },
        "visualContainerObjects": container(background=False),
    })
    if selected is not None:
        # El segmentador guarda lo que trae elegido en objects.general[].properties.filter.
        out["visual"]["objects"]["general"] = [{"properties": {"filter": {"filter": {
            "Version": 2,
            "From": [{"Name": "t", "Entity": entity, "Type": 0}],
            "Where": [{"Condition": {"In": {
                "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": prop}}],
                "Values": [[{"Literal": {"Value": f"{selected}L"}}]]}}}],
        }}}}]
    return out


def matrix(name, x, y, w, h, matrix_title, rows, columns, values) -> dict:
    """Tabla cruzada: filas × columnas con una o más medidas."""
    return visual(name, position(x, y, w, h), {
        "visualType": "pivotTable",
        "query": {"queryState": {"Rows": {"projections": rows}, "Columns": {"projections": columns},
                                 "Values": {"projections": values}}},
        "objects": {
            "columnHeaders": [{"properties": {"fontSize": lit("9D"), "fontColor": color(INK)}}],
            "rowHeaders": [{"properties": {"fontSize": lit("9D"), "fontColor": color(INK)}}],
            "values": [{"properties": {"fontSize": lit("9D")}}],
            "subTotals": [{"properties": {"rowSubtotals": lit("false"), "columnSubtotals": lit("false")}}],
        },
        "visualContainerObjects": container(matrix_title),
    })


def year_slicer(x=1056, selected: int | None = None) -> dict:
    return slicer("segmentador_anio", x, 12, 200, 64, "dim_fecha", "anio", "Año (vacío = todos)", selected=selected)


def modality_slicer(x=840) -> dict:
    return slicer("segmentador_modalidad", x, 12, 200, 64, "dim_modalidad", "modalidad", "Modalidad (vacío = todas)")


# ---------------------------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------------------------

YEAR = 2025                                   # año de referencia de las páginas de territorio
LAST_YEAR = 2026                              # último año con datos (enero–julio)
DEN = measure("Denuncias")
TASA = measure("Tasa por 100 mil (anual)", "Tasa por 100 mil")


CHECKS = sum(1 for _ in (ROOT / "reports" / "validacion_medidas.csv").open(encoding="utf-8")) - 1   # comparaciones de la Fase 4


def f(name: str) -> float:
    return float(k(name))


def n(name: str, decimals: int = 0) -> str:
    return num(f(name), decimals)


def p(name: str, decimals: int = 1) -> str:
    return pct(f(name), decimals)


def p_abs(name: str, decimals: int = 1) -> str:
    return pct(abs(f(name)), decimals)


p1 = {"name": "p1_resumen", "displayName": "1. Resumen", "visuals": [
    title("Denuncias policiales en el Perú",
          f"Resumen ejecutivo · {num(f('denuncias_total') / 1e6, 2)} millones de denuncias, enero 2018 – julio 2026"),
    year_slicer(),
    card("kpi_denuncias", 24, 88, 232, 92, "Denuncias", "Denuncias"),
    card("kpi_tasa", 274, 88, 232, 92, "Tasa por 100 mil (anual)", "Denuncias por 100 mil (anual)"),
    card("kpi_var", 524, 88, 232, 92, "Var. último periodo vs año anterior", f"Enero–julio {LAST_YEAR} vs {LAST_YEAR - 1}"),
    card("kpi_distritos", 774, 88, 232, 92, "Distritos con denuncias", "Distritos con denuncias"),
    card("kpi_alerta", 1024, 88, 232, 92, "Distritos en alerta", "Alertas de distrito (página 5)"),
    chart("linea_mensual", "lineChart", 24, 196, 808, 300, "Denuncias por mes",
          column("dim_fecha", "mes_inicio", "Mes", active=True), [DEN]),
    chart("barras_modalidad", "clusteredBarChart", 848, 196, 408, 300, "Denuncias por modalidad",
          column("dim_modalidad", "modalidad", "Modalidad", active=True), [DEN], sort=sort_by(DEN), labels=True),
    reading("lectura", 24, 512, 1232, 170, "Qué está pasando", [
        f"Las denuncias tocaron su máximo en 2023 ({n('denuncias_2023')}) y bajaron {p_abs('var_2023_2025')} hasta 2025; "
        f"enero–julio de 2026 va {p_abs('var_ene_jul_2026')} por debajo de 2025.",
        f"La extorsión se multiplicó por {n('extorsion_veces', 1)} desde 2018 y la estafa por {n('estafa_veces', 1)}. El robo cayó "
        f"{p_abs('var_robo_2023_2025', 0)} desde 2023, pero con saltos de registro: no es una baja confirmada del delito.",
        f"Lima Metropolitana tiene el {p('lima_met_pct_denuncias', 0)} de las denuncias, pero {k('dep_mayor_tasa')} y {k('dep_2')} "
        "tienen más denuncias por habitante.",
    ], "Qué conviene hacer", [
        f"Priorizar por tasa por habitante y no por conteo, y revisar las {n('alertas')} combinaciones en alerta (página 5).",
        "Antes de citar un alza o una baja, mirar si la serie tiene un salto de registro (página 2).",
    ]),
    footer(),
]}

p2 = {"name": "p2_modalidades", "displayName": "2. Modalidades", "visuals": [
    title("¿Qué modalidades crecen y cuáles caen?",
          f"La extorsión se multiplicó por {n('extorsion_veces', 1)} y la estafa por {n('estafa_veces', 1)} desde 2018; el robo "
          f"cae {p_abs('var_robo_2023_2025', 0)} desde 2023, con saltos de registro", width=1232),
    matrix("matriz_modalidad_anio", 24, 88, 776, 292, "Denuncias por modalidad y año (2026: enero–julio). Elija una fila para filtrar",
           [column("dim_modalidad", "modalidad", "Modalidad", active=True)],
           [column("dim_fecha", "anio", "Año", active=True)], [DEN]),
    chart("linea_modalidad", "lineChart", 24, 396, 776, 286, "Denuncias por mes (todas, o la modalidad elegida arriba)",
          column("dim_fecha", "mes_inicio", "Mes", active=True), [DEN]),
    table("tabla_saltos", 816, 88, 440, 340, "Saltos de más de 20 % de un mes a otro", [
        column("dim_fecha", "mes_inicio", "Mes"),
        column("dim_modalidad", "modalidad", "Modalidad"),
        measure("Variación del salto", "Variación"),
        measure("Denuncias en el mes del salto", "Denuncias del mes"),
    ], sort=sort_by(column("dim_fecha", "mes_inicio"), "Ascending"), widths=[80, 130, 80, 100]),
    reading("lectura", 816, 444, 440, 238, "Cómo leer esta página", [
        f"{int(f('saltos_total'))} saltos en cuatro modalidades. Un cambio así en un mes rara vez es el delito: suele ser el registro.",
        f"El robo explica el {p('aporte_robo_cambio_2023_2025', 0)} de la caída de 2023 a 2025 y tiene {int(f('saltos_robo'))} saltos.",
        f"«Otros» agrupa el {p('pct_otros', 0)} de las denuncias y la fuente no la abre: ningún total se lee por tipo de delito.",
        "La tendencia de largo plazo de extorsión y estafa es clara; su tamaño exacto depende de cómo se registró cada año.",
    ]),
    footer(),
]}

p3 = {"name": "p3_territorio", "displayName": "3. Territorio",
      "interactions": [{"source": "segmentador_anio", "target": "linea_tasa_anio", "type": "NoFilter"}], "visuals": [
    title("¿Qué territorios tienen más denuncias por habitante?",
          f"{k('dep_mayor_tasa')} ({n('dep_mayor_tasa_veces', 1)} veces la tasa nacional) y {k('dep_2')} ({n('dep_2_veces', 1)}) encabezan; "
          "Lima Metropolitana pesa por su población, no por su tasa", width=800),
    modality_slicer(),
    year_slicer(selected=YEAR),
    chart("barras_departamento", "clusteredBarChart", 24, 88, 560, 594, "Denuncias por 100 mil habitantes, por departamento",
          column("dim_distrito", "departamento", "Departamento", active=True), [TASA], sort=sort_by(TASA), labels=True,
          compact=True),
    card("kpi_tasa_nacional", 600, 88, 208, 92, "Tasa nacional", "Tasa nacional por 100 mil"),
    card("kpi_denuncias", 824, 88, 208, 92, "Denuncias", "Denuncias"),
    card("kpi_poblacion", 1048, 88, 208, 92, "Población (último año)", "Población del último año"),
    chart("linea_tasa_anio", "lineChart", 600, 196, 656, 250, "Tasa por 100 mil en el tiempo (elija un departamento)",
          column("dim_fecha", "anio", "Año", active=True), [TASA], categorical=True, labels=True),
    reading("lectura", 600, 462, 656, 220, "Lectura", [
        f"Solo {n('deps_sobre_nacional')} de {n('n_departamentos')} departamentos superan la tasa nacional ({n('tasa_nacional_2025')} en 2025).",
        f"Lima Metropolitana: {p('lima_met_pct_denuncias', 0)} de las denuncias con el {p('lima_met_pct_poblacion', 0)} de la población "
        f"({n('lima_met_veces', 2)} veces la tasa nacional).",
        f"Los cinco departamentos con menor tasa en 2018 la subieron {p('convergencia_5_bajos_cambio', 0)}: coherente con un sistema que "
        "llega a más lugares, y con la regresión a la media.",
        "Una tasa mezcla cuánto delito hay, cuánto se denuncia y qué tan fácil es denunciar: no mide inseguridad.",
    ]),
    footer(),
]}

p4 = {"name": "p4_distritos", "displayName": "4. Distritos", "visuals": [
    title("¿Qué distritos concentran las denuncias?",
          f"Diez distritos suman el {p('top10_participacion_2025')} de las denuncias y {n('distritos_para_50pct_2025')} de "
          f"{n('distritos_con_denuncias_total')} llegan a la mitad; las tasas más altas son de distritos comerciales o de paso", width=620),
    slicer("segmentador_departamento", 660, 12, 190, 64, "dim_distrito", "departamento", "Departamento"),
    modality_slicer(860),
    year_slicer(1060, selected=YEAR),
    card("kpi_top10", 24, 88, 296, 92, "Participación top 10 distritos", "Parte en los 10 distritos con más"),
    card("kpi_para_50", 336, 88, 296, 92, "Distritos para el 50 %", "Distritos que suman la mitad"),
    card("kpi_distritos", 648, 88, 296, 92, "Distritos con denuncias", "Distritos con denuncias"),
    card("kpi_lider", 960, 88, 296, 92, "Distrito líder", "Distrito con más denuncias", value_size=14),
    table("tabla_denuncias", 24, 196, 608, 486, "Distritos con más denuncias", [
        column("dim_distrito", "distrito_unico", "Distrito"),
        column("dim_distrito", "departamento", "Departamento"),
        DEN,
        measure("Población (último año)", "Población"),
    ], sort=sort_by(DEN), widths=[210, 150, 100, 100]),
    table("tabla_tasa", 648, 196, 608, 300, "Mayor tasa por 100 mil (distritos de 5 mil habitantes o más)", [
        column("dim_distrito", "distrito_unico", "Distrito"),
        column("dim_distrito", "departamento", "Departamento"),
        measure("Población (último año)", "Población"),
        measure("Tasa (distritos de 5 mil hab. o más)", "Tasa por 100 mil"),
    ], sort=sort_by(measure("Tasa (distritos de 5 mil hab. o más)")), widths=[190, 130, 90, 110]),
    reading("lectura", 648, 512, 608, 170, "Lectura", [
        "Las denuncias se registran donde se presentan, no donde vive la persona, y la población es la residente: los distritos "
        f"comerciales o de paso tienen tasas enormes (Arequipa, Lima, Miraflores) y no son «más peligrosos».",
        f"Encabezan el conteo {k('distrito_lider')} ({n('distrito_lider_denuncias')}) y {k('distrito_2')} ({n('distrito_2_denuncias')}).",
    ]),
    footer(),
]}

p5 = {"name": "p5_alertas", "displayName": "5. Alertas", "visuals": [
    title("¿Qué distritos se salen de su propia historia?",
          f"{n('alertas')} de {n('alertas_evaluadas')} combinaciones distrito–modalidad subieron muy por encima de lo normal; "
          "las cinco son escalones sostenidos, no picos", width=800),
    modality_slicer(),
    card("kpi_alertas", 24, 88, 196, 92, "Distritos en alerta", "Combinaciones en alerta"),
    card("kpi_evaluadas", 236, 88, 196, 92, "Combinaciones evaluadas", "Combinaciones evaluadas"),
    card("kpi_umbral", 448, 88, 196, 92, "Puntaje z", "Puntaje z (3 o más = alerta)"),
    table("tabla_alertas", 24, 196, 808, 486, "Distritos por puntaje de alerta (de mayor a menor; elija una fila)", [
        column("dim_distrito", "distrito_unico", "Distrito"),
        column("dim_distrito", "departamento", "Departamento"),
        column("dim_modalidad", "modalidad", "Modalidad"),
        measure("Estado de alerta", "Estado"),
        measure("Denuncias 12 m previos", "12 meses previos"),
        measure("Denuncias últimos 12 m", "Últimos 12 meses"),
        measure("Cambio 12 meses", "Cambio"),
        measure("Cambio nacional de la modalidad", "Cambio del país"),
        measure("Puntaje z", "Puntaje z"),
    ], sort=sort_by(measure("Puntaje z")), widths=[115, 100, 120, 70, 62, 62, 58, 62, 52]),
    chart("linea_seleccion", "lineChart", 848, 88, 408, 300, "Denuncias por mes de la fila elegida (sin elegir: país)",
          column("dim_fecha", "mes_inicio", "Mes", active=True), [DEN]),
    reading("lectura", 848, 404, 408, 278, "Cómo leer esta página", [
        "Compara los últimos 12 meses con los 12 anteriores de cada distrito y modalidad, descuenta lo que cambió el país "
        "y mide cuántas desviaciones se aparta del resto.",
        f"Los cinco casos son escalones: el nivel mensual se multiplica por 2 o más y se mantiene. Santa Anita (hurto) pasa de "
        f"{n('santa_anita_antes')} a {n('santa_anita_despues')} denuncias al mes desde junio de 2025.",
        "Se parece más a un cambio de registro que a un brote, pero los datos no permiten distinguirlo: sirve para preguntar a la comisaría.",
    ]),
    footer(),
]}

p6 = {"name": "p6_calendario", "displayName": "6. Calendario", "visuals": [
    title("¿Cuándo se denuncia más?",
          f"Casi no hay estacionalidad: el mes más alto ({k('estacional_mes_max')}) y el más bajo ({k('estacional_mes_min')}) "
          f"difieren {n('estacional_rango_pp', 1)} puntos; la pandemia fue la única ruptura grande", width=800),
    modality_slicer(),
    chart("columnas_indice", "clusteredColumnChart", 24, 88, 608, 280, "Parte del año que cae en cada mes (promedio 2018–2025, sin 2020)",
          column("dim_fecha", "mes_nombre", "Mes", active=True), [measure("Índice estacional", "% del año")], labels=True),
    chart("lineas_participacion", "lineChart", 648, 88, 608, 280, "Parte del año por mes, cada año (2026 no entra)",
          column("dim_fecha", "mes_nombre", "Mes", active=True), [measure("Participación del mes (años completos)", "% del año")],
          series=column("dim_fecha", "anio", "Año"), legend=True),
    chart("lineas_denuncias", "lineChart", 24, 384, 808, 298, "Denuncias por mes y año: abril de 2020",
          column("dim_fecha", "mes_nombre", "Mes", active=True), [DEN], series=column("dim_fecha", "anio", "Año"), legend=True),
    reading("lectura", 848, 384, 408, 298, "Lectura", [
        f"Un año parejo daría {p('estacional_parejo')} por mes. Aquí van de {p('estacional_min')} a {p('estacional_max')}: no hay una temporada.",
        "La violencia contra la mujer sube de enero a marzo; hurto y estafa, de octubre a diciembre (elija la modalidad).",
        f"Abril de 2020: {n('pandemia_abril_2020')} denuncias, {p_abs('pandemia_caida_abril', 0)} menos que en abril de 2019 "
        f"({n('pandemia_abril_2019')}). El año cerró {p_abs('pandemia_2020_vs_2019', 0)} abajo, y en 2022 ya superaba a 2019.",
    ]),
    footer(),
]}

p7 = {"name": "p7_notas", "displayName": "7. Notas", "visuals": [
    title("Notas", "Definiciones, fuentes, validaciones y límites"),
    textbox("definiciones", 24, 88, 400, 440, [
        ("Definiciones", 11, INK, True),
        ("Denuncia: hecho que una persona reporta a la Policía Nacional y queda en el SIDPOL. No es un delito probado "
         "ni mide cuánto delito hay.", 9, INK, False),
        ("Tasa por 100 mil: denuncias entre población proyectada, por 100 000 habitantes y por año. Se suman denuncias "
         "y población antes de dividir; nunca se promedian tasas.", 9, INK, False),
        ("Año incompleto: 2026 llega a julio. Su tasa se anualiza (7 de 12 meses) y las comparaciones usan enero–julio.", 9, INK, False),
        ("Alerta: el cambio de los últimos 12 meses se aparta 3 o más desviaciones robustas del resto de distritos de "
         "la modalidad, con al menos 20 denuncias más y 30 en los 12 meses previos.", 9, INK, False),
        ("Salto de serie: una modalidad grande cambia más de 20 % de un mes a otro, fuera de la pandemia.", 9, INK, False),
        ("Lima aparece partida en Lima Metropolitana y Región Lima, como en el padrón de población.", 9, INK, False),
    ], background=True),
    textbox("fuentes", 440, 88, 400, 440, [
        ("Fuentes y validación", 11, INK, True),
        ("Datos: tres conjuntos del Ministerio del Interior en datosabiertos.gob.pe: denuncias policiales del SIDPOL, "
         "violencia contra la mujer e indicadores de seguridad ciudadana (de ahí sale la población).", 9, INK, False),
        ("Violencia contra la mujer: el archivo principal y el archivo propio de la modalidad coinciden en las 94 940 celdas "
         "y en los 2 149 178 casos.", 9, INK, False),
        ("Extorsión: la suma coincide con el indicador oficial del Plan de Acción de Seguridad Ciudadana con una diferencia "
         "de −1,6 % a −5,3 % por año.", 9, INK, False),
        ("Población: la suma de provincias, departamentos y país cuadra en cada año; la de distritos queda corta desde "
         "2020 y se ajustó al total provincial.", 9, INK, False),
        ("Calidad: 40 reglas en seis dimensiones, 19 problemas documentados y ninguna denuncia excluida (7 359 931 en "
         "el archivo y en el modelo).", 9, INK, False),
        (f"Cada medida del tablero se comparó con el mismo cálculo en Python: {num(CHECKS)} comparaciones, diferencia máxima 3,9 × 10⁻¹⁵.", 9, INK, False),
        ("Detalle y código: github.com/MartinZapanaBerrospi/sidpol-denuncias-analytics", 9, ACCENT, False),
    ], background=True),
    textbox("limites", 856, 88, 400, 440, [
        ("Límites", 11, INK, True),
        ("Una denuncia no es un delito: mezcla cuánto delito hay, cuánto se denuncia y cómo se registra.", 9, INK, False),
        ("«Otros» es el 36 % de las denuncias y la fuente no lo desglosa. No hay homicidios en este conjunto.", 9, INK, False),
        ("19 saltos de serie en cuatro modalidades: las alzas y bajas grandes (robo, estafa, extorsión) pueden "
         "ser cambios de registro.", 9, INK, False),
        ("La cobertura del sistema creció: de 1 518 distritos con denuncias en 2018 a 1 758 en 2025.", 9, INK, False),
        ("La población es la residente y las denuncias se registran donde se presentan: las tasas de distritos "
         "comerciales o de paso no son comparables.", 9, INK, False),
        ("36 distritos del padrón no tienen ninguna denuncia: las tasas de departamentos como Huancavelica pueden "
         "estar hasta 4,4 % más altas.", 9, INK, False),
        ("Análisis descriptivo: dice qué pasó y cuánto, no por qué.", 9, INK, False),
        ("Los datos son estadísticas agregadas por distrito y mes: no hay personas identificables.", 9, INK, False),
    ], background=True),
    footer(),
]}

PAGES = [p1, p2, p3, p4, p5, p6, p7]
