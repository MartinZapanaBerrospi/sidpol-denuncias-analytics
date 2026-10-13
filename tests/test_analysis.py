"""Las cifras del análisis (Fase 5) salen del modelo curado y coinciden con las del tablero."""

import pandas as pd
import pytest

from src import config

ANALYSIS = config.REPORTS / "analisis"


@pytest.fixture(scope="module")
def key():
    table = pd.read_csv(ANALYSIS / "cifras_clave.csv")
    return dict(zip(table["cifra"], table["valor"]))


def number(key, name):
    return float(key[name])


def test_las_cifras_clave_estan_completas(key):
    assert len(key) >= 90
    for name in ["denuncias_total", "tasa_2025", "extorsion_veces", "dep_mayor_tasa", "alertas", "pandemia_caida_abril"]:
        assert name in key


def test_el_total_es_el_del_modelo_y_el_del_raw(key):
    assert number(key, "denuncias_total") == 7_359_931
    fact = pd.read_csv(config.CURATED / "fact_denuncia.csv")
    assert fact["cantidad"].sum() == number(key, "denuncias_total")


def test_las_variaciones_se_recalculan(key):
    assert number(key, "var_2023_2025") == pytest.approx(895_260 / 1_044_843 - 1)
    assert number(key, "extorsion_veces") == pytest.approx(26_730 / 3_072)
    assert number(key, "var_robo_2023_2025") == pytest.approx(57_200 / 141_708 - 1)


def test_la_tasa_por_departamento_coincide_con_la_medida_dax():
    dax = pd.read_csv(config.REPORTS / "validacion_medidas.csv")
    dax = dax[(dax["contexto"] == "anio_departamento") & (dax["medida"] == "Tasa por 100 mil (anual)")]
    dax = dax[dax["clave"].str.startswith("2025|")].assign(departamento=lambda t: t["clave"].str[5:])
    py = pd.read_csv(ANALYSIS / "p3_departamentos.csv").set_index("departamento")["tasa_por_100mil"]
    for row in dax.itertuples():
        assert py[row.departamento] == pytest.approx(float(row.python), rel=1e-9)
    assert len(dax) == 26


def test_las_alertas_son_las_del_modelo(key):
    alerts = pd.read_csv(ANALYSIS / "p4_alertas.csv")
    assert len(alerts) == number(key, "alertas") == 5
    assert (alerts["z"] >= 3).all()
    assert (alerts["veces"] > 1).all()


def test_la_estacionalidad_suma_cien_por_ciento():
    index = pd.read_csv(ANALYSIS / "p5_estacionalidad.csv")
    assert len(index) == 12
    assert index["total"].sum() == pytest.approx(1.0)


def test_la_pandemia_reduce_abril_de_2020(key):
    assert number(key, "pandemia_abril_2020") == 21_570
    assert number(key, "pandemia_caida_abril") < -0.65
