"""TAHAP 4 - DATA QUALITY CHECKS.
Setiap aturan diuji terhadap warehouse; hasil disimpan ke outputs/tables/quality_report.csv.
Aturan diambil dari README dataset (jumlah baris, k=5, rentang tanggal/jam, 78 kapanewon)."""
import os
import duckdb, pandas as pd
from config import WAREHOUSE, TAB, EXPECTED_ROWS, START, END

STRICT_ROWS = os.environ.get("JP_RAW") is None  # data sintetis tidak punya jumlah baris yang sama

CHECKS = [
    # (nama, SQL yang mengembalikan jumlah PELANGGARAN, keterangan)
    ("hourly: n_maids >= 5 (k-anonymity)", "SELECT COUNT(*) FROM s_kap_hourly WHERE n_maids < 5", "README bag. 5"),
    ("cell: n_maids >= 5 (k-anonymity)", "SELECT COUNT(*) FROM s_cell_daily WHERE n_maids < 5", "README bag. 5"),
    ("od: n_maids >= 5 (k-anonymity)", "SELECT COUNT(*) FROM s_od WHERE n_maids < 5", "README bag. 5"),
    ("hourly: jam 0-23", "SELECT COUNT(*) FROM s_kap_hourly WHERE hour NOT BETWEEN 0 AND 23", "README 4.2"),
    ("hourly: tanggal dalam periode", f"SELECT COUNT(*) FROM s_kap_hourly WHERE date NOT BETWEEN '{START}' AND '{END}'", ""),
    ("cell: tanggal dalam periode", f"SELECT COUNT(*) FROM s_cell_daily WHERE date NOT BETWEEN '{START}' AND '{END}'", ""),
    ("hourly: tidak ada duplikat (kapanewon,date,hour)",
     "SELECT COUNT(*) FROM (SELECT kapanewon_code,date,hour FROM s_kap_hourly GROUP BY ALL HAVING COUNT(*)>1)", "primary key"),
    ("cell: tidak ada duplikat (cell,date)",
     "SELECT COUNT(*) FROM (SELECT cell_id,date FROM s_cell_daily GROUP BY ALL HAVING COUNT(*)>1)", "primary key"),
    ("hourly: n_pings >= n_maids", "SELECT COUNT(*) FROM s_kap_hourly WHERE n_pings < n_maids", "logika: 1 perangkat >= 1 ping"),
    ("dimensi: 78 kapanewon", "SELECT ABS(COUNT(*) - 78) FROM dim_kapanewon", "README 4.2"),
    ("join peta: semua kapanewon punya poligon", "SELECT COUNT(*) FROM dim_kapanewon WHERE kode_bps IS NULL",
     "jika gagal: tambah alias di keys.py"),
    ("kalender: 151 hari tanpa celah", "SELECT ABS(COUNT(*) - 151) FROM s_calendar", ""),
    ("hourly: setiap tanggal punya data", f"SELECT 151 - COUNT(DISTINCT date) FROM s_kap_hourly", ""),
    # integritas referensial star schema (fakta -> dimensi)
    ("FK fact_presence_hourly -> dim_kapanewon",
     "SELECT COUNT(*) FROM fact_presence_hourly f LEFT JOIN dim_kapanewon d USING(kapanewon_code) WHERE d.kapanewon_code IS NULL", "star schema"),
    ("FK fact_presence_hourly -> dim_date",
     "SELECT COUNT(*) FROM fact_presence_hourly f LEFT JOIN dim_date d USING(date) WHERE d.date IS NULL", "star schema"),
    ("FK fact_presence_cell_daily -> dim_cell",
     "SELECT COUNT(*) FROM fact_presence_cell_daily f LEFT JOIN dim_cell d USING(cell_id) WHERE d.cell_id IS NULL", "star schema"),
    ("FK fact_od_monthly -> dim_kapanewon (asal & tujuan)",
     "SELECT COUNT(*) FROM fact_od_monthly f LEFT JOIN dim_kapanewon o ON o.kapanewon_code=f.origin_code "
     "LEFT JOIN dim_kapanewon d ON d.kapanewon_code=f.dest_code WHERE o.kapanewon_code IS NULL OR d.kapanewon_code IS NULL", "star schema"),
    ("dim_cell: setiap sel terpetakan ke kapanewon",
     "SELECT COUNT(*) FROM dim_cell WHERE kapanewon_code IS NULL", "spatial join, radius 1 km"),
    ("od: setiap origin punya denominator",
     "SELECT COUNT(*) FROM s_od o LEFT JOIN s_od_origin g USING(month, origin_code) WHERE g.n_homed_maids IS NULL", ""),
]
ROWS = {"presence_kapanewon_hourly.csv": "s_kap_hourly", "presence_cell500m_daily.csv": "s_cell_daily",
        "od_home_visits_kapanewon_monthly.csv": "s_od", "od_origin_homes_monthly.csv": "s_od_origin",
        "home_maids_vs_population_kapanewon.csv": "s_home_pop"}


def main():
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    out = []
    for name, sql, note in CHECKS:
        v = con.execute(sql).fetchone()[0]
        out.append({"check": name, "violations": int(v), "status": "PASS" if v == 0 else "FAIL", "note": note})
    for f, t in ROWS.items():
        n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        v = abs(n - EXPECTED_ROWS[f])
        out.append({"check": f"jumlah baris {f} = README ({EXPECTED_ROWS[f]:,})", "violations": v,
                    "status": "PASS" if v == 0 else ("FAIL" if STRICT_ROWS else "SKIP (sintetis)"), "note": f"aktual {n:,}"})
    miss = con.execute("SELECT kab_kota, kapanewon FROM dim_kapanewon WHERE kode_bps IS NULL").df()
    con.close()
    rep = pd.DataFrame(out)
    TAB.mkdir(parents=True, exist_ok=True)
    rep.to_csv(TAB / "quality_report.csv", index=False)
    print(rep.to_string(index=False))
    if len(miss):
        print("\nKapanewon tanpa poligon (perlu alias di keys.py):\n", miss.to_string(index=False))
    n_fail = (rep.status == "FAIL").sum()
    print(f"\n{len(rep) - n_fail}/{len(rep)} check lolos")
    return n_fail


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
