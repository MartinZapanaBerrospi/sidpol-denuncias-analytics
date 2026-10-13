"""Fase 5 — Responde las preguntas P1–P5 con cifras, desde data/curated.

Escribe las tablas de soporte en reports/analisis/ y las cifras que citan el tablero y el README
en reports/analisis/cifras_clave.csv. Las definiciones son las del modelo de Power BI
(docs/04_modelado.md): las tasas se calculan como suma entre suma y el año incompleto se
anualiza con habitantes-año.

Uso:
    python -m src.analysis
"""

import sys

import numpy as np
import pandas as pd

from src import config

OUT = config.REPORTS / "analisis"
LAST_YEAR = config.END[0]
CUTOFF_MONTH = config.END[1]
LAST_FULL_YEAR = LAST_YEAR - 1
PANDEMIC_YEAR = 2020
MIN_POPULATION = 5000           # distritos que entran al ranking de tasas
BIG_DISTRICT = 20000            # distritos "grandes" para comparar sin ruido
BIG_MODALITIES = ["Violencia contra la mujer e integrantes", "Hurto", "Robo", "Estafa", "Extorsión"]
MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "setiembre",
             "octubre", "noviembre", "diciembre"]

KEY: dict[str, tuple] = {}      # cifra -> (valor, descripción)


def key(name: str, value, description: str) -> None:
    KEY[name] = (value, description)


def load() -> dict:
    read = lambda n: pd.read_csv(config.CURATED / f"{n}.csv", dtype={"ubigeo": str, "departamento_id": str})
    t = {n: read(n) for n in ["dim_distrito", "dim_modalidad", "dim_fecha", "fact_poblacion", "fact_alerta_distrito",
                              "fact_salto_serie", "fact_denuncia"]}
    den = t["fact_denuncia"].merge(t["dim_modalidad"][["modalidad_id", "modalidad"]], on="modalidad_id")
    den = den.merge(t["dim_distrito"][["ubigeo", "distrito_unico", "provincia", "departamento", "zona"]], on="ubigeo")
    den["anio"] = den["mes_inicio"].str[:4].astype(int)
    den["mes"] = den["mes_inicio"].str[5:7].astype(int)
    t["den"] = den
    t["months"] = t["dim_fecha"].groupby("anio").size().to_dict()
    t["pop"] = t["fact_poblacion"].merge(t["dim_distrito"][["ubigeo", "departamento", "distrito_unico", "provincia"]], on="ubigeo")
    return t


def rate(den: float, pop: float, months: int = 12) -> float:
    """Denuncias por 100 mil habitantes en un año; con menos de 12 meses se anualiza."""
    return den / (pop * months / 12) * 1e5 if pop else np.nan


def yearly_rate(t: dict, den: pd.DataFrame, by: str | None = None) -> pd.DataFrame:
    """Tasa anual por año (y por territorio si se pide), con población del mismo territorio."""
    pop_by = ["anio"] + ([by] if by else [])
    population = t["pop"].groupby(pop_by)["poblacion"].sum().rename("poblacion").reset_index()
    counts = den.groupby(pop_by)["cantidad"].sum().rename("denuncias").reset_index()
    out = counts.merge(population, on=pop_by, how="left")
    out["meses"] = out["anio"].map(t["months"])
    out["tasa"] = out.apply(lambda r: rate(r["denuncias"], r["poblacion"], r["meses"]), axis=1)
    return out


def pct(a: float, b: float) -> float:
    return a / b - 1


# ---------------------------------------------------------------------------------------------
# P1 y P2: evolución y modalidades
# ---------------------------------------------------------------------------------------------

def p1_p2(t: dict) -> None:
    den = t["den"]
    by_year = den.pivot_table(index="anio", columns="modalidad", values="cantidad", aggfunc="sum", fill_value=0)
    by_year["Total"] = by_year.sum(axis=1)
    jan_jul = den[den["mes"] <= CUTOFF_MONTH].pivot_table(index="anio", columns="modalidad", values="cantidad",
                                                           aggfunc="sum", fill_value=0)
    jan_jul["Total"] = jan_jul.sum(axis=1)
    rates = yearly_rate(t, den).set_index("anio")

    table = by_year.stack().rename("denuncias").reset_index().rename(columns={"level_1": "modalidad"})
    table = table.merge(jan_jul.stack().rename("denuncias_ene_jul").reset_index().rename(columns={"level_1": "modalidad"}),
                        on=["anio", "modalidad"])
    table["tasa_total_por_100mil"] = table["anio"].map(rates["tasa"]).where(table["modalidad"] == "Total")
    table.to_csv(OUT / "p1_evolucion_anual.csv", index=False)

    total = by_year["Total"]
    key("denuncias_total", int(total.sum()), "Denuncias de enero de 2018 a julio de 2026")
    key("denuncias_2018", int(total[2018]), "Denuncias en 2018")
    key("denuncias_2023", int(total[2023]), "Denuncias en 2023, el máximo anual")
    key("denuncias_2025", int(total[2025]), "Denuncias en 2025")
    key("var_2023_2025", pct(total[2025], total[2023]), "Cambio de las denuncias entre 2023 y 2025")
    key("var_2018_2025", pct(total[2025], total[2018]), "Cambio de las denuncias entre 2018 y 2025")
    key("denuncias_ene_jul_2025", int(jan_jul["Total"][2025]), "Denuncias de enero a julio de 2025")
    key("denuncias_ene_jul_2026", int(jan_jul["Total"][LAST_YEAR]), "Denuncias de enero a julio de 2026")
    key("var_ene_jul_2026", pct(jan_jul["Total"][LAST_YEAR], jan_jul["Total"][2025]),
        "Cambio de enero–julio de 2026 frente a enero–julio de 2025")
    key("var_ene_jul_2026_2018", pct(jan_jul["Total"][LAST_YEAR], jan_jul["Total"][2018]),
        "Cambio de enero–julio de 2026 frente a enero–julio de 2018")
    key("tasa_2018", rates.loc[2018, "tasa"], "Denuncias por 100 mil habitantes, 2018")
    key("tasa_2023", rates.loc[2023, "tasa"], "Denuncias por 100 mil habitantes, 2023")
    key("tasa_2025", rates.loc[2025, "tasa"], "Denuncias por 100 mil habitantes, 2025")
    key("tasa_2026", rates.loc[LAST_YEAR, "tasa"], "Denuncias por 100 mil habitantes, 2026 (anualizada)")
    share = by_year.drop(columns="Total").sum()
    share = share / share.sum()
    key("pct_otros", share["Otros"], "Parte de las denuncias que cae en la modalidad Otros")
    key("pct_violencia", share["Violencia contra la mujer e integrantes"], "Parte de violencia contra la mujer")
    key("pct_hurto", share["Hurto"], "Parte de hurto")

    # P2: modalidades
    rows = []
    for m in [c for c in by_year.columns if c != "Total"]:
        y18, y23, y25 = by_year.loc[2018, m], by_year.loc[2023, m], by_year.loc[2025, m]
        a25, a26 = jan_jul.loc[2025, m], jan_jul.loc[LAST_YEAR, m]
        jumps = int((t["fact_salto_serie"]["modalidad_id"] ==
                     t["dim_modalidad"].set_index("modalidad").loc[m, "modalidad_id"]).sum())
        rows.append({"modalidad": m, "denuncias_2018": y18, "denuncias_2023": y23, "denuncias_2025": y25,
                     "var_2018_2025": pct(y25, y18), "var_2023_2025": pct(y25, y23),
                     "ene_jul_2025": a25, "ene_jul_2026": a26, "var_ene_jul_2026": pct(a26, a25),
                     "saltos_de_serie": jumps})
    mod = pd.DataFrame(rows).sort_values("denuncias_2025", ascending=False)
    mod.to_csv(OUT / "p2_modalidades.csv", index=False)
    m = mod.set_index("modalidad")
    key("extorsion_2018", int(m.loc["Extorsión", "denuncias_2018"]), "Denuncias de extorsión en 2018")
    key("extorsion_2025", int(m.loc["Extorsión", "denuncias_2025"]), "Denuncias de extorsión en 2025")
    key("extorsion_veces", m.loc["Extorsión", "denuncias_2025"] / m.loc["Extorsión", "denuncias_2018"],
        "Veces que se multiplicó la extorsión entre 2018 y 2025")
    key("var_extorsion_ene_jul_2026", m.loc["Extorsión", "var_ene_jul_2026"], "Extorsión, enero–julio 2026 frente a 2025")
    key("robo_2023", int(m.loc["Robo", "denuncias_2023"]), "Denuncias de robo en 2023, su máximo")
    key("robo_2025", int(m.loc["Robo", "denuncias_2025"]), "Denuncias de robo en 2025")
    key("var_robo_2023_2025", m.loc["Robo", "var_2023_2025"], "Cambio del robo entre 2023 y 2025")
    key("saltos_robo", int(m.loc["Robo", "saltos_de_serie"]), "Saltos de serie del robo")
    key("estafa_2018", int(m.loc["Estafa", "denuncias_2018"]), "Denuncias de estafa en 2018")
    key("estafa_2025", int(m.loc["Estafa", "denuncias_2025"]), "Denuncias de estafa en 2025")
    key("estafa_veces", m.loc["Estafa", "denuncias_2025"] / m.loc["Estafa", "denuncias_2018"], "Veces que se multiplicó la estafa")
    key("var_violencia_2018_2025", m.loc["Violencia contra la mujer e integrantes", "var_2018_2025"],
        "Cambio de la violencia contra la mujer entre 2018 y 2025")
    key("var_hurto_2023_2025", m.loc["Hurto", "var_2023_2025"], "Cambio del hurto entre 2023 y 2025")
    key("saltos_total", int(mod["saltos_de_serie"].sum()), "Saltos de serie detectados")

    # Contribución de cada modalidad al cambio 2023 → 2025
    contribution = (by_year.loc[2025] - by_year.loc[2023]).drop("Total")
    contribution = (contribution / (by_year.loc[2025, "Total"] - by_year.loc[2023, "Total"])).rename("aporte_al_cambio")
    contribution.reset_index().rename(columns={"index": "modalidad"}).to_csv(OUT / "p2_aporte_cambio_2023_2025.csv", index=False)
    key("aporte_robo_cambio_2023_2025", contribution["Robo"], "Parte de la caída 2023–2025 que explica el robo")

    # Cobertura del sistema (limitación)
    coverage = den.groupby("anio")["ubigeo"].nunique().rename("distritos_con_denuncias").reset_index()
    coverage["distritos_total"] = t["dim_distrito"].shape[0]
    coverage.to_csv(OUT / "p1_cobertura.csv", index=False)
    key("distritos_con_denuncias_2018", int(coverage.loc[coverage["anio"] == 2018, "distritos_con_denuncias"].iloc[0]),
        "Distritos con alguna denuncia en 2018")
    key("distritos_con_denuncias_2025", int(coverage.loc[coverage["anio"] == 2025, "distritos_con_denuncias"].iloc[0]),
        "Distritos con alguna denuncia en 2025")


# ---------------------------------------------------------------------------------------------
# P3: territorio
# ---------------------------------------------------------------------------------------------

def p3(t: dict) -> None:
    den, pop = t["den"], t["pop"]
    year = LAST_FULL_YEAR
    nat = rate(den.loc[den["anio"] == year, "cantidad"].sum(), pop.loc[pop["anio"] == year, "poblacion"].sum())

    dep = yearly_rate(t, den[den["anio"].isin([2018, year])], by="departamento")
    wide = dep.pivot(index="departamento", columns="anio", values=["denuncias", "poblacion", "tasa"])
    table = pd.DataFrame({
        "denuncias": wide[("denuncias", year)], "poblacion": wide[("poblacion", year)],
        "tasa_por_100mil": wide[("tasa", year)], "tasa_2018": wide[("tasa", 2018)],
    })
    table["veces_tasa_nacional"] = table["tasa_por_100mil"] / nat
    table["cambio_tasa_2018"] = table["tasa_por_100mil"] / table["tasa_2018"] - 1
    table["participacion_denuncias"] = table["denuncias"] / table["denuncias"].sum()
    table["participacion_poblacion"] = table["poblacion"] / table["poblacion"].sum()
    table = table.sort_values("tasa_por_100mil", ascending=False)
    table.reset_index().to_csv(OUT / "p3_departamentos.csv", index=False)

    key("tasa_nacional_2025", nat, "Tasa nacional por 100 mil habitantes en 2025")
    key("dep_mayor_tasa", table.index[0], "Departamento con mayor tasa en 2025")
    key("dep_mayor_tasa_valor", table.iloc[0]["tasa_por_100mil"], "Tasa del departamento con mayor tasa en 2025")
    key("dep_mayor_tasa_veces", table.iloc[0]["veces_tasa_nacional"], "Veces la tasa nacional del departamento líder")
    key("dep_2", table.index[1], "Segundo departamento por tasa")
    key("dep_2_valor", table.iloc[1]["tasa_por_100mil"], "Tasa del segundo departamento")
    key("dep_3", table.index[2], "Tercer departamento por tasa")
    key("dep_menor_tasa", table.index[-1], "Departamento con menor tasa en 2025")
    key("dep_menor_tasa_valor", table.iloc[-1]["tasa_por_100mil"], "Tasa del departamento con menor tasa en 2025")
    key("lima_met_tasa", table.loc["Lima Metropolitana", "tasa_por_100mil"], "Tasa de Lima Metropolitana en 2025")
    key("lima_met_veces", table.loc["Lima Metropolitana", "veces_tasa_nacional"], "Lima Metropolitana, veces la tasa nacional")
    key("lima_met_pct_denuncias", table.loc["Lima Metropolitana", "participacion_denuncias"],
        "Parte de las denuncias de 2025 que registra Lima Metropolitana")
    key("lima_met_pct_poblacion", table.loc["Lima Metropolitana", "participacion_poblacion"],
        "Parte de la población que vive en Lima Metropolitana")
    key("deps_sobre_nacional", int((table["veces_tasa_nacional"] > 1).sum()), "Departamentos con tasa sobre la nacional")
    key("n_departamentos", len(table), "Departamentos (Lima partida en dos)")
    low = table.nsmallest(5, "tasa_2018")
    key("convergencia_spearman", table["tasa_2018"].corr(table["cambio_tasa_2018"], method="spearman"),
        "Correlación de rangos entre la tasa de 2018 y su cambio hasta 2025: negativa = los más bajos suben más")
    key("convergencia_5_bajos_cambio", (low["tasa_por_100mil"].sum() / low["tasa_2018"].sum()) - 1,
        "Cambio de la tasa conjunta de los 5 departamentos con menor tasa en 2018")
    key("convergencia_5_bajos", ", ".join(low.index), "Los 5 departamentos con menor tasa en 2018")
    key("ratio_max_min_dep", table.iloc[0]["tasa_por_100mil"] / table.iloc[-1]["tasa_por_100mil"],
        "Veces entre el departamento con mayor y con menor tasa")

    # Provincias y distritos
    dist_den = den[den["anio"] == year].groupby("ubigeo")["cantidad"].sum()
    d = pop[pop["anio"] == year].set_index("ubigeo").copy()
    d["denuncias"] = dist_den.reindex(d.index).fillna(0)
    d["tasa_por_100mil"] = d["denuncias"] / d["poblacion"] * 1e5
    ranking = d[d["poblacion"] >= MIN_POPULATION].sort_values("tasa_por_100mil", ascending=False)
    ranking["veces_tasa_nacional"] = ranking["tasa_por_100mil"] / nat
    ranking.reset_index()[["ubigeo", "distrito_unico", "provincia", "departamento", "poblacion", "denuncias",
                           "tasa_por_100mil", "veces_tasa_nacional"]].to_csv(OUT / "p3_distritos_tasa.csv", index=False)
    big = ranking[ranking["poblacion"] >= BIG_DISTRICT]
    key("distritos_en_ranking", len(ranking), f"Distritos de {MIN_POPULATION} habitantes o más")
    key("distrito_mayor_tasa", big.iloc[0]["distrito_unico"], "Distrito grande (20 mil o más) con mayor tasa en 2025")
    key("distrito_mayor_tasa_valor", big.iloc[0]["tasa_por_100mil"], "Su tasa")
    key("distrito_mayor_tasa_dep", big.iloc[0]["departamento"], "Su departamento")
    key("distrito_menor_tasa_valor", big.iloc[-1]["tasa_por_100mil"], "Tasa más baja entre los distritos grandes")

    # Concentración por año
    rows = []
    for y in sorted(den["anio"].unique()):
        s = den[den["anio"] == y].groupby("ubigeo")["cantidad"].sum().sort_values(ascending=False)
        rows.append({"anio": y, "denuncias": s.sum(), "distritos_con_denuncias": len(s),
                     "participacion_top10": s.head(10).sum() / s.sum(),
                     "distritos_para_50pct": int((s.cumsum() / s.sum() < 0.5).sum() + 1)})
    conc = pd.DataFrame(rows)
    conc.to_csv(OUT / "p3_concentracion.csv", index=False)
    c = conc.set_index("anio")
    key("top10_participacion_2025", c.loc[year, "participacion_top10"], "Parte de las denuncias de 2025 en los 10 distritos con más")
    key("top10_participacion_2018", c.loc[2018, "participacion_top10"], "Lo mismo en 2018")
    key("distritos_para_50pct_2025", int(c.loc[year, "distritos_para_50pct"]), "Distritos que suman la mitad de las denuncias de 2025")
    key("distritos_con_denuncias_total", int(c.loc[year, "distritos_con_denuncias"]), "Distritos con denuncias en 2025")
    top = den[den["anio"] == year].groupby("distrito_unico")["cantidad"].sum().sort_values(ascending=False)
    key("distrito_lider", top.index[0], "Distrito con más denuncias en 2025")
    key("distrito_lider_denuncias", int(top.iloc[0]), "Sus denuncias")
    key("distrito_2", top.index[1], "Segundo distrito con más denuncias en 2025")
    key("distrito_2_denuncias", int(top.iloc[1]), "Sus denuncias")

    # Extorsión por departamento (donde más se concentra)
    ext = den[(den["modalidad"] == "Extorsión") & (den["anio"] == year)].groupby("departamento")["cantidad"].sum()
    ext_rate = (ext / pop[pop["anio"] == year].groupby("departamento")["poblacion"].sum() * 1e5).sort_values(ascending=False)
    ext_table = pd.DataFrame({"denuncias": ext, "tasa_por_100mil": ext_rate}).sort_values("tasa_por_100mil", ascending=False)
    ext_table.reset_index().to_csv(OUT / "p3_extorsion_departamentos.csv", index=False)
    key("extorsion_dep_1", ext_table.index[0], "Departamento con mayor tasa de extorsión en 2025")
    key("extorsion_dep_1_valor", ext_table.iloc[0]["tasa_por_100mil"], "Su tasa de extorsión")
    key("extorsion_dep_2", ext_table.index[1], "Segundo departamento por tasa de extorsión")
    key("extorsion_dep_2_valor", ext_table.iloc[1]["tasa_por_100mil"], "Su tasa de extorsión")
    key("extorsion_lima_met_pct", ext["Lima Metropolitana"] / ext.sum(), "Parte de las denuncias de extorsión de 2025 en Lima Metropolitana")


# ---------------------------------------------------------------------------------------------
# P4: alertas
# ---------------------------------------------------------------------------------------------

def level_shift(series: pd.Series, window: int = 6) -> dict:
    """Mes en que el nivel mensual cambia más: cociente entre la media de los 6 meses siguientes y los 6 anteriores."""
    values = series.to_numpy(dtype=float)
    best = None
    for i in range(window, len(values) - window + 1):
        before, after = values[i - window:i].mean(), values[i:i + window].mean()
        if before > 0 and (best is None or after / before > best[0]):
            best = (after / before, i, before, after)
    ratio, i, before, after = best
    return {"mes_del_cambio": series.index[i], "promedio_antes": before, "promedio_despues": after, "veces": ratio}


def p4(t: dict) -> None:
    den, alerts = t["den"], t["fact_alerta_distrito"]
    flagged = alerts[alerts["en_alerta"] == 1].merge(t["dim_distrito"], on="ubigeo").merge(t["dim_modalidad"], on="modalidad_id")
    months = t["dim_fecha"]["mes_inicio"].tolist()[-36:]
    rows = []
    for r in flagged.itertuples():
        s = den[(den["ubigeo"] == r.ubigeo) & (den["modalidad_id"] == r.modalidad_id)].groupby("mes_inicio")["cantidad"].sum()
        s = s.reindex(months, fill_value=0)
        shift = level_shift(s)
        rows.append({"distrito": r.distrito_unico, "departamento": r.departamento, "modalidad": r.modalidad,
                     "denuncias_12m_previos": r.denuncias_12m_previos, "denuncias_ultimos_12m": r.denuncias_ultimos_12m,
                     "variacion_pct": r.variacion_pct, "variacion_nacional_pct": r.variacion_nacional_pct, "z": r.z,
                     **shift})
    table = pd.DataFrame(rows).sort_values("z", ascending=False)
    table.to_csv(OUT / "p4_alertas.csv", index=False)
    key("alertas", len(table), "Combinaciones distrito–modalidad en alerta")
    key("alertas_evaluadas", len(alerts), "Combinaciones evaluadas")
    key("alertas_distritos", int(table["distrito"].nunique()), "Distritos distintos en alerta")
    key("alertas_con_salto_de_nivel", int((table["veces"] >= 1.8).sum()),
        "Alertas cuyo aumento es un salto de nivel de 1,8 veces o más entre dos semestres")
    top = table.iloc[0]
    sa = table[table["distrito"] == "Santa Anita"].iloc[0]
    key("santa_anita_hurto_previos", int(sa["denuncias_12m_previos"]), "Hurto en Santa Anita, 12 meses previos")
    key("santa_anita_hurto_ultimos", int(sa["denuncias_ultimos_12m"]), "Hurto en Santa Anita, últimos 12 meses")
    key("santa_anita_mes_cambio", sa["mes_del_cambio"], "Mes en que cambia el nivel del hurto en Santa Anita")
    key("santa_anita_antes", sa["promedio_antes"], "Promedio mensual de hurto antes del cambio")
    key("santa_anita_despues", sa["promedio_despues"], "Promedio mensual de hurto después del cambio")
    key("alerta_z_max", top["z"], "Puntaje z más alto")
    key("alerta_z_max_distrito", top["distrito"], "Distrito con el puntaje z más alto")


# ---------------------------------------------------------------------------------------------
# P5: calendario y pandemia
# ---------------------------------------------------------------------------------------------

def p5(t: dict) -> None:
    den = t["den"]
    full = den[(den["anio"] <= LAST_FULL_YEAR) & (den["anio"] != PANDEMIC_YEAR)]

    def seasonal(frame: pd.DataFrame) -> pd.Series:
        s = frame.groupby(["anio", "mes"])["cantidad"].sum()
        return (s / s.groupby(level=0).transform("sum")).groupby(level=1).mean()

    index = pd.DataFrame({"mes": range(1, 13), "mes_nombre": MONTHS_ES, "total": seasonal(full).to_numpy()})
    for m in BIG_MODALITIES:
        index[m] = seasonal(full[full["modalidad"] == m]).to_numpy()
    index.to_csv(OUT / "p5_estacionalidad.csv", index=False)
    key("estacional_mes_max", MONTHS_ES[int(index["total"].idxmax())], "Mes con mayor parte de las denuncias del año")
    key("estacional_max", index["total"].max(), "Parte del año en el mes con más denuncias")
    key("estacional_mes_min", MONTHS_ES[int(index["total"].idxmin())], "Mes con menor parte")
    key("estacional_min", index["total"].min(), "Parte del año en el mes con menos denuncias")
    key("estacional_parejo", 1 / 12, "Parte de cada mes si el año fuera parejo")
    key("estacional_rango_pp", (index["total"].max() - index["total"].min()) * 100, "Distancia entre el mes más alto y el más bajo, en puntos porcentuales")

    # Pandemia
    monthly = den.groupby(["anio", "mes"])["cantidad"].sum().unstack()
    covid = pd.DataFrame({"mes": range(1, 13), "mes_nombre": MONTHS_ES, "denuncias_2019": monthly.loc[2019].to_numpy(),
                          "denuncias_2020": monthly.loc[2020].to_numpy(), "denuncias_2021": monthly.loc[2021].to_numpy()})
    covid["var_2020_vs_2019"] = covid["denuncias_2020"] / covid["denuncias_2019"] - 1
    covid.to_csv(OUT / "p5_pandemia.csv", index=False)
    key("pandemia_abril_2020", int(monthly.loc[2020, 4]), "Denuncias de abril de 2020")
    key("pandemia_abril_2019", int(monthly.loc[2019, 4]), "Denuncias de abril de 2019")
    key("pandemia_caida_abril", monthly.loc[2020, 4] / monthly.loc[2019, 4] - 1, "Cambio de abril de 2020 frente a abril de 2019")
    key("pandemia_2020_vs_2019", den.loc[den["anio"] == 2020, "cantidad"].sum() / den.loc[den["anio"] == 2019, "cantidad"].sum() - 1,
        "Cambio de las denuncias de 2020 frente a 2019")
    key("pandemia_dic_vs_dic", monthly.loc[2020, 12] / monthly.loc[2019, 12] - 1, "Diciembre de 2020 frente a diciembre de 2019")
    key("recuperacion_2022_vs_2019", den.loc[den["anio"] == 2022, "cantidad"].sum() / den.loc[den["anio"] == 2019, "cantidad"].sum() - 1,
        "Las denuncias de 2022 frente a las de 2019")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    t = load()
    p1_p2(t)
    p3(t)
    p4(t)
    p5(t)
    table = pd.DataFrame([(k, v[0], v[1]) for k, v in KEY.items()], columns=["cifra", "valor", "descripcion"])
    table.to_csv(OUT / "cifras_clave.csv", index=False)
    print(f"{len(table)} cifras clave y {len(list(OUT.glob('*.csv'))) - 1} tablas en {OUT.relative_to(config.ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
