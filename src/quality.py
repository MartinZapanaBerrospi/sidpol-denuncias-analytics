"""Fase 2 — Perfilado y calidad de los archivos de denuncias.

Aplica las reglas de campo de src/parse.py y mide la calidad en seis dimensiones: completitud,
unicidad, validez, consistencia, exactitud y oportunidad. Escribe en reports/calidad/:

    perfilado_columnas.csv   una fila por columna del archivo principal: vacíos, distintos, rango
    perfilado_mensual.csv    una fila por mes: filas, denuncias, distritos con registro, UBIGEO de 5 dígitos
    reglas.csv               cada regla con filas y denuncias afectadas y su resultado
    rupturas.csv             saltos bruscos de las series mensuales por modalidad
    atipicos.csv             celdas distrito-modalidad-mes muy altas frente a su propia historia
    ubigeo_problemas.csv     códigos con dos nombres, sin población o repetidos
    cobertura_poblacion.csv  población de los distritos frente a la nacional, por año

y reports/validaciones.csv (comparación con otras cifras oficiales).

Termina con error si alguna regla bloqueante falla.

Uso:
    python -m src.quality
"""

import sys

import numpy as np
import pandas as pd

from src import config, parse, validate

PUBLICATION_DATES = {"denuncias": "2026-08-13", "violencia": "2026-08-21", "indicadores": "2026-08-26"}
BREAK_THRESHOLD = 0.20                      # salto de más de 20 % de un mes al siguiente
BREAK_MIN_MONTHLY = 1000                    # modalidades con menos denuncias mensuales fluctúan por azar
COVID_MONTHS = (202003, 202012)             # cierre y reapertura de la pandemia: se documentan aparte
OUTLIER_Z = 6.0
OUTLIER_MIN_COUNT = 30


class Rules:
    """Acumula reglas con un formato único: qué se evaluó, cuántas filas fallan y cuántas denuncias."""

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.rows = []

    def add(self, rule_id, dimension, rule, severity, fails, evaluated=None, detail=""):
        """fails: máscara booleana sobre las filas, o un número cuando la regla no es por fila."""
        if isinstance(fails, pd.Series):
            n_fail, n_eval = int(fails.sum()), (len(fails) if evaluated is None else evaluated)
            amount = int(self.df.loc[fails, "cantidad"].sum())
        else:
            n_fail, n_eval, amount = int(fails), evaluated, None
        result = "cumple" if n_fail == 0 else {"bloqueante": "falla", "alerta": "alerta", "info": "info"}[severity]
        self.rows.append({
            "id": rule_id, "dimension": dimension, "regla": rule, "severidad": severity,
            "evaluadas": n_eval, "fallan": n_fail,
            "pct_fallan": round(100 * n_fail / n_eval, 3) if n_eval else None,
            "denuncias_afectadas": amount, "resultado": result, "detalle": detail,
        })

    def table(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)


# ---------------------------------------------------------------------------------------------
# Perfilado
# ---------------------------------------------------------------------------------------------

def profile_columns() -> pd.DataFrame:
    raw = pd.read_csv(config.RAW / "denuncias.csv", dtype=str, keep_default_na=False)
    rows = []
    for col in raw.columns:
        values = raw[col]
        numeric = pd.to_numeric(values, errors="coerce")
        top = values.value_counts().head(3)
        rows.append({
            "columna": col,
            "tipo_detectado": "entero" if numeric.notna().all() and col != "UBIGEO_HECHO" else "texto",
            "vacios": int(values.str.strip().eq("").sum()),
            "con_espacios_extremos": int((values != values.str.strip()).sum()),
            "distintos": int(values.nunique()),
            "longitud_min": int(values.str.len().min()), "longitud_max": int(values.str.len().max()),
            "minimo": numeric.min() if numeric.notna().all() else "", "maximo": numeric.max() if numeric.notna().all() else "",
            "valores_frecuentes": " | ".join(f"{k} ({v})" for k, v in top.items()) if values.nunique() <= 200 else "",
        })
    return pd.DataFrame(rows)


def profile_months(den: pd.DataFrame) -> pd.DataFrame:
    g = den.groupby(["anio", "mes"])
    out = g.agg(filas=("cantidad", "size"), denuncias=("cantidad", "sum"), distritos=("ubigeo", "nunique"),
                pct_ubigeo_5_digitos=("ubigeo_con_cero_agregado", "mean")).reset_index()
    out["pct_ubigeo_5_digitos"] = (100 * out["pct_ubigeo_5_digitos"]).round(1)
    out.insert(0, "periodo", out["anio"].astype(str) + "-" + out["mes"].astype(str).str.zfill(2))
    return out


# ---------------------------------------------------------------------------------------------
# Rupturas, atípicos y códigos
# ---------------------------------------------------------------------------------------------

def monthly_series(den: pd.DataFrame) -> pd.DataFrame:
    s = den.assign(periodo=den["anio"] * 100 + den["mes"]).pivot_table(
        index="periodo", columns="modalidad", values="cantidad", aggfunc="sum", fill_value=0)
    return s


def detect_breaks(series: pd.DataFrame) -> pd.DataFrame:
    """Saltos de un mes al siguiente de más de BREAK_THRESHOLD, en modalidades de volumen suficiente.

    Un salto de un solo mes distingue un cambio brusco (de registro, de clasificación o de
    comportamiento) de una tendencia gradual, como el crecimiento de la extorsión desde 2021.
    """
    rows = []
    for modality in series.columns:
        s = series[modality]
        if s.median() < BREAK_MIN_MONTHLY:
            continue
        change = s / s.shift(1) - 1
        for period in s.index[change.abs() > BREAK_THRESHOLD]:
            if COVID_MONTHS[0] <= period <= COVID_MONTHS[1]:
                continue
            previous = s.index[s.index.get_loc(period) - 1]
            rows.append({"periodo": f"{period // 100}-{period % 100:02d}", "modalidad": modality,
                         "denuncias": int(s[period]), "mes_anterior": int(s[previous]),
                         "variacion_pct": round(100 * float(change[period]), 1)})
    return pd.DataFrame(rows, columns=["periodo", "modalidad", "denuncias", "mes_anterior", "variacion_pct"])         .sort_values(["modalidad", "periodo"]).reset_index(drop=True)


def detect_outliers(den: pd.DataFrame) -> pd.DataFrame:
    """Celdas muy altas frente a la historia de su propio distrito y modalidad (z robusto sobre log)."""
    d = den.assign(logq=np.log1p(den["cantidad"]))
    g = d.groupby(["ubigeo", "modalidad"])["logq"]
    d["n"] = g.transform("size")
    d["mediana"] = g.transform("median")
    d["mad"] = g.transform(lambda s: (s - s.median()).abs().median())
    d["z"] = (d["logq"] - d["mediana"]) / (1.4826 * d["mad"].clip(lower=0.1))
    flagged = d[(d["n"] >= 12) & (d["z"] > OUTLIER_Z) & (d["cantidad"] >= OUTLIER_MIN_COUNT)]
    cols = ["anio", "mes", "ubigeo", "departamento_fuente", "provincia", "distrito", "modalidad", "cantidad", "z"]
    return flagged[cols].assign(z=lambda x: x["z"].round(1)).sort_values("z", ascending=False).reset_index(drop=True)


def ubigeo_problems(den: pd.DataFrame, pop: dict) -> pd.DataFrame:
    rows = []
    names = den.groupby("ubigeo").agg(provincias=("provincia", "nunique"), distritos=("distrito", "nunique"),
                                      departamentos=("departamento_fuente", "nunique"), filas=("cantidad", "size"),
                                      denuncias=("cantidad", "sum"))
    for code, r in names[(names[["provincias", "distritos", "departamentos"]] > 1).any(axis=1)].iterrows():
        variants = den[den["ubigeo"] == code][["departamento_fuente", "provincia", "distrito"]].drop_duplicates()
        rows.append({"problema": "un_ubigeo_con_varios_nombres", "ubigeo": code, "filas": int(r["filas"]),
                     "denuncias": int(r["denuncias"]),
                     "detalle": " | ".join("/".join(v) for v in variants.itertuples(index=False))})
    known = set(pop["distrito"]["ubigeo"])
    missing = den[~den["ubigeo"].isin(known)]
    for code, g in missing.groupby("ubigeo"):
        rows.append({"problema": "ubigeo_sin_poblacion", "ubigeo": code, "filas": len(g),
                     "denuncias": int(g["cantidad"].sum()),
                     "detalle": "/".join(g[["departamento_fuente", "provincia", "distrito"]].iloc[0])})
    key = ["anio", "mes", "ubigeo", "modalidad"]
    for _, g in den[den.duplicated(key, keep=False)].groupby(key):
        rows.append({"problema": "clave_repetida", "ubigeo": g["ubigeo"].iloc[0], "filas": len(g),
                     "denuncias": int(g["cantidad"].sum()),
                     "detalle": f"{g['anio'].iloc[0]}-{g['mes'].iloc[0]:02d} {g['modalidad'].iloc[0]}"})
    return pd.DataFrame(rows, columns=["problema", "ubigeo", "filas", "denuncias", "detalle"])


def population_coverage(den: pd.DataFrame, pop: dict) -> pd.DataFrame:
    national = pop["nacional"].set_index("anio")["poblacion"]
    districts = pop["distrito"].groupby("anio").agg(poblacion_distritos=("poblacion", "sum"), distritos=("ubigeo", "nunique"))
    covered = den.merge(pop["distrito"][["ubigeo", "anio"]].assign(con_poblacion=True), on=["ubigeo", "anio"], how="left")
    covered["con_poblacion"] = covered["con_poblacion"].fillna(False).astype(bool)
    by_year = covered.groupby("anio").apply(
        lambda g: pd.Series({"denuncias": g["cantidad"].sum(),
                             "denuncias_con_poblacion": g.loc[g["con_poblacion"], "cantidad"].sum()}),
        include_groups=False)
    out = districts.join(by_year).join(national.rename("poblacion_nacional")).loc[config.START[0]:config.END[0]]
    out["brecha_poblacion_pct"] = (100 * (out["poblacion_distritos"] / out["poblacion_nacional"] - 1)).round(2)
    out["pct_denuncias_con_poblacion"] = (100 * out["denuncias_con_poblacion"] / out["denuncias"]).round(2)
    return out.reset_index()


# ---------------------------------------------------------------------------------------------
# Reglas
# ---------------------------------------------------------------------------------------------

def run_rules(den: pd.DataFrame, vio: pd.DataFrame, ind: pd.DataFrame, pop: dict, series: pd.DataFrame,
              breaks: pd.DataFrame, outliers: pd.DataFrame, checks: pd.DataFrame) -> pd.DataFrame:
    r = Rules(den)
    expected_months = {(y, m) for y in range(config.START[0], config.END[0] + 1) for m in range(1, 13)
                       if (y, m) <= config.END}
    months = set(zip(den["anio"], den["mes"]))
    raw = pd.read_csv(config.RAW / "denuncias.csv", dtype=str, keep_default_na=False)

    # Completitud
    r.add("C1", "Completitud", f"Los {len(expected_months)} meses del periodo están presentes", "bloqueante",
          len(expected_months - months), evaluated=len(expected_months))
    r.add("C2", "Completitud", "Las 7 modalidades aparecen en todos los meses", "bloqueante",
          int((series.reindex(columns=sorted(config.VALID_MODALITIES)).fillna(0) == 0).to_numpy().sum()),
          evaluated=len(series) * 7)
    r.add("C3", "Completitud", "Las 8 columnas esperadas están en el archivo principal", "bloqueante",
          len(set(parse.DENUNCIAS_COLUMNS) - set(raw.columns)), evaluated=len(parse.DENUNCIAS_COLUMNS))
    for col in raw.columns:
        r.add("C4", "Completitud", f"Sin vacíos: {col}", "bloqueante", raw[col].str.strip().eq("").set_axis(den.index))
    possible = den["ubigeo"].nunique() * len(expected_months) * 7
    r.add("C5", "Completitud", "La tabla es dispersa: un mes sin fila significa cero denuncias", "info",
          possible - len(den), evaluated=possible,
          detail=f"{len(den):,} filas de {possible:,} combinaciones posibles distrito-mes-modalidad; "
                 "para tasas y alertas se completa la grilla con ceros en la Fase 3")

    # Unicidad
    key = ["anio", "mes", "ubigeo", "modalidad"]
    r.add("U1", "Unicidad", "Una fila por año, mes, distrito y modalidad", "alerta", den.duplicated(key, keep=False),
          detail="Un UBIGEO con dos nombres de provincia (problema 2); se suman las dos filas")
    r.add("U2", "Unicidad", "No hay filas idénticas en todas las columnas", "bloqueante",
          den.duplicated(["anio", "mes", "departamento_fuente", "provincia", "distrito", "ubigeo", "modalidad",
                          "cantidad"], keep=False))

    # Validez
    r.add("V1", "Validez", f"Año entre {config.START[0]} y {config.END[0]}", "bloqueante",
          ~den["anio"].between(config.START[0], config.END[0]))
    r.add("V2", "Validez", "Mes entre 1 y 12", "bloqueante", ~den["mes"].between(1, 12))
    r.add("V3", "Validez", "Ningún mes posterior al corte", "bloqueante",
          (den["anio"] == config.END[0]) & (den["mes"] > config.END[1]))
    r.add("V4", "Validez", "Cantidad entera mayor que cero", "bloqueante", den["cantidad"] < 1)
    r.add("V5", "Validez", "Modalidad dentro del dominio de 7", "bloqueante", ~den["modalidad"].isin(config.VALID_MODALITIES))
    r.add("V6", "Validez", "UBIGEO numérico de 6 dígitos tras agregar el cero inicial", "bloqueante",
          ~den["ubigeo"].str.fullmatch(r"\d{6}"))
    r.add("V7", "Validez", "Código de departamento entre 01 y 25", "bloqueante",
          ~den["ubigeo"].str[:2].astype(int).between(1, 25))
    r.add("V8", "Validez", "El UBIGEO existe en el padrón de población", "alerta",
          ~den["ubigeo"].isin(set(pop["distrito"]["ubigeo"])),
          detail="Distritos creados recientemente; 0,006 % de las denuncias")
    r.add("V9", "Validez", "UBIGEO ya viene con 6 dígitos en el archivo", "info", den["ubigeo_con_cero_agregado"],
          detail="El archivo trató el código como número y perdió el cero inicial")

    # Consistencia
    names = den.groupby("ubigeo")[["provincia", "distrito", "departamento_fuente"]].transform("nunique")
    r.add("K1", "Consistencia", "Cada UBIGEO tiene un solo nombre de provincia y de distrito", "alerta",
          (names > 1).any(axis=1))
    per_department = den.groupby("departamento_fuente")["departamento_id"].transform("nunique")
    r.add("K2", "Consistencia", "Cada nombre de departamento corresponde a un solo código", "bloqueante", per_department > 1)
    lima_m = den["departamento_fuente"] == parse.LIMA_METROPOLITANA
    r.add("K3", "Consistencia", "Lima Metropolitana es solo la provincia de Lima", "bloqueante",
          lima_m & (den["provincia"] != "LIMA"))
    r.add("K4", "Consistencia", "Región Lima no incluye la provincia de Lima", "bloqueante",
          (den["departamento_fuente"] == parse.REGION_LIMA) & (den["provincia"] == "LIMA"))
    homonyms = den.groupby("distrito")["ubigeo"].transform("nunique") > 1
    r.add("K5", "Consistencia", "El nombre de distrito identifica un solo UBIGEO", "info", homonyms,
          detail=f"{den.loc[homonyms, 'distrito'].nunique()} nombres de distrito se repiten en provincias distintas; "
                 "la identidad de un distrito es su UBIGEO, nunca su nombre")
    r.add("K6", "Consistencia", "Las columnas del archivo de violencia equivalen a las del principal", "bloqueante",
          len(set(parse.VIOLENCIA_COLUMNS.values()) - set(parse.DENUNCIAS_COLUMNS.values()) - {"departamento_fuente"}),
          evaluated=len(parse.VIOLENCIA_COLUMNS))
    r.add("K7", "Consistencia", "Sin saltos bruscos de un mes a otro en las series por modalidad", "alerta", len(breaks),
          evaluated=len(series) * 7,
          detail="Saltos de más de 20 % en modalidades de más de 1 000 denuncias al mes, fuera de la pandemia; "
                 "ver reports/calidad/rupturas.csv")
    r.add("K8", "Consistencia", "Sin celdas distrito-modalidad-mes muy altas frente a su propia historia", "alerta",
          len(outliers), evaluated=len(den), detail="z robusto sobre el logaritmo; ver atipicos.csv")

    # Exactitud
    for validation, group in checks.groupby("validacion"):
        label = {"V1": "violencia contra la mujer idéntica en ambos archivos", "V3": "población de los distritos suma la nacional"}.get(
            validation, f"{group['medida'].iloc[0]} frente al indicador oficial")
        fails = int(group["resultado"].eq("falla").sum())
        warns = int(group["resultado"].eq("alerta").sum())
        severity = "bloqueante" if fails or not warns else "alerta"
        gap = group["diferencia_pct"].abs()
        if group["resultado"].eq("info").all():
            r.add("E", "Exactitud", f"{validation}: {label}", "info", len(group), evaluated=len(group),
                  detail=f"diferencia de {group['diferencia_pct'].max():.1f} % a {group['diferencia_pct'].min():.1f} % según el año (no es una prueba; se explica en 02_calidad.md)")
        else:
            r.add("E", "Exactitud", f"{validation}: {label}", severity, fails + warns, evaluated=len(group),
                  detail=f"diferencia absoluta máxima {gap.max():.3f} %"
                         + ("; 2026 queda corto de población distrital (se imputa en la Fase 3)" if warns else ""))

    # Oportunidad
    last_month_end = pd.Timestamp(config.END[0], config.END[1], 1) + pd.offsets.MonthEnd(0)
    for name, date in PUBLICATION_DATES.items():
        lag = (pd.Timestamp(date) - last_month_end).days
        r.add("O1", "Oportunidad", f"Publicación a menos de 30 días del cierre: {name}", "alerta", int(lag > 30),
              evaluated=1, detail=f"publicado el {date}, {lag} días después de cerrar julio de 2026")
    r.add("O2", "Oportunidad", "El último año está completo", "info", 1, evaluated=1,
          detail="2026 llega a julio: las comparaciones usan enero–julio de cada año")
    return r.table()


# ---------------------------------------------------------------------------------------------

def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    config.QUALITY.mkdir(parents=True, exist_ok=True)
    den, vio, ind = parse.read_denuncias(), parse.read_violencia(), parse.read_indicadores()
    pop = parse.population(ind)
    series = monthly_series(den)
    breaks, outliers = detect_breaks(series), detect_outliers(den)
    checks = validate.compare_all(den, vio, ind, pop)
    rules = run_rules(den, vio, ind, pop, series, breaks, outliers, checks)

    profile_columns().to_csv(config.QUALITY / "perfilado_columnas.csv", index=False)
    profile_months(den).to_csv(config.QUALITY / "perfilado_mensual.csv", index=False)
    rules.to_csv(config.QUALITY / "reglas.csv", index=False)
    breaks.to_csv(config.QUALITY / "rupturas.csv", index=False)
    outliers.to_csv(config.QUALITY / "atipicos.csv", index=False)
    ubigeo_problems(den, pop).to_csv(config.QUALITY / "ubigeo_problemas.csv", index=False)
    population_coverage(den, pop).to_csv(config.QUALITY / "cobertura_poblacion.csv", index=False)
    checks.to_csv(config.REPORTS / "validaciones.csv", index=False)

    print(f"Denuncias: {len(den):,} filas, {den['cantidad'].sum():,} denuncias")
    print(rules.groupby(["dimension", "resultado"]).size().unstack(fill_value=0).to_string())
    print(f"Rupturas: {len(breaks)} · atípicos: {len(outliers)}")
    failed = rules[rules["resultado"] == "falla"]
    for row in failed.itertuples():
        print(f"  ✗ {row.id} {row.regla}: {row.fallan} de {row.evaluadas}")
    return 1 if len(failed) else 0


if __name__ == "__main__":
    sys.exit(main())
