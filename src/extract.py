"""Fase 1 — Registra los archivos de datos abiertos bajados del portal.

El portal (datosabiertos.gob.pe) responde 418 a los clientes que no son navegadores, y este
proyecto no intenta evadirlo. La descarga se hace una vez en el navegador: el botón de cada
conjunto entrega un zip con todos sus recursos (ver config.DOWNLOAD_URLS), que se deja en
data/raw/descarga/. Este script:

1. Extrae de cada zip los archivos que usa el proyecto (config.SPEC), sin modificar un byte.
2. Compara cada uno con el inventario del portal (data/reference/inventario_portal.csv).
3. Registra en data/raw/manifest.csv su URL, fecha de publicación, tamaño y hash SHA-256.
4. Falla si falta alguno de los archivos esperados.

Es idempotente: un archivo cuyo hash no cambió no se reescribe ni altera el manifiesto.

Uso:
    python -m src.extract              # extrae y registra lo que haya en data/raw/descarga/
    python -m src.extract --verificar  # solo comprueba lo ya extraído contra el manifiesto
"""

import argparse
import csv
import hashlib
import io
import sys
import zipfile
from datetime import datetime, timezone

from src import config

MANIFEST_FIELDS = [
    "clave", "archivo_portal", "url", "publicado_en", "bytes_portal", "archivo", "bytes", "sha256",
    "origen", "estado", "registrado_en",
]


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_inventory() -> dict:
    with config.PORTAL_INVENTORY.open(encoding="utf-8", newline="") as f:
        return {r["archivo_portal"]: r for r in csv.DictReader(f)}


def load_manifest() -> dict:
    if not config.MANIFEST.exists():
        return {}
    with config.MANIFEST.open(encoding="utf-8", newline="") as f:
        return {r["clave"]: r for r in csv.DictReader(f)}


def save_manifest(rows: dict) -> None:
    config.MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    order = [spec[0] for spec in config.SPEC]
    with config.MANIFEST.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows[k] for k in order if k in rows)


def read_member(zip_bytes: bytes, path: list[str]) -> bytes:
    """Lee un archivo del zip; si 'path' tiene dos elementos, el primero es un zip anidado."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        content = zf.read(path[0])
    return content if len(path) == 1 else read_member(content, path[1:])


def container_bytes(zip_bytes: bytes, path: list[str]) -> int:
    """Tamaño que el portal lista para el recurso: el del propio archivo, o el del zip anidado."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        return zf.getinfo(path[0]).file_size


def register(manifest: dict, inventory: dict) -> dict:
    counts = {"nuevo": 0, "sin_cambios": 0, "actualizado": 0, "distinto_al_inventario": 0}
    zips: dict[str, bytes] = {}
    for key, zip_name, path, portal_name, target in config.SPEC:
        zip_path = config.DOWNLOADS / zip_name
        if not zip_path.exists():
            raise FileNotFoundError(zip_path)
        zips.setdefault(zip_name, zip_path.read_bytes())
        content = read_member(zips[zip_name], path)
        digest = sha256(content)
        previous = manifest.get(key)
        if previous and previous["sha256"] == digest and target.exists():
            counts["sin_cambios"] += 1
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        listed = inventory.get(portal_name, {})
        portal_bytes = container_bytes(zips[zip_name], path)
        state = "ok" if listed.get("bytes") == str(portal_bytes) else "distinto_al_inventario"
        counts["actualizado" if previous else "nuevo"] += 1
        if state != "ok":
            counts["distinto_al_inventario"] += 1
            print(f"  ! {portal_name}: {portal_bytes} bytes; el inventario dice {listed.get('bytes', 'nada')}")
        manifest[key] = {
            "clave": key,
            "archivo_portal": portal_name,
            "url": config.FILE_URL.format(name=portal_name.replace(" ", "%20")),
            "publicado_en": listed.get("publicado_en", ""),
            "bytes_portal": portal_bytes,
            "archivo": target.relative_to(config.ROOT).as_posix(),
            "bytes": len(content),
            "sha256": digest,
            "origen": zip_name,
            "estado": state,
            "registrado_en": now(),
        }
    return counts


def verify(manifest: dict) -> list[str]:
    """Archivos que faltan, cuyo hash ya no coincide con el manifiesto o que no están registrados."""
    problems = []
    for key, *_ in config.SPEC:
        if key not in manifest:
            problems.append(f"{key}: no está en el manifiesto")
            continue
        path = config.ROOT / manifest[key]["archivo"]
        if not path.exists():
            problems.append(f"{key}: falta {manifest[key]['archivo']}")
        elif sha256(path.read_bytes()) != manifest[key]["sha256"]:
            problems.append(f"{key}: el contenido de {manifest[key]['archivo']} no coincide con el manifiesto")
    return problems


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--verificar", action="store_true", help="solo comprueba lo ya extraído")
    args = parser.parse_args()

    manifest = load_manifest()
    if not args.verificar:
        try:
            counts = register(manifest, load_inventory())
        except FileNotFoundError as missing:
            print(f"Falta {missing}.")
            print("Descarga desde el navegador el zip de cada conjunto y déjalo en data/raw/descarga/:")
            for key, url in config.DOWNLOAD_URLS.items():
                print(f"  {key}: {url}   (página: {config.DATASET_PAGES[key]})")
            return 1
        save_manifest(manifest)
        print(f"Archivos: {counts['nuevo']} nuevos, {counts['actualizado']} actualizados, "
              f"{counts['sin_cambios']} sin cambios, {counts['distinto_al_inventario']} distintos al inventario")
        print(f"Manifiesto: {config.MANIFEST.relative_to(config.ROOT)} ({len(manifest)} archivos)")

    problems = verify(manifest)
    for p in problems:
        print(f"  ✗ {p}")
    if problems:
        return 1
    print(f"Verificación: {len(manifest)} archivos completos y con el hash esperado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
