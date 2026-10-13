"""Los reportes versionados de la Fase 2 cumplen lo que dice la documentación."""

import pandas as pd
import pytest

from src import config


@pytest.fixture(scope="module")
def rules():
    return pd.read_csv(config.QUALITY / "reglas.csv")


@pytest.fixture(scope="module")
def checks():
    return pd.read_csv(config.REPORTS / "validaciones.csv")


def test_ninguna_regla_bloqueante_falla(rules):
    assert len(rules) == 40
    assert not (rules["resultado"] == "falla").any()
    assert set(rules["dimension"]) == {"Completitud", "Unicidad", "Validez", "Consistencia", "Exactitud", "Oportunidad"}


def test_v1_la_violencia_es_identica_en_ambos_archivos(checks):
    v1 = checks[checks["validacion"] == "V1"]
    assert len(v1) == 9 and (v1["diferencia_pct"] == 0).all()
    assert v1["calculado"].sum() == 2_149_178
    assert "0 distintas" in " ".join(v1["detalle"])


def test_v2_la_extorsion_esta_dentro_de_la_tolerancia(checks):
    v2 = checks[checks["validacion"] == "V2-7"]
    assert (v2["resultado"] == "cumple").all()
    assert v2["diferencia_pct"].between(-6, 0).all()


def test_v3_la_poblacion_cuadra_hasta_2025(checks):
    v3 = checks[checks["validacion"] == "V3"].set_index("anio")
    assert (v3.loc[:2025, "resultado"] == "cumple").all()
    assert v3.loc[2026, "resultado"] == "alerta"
    assert v3.loc[2018, "diferencia_pct"] == 0


def test_las_rupturas_incluyen_los_cambios_de_nivel_del_robo():
    breaks = pd.read_csv(config.QUALITY / "rupturas.csv")
    robo = breaks[breaks["modalidad"] == "Robo"].set_index("periodo")["variacion_pct"]
    assert robo["2024-04"] < -20 and robo["2024-11"] < -20 and robo["2022-12"] > 20
    assert len(breaks) == 19


def test_la_cobertura_de_poblacion_es_casi_total():
    coverage = pd.read_csv(config.QUALITY / "cobertura_poblacion.csv")
    assert (coverage["pct_denuncias_con_poblacion"] >= 99.9).all()
    assert coverage["denuncias"].sum() == 7_359_931
