"""Pruebas de lectura, limpieza y validación con recortes reales de los archivos."""

from pathlib import Path

import pandas as pd
import pytest

from src import config, parse, validate

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def raw(tmp_path, monkeypatch):
    """Carpeta raw temporal con los recortes de los tres archivos, con los nombres que espera parse.py."""
    monkeypatch.setattr(config, "RAW", tmp_path)
    for fixture, name in [("denuncias", "denuncias.csv"), ("violencia", "violencia_mujer.csv"),
                          ("indicadores", "indicadores.csv")]:
        (tmp_path / name).write_bytes((FIXTURES / f"{fixture}_recorte.csv").read_bytes())
    return tmp_path


def test_agrega_el_cero_inicial_al_ubigeo(raw):
    den = parse.read_denuncias()
    assert den["ubigeo"].str.fullmatch(r"\d{6}").all()
    row = den[den["distrito"] == "ARAMANGO"].iloc[0]
    assert row["ubigeo_original"] == "10202" and row["ubigeo"] == "010202" and row["ubigeo_con_cero_agregado"]
    assert not den[den["distrito"] == "ASIA"].iloc[0]["ubigeo_con_cero_agregado"]


def test_las_tildes_se_leen_en_utf_8(raw):
    den = parse.read_denuncias()
    assert "Extorsión" in set(den["modalidad"]) and "CAÑETE" in set(den["provincia"])
    assert set(den["modalidad"]) <= config.VALID_MODALITIES


def test_lima_se_reparte_en_dos_departamentos(raw):
    den = parse.read_denuncias().set_index("distrito")
    assert den.loc["LIMA", "departamento_id"] == "1501"
    assert den.loc["ASIA", "departamento_id"] == "1599"
    assert den.loc["BELLAVISTA", "departamento_id"] == "7"      # Callao
    assert den.loc["ARAMANGO", "departamento_id"].iloc[0] == "1"  # Amazonas, sin cero inicial


def test_un_ubigeo_con_dos_nombres_produce_clave_repetida(raw):
    den = parse.read_denuncias()
    putumayo = den[den["ubigeo"] == "160801"]
    assert len(putumayo) == 2 and putumayo["provincia"].nunique() == 2
    key = ["anio", "mes", "ubigeo", "modalidad"]
    assert den.duplicated(key, keep=False).sum() == 2


def test_el_archivo_de_violencia_tiene_bom_y_otro_formato(raw):
    assert (raw / "violencia_mujer.csv").read_bytes()[:3] == b"\xef\xbb\xbf"
    vio = parse.read_violencia()
    assert {"anio", "mes", "ubigeo", "cantidad", "departamento_fuente"} <= set(vio.columns)
    assert (vio["modalidad"] == parse.MODALIDAD_VIOLENCIA).all()


def test_v1_la_violencia_coincide_celda_por_celda(raw):
    den, vio = parse.read_denuncias(), parse.read_violencia()
    result = validate.v1_violencia(den, vio)
    assert (result["oficial"] == result["calculado"]).all()


def test_v1_detecta_una_celda_alterada(raw):
    den, vio = parse.read_denuncias(), parse.read_violencia()
    vio.loc[vio.index[0], "cantidad"] += 5
    result = validate.finish(validate.v1_violencia(den, vio))
    assert (result["resultado"] == "falla").any()


def test_la_poblacion_no_se_suma_por_indicador(raw):
    ind = parse.read_indicadores()
    pop = parse.population(ind)
    aramango = pop["distrito"].query("ubigeo == '010202' and anio == 2018")
    assert len(aramango) == 1 and aramango["poblacion"].item() == 10422     # tres indicadores, una población
    assert len(pop["nacional"].query("anio == 2018")) == 1


def test_el_departamento_de_indicadores_usa_las_mismas_claves(raw):
    pop = parse.population(parse.read_indicadores())
    assert {"1501", "1599", "7"} <= set(pop["departamento"]["ubigeo_original"])


def test_normaliza_espacios_en_los_nombres():
    df = pd.DataFrame({"departamento_fuente": [" LIMA "], "provincia": ["LIMA "], "distrito": [" X"],
                       "ubigeo_original": ["10101"], "anio": [2020], "mes": [1], "modalidad": ["Hurto"], "cantidad": [1]})
    out = parse.finish(df)
    assert out["distrito"].iloc[0] == "X" and out["ubigeo"].iloc[0] == "010101"
