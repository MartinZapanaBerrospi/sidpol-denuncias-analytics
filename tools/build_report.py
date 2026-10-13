"""Genera el informe de Power BI (PBIR) y el archivo .pbip.

Escribe powerbi/sidpol.Report/ con el tema, las páginas y sus visuales. Como el modelo, los
identificadores se derivan de los nombres, así que regenerar produce los mismos archivos.

Uso:
    python tools/build_report.py
"""

import json
import shutil
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from report_pages import PAGES  # noqa: E402

NAME = "sidpol"
REPORT = ROOT / "powerbi" / f"{NAME}.Report"
NS = uuid.UUID("b3d0f4c8-5a21-4e6b-8f47-9d2c1a7e6b30")
BASE_THEME = "Fluent2-CY26SU08"
THEME_NAME = "Sidpol.json"
VERSIONS = {"visual": "2.12.0", "report": "3.4.0", "page": "2.3.1"}

THEME = {
    "name": "Sidpol",
    # Paleta categórica: azul, naranja, verde azulado, ocre, gris, morado, rojo, verde.
    "dataColors": ["#1f5f99", "#d9822b", "#2a9d8f", "#b5893c", "#6c757d", "#8e5ea2", "#c0504d", "#4f9d4a"],
    "background": "#ffffff",
    "foreground": "#1b1f24",
    "tableAccent": "#1f5f99",
    "good": "#2a7d4f",
    "bad": "#b8433a",
    "neutral": "#8a8f98",
    "textClasses": {
        "label": {"fontFace": "Segoe UI", "color": "#4a5058", "fontSize": 9},
        "title": {"fontFace": "Segoe UI Semibold", "color": "#1b1f24", "fontSize": 11},
        "header": {"fontFace": "Segoe UI Semibold", "color": "#1b1f24", "fontSize": 12},
        "callout": {"fontFace": "Segoe UI Semibold", "color": "#1b1f24", "fontSize": 24},
    },
    "visualStyles": {
        "*": {"*": {
            "background": [{"show": True, "color": {"solid": {"color": "#ffffff"}}, "transparency": 0}],
            "border": [{"show": True, "color": {"solid": {"color": "#e3e6ea"}}, "radius": 4}],
            "title": [{"fontSize": 11, "fontColor": {"solid": {"color": "#1b1f24"}}}],
        }},
        "page": {"*": {"background": [{"color": {"solid": {"color": "#f4f5f7"}}, "transparency": 0}]}},
    },
}


def lid(*parts: str) -> str:
    return str(uuid.uuid5(NS, "/".join(parts)))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    if REPORT.exists():
        for child in REPORT.iterdir():
            if child.name != ".pbi":          # .pbi guarda ajustes locales de Desktop
                shutil.rmtree(child) if child.is_dir() else child.unlink()

    write_json(ROOT / "powerbi" / f"{NAME}.pbip", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    })
    write_json(REPORT / ".platform", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": NAME},
        "config": {"version": "2.0", "logicalId": lid("logical", "report")},
    })
    write_json(REPORT / "definition.pbir", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}},
    })
    definition = REPORT / "definition"
    write_json(definition / "version.json", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0",
    })
    write_json(definition / "report.json", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json",
        "themeCollection": {
            "baseTheme": {"name": BASE_THEME, "reportVersionAtImport": VERSIONS, "type": "SharedResources"},
            "customTheme": {"name": THEME_NAME, "reportVersionAtImport": VERSIONS, "type": "RegisteredResources"},
        },
        "objects": {
            "section": [{"properties": {"verticalAlignment": {"expr": {"Literal": {"Value": "'Top'"}}}}}],
            "outspacePane": [{"properties": {"expanded": {"expr": {"Literal": {"Value": "false"}}}}}],
        },
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": BASE_THEME, "path": f"BaseThemes/{BASE_THEME}.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": THEME_NAME, "path": THEME_NAME, "type": "CustomTheme"}]},
        ],
        "settings": {
            "useStylableVisualContainerHeader": True,
            "exportDataMode": "AllowSummarized",
            "defaultDrillFilterOtherVisuals": True,
            "allowChangeFilterTypes": True,
            "useEnhancedTooltips": True,
            "useDefaultAggregateDisplayName": True,
        },
    })
    base = ROOT / "tools" / "assets" / f"{BASE_THEME}.json"      # tema base de Power BI Desktop 2.157
    shared = REPORT / "StaticResources" / "SharedResources" / "BaseThemes" / f"{BASE_THEME}.json"
    shared.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(base, shared)
    write_json(REPORT / "StaticResources" / "RegisteredResources" / THEME_NAME, THEME)

    pages_dir = definition / "pages"
    order = []
    for page in PAGES:
        order.append(page["name"])
        write_json(pages_dir / page["name"] / "page.json", {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json",
            "name": page["name"],
            "displayName": page["displayName"],
            "displayOption": "FitToPage",
            "height": 720,
            "width": 1280,
        })
        for z, visual in enumerate(page.get("visuals", [])):
            visual["position"]["z"] = z * 1000
            visual["position"]["tabOrder"] = z * 1000
            write_json(pages_dir / page["name"] / "visuals" / visual["name"] / "visual.json", visual)
    write_json(pages_dir / "pages.json", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
        "pageOrder": order,
        "activePageName": order[0],
    })
    n_visuals = sum(len(p.get("visuals", [])) for p in PAGES)
    print(f"Informe: {len(PAGES)} páginas, {n_visuals} visuales -> {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
