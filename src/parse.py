"""Lectura de los archivos de datos abiertos y reglas de limpieza a nivel de campo.

Cada función resuelve un problema del catálogo de la Fase 2 (docs/02_calidad.md); el número del
problema va en el comentario. La Fase 2 las usa para medir la calidad y la Fase 3 para construir
el modelo, así que las dos fases aplican exactamente las mismas reglas.
"""

import pandas as pd

from src import config

# Nombre en el archivo -> nombre en el proyecto
DENUNCIAS_COLUMNS = {
    "ANIO": "anio", "MES": "mes", "DPTO_HECHO_NEW": "departamento_fuente", "PROV_HECHO": "provincia",
    "DIST_HECHO": "distrito", "UBIGEO_HECHO": "ubigeo_original", "P_MODALIDADES": "modalidad",
    "cantidad": "cantidad",
}
# El archivo de violencia usa otro orden y otras mayúsculas (problema 6)
VIOLENCIA_COLUMNS = {
    "PROV_HECHO": "provincia", "DIST_HECHO": "distrito", "UBIGEO_HECHO": "ubigeo_original", "AÑO": "anio",
    "MES": "mes", "DPTO_HECHO": "departamento_fuente", "CANTIDAD": "cantidad",
}
MODALIDAD_VIOLENCIA = "Violencia contra la mujer e integrantes"
LIMA_METROPOLITANA = "LIMA METROPOLITANA"
REGION_LIMA = "REGION LIMA"
# Indicadores oficiales SIDPOL que se contrastan con el archivo principal (diccionario oficial)
INDICATOR_EXTORTION = 7
INDICATOR_PATRIMONY = 2
INDICATOR_KIDNAPPING = 8


def pad_ubigeo(values: pd.Series) -> pd.Series:
    """Problema 1: el archivo guarda el UBIGEO como número y pierde el cero inicial (10202 por 010202)."""
    return values.astype("string").str.strip().str.zfill(6)


def department_key(ubigeo: pd.Series, source_name: pd.Series) -> pd.Series:
    """Clave del departamento, la misma que usa el archivo de indicadores para el ámbito regional.

    Problema 3: Lima viene partida en 'LIMA METROPOLITANA' (1501) y 'REGION LIMA' (1599); los demás
    departamentos usan el código oficial sin cero inicial ('1' = Amazonas).
    """
    key = ubigeo.str[:2].astype(int).astype("string")
    key = key.mask(source_name == LIMA_METROPOLITANA, "1501").mask(source_name == REGION_LIMA, "1599")
    return key


def read_denuncias() -> pd.DataFrame:
    df = pd.read_csv(config.RAW / "denuncias.csv", dtype={"UBIGEO_HECHO": "string"})
    return finish(df.rename(columns=DENUNCIAS_COLUMNS))


def read_violencia() -> pd.DataFrame:
    df = pd.read_csv(config.RAW / "violencia_mujer.csv", dtype={"UBIGEO_HECHO": "string"})
    df = finish(df.rename(columns=VIOLENCIA_COLUMNS))
    df["modalidad"] = MODALIDAD_VIOLENCIA
    return df


def finish(df: pd.DataFrame) -> pd.DataFrame:
    """Textos sin espacios en los extremos, UBIGEO de 6 dígitos y clave de departamento."""
    for col in ["departamento_fuente", "provincia", "distrito"]:
        df[col] = df[col].astype("string").str.strip()
    df["ubigeo"] = pad_ubigeo(df["ubigeo_original"])
    df["ubigeo_con_cero_agregado"] = df["ubigeo_original"].astype("string").str.len().lt(6)
    df["departamento_id"] = department_key(df["ubigeo"], df["departamento_fuente"])
    return df


def read_indicadores() -> pd.DataFrame:
    df = pd.read_csv(config.RAW / "indicadores.csv", dtype={"UBIGEO_DASH": "string"})
    return df.rename(columns={"UBIGEO_DASH": "ubigeo_original", "ANIO": "anio", "AMBITO": "ambito",
                              "INDICADOR": "indicador", "FUENTE": "fuente"})


def population(indicators: pd.DataFrame) -> dict:
    """Población proyectada por territorio y año.

    Problema 5: cada indicador repite la población del territorio, así que sumarla directamente la
    inflaría. Se toma un valor por (ámbito, territorio, año), uniendo todas las fuentes: con las de
    SIDPOL solas faltan distritos que otras fuentes sí cubren.
    """
    unique = (indicators.groupby(["ambito", "ubigeo_original", "anio"], as_index=False)
              ["POBLACION_PROYECTADA"].first())
    out = {}
    for ambito, name in [(0, "nacional"), (1, "departamento"), (2, "provincia"), (3, "distrito")]:
        part = unique[unique["ambito"] == ambito].drop(columns="ambito").rename(
            columns={"POBLACION_PROYECTADA": "poblacion"})
        if ambito == 3:
            part["ubigeo"] = pad_ubigeo(part["ubigeo_original"])
        out[name] = part.reset_index(drop=True)
    return out
