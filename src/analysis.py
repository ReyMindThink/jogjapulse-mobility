"""TAHAP 5 - ANALISIS. Menjawab 4 pertanyaan penelitian dari tabel gold; hasil -> outputs/tables + findings.json.

Q1 Di mana orang beraktivitas siang hari? (indeks penarik siang/malam per kapanewon)
Q2 Apakah PPKM (level 2/3/4) sejalan dengan perubahan pola mobilitas?
   -> dibandingkan HANYA di dalam panel segmen 3 (16 Feb - 30 Apr) agar tidak tercampur
      perubahan sampel perangkat 1 Jan & 16 Feb (README bag. 6.1), + kontrol tren waktu.
Q3 Apakah libur Nataru menaikkan porsi kehadiran di titik wisata?
Q4 Kapanewon mana yang menjadi tujuan kunjungan dari wilayah lain? (OD Des-Feb)
"""
import json
import duckdb, numpy as np, pandas as pd
import statsmodels.formula.api as smf
from config import WAREHOUSE, TAB, NIGHT_HOURS

pd.set_option("display.width", 200)


def q0_panel(con):
    d = con.execute("""SELECT panel_segment, MIN(date) mulai, MAX(date) selesai,
                              ROUND(AVG(device_hours)) rata2_device_hours_per_hari
                       FROM g_daily WHERE NOT is_anomali GROUP BY 1 ORDER BY 1""").df()
    first, last = con.execute("""SELECT
        AVG(device_hours) FILTER (WHERE date < '2021-12-08'),
        AVG(device_hours) FILTER (WHERE date > '2022-04-23') FROM g_daily""").fetchone()
    return d, {"penurunan_panel_pct": round(100 * (1 - last / first), 1)}


def q1b_night_bias(con):
    """Uji: apakah ponsel di kota lebih aktif malam hari? Profil jam relatif per kabupaten/kota."""
    p = con.execute("""
        WITH b AS (SELECT s.hour, d.kab_kota, s.n_maids FROM g_kap_hour_share s JOIN dim_kapanewon d USING(kapanewon_code)
                   JOIN s_calendar k USING(date) WHERE NOT k.is_libur AND NOT k.is_anomali AND NOT k.periode_nataru)
        SELECT kab_kota, hour, SUM(n_maids) n FROM b GROUP BY ALL ORDER BY 1, 2""").df()
    p["rel"] = p.n / p.groupby("kab_kota").n.transform("mean")
    at2 = p[p.hour == 2].set_index("kab_kota").rel.round(2).to_dict()
    return p, {"aktivitas_relatif_jam_02": at2}


def q1_attractor(con):
    a = con.execute("""SELECT kab_kota, kapanewon, kode_bps, day_share, night_share, night_slots, attractor_index
                       FROM g_attractor WHERE ppkm_level = 0 ORDER BY attractor_index DESC""").df()
    max_slots = a.night_slots.max()
    a["night_coverage"] = a.night_slots / max_slots
    a["reliable"] = a.night_coverage >= 0.5   # sedikit slot malam terpublikasi -> indeks bias (README 6.5)
    r = a[a.reliable]
    return a, {"top5_penarik_siang": r.head(5)[["kapanewon", "kab_kota", "attractor_index"]].round(2).to_dict("records"),
               "top5_hunian": r.tail(5)[["kapanewon", "kab_kota", "attractor_index"]].round(2).to_dict("records"),
               "n_reliable": int(r.shape[0])}


def q2_ppkm(con):
    c = con.execute("""SELECT * FROM g_core_share
                       WHERE panel_segment = 3 AND NOT is_libur AND NOT is_anomali ORDER BY date""").df()
    c["t"] = (c.date - c.date.min()).dt.days
    m = smf.ols("kota_day_share ~ C(ppkm_level, Treatment(2)) + t", data=c).fit(cov_type="HC3")
    desc = c.groupby("ppkm_level").kota_day_share.agg(["mean", "count"]).reset_index()

    p = con.execute(f"""SELECT ppkm_level, hour, AVG(rel) rel FROM g_hourly_profile
                        WHERE panel_segment = 3 AND NOT is_libur AND NOT is_anomali GROUP BY ALL ORDER BY 1,2""").df()
    ev = con.execute("""WITH d AS (SELECT date, ppkm_level, SUM(rel) FILTER (WHERE hour BETWEEN 19 AND 23) / 24 ev
                        FROM g_hourly_profile WHERE panel_segment = 3 AND NOT is_libur AND NOT is_anomali GROUP BY ALL)
                        SELECT * FROM d ORDER BY date""").df()
    ev["t"] = (ev.date - ev.date.min()).dt.days
    m2 = smf.ols("ev ~ C(ppkm_level, Treatment(2)) + t", data=ev).fit(cov_type="HC3")

    def coefs(model):
        return {k.split("]")[0].split(".")[-1]: {"coef": round(v, 5), "p": round(model.pvalues[k], 4)}
                for k, v in model.params.items() if "ppkm" in k}
    f = {"kota_day_share_mean_by_level": desc.round(4).to_dict("records"),
         "ols_kota_share_vs_level2": coefs(m), "ols_kota_r2": round(m.rsquared, 3),
         "ols_evening_vs_level2": coefs(m2), "n_hari": int(len(c))}
    return c, p, ev, f


def q2b_aba(con):
    """Desain A-B-A: PPKM 3 -> 4 -> 3 dalam satu segmen panel, sebelum Ramadan (16 Feb - 1 Apr)."""
    from scipy.stats import mannwhitneyu
    k = con.execute("""
        SELECT s.date, d.kab_kota, SUM(s.share) / 8 AS sh FROM g_kap_hour_share s
        JOIN dim_kapanewon d USING(kapanewon_code) JOIN s_calendar k USING(date)
        WHERE s.hour BETWEEN 9 AND 16 AND s.date BETWEEN '2022-02-16' AND '2022-04-01'
          AND NOT k.is_libur AND NOT k.is_anomali GROUP BY ALL""").df()
    k["fase"] = np.select([k.date < "2022-03-08", k.date <= "2022-03-21"],
                          ["A: PPKM 3\n16 Feb-7 Mar", "B: PPKM 4\n9-21 Mar"], "C: PPKM 3\n22 Mar-1 Apr")
    kota = k[k.kab_kota == "YOGYAKARTA"]
    A, B, C = [g.sh.values for _, g in kota.groupby("fase")]
    tab = k.pivot_table(index="kab_kota", columns="fase", values="sh").round(4)
    f = {"kota_share_fase": kota.groupby("fase").sh.agg(["mean", "std", "count"]).round(4).reset_index().to_dict("records"),
         "p_A_vs_B": round(mannwhitneyu(A, B).pvalue, 4), "p_B_vs_C": round(mannwhitneyu(B, C).pvalue, 4),
         "p_A_vs_C": round(mannwhitneyu(A, C).pvalue, 4), "share_per_kab": tab.reset_index().to_dict("records")}
    return k, tab, f


def q3_tourism(con):
    s = con.execute("SELECT * FROM g_site_share WHERE NOT is_anomali ORDER BY site, date").df()
    win = s[s.date <= "2022-01-16"].copy()
    base = win[(win.date < "2021-12-24")]
    nat = win[win.periode_nataru]
    uplift = (nat.groupby("site").share.mean() / base.groupby("site").share.mean()).rename("rasio_nataru_vs_awal_des")
    tab = pd.concat([base.groupby("site").share.mean().rename("share_1_23_des"),
                     nat.groupby("site").share.mean().rename("share_nataru"), uplift], axis=1).reset_index()
    peak = nat.loc[nat.groupby("site").share.idxmax(), ["site", "date"]].rename(columns={"date": "hari_puncak"})
    tab = tab.merge(peak, on="site", how="left")
    j = con.execute("""SELECT site,
        AVG(share) FILTER (WHERE date BETWEEN '2021-12-01' AND '2021-12-23') des_1_23,
        AVG(share) FILTER (WHERE date BETWEEN '2021-12-24' AND '2021-12-30') natal_24_30,
        AVG(share) FILTER (WHERE date = '2021-12-31') malam_tahun_baru,
        AVG(share) FILTER (WHERE date IN ('2022-01-01', '2022-01-02')) tahun_baru_1_2_jan,
        AVG(share) FILTER (WHERE date BETWEEN '2022-01-03' AND '2022-01-31') jan_3_31
        FROM g_site_share GROUP BY 1 ORDER BY 1""").df()
    j.iloc[:, 1:] = (j.iloc[:, 1:] * 1000).round(2)   # permil
    j.to_csv(TAB / "q3_nataru_vs_january.csv", index=False)
    return s, tab, {"nataru_uplift": tab.assign(hari_puncak=tab.hari_puncak.astype(str)).round(5).to_dict("records"),
                    "permil_per_periode": j.to_dict("records")}


def q4_od(con):
    att = con.execute("""SELECT month, dest_kab_kota, dest_kapanewon, n_origins, inflow_share
                         FROM g_od_attract ORDER BY month, inflow_share DESC""").df()
    top = att.groupby("month").head(10)
    vr = con.execute("""
        WITH v AS (SELECT month, dest_code, dest_kab_kota, dest_kapanewon, SUM(n_maids) visitors, COUNT(*) n_orig
                   FROM g_od GROUP BY ALL)
        SELECT v.*, g.n_homed_maids AS residents, visitors * 1.0 / g.n_homed_maids AS visitor_per_resident,
               visitors * 1.0 / SUM(visitors) OVER (PARTITION BY v.month) AS inflow_share
        FROM v JOIN s_od_origin g ON g.month = v.month AND g.origin_code = v.dest_code
        ORDER BY v.month, visitors DESC""").df()
    vr.to_csv(TAB / "q4_visitors_per_destination.csv", index=False)
    flows = con.execute("""SELECT month, origin_kapanewon, dest_kapanewon, n_maids, visit_prob
                           FROM g_od WHERE month='2021-12' ORDER BY n_maids DESC LIMIT 15""").df()
    kota = con.execute("""SELECT month, SUM(n_maids) FILTER (WHERE dest_kab_kota='YOGYAKARTA') * 1.0 / SUM(n_maids) s
                          FROM g_od GROUP BY 1 ORDER BY 1""").df()
    return top, flows, {"top5_tujuan_des": top[top.month == "2021-12"].head(5)[["dest_kapanewon", "dest_kab_kota",
                                                                                  "n_origins", "inflow_share"]].round(4).to_dict("records"),
                        "porsi_kunjungan_ke_kota_per_bulan": kota.round(4).to_dict("records")}


def q5_validation(con):
    v = con.execute("SELECT * FROM s_home_pop").df()
    ok = v[v.kapanewon.str.upper() != "GONDOMANAN"]
    r_lin = np.corrcoef(ok.n_users, ok.pop_actual)[0, 1]
    r_log = np.corrcoef(np.log(ok.n_users), np.log(ok.pop_actual))[0, 1]
    return v, {"r_home_vs_pop_linear": round(r_lin, 3), "r_home_vs_pop_loglog": round(r_log, 3),
               "median_ratio_device_per_penduduk": round((v.n_users / v.pop_actual).median(), 3)}


def main():
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    TAB.mkdir(parents=True, exist_ok=True)
    F = {}
    d, F["Q0_panel"] = q0_panel(con); d.to_csv(TAB / "q0_panel_segments.csv", index=False)
    a, F["Q1_attractor_naif"] = q1_attractor(con); a.to_csv(TAB / "q1_attractor_index.csv", index=False)
    nb, F["Q1b_bias_malam"] = q1b_night_bias(con); nb.to_csv(TAB / "q1b_night_profile_by_kab.csv", index=False)
    c, p, ev, F["Q2_ppkm"] = q2_ppkm(con); p.to_csv(TAB / "q2_hourly_profile_by_level.csv", index=False)
    k, kt, F["Q2b_ABA"] = q2b_aba(con); kt.to_csv(TAB / "q2b_aba_share_per_kab.csv")
    k.to_csv(TAB / "q2b_aba_daily.csv", index=False)
    s, t, F["Q3_nataru"] = q3_tourism(con); t.to_csv(TAB / "q3_nataru_uplift.csv", index=False)
    top, flows, F["Q4_od"] = q4_od(con); top.to_csv(TAB / "q4_top_destinations.csv", index=False)
    flows.to_csv(TAB / "q4_top_flows_dec.csv", index=False)
    v, F["Q5_validasi"] = q5_validation(con)
    con.close()
    (TAB / "findings.json").write_text(json.dumps(F, indent=1, default=str, ensure_ascii=False))
    print(json.dumps(F, indent=1, default=str, ensure_ascii=False))


if __name__ == "__main__":
    main()
