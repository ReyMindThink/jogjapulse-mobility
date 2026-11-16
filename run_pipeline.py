"""Jalankan seluruh pipeline: python run_pipeline.py [--skip-ingest]

  1. ingest     : unduh dataset Zenodo + verifikasi MD5            -> data/raw/        (bronze)
  2. external   : kalender PPKM/libur (sumber data ke-2)           -> data/external/
  3. warehouse  : load bertipe + transformasi SQL di DuckDB         -> data/warehouse.duckdb (silver+gold)
  4. quality    : uji kualitas data (k-anonymity, PK, rentang, join) -> outputs/tables/quality_report.csv
  5. analysis   : statistik untuk Q1-Q4                             -> outputs/tables/
  6. visualize  : 7 gambar 16:9                                    -> outputs/figures/
"""
import subprocess, sys, time
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
STEPS = ["ingest", "build_calendar", "warehouse", "quality", "analysis", "visualize"]
# build_boundaries.py tidak dijalankan otomatis: hasilnya (kapanewon_diy.geojson) sudah ada di repo.

skip = {"ingest"} if "--skip-ingest" in sys.argv else set()
for step in STEPS:
    if step in skip:
        continue
    t = time.time()
    print(f"\n=== {step} ===", flush=True)
    r = subprocess.run([sys.executable, f"{step}.py"], cwd=SRC)
    if r.returncode:
        sys.exit(f"Tahap '{step}' gagal (kode {r.returncode}) - pipeline berhenti.")
    print(f"--- {step} selesai ({time.time() - t:.1f} dtk)")
print("\nPipeline selesai. Lihat outputs/")
