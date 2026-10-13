"""El modelo curado versionado cumple las reglas de la Fase 3."""

import pandas as pd
import pytest

from src import config

TABLES = ["fact_denuncia", "fact_poblacion", "fact_alerta_distrito", "fact_salto_serie",
          "dim_distrito", "dim_modalidad", "dim_fecha", "dim_anio"]


@pytest.fixture(scope="module")
def t():
    return {name: pd.read_csv(config.CURATED / f"{name}.csv", dtype={"ubigeo": str, "departamento_id": str}) for name in TABLES}


def test_las_claves_no_se_repiten(t):
    assert not t["fact_denuncia"].duplicated(["mes_inicio", "ubigeo", "modalidad_id"]).any()
    assert not t["fact_poblacion"].duplicated(["ubigeo", "anio"]).any()
    assert not t["dim_distrito"].duplicated("ubigeo").any()
    assert not t["dim_distrito"].duplicated("distrito_unico").any()


def test_toda_clave_foranea_existe(t):
    assert t["fact_denuncia"]["ubigeo"].isin(t["dim_distrito"]["ubigeo"]).all()
    assert t["fact_denuncia"]["modalidad_id"].isin(t["dim_modalidad"]["modalidad_id"]).all()
    assert t["fact_denuncia"]["mes_inicio"].isin(t["dim_fecha"]["mes_inicio"]).all()
    assert t["fact_poblacion"]["ubigeo"].isin(t["dim_distrito"]["ubigeo"]).all()
    assert t["fact_alerta_distrito"]["ubigeo"].isin(t["dim_distrito"]["ubigeo"]).all()


def test_el_ubigeo_tiene_seis_digitos(t):
    assert (t["dim_distrito"]["ubigeo"].str.len() == 6).all()
    assert (t["fact_denuncia"]["ubigeo"].str.len() == 6).all()


def test_el_linaje_no_pierde_denuncias():
    trail = pd.read_csv(config.REPORTS / "linaje.csv")
    assert trail["denuncias"].iloc[:3].nunique() == 1
    assert trail["denuncias"].iloc[0] == 7_359_931
    assert trail["filas"].iloc[0] - trail["filas"].iloc[2] == 1      # la clave repetida del problema 2


def test_la_suma_del_hecho_es_la_del_raw(t):
    assert t["fact_denuncia"]["cantidad"].sum() == 7_359_931


def test_lima_esta_partida_en_dos(t):
    ids = set(t["dim_distrito"]["departamento_id"])
    assert {"1501", "1599"} <= ids and "15" not in ids


def test_la_poblacion_ajustada_cuadra_con_la_oficial():
    check = pd.read_csv(config.REPORTS / "validacion_poblacion.csv")
    assert len(check) == 26 * 9
    assert check["diferencia_pct"].max() <= 0.1                  # nunca supera la cifra oficial
    assert check["diferencia_pct"].min() > -5                    # la brecha son distritos sin denuncias
    assert (check.loc[check["departamento"] == "Lima Metropolitana", "diferencia_pct"].abs() < 0.1).all()


def test_la_poblacion_conserva_el_total_provincial(t):
    pop = t["fact_poblacion"]
    assert (pop["poblacion"] > 0).all()
    assert set(pop["poblacion_ajustada"]) <= {0, 1} and set(pop["poblacion_imputada"]) <= {0, 1}
    # sin ajuste hasta 2019: la fuente ya cuadraba
    assert pop.loc[pop["anio"] <= 2019, "poblacion_ajustada"].sum() == 0
    # casi todo distrito ajustado cambia (en los más chicos el redondeo puede dejarlo igual)
    adjusted = pop[pop["poblacion_ajustada"] == 1]
    assert len(adjusted) > 0 and (adjusted["poblacion"] != adjusted["poblacion_fuente"]).mean() > 0.9


def test_las_alertas_son_pocas_y_estan_ordenadas(t):
    alerts = t["fact_alerta_distrito"]
    assert 0 < alerts["en_alerta"].sum() < 20
    flagged = alerts[alerts["en_alerta"] == 1]
    assert (flagged["z"] >= 3).all()
    assert ((flagged["denuncias_ultimos_12m"] - flagged["denuncias_12m_previos"]) >= 20).all()
    assert (alerts["denuncias_12m_previos"] >= 30).all()


def test_las_rupturas_son_las_documentadas(t):
    assert len(t["fact_salto_serie"]) == 19


def test_el_calendario_cubre_el_periodo(t):
    f = t["dim_fecha"]
    assert len(f) == 103 and f["mes_inicio"].iloc[0] == "2018-01-01" and f["mes_inicio"].iloc[-1] == "2026-07-01"
    assert f["es_pandemia"].sum() == 10
