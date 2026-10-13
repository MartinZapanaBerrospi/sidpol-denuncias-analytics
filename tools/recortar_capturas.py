"""Recorta el lienzo del informe de las capturas de Power BI Desktop y las guarda en docs/img/.

tools/capturas.ps1 captura la ventana completa (con cintas y paneles). Este script ubica el lienzo
por el color de fondo de página del tema (#f4f5f7) y conserva solo esa área.

Uso:
    python tools/recortar_capturas.py <carpeta_de_capturas>
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PAGE_BACKGROUND = np.array([244, 245, 247])     # "page" en el tema PeruCompras.json
BOTTOM_TRIM = 12                                  # píxeles
NAMES = ["01_resumen", "02_catalogos", "03_concentracion", "04_entidades", "05_calendario",
         "06_gran_compra", "07_notas"]


def canvas_box(image: Image.Image) -> tuple[int, int, int, int]:
    pixels = np.asarray(image.convert("RGB")).astype(int)
    is_background = np.abs(pixels - PAGE_BACKGROUND).sum(axis=2) <= 3
    rows = np.where(is_background.sum(axis=1) > 300)[0]
    cols = np.where(is_background.sum(axis=0) > 300)[0]
    left, top, right, bottom = cols.min(), rows.min(), cols.max() + 1, rows.max() + 1
    ratio = (right - left) / (bottom - top)
    if not 1.70 < ratio < 1.85:
        raise ValueError(f"El área detectada no es 16:9 ({ratio:.2f}); revisar la captura")
    return left, top, right, bottom


def main() -> int:
    source = Path(sys.argv[1])
    target = ROOT / "docs" / "img"
    target.mkdir(parents=True, exist_ok=True)
    for i, name in enumerate(NAMES, start=1):
        capture = source / f"{i:02d}_pagina.png"
        image = Image.open(capture)
        left, top, right, bottom = canvas_box(image)
        # Los últimos píxeles del lienzo quedan bajo el globo de ayuda de la pestaña seleccionada; el pie
        # de fuente termina antes, así que se recortan sin perder contenido.
        box = (left, top, right, bottom - BOTTOM_TRIM)
        image.crop(box).save(target / f"{name}.png", optimize=True)
        print(f"{capture.name} -> docs/img/{name}.png {tuple(int(v) for v in box)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
