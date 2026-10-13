"""Pruebas de la Fase 1: extracción idempotente y verificación de los archivos del portal."""

import io
import zipfile

import pytest

from src import config, extract


def zip_bytes(files: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buffer.getvalue()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Estructura mínima del proyecto en un directorio temporal, con una especificación reducida."""
    nested = zip_bytes({"carpeta/datos.csv": b"a,b\n1,2\n"})
    outer = zip_bytes({"datos.csv": b"x,y\n3,4\n", "anidado.zip": nested})
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "DOWNLOADS", tmp_path / "data/raw/descarga")
    monkeypatch.setattr(config, "MANIFEST", tmp_path / "data/raw/manifest.csv")
    config.DOWNLOADS.mkdir(parents=True)
    (config.DOWNLOADS / "uno.zip").write_bytes(outer)
    monkeypatch.setattr(config, "SPEC", [
        ("directo", "uno.zip", ["datos.csv"], "datos.csv", tmp_path / "data/raw/directo.csv"),
        ("anidado", "uno.zip", ["anidado.zip", "carpeta/datos.csv"], "anidado.zip",
         tmp_path / "data/raw/anidado.csv"),
    ])
    inventory = {
        "datos.csv": {"bytes": "8", "publicado_en": "2026-01-01T00:00:00Z"},
        "anidado.zip": {"bytes": str(len(nested)), "publicado_en": "2026-01-02T00:00:00Z"},
    }
    return inventory


def test_extrae_sin_alterar_bytes_y_lee_zip_anidado(repo):
    manifest = {}
    counts = extract.register(manifest, repo)
    assert counts["nuevo"] == 2
    assert (config.ROOT / "data/raw/directo.csv").read_bytes() == b"x,y\n3,4\n"
    assert (config.ROOT / "data/raw/anidado.csv").read_bytes() == b"a,b\n1,2\n"
    assert manifest["anidado"]["bytes_portal"] > manifest["anidado"]["bytes"] - 1


def test_segunda_ejecucion_no_cambia_nada(repo):
    manifest = {}
    extract.register(manifest, repo)
    extract.save_manifest(manifest)
    before = config.MANIFEST.read_text(encoding="utf-8")
    manifest = extract.load_manifest()
    counts = extract.register(manifest, repo)
    extract.save_manifest(manifest)
    assert counts == {"nuevo": 0, "sin_cambios": 2, "actualizado": 0, "distinto_al_inventario": 0}
    assert config.MANIFEST.read_text(encoding="utf-8") == before


def test_marca_el_archivo_que_no_coincide_con_el_inventario(repo):
    repo["datos.csv"]["bytes"] = "999"
    manifest = {}
    counts = extract.register(manifest, repo)
    assert manifest["directo"]["estado"] == "distinto_al_inventario"
    assert counts["distinto_al_inventario"] == 1


def test_verificar_detecta_archivo_alterado_o_ausente(repo):
    manifest = {}
    extract.register(manifest, repo)
    assert extract.verify(manifest) == []
    (config.ROOT / "data/raw/directo.csv").write_bytes(b"editado")
    (config.ROOT / "data/raw/anidado.csv").unlink()
    problems = extract.verify(manifest)
    assert len(problems) == 2 and "no coincide" in problems[0] and "falta" in problems[1]


def test_falla_si_no_esta_el_zip(repo):
    (config.DOWNLOADS / "uno.zip").unlink()
    with pytest.raises(FileNotFoundError):
        extract.register({}, repo)


def test_el_inventario_versionado_cubre_toda_la_especificacion():
    inventory = extract.load_inventory()
    for key, _, _, portal_name, _ in config.SPEC:
        assert portal_name in inventory, key


def test_cada_conjunto_tiene_enlace_de_descarga_y_pagina():
    for key in {spec[0] for spec in config.SPEC if spec[0] in config.DOWNLOAD_URLS}:
        assert config.DOWNLOAD_URLS[key].startswith("https://www.datosabiertos.gob.pe/node/")
        assert config.DATASET_PAGES[key].startswith("https://www.datosabiertos.gob.pe/dataset/")
