"""Exactitud: compara el archivo principal con otras cifras oficiales de la misma institución.

V1  Violencia contra la mujer: el archivo principal frente al archivo de violencia, celda por celda.
V2  Indicadores oficiales SIDPOL (extorsión, patrimonio, secuestro) frente a las sumas del archivo
    principal. Solo la extorsión tiene tolerancia; los otros dos se miden y se explican.
V3  Población: la suma de los distritos frente a la población nacional oficial.
"""

import sys

import numpy as np
import pandas as pd

from src import config, parse

EXTORTION_TOLERANCE_PCT = 6.0
POPULATION_TOLERANCE_PCT = 1.0
FULL_YEARS_END = 2025        # 2026 llega a julio y su población distrital está incompleta


def v1_violencia(den: pd.DataFrame, vio: pd.DataFrame) -> pd.DataFrame:
    main = den[den["modalidad"] == parse.MODALIDAD_VIOLENCIA]
    key = ["anio", "mes", "ubigeo"]
    a = main.groupby(key)["cantidad"].sum().rename("principal")
    b = vio.groupby(key)["cantidad"].sum().rename("violencia")
    both = pd.concat([a, b], axis=1)
    both["distinta"] = both["principal"].fillna(-1) != both["violencia"].fillna(-1)
    by_year = both.reset_index().groupby("anio").agg(
        oficial=("violencia", "sum"), calculado=("principal", "sum"), celdas=("distinta", "size"),
        celdas_distintas=("distinta", "sum"))
    rows = []
    for year, r in by_year.iterrows():
        rows.append(("V1", year, "denuncias de violencia contra la mujer", r["oficial"], r["calculado"], 0.0,
                     "bloqueante", f"{int(r['celdas'])} celdas año-mes-distrito; {int(r['celdas_distintas'])} distintas"))
    return pd.DataFrame(rows, columns=COLUMNS)


def v2_indicador(den: pd.DataFrame, ind: pd.DataFrame) -> pd.DataFrame:
    official = ind[(ind["fuente"] == "SIDPOL") & (ind["ambito"] == 0)]
    spec = [
        (parse.INDICATOR_EXTORTION, ["Extorsión"], "extorsión", EXTORTION_TOLERANCE_PCT, "bloqueante"),
        (parse.INDICATOR_PATRIMONY, ["Hurto", "Robo"], "delitos contra el patrimonio (hurto + robo)", None, "info"),
        (parse.INDICATOR_KIDNAPPING, ["Secuestro"], "secuestro", None, "info"),
    ]
    rows = []
    for code, modalities, label, tolerance, severity in spec:
        off = official[official["indicador"] == code].set_index("anio")["VALORES"]
        mine = den[den["modalidad"].isin(modalities)].groupby("anio")["cantidad"].sum()
        for year in sorted(set(off.index) & set(mine.index)):
            rows.append((f"V2-{code}", year, f"denuncias de {label}", float(off[year]), float(mine[year]),
                         tolerance, severity, f"indicador oficial {code} del Plan de Acción de Seguridad Ciudadana"))
    return pd.DataFrame(rows, columns=COLUMNS)


def v3_poblacion(pop: dict) -> pd.DataFrame:
    national = pop["nacional"].set_index("anio")["poblacion"]
    districts = pop["distrito"].groupby("anio")["poblacion"].sum()
    count = pop["distrito"].groupby("anio")["ubigeo"].nunique()
    rows = []
    for year in range(config.START[0], config.END[0] + 1):
        severity = "bloqueante" if year <= FULL_YEARS_END else "alerta"
        rows.append(("V3", year, "población de los distritos", float(national[year]), float(districts[year]),
                     POPULATION_TOLERANCE_PCT, severity, f"{int(count[year])} distritos con población"))
    return pd.DataFrame(rows, columns=COLUMNS)


COLUMNS = ["validacion", "anio", "medida", "oficial", "calculado", "tolerancia_pct", "severidad", "detalle"]


def finish(table: pd.DataFrame) -> pd.DataFrame:
    table = table.copy()
    table["diferencia_pct"] = (100 * (table["calculado"] / table["oficial"] - 1)).round(3)
    within = table["diferencia_pct"].abs().le(table["tolerancia_pct"].fillna(np.inf))
    table["resultado"] = np.where(table["tolerancia_pct"].isna(), "info",
                                  np.where(within, "cumple", np.where(table["severidad"] == "alerta", "alerta", "falla")))
    return table


def compare_all(den: pd.DataFrame, vio: pd.DataFrame, ind: pd.DataFrame, pop: dict) -> pd.DataFrame:
    return finish(pd.concat([v1_violencia(den, vio), v2_indicador(den, ind), v3_poblacion(pop)], ignore_index=True))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    table = compare_all(parse.read_denuncias(), parse.read_violencia(), parse.read_indicadores(),
                        parse.population(parse.read_indicadores()))
    config.REPORTS.mkdir(parents=True, exist_ok=True)
    table.to_csv(config.REPORTS / "validaciones.csv", index=False)
    with pd.option_context("display.width", 200, "display.max_rows", None):
        print(table[["validacion", "anio", "oficial", "calculado", "diferencia_pct", "resultado"]].to_string(index=False))
    return 1 if (table["resultado"] == "falla").any() else 0


if __name__ == "__main__":
    sys.exit(main())
