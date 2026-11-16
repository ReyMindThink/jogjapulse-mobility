"""TAHAP 6 - VISUALISASI. Semua gambar 16:9 (siap slide/video) -> outputs/figures/*.png"""
import duckdb, numpy as np, pandas as pd, geopandas as gpd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.colors import TwoSlopeNorm, LinearSegmentedColormap
from config import WAREHOUSE, EXTERNAL, FIG, TAB, PANEL_BREAKS, ANOMALY_DATES

# ---- palet (tervalidasi CVD; lihat README repo) ----
INK, INK2, MUTED, GRID, AXIS, SURF = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
S1, S2, S3, S4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
LEVEL_COL = {2: S1, 3: S4, 4: S2}  # level PPKM -> warna tetap di semua grafik
LEVEL_BG = {2: "#ffffff", 3: "#fdf1d6", 4: "#fbe0d4"}
DIVERGING = LinearSegmentedColormap.from_list("div", ["#184f95", "#6da7ec", "#f0efec", "#ec8a87", "#a8292a"])
SEQ = LinearSegmentedColormap.from_list("seq", ["#cde2fb", "#6da7ec", "#2a78d6", "#104281"])

plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "font.family": "DejaVu Sans", "font.size": 13, "text.color": INK,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": .8, "axes.spines.top": False,
    "axes.spines.right": False, "axes.titlesize": 18, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "lines.linewidth": 2, "legend.frameon": False,
})
SIZE = (16, 9)
SRC = "Sumber: JogjaPulse (Widyawan dkk., 2026, Zenodo 10.5281/zenodo.23157460); PPKM: Inmendagri/Ingub DIY"


def save(fig, name, note=SRC):
    fig.text(0.01, 0.01, note, fontsize=9, color=MUTED)
    fig.savefig(FIG / name, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print("  ->", name)


def shade_ppkm(ax, cal, ymax_frac=1):
    cal = cal.sort_values("date")
    seg = (cal.ppkm_level != cal.ppkm_level.shift()).cumsum()
    for _, g in cal.groupby(seg):
        lv = g.ppkm_level.iloc[0]
        ax.axvspan(g.date.min(), g.date.max() + pd.Timedelta(days=1), color=LEVEL_BG[lv], zorder=0, lw=0)
        if lv > 2:
            ax.text(g.date.min() + (g.date.max() - g.date.min()) / 2, 1.0, f"PPKM {lv}", transform=ax.get_xaxis_transform(),
                    ha="center", va="bottom", fontsize=11, color=INK2, fontweight="bold")
    for b in PANEL_BREAKS:
        ax.axvline(pd.Timestamp(b), color=INK2, ls=(0, (4, 3)), lw=1.2, zorder=1)
    for a in ANOMALY_DATES:
        ax.axvline(pd.Timestamp(a), color=MUTED, ls=":", lw=1, zorder=1)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b\n%Y"))


def fig1_panel(con, cal):
    d = con.execute("SELECT date, device_hours FROM g_daily ORDER BY date").df()
    fig, ax = plt.subplots(figsize=SIZE)
    shade_ppkm(ax, cal)
    ax.plot(d.date, d.device_hours / 1e3, color=S1)
    ax.set_title("Data mentah menipu: jumlah perangkat anjlok karena SAMPEL, bukan karena mobilitas", pad=28)
    ax.set_ylabel("Σ perangkat-jam per hari (ribu)")
    for b, lab in zip(PANEL_BREAKS, ["1 Jan: sampel berubah", "16 Feb: sampel berubah"]):
        ax.annotate(lab, (pd.Timestamp(b), ax.get_ylim()[1] * .92), xytext=(6, 0), textcoords="offset points",
                    fontsize=11, color=INK2)
    ax.annotate("8 Mar: anomali data", (pd.Timestamp(ANOMALY_DATES[0]), ax.get_ylim()[1] * .6), xytext=(6, 0),
                textcoords="offset points", fontsize=11, color=MUTED)
    ax.set_ylim(bottom=0)
    save(fig, "f1_panel_problem.png")


def fig2_night_bias(con):
    """Jebakan #2: ponsel di kota jauh lebih aktif malam hari -> indeks siang/malam bias."""
    p = pd.read_csv(TAB / "q1b_night_profile_by_kab.csv")
    a = pd.read_csv(TAB / "q1_attractor_index.csv")
    fig, (ax, bx) = plt.subplots(1, 2, figsize=SIZE, gridspec_kw={"width_ratios": [1.25, 1], "wspace": .35})
    for kab, col, lab in [("YOGYAKARTA", S1, "Kota Yogyakarta"), ("GUNUNGKIDUL", S2, "Gunungkidul")]:
        g = p[p.kab_kota == kab]
        ax.plot(g.hour, g.rel, color=col, lw=2.5, marker="o", ms=5, label=lab)
    for kab, col in [("YOGYAKARTA", S1), ("GUNUNGKIDUL", S2)]:
        v = p[(p.kab_kota == kab) & (p.hour == 2)].rel.iloc[0]
        ax.annotate(f"{v:.2f}", (2, v), xytext=(10, 0), textcoords="offset points", va="center", fontsize=12,
                    color=INK, fontweight="bold")
    ax.axvspan(0, 5, color=GRID, alpha=.5, zorder=0)
    ax.text(2.5, ax.get_ylim()[1] * .98, "jam malam\n(dipakai\nindeks)", ha="center", va="top", fontsize=10, color=INK2)
    ax.set_xticks(range(0, 24, 3)); ax.set_xlabel("Jam (WIB)"); ax.set_ylabel("Aktivitas relatif (1 = rata-rata harian)")
    ax.set_title("Jam 02.00: ponsel di kota 3,6x lebih 'hidup'", fontsize=16); ax.legend(loc="lower right")
    r = a[a.reliable].sort_values("attractor_index")
    show = pd.concat([r.head(4), r.tail(4)])
    cols = [MUTED if k != "GONDOMANAN" else S1 for k in show.kapanewon]
    bx.barh(show.kapanewon.str.title() + " (" + show.kab_kota.str.title().str.replace("Yogyakarta", "Kota") + ")",
            show.attractor_index, color=cols, height=.65)
    bx.axvline(1, color=AXIS, lw=1.2); bx.grid(axis="y", visible=False)
    for y, v in enumerate(show.attractor_index):
        bx.text(v + .02, y, f"{v:.2f}", va="center", fontsize=11, color=INK2)
    bx.set_xlabel("Indeks naif = porsi siang ÷ porsi malam")
    bx.set_title("Akibatnya: Malioboro tampak 'hunian',\ndesa tampak 'pusat aktivitas'", fontsize=15)
    fig.suptitle("Jebakan #2 — ping ≠ orang: perangkat hanya terekam saat aplikasinya aktif", x=.01, ha="left",
                 fontsize=19, fontweight="bold")
    save(fig, "f2_night_activity_bias.png")


def fig3_core_share(con, cal):
    c = con.execute("SELECT * FROM g_core_share WHERE NOT is_anomali ORDER BY date").df()
    fig, ax = plt.subplots(figsize=SIZE)
    shade_ppkm(ax, cal)
    ax.plot(c.date, c.kota_day_share * 100, color=MUTED, lw=1, alpha=.7, label="harian")
    ax.plot(c.date, c.kota_day_share.rolling(7, center=True, min_periods=4).mean() * 100, color=S1, lw=2.5, label="rata-rata 7 hari")
    ax.set_title("Porsi kehadiran siang (09-16) di Kota Yogyakarta terhadap seluruh DIY", pad=28)
    ax.set_ylabel("% dari total perangkat DIY pada jam yang sama"); ax.legend(loc="lower left")
    save(fig, "f3_kota_share_timeseries.png")


def fig4_aba(con):
    """Temuan PPKM: desain A-B-A (PPKM 3 -> 4 -> 3), satu segmen panel, sebelum Ramadan."""
    k = pd.read_csv(TAB / "q2b_aba_daily.csv", parse_dates=["date"])
    kota = k[k.kab_kota == "YOGYAKARTA"]
    fases = sorted(kota.fase.unique())
    fig, (ax, bx) = plt.subplots(1, 2, figsize=SIZE, gridspec_kw={"width_ratios": [1, 1.1], "wspace": .3})
    cols = [S4, S2, S4]
    for i, (f, c) in enumerate(zip(fases, cols)):
        v = kota[kota.fase == f].sh * 100
        ax.bar(i, v.mean(), color=c, width=.6, zorder=2)
        ax.scatter(np.full(len(v), i) + np.random.default_rng(i).uniform(-.18, .18, len(v)), v, s=22,
                   color=INK2, zorder=3, alpha=.7)
        ax.text(i, v.mean() + .15, f"{v.mean():.1f}%", ha="center", fontsize=15, fontweight="bold")
    ax.set_xticks(range(3)); ax.set_xticklabels(fases, fontsize=12)
    ax.set_ylim(17, 23.5); ax.grid(axis="x", visible=False)
    ax.set_ylabel("Porsi kehadiran siang di Kota Yogyakarta (%)")
    ax.set_title("Kota Yogyakarta: turun saat PPKM 4, pulih setelahnya", fontsize=15)
    ax.text(.5, 22.8, "p = 0,008", ha="center", fontsize=11, color=INK2)
    ax.text(1.5, 22.8, "p = 0,005", ha="center", fontsize=11, color=INK2)
    ax.set_xlabel("titik = 1 hari kerja · uji Mann-Whitney", fontsize=10, color=MUTED)
    t = k.pivot_table(index="kab_kota", columns="fase", values="sh")
    d = ((t[fases[1]] - t[fases[0]]) * 100).sort_values()
    lab = d.index.str.title().str.replace("Yogyakarta", "Kota Yogyakarta")
    bx.barh(lab, d, color=[DIVERGING(.1) if v < 0 else DIVERGING(.9) for v in d], height=.6)
    bx.axvline(0, color=AXIS, lw=1.2); bx.grid(axis="y", visible=False)
    for y, v in enumerate(d):
        bx.text(v + (.05 if v > 0 else -.05), y, f"{v:+.1f} pp", va="center", ha="left" if v > 0 else "right",
                fontsize=12, color=INK2)
    bx.set_xlim(d.min() - .8, d.max() + .8)
    bx.set_xlabel("Perubahan porsi siang, PPKM 4 vs PPKM 3 sebelumnya (poin persen)")
    bx.set_title("Aktivitas bergeser dari pusat ke pinggiran", fontsize=15)
    fig.suptitle("PPKM level 4 (8-21 Mar 2022) — perbandingan di dalam satu segmen sampel", x=.01, ha="left",
                 fontsize=19, fontweight="bold")
    save(fig, "f4_ppkm4_aba.png")


def fig5_tourism(con, cal):
    """Jebakan #3: lonjakan 1 Jan di titik wisata berimpit dengan pergantian sampel."""
    s = con.execute("""SELECT site, date, share FROM g_site_share WHERE site IN ('Malioboro', 'Tugu Jogja')
                       AND date <= '2022-01-31' ORDER BY site, date""").df()
    fig, ax = plt.subplots(figsize=(18, 9))
    ax.axvspan(pd.Timestamp("2021-12-24"), pd.Timestamp("2022-01-03"), color="#fbe0d4", zorder=0, lw=0)
    ax.text(pd.Timestamp("2021-12-29"), .97, "Nataru", transform=ax.get_xaxis_transform(), ha="center", va="top",
            fontsize=12, fontweight="bold", color=INK2)
    for site, col in [("Malioboro", S1), ("Tugu Jogja", S3)]:
        g = s[s.site == site]
        ax.plot(g.date, g.share * 1000, color=col, lw=2.2, label=site)
        for a, b in [("2021-12-01", "2021-12-31"), ("2022-01-01", "2022-01-31")]:
            m = g[(g.date >= a) & (g.date <= b)].share.mean() * 1000
            ax.hlines(m, pd.Timestamp(a), pd.Timestamp(b), color=col, ls="--", lw=1.2, alpha=.8)
    ax.axvline(pd.Timestamp("2022-01-01"), color=INK2, ls=(0, (4, 3)), lw=1.4)
    ax.annotate("1 Jan: sampel perangkat berganti\n→ rata-rata Januari ikut naik ~50%\n(bukan efek liburan)",
                (pd.Timestamp("2022-01-01"), 21.5), xytext=(12, 0), textcoords="offset points", fontsize=12, color=INK)
    ax.set_ylabel("Porsi perangkat DIY dalam radius 1 km (‰)"); ax.set_ylim(bottom=0)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.legend(loc="upper left", title="garis putus = rata-rata bulanan", title_fontsize=10)
    ax.set_title("Jebakan #3 — lonjakan Malioboro & Tugu di Tahun Baru berimpit dengan pergantian sampel")
    save(fig, "f5_nataru_panel_break.png")


def fig6_od(con):
    geo = gpd.read_file(EXTERNAL / "kapanewon_diy.geojson").to_crs(32749)
    dim = con.execute("SELECT kapanewon_code, kode_bps FROM dim_kapanewon").df()
    cen = geo.set_index("kode_bps").geometry.representative_point()
    od = con.execute("""SELECT origin_code, dest_code, n_maids FROM g_od WHERE month='2021-12'
                        ORDER BY n_maids DESC LIMIT 60""").df()
    code2bps = dict(zip(dim.kapanewon_code, dim.kode_bps))
    att = pd.read_csv(TAB / "q4_top_destinations.csv"); att = att[att.month == "2021-12"].head(10)
    fig, (ax, bx) = plt.subplots(1, 2, figsize=SIZE, gridspec_kw={"width_ratios": [1.3, 1], "wspace": .3})
    geo.plot(ax=ax, color="#f0efec", edgecolor=AXIS, linewidth=.5)
    w = od.n_maids / od.n_maids.max()
    for (_, r), wi in zip(od.iterrows(), w):
        o, d = cen.get(code2bps.get(r.origin_code)), cen.get(code2bps.get(r.dest_code))
        if o is None or d is None: continue
        ax.annotate("", xy=(d.x, d.y), xytext=(o.x, o.y),
                    arrowprops=dict(arrowstyle="-|>", color=S1, alpha=.25 + .6 * wi, lw=.6 + 4 * wi,
                                    connectionstyle="arc3,rad=.2", mutation_scale=8 + 6 * wi))
    ax.set_axis_off(); ax.set_title("60 aliran kunjungan antar-kapanewon\nterbesar (Des 2021)", fontsize=15)
    bx.barh(att.dest_kapanewon.str.title()[::-1], att.inflow_share[::-1] * 100, color=S1, height=.65)
    for y, v in enumerate(att.inflow_share[::-1] * 100):
        bx.text(v + .1, y, f"{v:.1f}%", va="center", fontsize=10, color=INK2)
    bx.grid(axis="y", visible=False); bx.set_xlabel("% dari seluruh kunjungan lintas-kapanewon")
    bx.set_title("10 tujuan teratas", fontsize=14)
    save(fig, "f6_od_flows.png")


def fig7_validation(con):
    v = con.execute("SELECT * FROM s_home_pop").df()
    fig, ax = plt.subplots(figsize=SIZE)
    gm = v.kapanewon.str.upper() == "GONDOMANAN"
    ax.scatter(v.pop_actual[~gm], v.n_users[~gm], s=60, color=S1, edgecolor=SURF, linewidth=1.5, label="kapanewon")
    ax.scatter(v.pop_actual[gm], v.n_users[gm], s=90, color=S2, edgecolor=SURF, linewidth=1.5, label="Gondomanan (Malioboro)")
    ax.set_xscale("log"); ax.set_yscale("log")
    xs = np.array([v.pop_actual.min() * .8, v.pop_actual.max() * 1.25])
    ax.plot(xs, xs * v.n_users.sum() / v.pop_actual.sum(), color=MUTED, ls="--", lw=1, label="rasio rata-rata DIY")
    ok = v[~gm]
    r = np.corrcoef(np.log(ok.n_users), np.log(ok.pop_actual))[0, 1]
    rl = np.corrcoef(ok.n_users, ok.pop_actual)[0, 1]
    ax.text(.98, .04, f"r = {rl:.2f} (linear), {r:.2f} (log-log)\nn = {len(ok)}, tanpa Gondomanan", transform=ax.transAxes,
            ha="right", fontsize=13, color=INK2)
    ax.set_xlim(*xs)
    ax.set_xlabel("Penduduk resmi (log)"); ax.set_ylabel("Perangkat dengan 'rumah' di kapanewon (log)")
    ax.set_title("Seberapa mewakili? Perangkat vs penduduk per kapanewon"); ax.legend(loc="lower right", bbox_to_anchor=(1, .12))
    save(fig, "f7_representativeness.png")


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    cal = con.execute("SELECT date, ppkm_level FROM s_calendar").df()
    for f in (fig1_panel, fig3_core_share, fig5_tourism):
        f(con, cal)
    for f in (fig2_night_bias, fig4_aba, fig6_od, fig7_validation):
        f(con)
    con.close()


if __name__ == "__main__":
    main()
