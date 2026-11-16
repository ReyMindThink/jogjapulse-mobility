"""TAHAP 2-3 - LOAD (silver) & TRANSFORM (gold) di DuckDB.

silver (staging) : tabel bertipe tegas (kode wilayah sebagai TEXT, tanggal sebagai DATE).
storage (core)   : star schema / fact constellation -> dim_date, dim_kapanewon, dim_cell,
                   fact_presence_hourly, fact_presence_cell_daily, fact_od_monthly.
gold (presentasi): cuboid termaterialisasi (partial materialization), siap-analisis. SEMUA ukuran dinormalisasi (porsi terhadap total DIY pada jam/hari yang sama)
        karena ukuran sampel perangkat berubah drastis sepanjang periode (README bag. 6.1).
"""
import os
from pathlib import Path
import duckdb, pandas as pd, geopandas as gpd
from config import RAW, EXTERNAL, WAREHOUSE, NIGHT_HOURS, DAY_HOURS, TOURISM_SITES
from keys import kap_key

RAW = Path(os.environ.get("JP_RAW", RAW))  # bisa diarahkan ke data sintetis untuk tes


def build(con):
    r = lambda f: str(RAW / f)
    # ---------------- SILVER ----------------
    con.execute(f"""
    CREATE OR REPLACE TABLE s_kap_hourly AS
    SELECT kab_code, kab_kota, kapanewon_code, kapanewon, CAST(date AS DATE) AS date,
           CAST(hour AS INT) AS hour, CAST(n_maids AS INT) AS n_maids, CAST(n_pings AS BIGINT) AS n_pings
    FROM read_csv('{r("presence_kapanewon_hourly.csv")}', header=true, all_varchar=true);

    CREATE OR REPLACE TABLE s_cell_daily AS
    SELECT cell_id, CAST(x_min_utm AS INT) x_min_utm, CAST(y_min_utm AS INT) y_min_utm,
           CAST(centroid_lon AS DOUBLE) lon, CAST(centroid_lat AS DOUBLE) lat,
           CAST(date AS DATE) date, CAST(n_maids AS INT) n_maids
    FROM read_csv('{r("presence_cell500m_daily.csv")}', header=true, all_varchar=true);

    CREATE OR REPLACE TABLE s_od AS
    SELECT month, origin_code, origin_kab_kota, origin_kapanewon, dest_code, dest_kab_kota, dest_kapanewon,
           CAST(n_maids AS INT) n_maids, CAST(reduced_quality AS BOOLEAN) reduced_quality
    FROM read_csv('{r("od_home_visits_kapanewon_monthly.csv")}', header=true, all_varchar=true);

    CREATE OR REPLACE TABLE s_od_origin AS
    SELECT month, origin_code, CAST(n_homed_maids AS INT) n_homed_maids,
           TRY_CAST(n_homed_maids_daytime AS INT) n_homed_maids_daytime
    FROM read_csv('{r("od_origin_homes_monthly.csv")}', header=true, all_varchar=true);

    CREATE OR REPLACE TABLE s_home_pop AS
    SELECT KAB_KOTA kab_kota, KEC_KAPN kapanewon, CAST(n_users AS INT) n_users,
           CAST(pop_actual AS DOUBLE) pop_actual
    FROM read_csv('{r("home_maids_vs_population_kapanewon.csv")}', header=true, all_varchar=true);

    CREATE OR REPLACE TABLE s_calendar AS
    SELECT CAST(date AS DATE) date, CAST(ppkm_level AS INT) ppkm_level, libur_nasional,
           CAST(is_libur AS BOOLEAN) is_libur, CAST(periode_nataru AS BOOLEAN) periode_nataru,
           CAST(periode_ramadan AS BOOLEAN) periode_ramadan, CAST(is_anomali AS BOOLEAN) is_anomali,
           CAST(panel_segment AS INT) panel_segment, hari
    FROM read_csv('{EXTERNAL / "kalender_kebijakan_diy.csv"}', header=true, all_varchar=true);
    """)

    # dimensi wilayah: kode JogjaPulse <-> poligon HDX (join lewat nama yang dinormalisasi)
    dim = con.execute("SELECT DISTINCT kab_code, kab_kota, kapanewon_code, kapanewon FROM s_kap_hourly").df()
    dim["kap_key"] = [kap_key(a, b) for a, b in zip(dim.kab_kota, dim.kapanewon)]
    geo = gpd.read_file(EXTERNAL / "kapanewon_diy.geojson")[["kap_key", "kode_bps", "luas_km2"]]
    dim = dim.merge(geo, on="kap_key", how="left")
    dim["is_kota"] = dim.kab_kota.str.upper().eq("YOGYAKARTA")
    con.register("dim_df", dim)
    con.execute("CREATE OR REPLACE TABLE dim_kapanewon AS SELECT * FROM dim_df")

    # ---------------- STORAGE: STAR SCHEMA (fact constellation / galaxy) ----------------
    # 3 tabel fakta berbagi dimensi dim_date & dim_kapanewon (materi: "Fact Constellations")
    con.execute("""
    CREATE OR REPLACE TABLE dim_date AS
    SELECT date, year(date) AS tahun, month(date) AS bulan, strftime(date, '%Y-%m') AS bulan_key,
           CAST(week(date) AS INT) AS minggu, hari, dayofweek(date) IN (0, 6) AS is_weekend,
           is_libur, libur_nasional, ppkm_level, periode_nataru, periode_ramadan, is_anomali, panel_segment
    FROM s_calendar;

    CREATE OR REPLACE TABLE fact_presence_hourly AS      -- grain: kapanewon x tanggal x jam
    SELECT kapanewon_code, date, hour, n_maids, n_pings FROM s_kap_hourly;

    CREATE OR REPLACE TABLE fact_od_monthly AS           -- grain: asal x tujuan x bulan
    SELECT month AS bulan_key, origin_code, dest_code, n_maids, reduced_quality FROM s_od;
    """)
    # dim_cell: hierarki sel 500 m -> kapanewon -> kabupaten lewat spatial join titik tengah sel
    cells = con.execute("SELECT DISTINCT cell_id, x_min_utm, y_min_utm, lon, lat FROM s_cell_daily").df()
    pts = gpd.GeoDataFrame(cells, geometry=gpd.points_from_xy(cells.lon, cells.lat), crs=4326).to_crs(32749)
    poly = gpd.read_file(EXTERNAL / "kapanewon_diy.geojson")[["kode_bps", "geometry"]].to_crs(32749)
    j = gpd.sjoin_nearest(pts, poly, how="left", max_distance=1000).drop_duplicates("cell_id")
    code = con.execute("SELECT kode_bps, kapanewon_code FROM dim_kapanewon").df()
    dc = j.drop(columns=["geometry", "index_right"]).merge(code, on="kode_bps", how="left")
    con.register("dim_cell_df", dc)
    con.execute("""
    CREATE OR REPLACE TABLE dim_cell AS SELECT cell_id, x_min_utm, y_min_utm, lon, lat, kapanewon_code FROM dim_cell_df;
    CREATE OR REPLACE TABLE fact_presence_cell_daily AS  -- grain: sel 500 m x tanggal
    SELECT cell_id, date, n_maids FROM s_cell_daily;
    """)
    con.unregister("dim_df"); con.unregister("dim_cell_df")

    # ---------------- GOLD ----------------
    night, day = ",".join(map(str, NIGHT_HOURS)), ",".join(map(str, DAY_HOURS))
    con.execute(f"""
    -- G1. ringkasan harian: ukuran panel + kalender (untuk menunjukkan masalah sampel)
    CREATE OR REPLACE TABLE g_daily AS
    WITH h AS (SELECT date, SUM(n_maids) device_hours, SUM(n_pings) pings, COUNT(*) kap_hours_published
               FROM fact_presence_hourly GROUP BY date),
         c AS (SELECT date, SUM(n_maids) device_cells, COUNT(*) cells_published FROM fact_presence_cell_daily GROUP BY date)
    SELECT k.*, h.device_hours, h.pings, h.kap_hours_published, c.device_cells, c.cells_published
    FROM s_calendar k LEFT JOIN h USING(date) LEFT JOIN c USING(date) ORDER BY date;

    -- G2. porsi kehadiran tiap kapanewon pada jam yang sama (normalisasi utama)
    CREATE OR REPLACE TABLE g_kap_hour_share AS
    SELECT h.*, n_maids * 1.0 / SUM(n_maids) OVER (PARTITION BY date, hour) AS share,
           n_pings * 1.0 / n_maids AS pings_per_device
    FROM fact_presence_hourly h;

    -- G3. indeks penarik siang (day/night): porsi siang / porsi malam, hari kerja normal saja
    CREATE OR REPLACE TABLE g_attractor AS
    WITH base AS (
      SELECT s.*, k.ppkm_level, k.panel_segment
      FROM g_kap_hour_share s JOIN s_calendar k USING(date)
      WHERE NOT k.is_libur AND NOT k.is_anomali AND NOT k.periode_nataru),
    agg AS (
      SELECT kapanewon_code, ppkm_level,
             AVG(share) FILTER (WHERE hour IN ({day}))   AS day_share,
             AVG(share) FILTER (WHERE hour IN ({night})) AS night_share,
             COUNT(*)   FILTER (WHERE hour IN ({night})) AS night_slots
      FROM base GROUP BY ALL
      UNION ALL
      SELECT kapanewon_code, 0 AS ppkm_level,   -- 0 = seluruh periode
             AVG(share) FILTER (WHERE hour IN ({day})), AVG(share) FILTER (WHERE hour IN ({night})),
             COUNT(*)   FILTER (WHERE hour IN ({night}))
      FROM base GROUP BY ALL)
    SELECT a.*, a.day_share / NULLIF(a.night_share, 0) AS attractor_index, d.kab_kota, d.kapanewon, d.kode_bps
    FROM agg a JOIN dim_kapanewon d USING(kapanewon_code);

    -- G4. profil jam harian DIY (dinormalisasi per hari: nilai jam / rata-rata jam hari itu)
    CREATE OR REPLACE TABLE g_hourly_profile AS
    WITH t AS (SELECT date, hour, SUM(n_maids) dh FROM fact_presence_hourly GROUP BY ALL),
         n AS (SELECT *, dh / AVG(dh) OVER (PARTITION BY date) AS rel FROM t)
    SELECT n.*, k.ppkm_level, k.panel_segment, k.is_libur, k.is_anomali, k.periode_nataru
    FROM n JOIN s_calendar k USING(date);

    -- G5. porsi siang Kota Yogyakarta (pusat aktivitas) per hari
    CREATE OR REPLACE TABLE g_core_share AS
    SELECT s.date, SUM(s.share) FILTER (WHERE d.is_kota) / COUNT(DISTINCT s.hour) AS kota_day_share,
           k.ppkm_level, k.panel_segment, k.is_libur, k.is_anomali, k.periode_nataru, k.hari
    FROM g_kap_hour_share s JOIN dim_kapanewon d USING(kapanewon_code) JOIN s_calendar k USING(date)
    WHERE s.hour IN ({day}) GROUP BY s.date, k.ppkm_level, k.panel_segment, k.is_libur, k.is_anomali,
                                    k.periode_nataru, k.hari ORDER BY s.date;

    -- G6. porsi harian tiap sel 500 m
    CREATE OR REPLACE TABLE g_cell_share AS
    SELECT f.*, c.lon, c.lat, n_maids * 1.0 / SUM(n_maids) OVER (PARTITION BY f.date) AS share
    FROM fact_presence_cell_daily f JOIN dim_cell c USING(cell_id);

    -- G7. OD: hanya Des 2021 - Feb 2022 (Mar-Apr reduced_quality, README bag. 6.6)
    CREATE OR REPLACE TABLE g_od AS
    SELECT f.bulan_key AS month, f.origin_code, o.kab_kota AS origin_kab_kota, o.kapanewon AS origin_kapanewon,
           f.dest_code, d.kab_kota AS dest_kab_kota, d.kapanewon AS dest_kapanewon, f.n_maids, f.reduced_quality,
           g.n_homed_maids, g.n_homed_maids_daytime, f.n_maids * 1.0 / g.n_homed_maids_daytime AS visit_prob
    FROM fact_od_monthly f
    JOIN dim_kapanewon o ON o.kapanewon_code = f.origin_code
    JOIN dim_kapanewon d ON d.kapanewon_code = f.dest_code
    JOIN s_od_origin g ON g.month = f.bulan_key AND g.origin_code = f.origin_code
    WHERE NOT f.reduced_quality AND f.origin_code <> f.dest_code;

    CREATE OR REPLACE TABLE g_od_attract AS
    SELECT month, dest_code, dest_kab_kota, dest_kapanewon,
           COUNT(*) AS n_origins, SUM(visit_prob) AS sum_visit_prob,
           SUM(n_maids) * 1.0 / SUM(SUM(n_maids)) OVER (PARTITION BY month) AS inflow_share
    FROM g_od GROUP BY month, dest_code, dest_kab_kota, dest_kapanewon;
    """)

    # G8. titik wisata: sel dalam radius 1 km dari koordinat situs
    cells = con.execute("SELECT cell_id, lon, lat FROM dim_cell").df()
    g = gpd.GeoDataFrame(cells, geometry=gpd.points_from_xy(cells.lon, cells.lat), crs=4326).to_crs(32749)
    rows = []
    for name, (lon, lat) in TOURISM_SITES.items():
        p = gpd.GeoSeries.from_xy([lon], [lat], crs=4326).to_crs(32749).iloc[0]
        for cid in g.loc[g.distance(p) <= 1000, "cell_id"]:
            rows.append({"site": name, "cell_id": cid})
    con.register("site_df", pd.DataFrame(rows, columns=["site", "cell_id"]))
    con.execute("""
    CREATE OR REPLACE TABLE g_site_share AS
    SELECT s.site, c.date, SUM(c.share) AS share, COUNT(*) AS cells_published,
           k.ppkm_level, k.periode_nataru, k.is_libur, k.is_anomali, k.panel_segment, k.hari
    FROM site_df s JOIN g_cell_share c USING(cell_id) JOIN s_calendar k ON k.date = c.date
    GROUP BY ALL ORDER BY s.site, c.date;
    """)


def main():
    WAREHOUSE.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(WAREHOUSE))
    build(con)
    for (t,) in con.execute("SELECT table_name FROM information_schema.tables ORDER BY 1").fetchall():
        print(f"{t:22s} {con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]:>9,} baris")
    con.close()


if __name__ == "__main__":
    main()
