"""Fase 3 — Transforma las denuncias: raw → staging → modelo en estrella (data/curated).

    raw       3 CSV tal como los publica el portal (data/raw)
    staging   denuncias limpias con UBIGEO de 6 dígitos (data/staging/denuncias.parquet)
    curated   hechos y dimensiones que lee Power BI (data/curated/*.csv)

Ninguna denuncia se excluye: lo que la Fase 2 marcó queda como columna de marca. El linaje
(filas y denuncias en cada paso) se escribe en reports/linaje.csv y el script falla si algún paso
pierde o duplica una denuncia.

Uso:
    python -m src.transform
"""

import sys

import numpy as np
import pandas as pd

from src import config, parse, quality

MODALITIES = [   # (id, modalidad, grupo)
    (1, "Hurto", "Contra el patrimonio"),
    (2, "Robo", "Contra el patrimonio"),
    (3, "Extorsión", "Extorsión y secuestro"),
    (4, "Secuestro", "Extorsión y secuestro"),
    (5, "Estafa", "Estafa"),
    (6, "Violencia contra la mujer e integrantes", "Violencia"),
    (7, "Otros", "Otros"),
]
MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "setiembre",
             "octubre", "noviembre", "diciembre"]
SMALL_WORDS = {"de", "del", "la", "las", "los", "y", "el", "e", "en"}
ALERT_MIN_PREVIOUS = 30          # denuncias mínimas en la ventana previa para evaluar un distrito
ALERT_MIN_INCREASE = 20          # aumento mínimo en denuncias para marcarlo
ALERT_Z = 3.0
WINDOW_MONTHS = 12
POPULATION_GAP_PCT = 5.0         # máxima diferencia aceptada entre el modelo y la población oficial de un departamento
ADJUST_TOLERANCE = 0.001         # una diferencia menor a 0,1 % no se marca como población ajustada


def proper(text: str) -> str:
    """'SAN JOSE DE SISA' -> 'San Jose de Sisa': los nombres vienen en mayúsculas y sin tildes."""
    words = text.lower().split()
    return " ".join(w if i and w in SMALL_WORDS else w.capitalize() for i, w in enumerate(words))


# ---------------------------------------------------------------------------------------------
# Dimensiones
# ---------------------------------------------------------------------------------------------

def dim_distrito(den: pd.DataFrame) -> pd.DataFrame:
    """Un distrito por UBIGEO, con el nombre más reciente (problema 2) y la provincia al lado (problema 9)."""
    latest = den.sort_values(["anio", "mes"]).groupby("ubigeo").tail(1).set_index("ubigeo")
    first = den.groupby("ubigeo").agg(primer_mes=("anio", "min"))
    dim = latest[["departamento_id", "provincia", "distrito"]].copy()
    dim["provincia"] = dim["provincia"].map(proper)
    dim["distrito"] = dim["distrito"].map(proper)
    departments = pd.read_csv(config.REFERENCE / "departamentos.csv", dtype={"departamento_id": str})
    dim = dim.reset_index().merge(departments[["departamento_id", "departamento", "zona"]],
                                  on="departamento_id", how="left")
    homonym = dim["distrito"].duplicated(keep=False)
    dim["distrito_unico"] = dim["distrito"].where(~homonym, dim["distrito"] + " (" + dim["provincia"] + ")")
    return dim[["ubigeo", "distrito", "distrito_unico", "provincia", "departamento_id", "departamento", "zona"]] \
        .sort_values("ubigeo").reset_index(drop=True)


def dim_modalidad() -> pd.DataFrame:
    return pd.DataFrame(MODALITIES, columns=["modalidad_id", "modalidad", "grupo"])


def dim_fecha() -> pd.DataFrame:
    months = pd.period_range(f"{config.START[0]}-{config.START[1]:02d}", f"{config.END[0]}-{config.END[1]:02d}", freq="M")
    start = months.to_timestamp()
    covid = (start >= "2020-03-01") & (start <= "2020-12-01")
    return pd.DataFrame({
        "mes_inicio": start.date,
        "anio": months.year,
        "mes": months.month,
        "mes_nombre": [MONTHS_ES[m - 1] for m in months.month],
        "trimestre": "T" + months.quarter.astype(str),
        "anio_mes": months.strftime("%Y-%m"),
        "es_ene_jul": (months.month <= config.END[1]).astype(int),
        "es_pandemia": covid.astype(int),
    })


def dim_anio() -> pd.DataFrame:
    years = list(range(config.START[0], config.END[0] + 1))
    return pd.DataFrame({"anio": years, "periodo": ["Año completo" if y < config.END[0] else "Enero–julio" for y in years]})


# ---------------------------------------------------------------------------------------------
# Hechos
# ---------------------------------------------------------------------------------------------

def fact_denuncia(den: pd.DataFrame, modalities: pd.DataFrame, outliers: pd.DataFrame) -> pd.DataFrame:
    """Una fila por mes × distrito × modalidad con denuncias; la clave repetida (problema 2) se suma."""
    merged = den.groupby(["anio", "mes", "ubigeo", "modalidad"], as_index=False)["cantidad"].sum()
    merged["mes_inicio"] = pd.to_datetime(dict(year=merged["anio"], month=merged["mes"], day=1)).dt.date
    merged = merged.merge(modalities[["modalidad", "modalidad_id"]], on="modalidad", how="left")
    flagged = set(zip(outliers["anio"], outliers["mes"], outliers["ubigeo"], outliers["modalidad"]))
    merged["celda_atipica"] = [int(k in flagged) for k in zip(merged["anio"], merged["mes"], merged["ubigeo"], merged["modalidad"])]
    return merged[["mes_inicio", "ubigeo", "modalidad_id", "cantidad", "celda_atipica"]] \
        .sort_values(["mes_inicio", "ubigeo", "modalidad_id"]).reset_index(drop=True)


def fact_poblacion(districts: pd.DataFrame, pop: dict) -> pd.DataFrame:
    """Población por distrito y año. Los años sin dato (problema 6) arrastran el último año conocido y se marcan."""
    years = range(config.START[0], config.END[0] + 1)
    # El padrón de la fuente incluye distritos sin denuncias; entran al reparto para que cada
    # provincia suma su total oficial, pero solo se devuelven los distritos del modelo.
    everyone = sorted(set(districts["ubigeo"]) | set(pop["distrito"]["ubigeo"]))
    grid = pd.MultiIndex.from_product([everyone, years], names=["ubigeo", "anio"]).to_frame(index=False)
    known = pop["distrito"][["ubigeo", "anio", "poblacion"]]
    out = grid.merge(known, on=["ubigeo", "anio"], how="left").sort_values(["ubigeo", "anio"])
    out["poblacion_imputada"] = out["poblacion"].isna().astype(int)
    out["poblacion"] = out.groupby("ubigeo")["poblacion"].ffill()
    out["poblacion"] = out.groupby("ubigeo")["poblacion"].bfill()
    out = out.dropna(subset=["poblacion"]).rename(columns={"poblacion": "poblacion_fuente"})

    # Problema 7: desde 2020 la población por distrito de la fuente suma menos que la oficial de su
    # provincia (hasta 30 % menos en algunas), aunque provincias, departamentos y país sí cuadran
    # entre sí. Se reparte el total provincial oficial entre sus distritos en proporción a la
    # población publicada de cada uno. Así los departamentos suman la cifra oficial.
    province = pop["provincia"].assign(
        provincia=lambda t: (t["ubigeo_original"].astype(int) // 100).astype(str).str.zfill(4)
    )[["provincia", "anio", "poblacion"]].rename(columns={"poblacion": "poblacion_provincia"})
    out["provincia"] = out["ubigeo"].str[:4]
    out = out.merge(province, on=["provincia", "anio"], how="left")
    published = out.groupby(["provincia", "anio"])["poblacion_fuente"].transform("sum")
    factor = (out["poblacion_provincia"] / published).fillna(1.0)
    out["poblacion"] = (out["poblacion_fuente"] * factor).round().astype(int)
    out["poblacion_ajustada"] = ((factor - 1).abs() > ADJUST_TOLERANCE).astype(int)
    out["poblacion_fuente"] = out["poblacion_fuente"].astype(int)
    out = out[out["ubigeo"].isin(districts["ubigeo"])]
    return out.drop(columns=["provincia", "poblacion_provincia"]).reset_index(drop=True)


def fact_salto_serie(series: pd.DataFrame, modalities: pd.DataFrame) -> pd.DataFrame:
    breaks = quality.detect_breaks(series)
    breaks["mes_inicio"] = pd.to_datetime(breaks["periodo"] + "-01").dt.date
    breaks = breaks.merge(modalities[["modalidad", "modalidad_id"]], on="modalidad", how="left")
    return breaks[["mes_inicio", "modalidad_id", "denuncias", "mes_anterior", "variacion_pct"]]


def district_alerts(den: pd.DataFrame, modalities: pd.DataFrame) -> pd.DataFrame:
    """Distritos que crecen mucho más que el país en una modalidad (P4).

    Compara las denuncias de los últimos 12 meses con las 12 anteriores, descuenta la variación
    nacional de esa modalidad (así un salto del sistema, como el del robo, no marca a todos) y
    estandariza con la mediana y la desviación absoluta de todos los distritos de la modalidad.
    """
    last = pd.Period(f"{config.END[0]}-{config.END[1]:02d}", freq="M")
    period = pd.PeriodIndex.from_fields(year=den["anio"], month=den["mes"], freq="M")
    age = (last - period).map(lambda p: p.n)
    d = den.assign(ventana=np.where(age < WINDOW_MONTHS, "actual", np.where(age < 2 * WINDOW_MONTHS, "previa", "")))
    d = d[d["ventana"] != ""]
    d = d[d["modalidad"] != "Otros"]
    table = d.pivot_table(index=["modalidad", "ubigeo"], columns="ventana", values="cantidad", aggfunc="sum", fill_value=0)
    table = table.reindex(columns=["actual", "previa"], fill_value=0).reset_index()
    rows = []
    for modality, g in table.groupby("modalidad"):
        national = g["actual"].sum() / g["previa"].sum()
        g = g[g["previa"] >= ALERT_MIN_PREVIOUS].copy()
        g["variacion_pct"] = 100 * (g["actual"] / g["previa"] - 1)
        g["variacion_nacional_pct"] = 100 * (national - 1)
        g["exceso_log"] = np.log((g["actual"] + 1) / (g["previa"] + 1)) - np.log(national)
        center = g["exceso_log"].median()
        spread = 1.4826 * (g["exceso_log"] - center).abs().median()
        g["z"] = (g["exceso_log"] - center) / spread
        g["en_alerta"] = ((g["z"] >= ALERT_Z) & (g["actual"] - g["previa"] >= ALERT_MIN_INCREASE)).astype(int)
        rows.append(g)
    out = pd.concat(rows, ignore_index=True)
    out = out.merge(modalities[["modalidad", "modalidad_id"]], on="modalidad", how="left")
    out = out.rename(columns={"actual": "denuncias_ultimos_12m", "previa": "denuncias_12m_previos"})
    for col in ["variacion_pct", "variacion_nacional_pct", "exceso_log", "z"]:
        out[col] = out[col].round(3)
    return out[["ubigeo", "modalidad_id", "denuncias_ultimos_12m", "denuncias_12m_previos", "variacion_pct",
                "variacion_nacional_pct", "z", "en_alerta"]].sort_values(["modalidad_id", "z"], ascending=[True, False]) \
        .reset_index(drop=True)


# ---------------------------------------------------------------------------------------------
# Linaje e integridad
# ---------------------------------------------------------------------------------------------

def check_integrity(tables: dict) -> list[str]:
    problems = []
    keys = {"fact_denuncia": ["mes_inicio", "ubigeo", "modalidad_id"], "fact_poblacion": ["ubigeo", "anio"],
            "dim_distrito": ["ubigeo"], "dim_modalidad": ["modalidad_id"], "dim_fecha": ["mes_inicio"],
            "dim_anio": ["anio"], "fact_alerta_distrito": ["ubigeo", "modalidad_id"],
            "fact_salto_serie": ["mes_inicio", "modalidad_id"]}
    for name, key in keys.items():
        if tables[name].duplicated(key).any():
            problems.append(f"{name}: clave {key} repetida")
    foreign = [("fact_denuncia", "ubigeo", "dim_distrito", "ubigeo"),
               ("fact_denuncia", "modalidad_id", "dim_modalidad", "modalidad_id"),
               ("fact_denuncia", "mes_inicio", "dim_fecha", "mes_inicio"),
               ("fact_poblacion", "ubigeo", "dim_distrito", "ubigeo"),
               ("fact_poblacion", "anio", "dim_anio", "anio"),
               ("fact_alerta_distrito", "ubigeo", "dim_distrito", "ubigeo"),
               ("fact_alerta_distrito", "modalidad_id", "dim_modalidad", "modalidad_id"),
               ("fact_salto_serie", "modalidad_id", "dim_modalidad", "modalidad_id"),
               ("fact_salto_serie", "mes_inicio", "dim_fecha", "mes_inicio"),
               ("dim_fecha", "anio", "dim_anio", "anio")]
    for fact, fk, dim, key in foreign:
        orphans = ~tables[fact][fk].isin(tables[dim][key])
        if orphans.any():
            problems.append(f"{fact}.{fk}: {int(orphans.sum())} filas sin {dim}")
    for name, table in tables.items():
        nulls = table.isna().sum()
        for col, n in nulls[nulls > 0].items():
            problems.append(f"{name}.{col}: {n} nulos")
    if tables["dim_distrito"]["distrito_unico"].duplicated().any():
        problems.append("dim_distrito: distrito_unico repetido")
    return problems


def population_vs_official(tables: dict, pop: dict) -> pd.DataFrame:
    """Valida fact_poblacion contra la población oficial de cada departamento (V4).

    La brecha que queda son los distritos del padrón que no registran ninguna denuncia: sus
    habitantes cuentan para el departamento oficial pero el modelo no tiene fila para ellos.
    """
    model = tables["fact_poblacion"].merge(tables["dim_distrito"][["ubigeo", "departamento_id", "departamento"]], on="ubigeo")
    model = model.groupby(["departamento_id", "departamento", "anio"], as_index=False)["poblacion"].sum()
    official = pop["departamento"].assign(departamento_id=lambda t: t["ubigeo_original"].astype(str))
    official = official[["departamento_id", "anio", "poblacion"]].rename(columns={"poblacion": "poblacion_oficial"})
    out = model.merge(official, on=["departamento_id", "anio"], how="left").rename(columns={"poblacion": "poblacion_modelo"})
    out["diferencia_pct"] = (100 * (out["poblacion_modelo"] / out["poblacion_oficial"] - 1)).round(3)
    return out[["anio", "departamento_id", "departamento", "poblacion_oficial", "poblacion_modelo", "diferencia_pct"]]


def lineage(raw: pd.DataFrame, staging: pd.DataFrame, fact: pd.DataFrame) -> pd.DataFrame:
    rows = [
        ("1. raw", "CSV del portal", len(raw), int(raw["cantidad"].sum()), len(raw.columns), "Tal como se publica"),
        ("2. staging", "Denuncias con UBIGEO de 6 dígitos", len(staging), int(staging["cantidad"].sum()), len(staging.columns),
         "Reglas de campo: 0 filas excluidas"),
        ("3. curated", "fact_denuncia", len(fact), int(fact["cantidad"].sum()), len(fact.columns),
         "Suma la clave repetida (problema 2): 1 fila menos, mismas denuncias"),
        ("3a. marca", "Celdas atípicas", int(fact["celda_atipica"].sum()),
         int(fact.loc[fact["celda_atipica"] == 1, "cantidad"].sum()), None, "Subconjunto, no exclusión"),
    ]
    return pd.DataFrame(rows, columns=["paso", "descripcion", "filas", "denuncias", "columnas", "nota"])


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raw = pd.read_csv(config.RAW / "denuncias.csv", dtype={"UBIGEO_HECHO": "string"})
    den = parse.read_denuncias()
    indicators = parse.read_indicadores()
    pop = parse.population(indicators)
    outliers = quality.detect_outliers(den)
    series = quality.monthly_series(den)

    config.STAGING.mkdir(parents=True, exist_ok=True)
    den.to_parquet(config.STAGING / "denuncias.parquet", index=False)

    modalities = dim_modalidad()
    districts = dim_distrito(den)
    tables = {
        "fact_denuncia": fact_denuncia(den, modalities, outliers),
        "fact_poblacion": fact_poblacion(districts, pop),
        "fact_alerta_distrito": district_alerts(den, modalities),
        "fact_salto_serie": fact_salto_serie(series, modalities),
        "dim_distrito": districts,
        "dim_modalidad": modalities,
        "dim_fecha": dim_fecha(),
        "dim_anio": dim_anio(),
    }
    problems = check_integrity(tables)
    trail = lineage(raw, den, tables["fact_denuncia"])
    base = trail.iloc[0]
    for row in trail.iloc[1:3].itertuples():
        if row.denuncias != base.denuncias:
            problems.append(f"Linaje: {row.paso} tiene {row.denuncias} denuncias; raw tiene {base.denuncias}")
    comparison = population_vs_official(tables, pop)
    if comparison["poblacion_oficial"].isna().any():
        problems.append("fact_poblacion: departamento sin población oficial")
    worst = comparison["diferencia_pct"].min()
    if worst < -POPULATION_GAP_PCT or comparison["diferencia_pct"].max() > ADJUST_TOLERANCE * 100:
        problems.append(f"fact_poblacion: un departamento difiere {worst} % de la población oficial")
    for p in problems:
        print(f"  ✗ {p}")
    if problems:
        return 1

    config.CURATED.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        table.to_csv(config.CURATED / f"{name}.csv", index=False, lineterminator="\n")
    config.REPORTS.mkdir(parents=True, exist_ok=True)
    trail.to_csv(config.REPORTS / "linaje.csv", index=False)
    comparison.to_csv(config.REPORTS / "validacion_poblacion.csv", index=False)

    print(trail[["paso", "filas", "denuncias"]].to_string(index=False))
    for name, table in tables.items():
        size = (config.CURATED / f"{name}.csv").stat().st_size / 1e6
        print(f"  {name}: {len(table):,} filas, {size:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
