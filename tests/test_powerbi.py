"""Pruebas del modelo de Power BI que no necesitan Power BI Desktop."""

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_model  # noqa: E402
import validate_measures  # noqa: E402

DEFINITION = ROOT / "powerbi" / "sidpol.SemanticModel" / "definition"
# Palabras que DAX no admite como nombre de variable (el error de la Fase 4 fue 'top').
RESERVED = {"top", "var", "return", "true", "false", "not", "and", "or", "in", "order", "by", "asc", "desc",
            "define", "evaluate", "measure", "column", "table", "datatable", "start", "at", "skip", "dense"}


def test_las_variables_dax_no_usan_palabras_reservadas():
    for _, name, expr, _, _ in build_model.MEASURES:
        for var in re.findall(r"\bVAR\s+(\w+)", expr):
            assert var.lower() not in RESERVED, f"{name}: VAR {var}"


def test_las_medidas_validadas_existen_en_el_modelo():
    names = {m[1] for m in build_model.MEASURES}
    for group in (validate_measures.GLOBAL, validate_measures.BY_YEAR, validate_measures.BY_MODALITY,
                  validate_measures.BY_DEPARTMENT, validate_measures.BY_YEAR_DEPARTMENT, validate_measures.BY_MONTH):
        assert set(group) <= names


def test_el_tmdl_versionado_es_el_que_produce_el_generador(tmp_path, monkeypatch):
    monkeypatch.setattr(build_model, "MODEL", tmp_path / "modelo")
    build_model.main()
    for generated in (tmp_path / "modelo" / "definition").rglob("*.tmdl"):
        versioned = DEFINITION / generated.relative_to(tmp_path / "modelo" / "definition")
        if generated.name == "expressions.tmdl":
            continue  # contiene la ruta local de data/curated
        assert versioned.read_text(encoding="utf-8") == generated.read_text(encoding="utf-8"), versioned.name


def test_todas_las_medidas_coinciden_con_python():
    result = pd.read_csv(ROOT / "reports" / "validacion_medidas.csv")
    expected = (len(validate_measures.GLOBAL) + len(validate_measures.TEXTS)
                + 9 * len(validate_measures.BY_YEAR) + 7 * len(validate_measures.BY_MODALITY)
                + 26 * len(validate_measures.BY_DEPARTMENT) + 234 * len(validate_measures.BY_YEAR_DEPARTMENT)
                + 12 * len(validate_measures.BY_MONTH))
    assert len(result) == expected
    assert (result["resultado"] == "cumple").all()


def visuals_by_page():
    import json
    pages = {}
    for path in (ROOT / "powerbi" / "sidpol.Report" / "definition" / "pages").glob("*/visuals/*/visual.json"):
        pages.setdefault(path.parents[2].name, []).append(json.loads(path.read_text(encoding="utf-8")))
    return pages


def test_los_visuales_caben_en_el_lienzo_y_no_se_enciman():
    for page, visuals in visuals_by_page().items():
        boxes = [(v["name"], v["position"]) for v in visuals]
        for name, p in boxes:
            assert p["x"] >= 0 and p["y"] >= 0, (page, name)
            assert p["x"] + p["width"] <= 1280 and p["y"] + p["height"] <= 720, (page, name)
        for i, (a, pa) in enumerate(boxes):
            for b, pb in boxes[i + 1:]:
                overlap = (pa["x"] < pb["x"] + pb["width"] and pb["x"] < pa["x"] + pa["width"]
                           and pa["y"] < pb["y"] + pb["height"] and pb["y"] < pa["y"] + pa["height"])
                assert not overlap, (page, a, b)


def test_los_visuales_solo_usan_medidas_y_columnas_del_modelo():
    import json
    measures = {m[1] for m in build_model.MEASURES}
    columns = {(t, c[0]) for t, spec in build_model.TABLES.items() for c in spec["columns"]}

    def walk(node):
        if isinstance(node, dict):
            if "Measure" in node:
                assert node["Measure"]["Property"] in measures, node["Measure"]["Property"]
            if "Column" in node:
                ref = (node["Column"]["Expression"]["SourceRef"]["Entity"], node["Column"]["Property"])
                assert ref in columns, ref
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for visuals in visuals_by_page().values():
        for v in visuals:
            walk(v)


def test_cada_pagina_tiene_titulo_y_fuente():
    for page, visuals in visuals_by_page().items():
        names = {v["name"] for v in visuals}
        assert {"titulo", "fuente"} <= names, page


def test_cada_columna_del_csv_esta_en_el_modelo():
    for name, spec in build_model.TABLES.items():
        header = (ROOT / "data" / "curated" / f"{name}.csv").open(encoding="utf-8").readline().strip().split(",")
        loaded = [c[0] for c in spec["columns"] if not c[2].get("expression")]  # sin columnas calculadas
        assert loaded == header, name
