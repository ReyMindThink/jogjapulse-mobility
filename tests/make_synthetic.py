"""Data SINTETIS berskema identik dengan JogjaPulse - HANYA untuk menguji pipeline.
Jangan pernah dipakai untuk analisis/laporan."""
import sys, numpy as np, pandas as pd, geopandas as gpd
from pathlib import Path

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(0)
kap = gpd.read_file(Path(__file__).resolve().parents[1] / "data/external/kapanewon_diy.geojson")
kabmap = {"Kulon Progo": ("34.01", "KULON PROGO"), "Bantul": ("34.02", "BANTUL"),
          "Gunung Kidul": ("34.03", "GUNUNGKIDUL"), "Sleman": ("34.04", "SLEMAN"),
          "Kota Yogyakarta": ("34.71", "YOGYAKARTA")}
K = pd.DataFrame({"kab_code": [kabmap[r][0] for r in kap.regency], "kab_kota": [kabmap[r][1] for r in kap.regency],
                  "kapanewon": [d.upper().replace(" ", "") for d in kap.district]})
K["kapanewon_code"] = K.kab_code + "." + (K.groupby("kab_code").cumcount() + 1).map("{:02d}".format)
K["w"] = rng.lognormal(0, 1, len(K)) * np.where(K.kab_kota == "YOGYAKARTA", 3, 1)
K["day_mult"] = np.where(K.kab_kota == "YOGYAKARTA", 1.8, rng.uniform(0.6, 1.3, len(K)))
dates = pd.date_range("2021-12-01", "2022-04-30")
panel = np.where(dates < "2022-01-01", 87000, np.where(dates < "2022-02-16", 45000, 20000)) * np.linspace(1, .5, len(dates))
panel[dates == "2022-03-08"] *= .3
diurnal = np.array([.25, .2, .18, .17, .2, .35, .55, .7, .8, .85, .9, .95, 1, 1, 1, .98, .97, 1, 1, 1, .95, .8, .6, .4])

rows = []
for di, d in enumerate(dates):
    for h in range(24):
        isday = 9 <= h <= 16
        lam = panel[di] * .004 * diurnal[h] * K.w * np.where(isday, K.day_mult, 1)
        n = rng.poisson(lam)
        rows.append(pd.DataFrame({"kab_code": K.kab_code, "kab_kota": K.kab_kota, "kapanewon_code": K.kapanewon_code,
                                  "kapanewon": K.kapanewon, "date": d.strftime("%Y-%m-%d"), "hour": h,
                                  "n_maids": n, "n_pings": n * rng.integers(2, 8, len(K))}))
H = pd.concat(rows); H = H[H.n_maids >= 5]
H.to_csv(out / "presence_kapanewon_hourly.csv", index=False)

# sel 500 m: ambil titik acak di dalam DIY
pts = kap.to_crs(32749).sample_points(60, rng=1).explode().reset_index(drop=True)
xs = (pts.x // 500).astype(int); ys = (pts.y // 500).astype(int)
cells = pd.DataFrame({"i": xs, "j": ys}).drop_duplicates()
cells["x_min_utm"] = cells.i * 500; cells["y_min_utm"] = cells.j * 500
cg = gpd.GeoSeries.from_xy(cells.x_min_utm + 250, cells.y_min_utm + 250, crs=32749).to_crs(4326)
cells["centroid_lon"] = cg.x.round(6).values; cells["centroid_lat"] = cg.y.round(6).values
cells["cell_id"] = "E" + cells.i.astype(str) + "_N" + cells.j.astype(str)
cells["w"] = rng.lognormal(0, 1.2, len(cells))
mal = (abs(cells.centroid_lon - 110.3655) < .01) & (abs(cells.centroid_lat + 7.7926) < .01)
crow = []
for di, d in enumerate(dates):
    boost = 3 if pd.Timestamp("2021-12-24") <= d <= pd.Timestamp("2022-01-02") else 1
    n = rng.poisson(panel[di] * .0002 * cells.w * np.where(mal, boost, 1))
    crow.append(pd.DataFrame({**{c: cells[c] for c in ["cell_id", "x_min_utm", "y_min_utm", "centroid_lon", "centroid_lat"]},
                              "date": d.strftime("%Y-%m-%d"), "n_maids": n}))
C = pd.concat(crow); C = C[C.n_maids >= 5]
C.to_csv(out / "presence_cell500m_daily.csv", index=False)

# OD bulanan
od, org = [], []
for m, sc in zip(["2021-12", "2022-01", "2022-02", "2022-03", "2022-04"], [1, .6, .4, .2, .1]):
    homes = (K.w * 2000 * sc).astype(int)
    for i, o in K.iterrows():
        org.append({"month": m, "origin_kab_code": o.kab_code, "origin_kab_kota": o.kab_kota, "origin_code": o.kapanewon_code,
                    "origin_kapanewon": o.kapanewon, "n_homed_maids": homes[i], "n_homed_maids_daytime": int(homes[i] * .9),
                    "reduced_quality": m >= "2022-03"})
        flow = rng.poisson(homes[i] * .3 * K.w * K.day_mult / K.w.sum())
        flow[i] = int(homes[i] * .85)
        for j, dd in K.iterrows():
            if flow[j] >= 5:
                od.append({"month": m, "origin_kab_code": o.kab_code, "origin_kab_kota": o.kab_kota, "origin_code": o.kapanewon_code,
                           "origin_kapanewon": o.kapanewon, "dest_kab_code": dd.kab_code, "dest_kab_kota": dd.kab_kota,
                           "dest_code": dd.kapanewon_code, "dest_kapanewon": dd.kapanewon, "n_maids": flow[j],
                           "reduced_quality": m >= "2022-03"})
pd.DataFrame(od).to_csv(out / "od_home_visits_kapanewon_monthly.csv", index=False)
pd.DataFrame(org).to_csv(out / "od_origin_homes_monthly.csv", index=False)
hp = pd.DataFrame({"KAB_KOTA": K.kab_kota, "KEC_KAPN": K.kapanewon, "n_users": (K.w * 5000).astype(int),
                   "pop_actual": (K.w * 40000).round()})
hp["ratio"] = hp.n_users / hp.pop_actual
hp.to_csv(out / "home_maids_vs_population_kapanewon.csv", index=False)
print("synthetic:", len(H), "hourly rows,", len(C), "cell rows,", len(od), "od rows")
