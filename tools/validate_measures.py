"""Valida las medidas DAX del modelo contra el mismo cálculo hecho en Python.

Dos pasos, porque la consulta DAX se ejecuta en Power BI Desktop (con el MCP de modelado o con
DAX Studio):

    python tools/validate_measures.py consulta            # escribe tools/validacion_medidas.dax
    (ejecutar esa consulta en Power BI y guardar el resultado como CSV)
    python tools/validate_measures.py comparar <csv_dax>  # compara y escribe reports/validacion_medidas.csv

La comparación cubre cada medida numérica en seis contextos: el total, cada año, cada modalidad,
cada departamento, cada año × departamento y cada mes del calendario.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config  # noqa: E402

QUERY_FILE = ROOT / "tools" / "validacion_medidas.dax"
OUT = config.REPORTS / "validacion_medidas.csv"
TOLERANCE = 1e-6          # diferencia relativa admitida (redondeo de punto flotante)

COMMON = ["Denuncias", "Distritos con denuncias", "Denuncias ene–jul", "Meses cubiertos", "Población (último año)",
          "Habitantes-año", "Tasa por 100 mil (anual)", "Participación top 10 distritos",
          "Distritos para el 50 %", "Participación del distrito líder"]
GLOBAL = COMMON + ["Denuncias (miles)", "Combinaciones evaluadas", "Distritos en alerta", "Denuncias últimos 12 m",
                   "Denuncias 12 m previos", "Cambio 12 meses", "Saltos de serie", "Denuncias en celdas atípicas",
                   "Tasa (distritos de 5 mil hab. o más)"]
BY_YEAR = COMMON + ["Var. interanual", "Población del año"]
BY_MODALITY = COMMON + ["Participación de la modalidad", "Combinaciones evaluadas", "Distritos en alerta",
                        "Denuncias últimos 12 m", "Denuncias 12 m previos", "Cambio 12 meses",
                        "Cambio nacional de la modalidad", "Saltos de serie", "Denuncias en celdas atípicas"]
BY_DEPARTMENT = COMMON + ["Tasa nacional", "Veces la tasa nacional"]
BY_YEAR_DEPARTMENT = ["Denuncias", "Población del año", "Habitantes-año", "Tasa por 100 mil (anual)"]
BY_MONTH = ["Índice estacional"]      # contexto: cada mes del calendario (1 a 12)
TEXTS = {"Distrito líder", "Corte de datos"}
CUTOFF_MONTH = config.END[1]
LAST_FULL_YEAR = config.END[0] if config.END[1] == 12 else config.END[0] - 1
PANDEMIC_YEAR = 2020
MIN_POPULATION_FOR_RATE = 5000


# ---------------------------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------------------------

class Data:
    def __init__(self) -> None:
        read = lambda n: pd.read_csv(config.CURATED / f"{n}.csv", dtype={"ubigeo": str})
        self.districts = read("dim_distrito")
        self.modalities = read("dim_modalidad")
        self.calendar = read("dim_fecha")
        self.alerts = read("fact_alerta_distrito").merge(self.districts[["ubigeo", "departamento"]], on="ubigeo")
        self.jumps = read("fact_salto_serie")
        self.pop = read("fact_poblacion")
        den = read("fact_denuncia").merge(self.districts[["ubigeo", "distrito_unico", "departamento"]], on="ubigeo")
        den = den.merge(self.modalities[["modalidad_id", "modalidad"]], on="modalidad_id")
        den["anio"] = den["mes_inicio"].str[:4].astype(int)
        den["mes"] = den["mes_inicio"].str[5:7].astype(int)
        self.den = den
        self.months = self.calendar.groupby("anio").size().to_dict()          # meses por año en el calendario


def providers_for_share(amounts: pd.Series, share: float) -> int:
    """Igual que la medida DAX: elementos cuyo acumulado de los estrictamente mayores es < share del total."""
    values = amounts.to_numpy()
    order = np.sort(values)[::-1]
    cum = np.concatenate([[0], np.cumsum(order)])
    first = {v: cum[i] for i, v in reversed(list(enumerate(order)))}
    before = np.array([first[v] for v in values])
    return int((before < share * values.sum()).sum())


def population(d: Data, year: int, departments: set | None = None) -> int:
    p = d.pop[d.pop["anio"] == year]
    if departments is not None:
        p = p[p["ubigeo"].isin(d.districts.loc[d.districts["departamento"].isin(departments), "ubigeo"])]
    return int(p["poblacion"].sum())


def exposure(d: Data, months_by_year: dict, departments: set | None) -> float:
    return sum(population(d, y, departments) * m / 12 for y, m in months_by_year.items())


def measures(d: Data, names: list[str], den: pd.DataFrame, months_by_year: dict, departments: set | None = None,
             prior: pd.DataFrame | None = None) -> dict:
    total = den["cantidad"].sum()
    by_district = den.groupby("ubigeo")["cantidad"].sum()
    hab = exposure(d, months_by_year, departments)
    last_year = max(months_by_year)
    out = {
        "Denuncias": total,
        "Denuncias (miles)": total / 1000,
        "Distritos con denuncias": den["ubigeo"].nunique(),
        "Denuncias ene–jul": den.loc[den["mes"] <= CUTOFF_MONTH, "cantidad"].sum(),
        "Meses cubiertos": sum(months_by_year.values()),
        "Población (último año)": population(d, last_year, departments),
        "Población del año": population(d, last_year, departments),
        "Habitantes-año": hab,
        "Tasa por 100 mil (anual)": total / hab * 1e5 if hab else np.nan,
        "Participación top 10 distritos": by_district.nlargest(10).sum() / total if total else np.nan,
        "Distritos para el 50 %": providers_for_share(by_district, 0.5) if total else np.nan,
        "Participación del distrito líder": by_district.max() / total if total else np.nan,
        "Var. interanual": (total / prior["cantidad"].sum() - 1) if prior is not None and len(prior) else np.nan,
        "Tasa (distritos de 5 mil hab. o más)": np.nan,
    }
    return {k: out[k] for k in names if k in out}


def alert_measures(d: Data, names: list[str], modality_id: int | None) -> dict:
    a = d.alerts if modality_id is None else d.alerts[d.alerts["modalidad_id"] == modality_id]
    j = d.jumps if modality_id is None else d.jumps[d.jumps["modalidad_id"] == modality_id]
    cur, prev = a["denuncias_ultimos_12m"].sum(), a["denuncias_12m_previos"].sum()
    out = {
        "Combinaciones evaluadas": len(a),
        "Distritos en alerta": int(a["en_alerta"].sum()),
        "Denuncias últimos 12 m": cur,
        "Denuncias 12 m previos": prev,
        "Cambio 12 meses": (cur - prev) / prev if prev else np.nan,
        "Cambio nacional de la modalidad": a["variacion_nacional_pct"].mean() / 100 if modality_id else np.nan,
        "Saltos de serie": len(j),
    }
    return {k: out[k] for k in names if k in out}


def expected() -> pd.DataFrame:
    d = Data()
    den = d.den
    cal_all = dict(d.months)
    atypical = lambda x: x.loc[x["celda_atipica"] == 1, "cantidad"].sum()
    rows: list[tuple] = []

    def add(context, key, values):
        rows.extend((context, key, k, v) for k, v in values.items())

    # Total
    values = measures(d, GLOBAL, den, cal_all)
    values["Denuncias en celdas atípicas"] = atypical(den)
    values.update(alert_measures(d, GLOBAL, None))
    # Distritos de 5 mil o más: la medida devuelve la tasa solo si la población del último año lo permite;
    # en el total no hay distrito elegido, así que la población es la del país y la tasa se devuelve entera.
    values["Tasa (distritos de 5 mil hab. o más)"] = values["Tasa por 100 mil (anual)"]
    add("global", "total", values)

    # Por año
    for year, g in den.groupby("anio"):
        months = {year: cal_all[year]}
        prior = None
        if year - 1 in cal_all:
            months_present = d.calendar.loc[d.calendar["anio"] == year, "mes"]
            prior = den[(den["anio"] == year - 1) & den["mes"].isin(months_present)]
        add("anio", str(year), measures(d, BY_YEAR, g, months, prior=prior))

    # Por modalidad
    for (mid, name), g in den.groupby(["modalidad_id", "modalidad"]):
        values = measures(d, BY_MODALITY, g, cal_all)
        values["Participación de la modalidad"] = g["cantidad"].sum() / den["cantidad"].sum()
        values["Denuncias en celdas atípicas"] = atypical(g)
        values.update(alert_measures(d, BY_MODALITY, mid))
        add("modalidad", name, values)

    # Por departamento
    nat = measures(d, ["Tasa por 100 mil (anual)"], den, cal_all)["Tasa por 100 mil (anual)"]
    for dept, g in den.groupby("departamento"):
        values = measures(d, BY_DEPARTMENT, g, cal_all, departments={dept})
        values["Tasa nacional"] = nat
        values["Veces la tasa nacional"] = values["Tasa por 100 mil (anual)"] / nat
        add("departamento", dept, values)

    # Por año y departamento
    for (year, dept), g in den.groupby(["anio", "departamento"]):
        add("anio_departamento", f"{year}|{dept}",
            measures(d, BY_YEAR_DEPARTMENT, g, {year: cal_all[year]}, departments={dept}))

    # Índice estacional por mes
    full = den[(den["anio"] <= LAST_FULL_YEAR) & (den["anio"] != PANDEMIC_YEAR)]
    shares = full.groupby(["anio", "mes"])["cantidad"].sum()
    shares = shares / shares.groupby(level=0).transform("sum")
    for month, value in shares.groupby(level=1).mean().items():
        rows.append(("mes", str(month), "Índice estacional", value))

    # Textos
    leader = den.groupby("distrito_unico")["cantidad"].sum().idxmax()
    rows.append(("global", "total", "Distrito líder", leader))
    months_es = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "setiembre",
                 "octubre", "noviembre", "diciembre"]
    rows.append(("global", "total", "Corte de datos",
                 f"Denuncias registradas hasta {months_es[config.END[1] - 1]} de {config.END[0]}"))
    return pd.DataFrame(rows, columns=["contexto", "clave", "medida", "python"])


# ---------------------------------------------------------------------------------------------
# DAX
# ---------------------------------------------------------------------------------------------

def dax_name(name: str) -> str:
    """Medida como texto: así se pueden mezclar cifras y textos en una sola tabla (UNION exige un solo tipo)."""
    return 'FORMAT ( [' + name.replace("]", "]]") + '], "General Number" )'


def query() -> str:
    parts = []
    for m in GLOBAL + sorted(TEXTS):
        parts.append(f'ROW ( "contexto", "global", "clave", "total", "medida", "{m}", "valor", {dax_name(m)} )')
    for m in BY_YEAR:
        parts.append(f'SELECTCOLUMNS ( VALUES ( dim_fecha[anio] ), "contexto", "anio", "clave", FORMAT ( dim_fecha[anio], "0" ), '
                     f'"medida", "{m}", "valor", {dax_name(m)} )')
    for m in BY_MODALITY:
        parts.append(f'SELECTCOLUMNS ( VALUES ( dim_modalidad[modalidad] ), "contexto", "modalidad", "clave", dim_modalidad[modalidad], '
                     f'"medida", "{m}", "valor", {dax_name(m)} )')
    for m in BY_DEPARTMENT:
        parts.append(f'SELECTCOLUMNS ( VALUES ( dim_distrito[departamento] ), "contexto", "departamento", "clave", dim_distrito[departamento], '
                     f'"medida", "{m}", "valor", {dax_name(m)} )')
    for m in BY_YEAR_DEPARTMENT:
        parts.append('SELECTCOLUMNS ( SUMMARIZE ( fact_denuncia, dim_fecha[anio], dim_distrito[departamento] ), '
                     '"contexto", "anio_departamento", "clave", FORMAT ( dim_fecha[anio], "0" ) & "|" & dim_distrito[departamento], '
                     f'"medida", "{m}", "valor", {dax_name(m)} )')
    for m in BY_MONTH:
        parts.append(f'SELECTCOLUMNS ( VALUES ( dim_fecha[mes] ), "contexto", "mes", "clave", FORMAT ( dim_fecha[mes], "0" ), '
                     f'"medida", "{m}", "valor", {dax_name(m)} )')
    return "EVALUATE\nUNION (\n    " + ",\n    ".join(parts) + "\n)\n"


def compare(dax_csv: Path) -> pd.DataFrame:
    dax = pd.read_csv(dax_csv, dtype=str)
    dax.columns = [c.strip("[]").split("[")[-1] for c in dax.columns]
    dax["dax"] = pd.to_numeric(dax["valor"].str.replace(",", ".", regex=False), errors="coerce")
    exp = expected()
    text = exp["medida"].isin(TEXTS)
    out = exp.merge(dax[["contexto", "clave", "medida", "dax", "valor"]], on=["contexto", "clave", "medida"], how="outer")
    out["python"] = out["python"].where(~out["medida"].isin(TEXTS), out["python"])
    numeric = ~out["medida"].isin(TEXTS)
    py = pd.to_numeric(out["python"].where(numeric), errors="coerce")
    # En DAX, una suma o un conteo sin filas devuelve BLANK; en Python, 0. Se tratan como iguales.
    dax_value = out["dax"].where(out["dax"].notna() | py.ne(0), 0.0)
    out["diferencia_relativa"] = (dax_value - py).abs() / py.abs().clip(lower=1e-9)
    both_blank = dax_value.isna() & py.isna()
    match = dax_value.notna() & py.notna() & (out["diferencia_relativa"] <= TOLERANCE)
    out["resultado"] = np.where(numeric, np.where(both_blank | match, "cumple", "falla"),
                                np.where(out["python"].astype(str) == out["valor"].astype(str), "cumple", "falla"))
    out["dax"] = out["dax"].where(numeric, np.nan)
    out["python"] = out["python"].astype(str).where(~numeric, py.astype(float).astype(str))
    return out.drop(columns="valor")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) >= 2 and sys.argv[1] == "consulta":
        QUERY_FILE.write_text(query(), encoding="utf-8")
        print(f"Consulta escrita en {QUERY_FILE.relative_to(ROOT)}")
        return 0
    if len(sys.argv) == 3 and sys.argv[1] == "comparar":
        result = compare(Path(sys.argv[2]))
        result.to_csv(OUT, index=False)
        failed = result[result["resultado"] != "cumple"]
        print(f"{len(result)} comparaciones; {len(failed)} fallan; diferencia relativa máxima "
              f"{result['diferencia_relativa'].max():.2e}")
        if len(failed):
            print(failed.to_string(index=False))
        return 1 if len(failed) else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
