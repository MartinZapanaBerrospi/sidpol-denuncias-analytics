"""Parámetros del proyecto: periodo, fuentes, rutas y reglas."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
DOWNLOADS = RAW / "descarga"      # zips bajados desde el navegador
STAGING = DATA / "staging"
CURATED = DATA / "curated"
REFERENCE = DATA / "reference"
SOURCES = ROOT / "docs" / "fuentes"
REPORTS = ROOT / "reports"
QUALITY = REPORTS / "calidad"
MANIFEST = RAW / "manifest.csv"
PORTAL_INVENTORY = REFERENCE / "inventario_portal.csv"

# Periodo de análisis (inclusive). El conjunto principal llega hasta el último mes cerrado.
START = (2018, 1)
END = (2026, 7)

PORTAL = "https://www.datosabiertos.gob.pe"
FILE_URL = PORTAL + "/sites/default/files/{name}"
DOWNLOAD_URLS = {   # zip con todos los recursos del conjunto, que el portal arma al momento
    "denuncias": PORTAL + "/node/22156/dataset/download",
    "violencia": PORTAL + "/node/21199/dataset/download",
    "indicadores": PORTAL + "/node/23663/dataset/download",
}
DATASET_PAGES = {
    "denuncias": PORTAL + "/dataset/denuncias-policiales-registradas-nivel-nacional-mininter",
    "violencia": PORTAL + "/dataset/violencia-contra-la-mujer-y-los-integrantes-del-grupo-familiar-registrada-por-la-pnp",
    "indicadores": PORTAL + "/dataset/indicadores-de-seguridad-ciudadana-y-tendencias-territoriales-mininter",
}

# Qué se extrae de cada zip: (clave, zip bajado, ruta dentro del zip, nombre en el portal, destino)
# "ruta" es una lista cuando el archivo está dentro de un zip anidado.
SPEC = [
    ("denuncias", "sidpol_denuncias_2026-10-13.zip",
     ["DATASET_Denuncias_Policiales_Ene 2018 a Julio 2026.csv"],
     "DATASET_Denuncias_Policiales_Ene 2018 a Julio 2026.csv", RAW / "denuncias.csv"),
    ("violencia", "sidpol_violencia_mujer_2026-10-13.zip",
     ["DATASET_Viol_Cont_Muj_Ene 2018 a Jul 2026.csv"],
     "DATASET_Viol_Cont_Muj_Ene 2018 a Jul 2026.csv", RAW / "violencia_mujer.csv"),
    ("indicadores", "mininter_indicadores_2026-10-13.zip",
     ["DataSet_Ind_Plan_Acc_Segu_Ciud_Jul 2026.zip",
      "DataSet_Ind_Plan_Acc_Segu_Ciud_Jul 2026/DATASET_Ind_ Plan_Acc_Seg_Ciud_2009 a Jul 2026.csv"],
     "DataSet_Ind_Plan_Acc_Segu_Ciud_Jul 2026.zip", RAW / "indicadores.csv"),
    ("diccionario_denuncias", "sidpol_denuncias_2026-10-13.zip",
     ["DICCIONARIO_DATOS_Denuncias_Policiales_Abr 2026.xlsx"],
     "DICCIONARIO_DATOS_Denuncias_Policiales_Abr 2026.xlsx", SOURCES / "diccionario_denuncias.xlsx"),
    ("metadato_denuncias", "sidpol_denuncias_2026-10-13.zip",
     ["METADATO_Denuncias_Policiales_Julio 2026.docx"],
     "METADATO_Denuncias_Policiales_Julio 2026.docx", SOURCES / "metadato_denuncias.docx"),
    ("diccionario_violencia", "sidpol_violencia_mujer_2026-10-13.zip",
     ["DICIONARIO_DATOS_Violencia_Contra_la_Mujer.xlsx"],
     "DICIONARIO_DATOS_Violencia_Contra_la_Mujer.xlsx", SOURCES / "diccionario_violencia.xlsx"),
    ("metadato_violencia", "sidpol_violencia_mujer_2026-10-13.zip",
     ["METADATO_Viol_Cont_Muj-Feb 2026.docx"],
     "METADATO_Viol_Cont_Muj-Feb 2026.docx", SOURCES / "metadato_violencia.docx"),
    ("diccionario_indicadores", "mininter_indicadores_2026-10-13.zip",
     ["DICCIONAR_DATOS_ Ind_ Plan_Acc_Seg_Ciud_Jun 2026.xlsx"],
     "DICCIONAR_DATOS_ Ind_ Plan_Acc_Seg_Ciud_Jun 2026.xlsx", SOURCES / "diccionario_indicadores.xlsx"),
    ("metadato_indicadores", "mininter_indicadores_2026-10-13.zip",
     ["METADATO_ Ind_ Plan_Acc_Seg_Ciud_Nov 2025_0.docx"],
     "METADATO_ Ind_ Plan_Acc_Seg_Ciud_Nov 2025_0.docx", SOURCES / "metadato_indicadores.docx"),
]

# Reglas de negocio y tolerancias
VALID_MODALITIES = {"Otros", "Violencia contra la mujer e integrantes", "Hurto", "Robo", "Estafa",
                    "Extorsión", "Secuestro"}
RATE_BASE = 100_000
OUTLIER_IQR_FACTOR = 3
