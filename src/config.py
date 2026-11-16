"""Konfigurasi bersama untuk seluruh pipeline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"            # bronze: file asli dari Zenodo (tidak diubah)
EXTERNAL = ROOT / "data" / "external"  # sumber data ke-2: kalender kebijakan + batas wilayah
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"  # silver + gold
FIG = ROOT / "outputs" / "figures"
TAB = ROOT / "outputs" / "tables"

ZENODO_RECORD = "23157460"
START, END = "2021-12-01", "2022-04-30"

# Jumlah baris menurut README (bagian 2) -> dipakai di quality check
EXPECTED_ROWS = {
    "presence_cell500m_daily.csv": 183_548,
    "presence_kapanewon_hourly.csv": 230_418,
    "home_maids_vs_population_kapanewon.csv": 78,
    "validation_night_presence_kapanewon.csv": 156,
    "od_home_visits_kapanewon_monthly.csv": 9_894,
    "od_origin_homes_monthly.csv": 390,
}

# Hari bermasalah yang disebut README bagian 6
ANOMALY_DATES = ["2022-03-08"]          # drop satu hari (masalah pengiriman data)
PANEL_BREAKS = ["2022-01-01", "2022-02-16"]  # perubahan mendadak ukuran sampel perangkat

# Definisi jendela waktu
NIGHT_HOURS = list(range(0, 6))    # 00-05 WIB, sama dengan validasi README
DAY_HOURS = list(range(9, 17))     # 09-16 WIB, jam kerja/kuliah

# Titik wisata untuk analisis Nataru (lon, lat) -> dicocokkan ke sel 500 m terdekat (radius 1 km)
TOURISM_SITES = {
    "Malioboro": (110.3655, -7.7926),
    "Pantai Parangtritis": (110.3290, -8.0250),
    "Baron-Kukup (GK)": (110.5490, -8.1290),
    "Candi Prambanan": (110.4914, -7.7520),
    "Tugu Jogja": (110.3671, -7.7829),
}
