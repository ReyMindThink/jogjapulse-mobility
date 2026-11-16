# JogjaPulse Mobility — Pipeline & Analisis Mobilitas Manusia di DIY (Des 2021 – Apr 2022)

Proyek mata kuliah **Rekayasa Data** (topik: *human mobility*) — Rasyid, S1 Teknologi Informasi UGM.
Slide presentasi: [`docs/jogjapulse_presentasi.pptx`](docs/jogjapulse_presentasi.pptx).
Pipeline data end-to-end yang mengambil data kehadiran perangkat seluler teragregasi di Daerah Istimewa Yogyakarta, menggabungkannya dengan **kalender kebijakan PPKM & hari libur** serta **batas wilayah kapanewon**, lalu menganalisis pola mobilitas.

## Ringkasan hasil

> **Tiga jebakan data, dan apa yang tetap bisa disimpulkan.**

| | Temuan | Bukti |
|---|---|---|
| ⚠️ Jebakan 1 | Jumlah perangkat-jam harian turun **87%** (minggu pertama Des → minggu terakhir Apr) dengan patahan 1 Jan & 16 Feb — **artefak sampel**, bukan mobilitas. Semua analisis memakai **porsi** terhadap total DIY. | `f1_panel_problem.png` |
| ⚠️ Jebakan 2 | **Ping ≠ orang.** Pukul 02.00, aktivitas relatif ponsel di Kota Yogyakarta **0,72** vs Gunungkidul **0,20** (3,6×). Indeks siang/malam yang naif membuat Gondomanan/Malioboro tampak "hunian" (0,28) dan desa tampak "pusat aktivitas" (Playen 1,45). | `f2_night_activity_bias.png` |
| ✅ Temuan 1 | **Ke mana orang pergi** (OD, robust terhadap intensitas pemakaian ponsel): tujuan lintas-kapanewon terbesar Des 2021 adalah **Depok, Sleman (7,4%, dari 70 kapanewon asal)**, lalu Ngaglik, Gamping (5,7%), Banguntapan (5,4%), Pakem (5,1%) — koridor kampus & pinggiran kota, bukan hanya pusat kota. | `f6_od_flows.png` |
| ✅ Temuan 2 | **PPKM level 4** (8–21 Mar 2022), desain A-B-A dalam satu segmen sampel, sebelum Ramadan: porsi siang Kota Yogyakarta **20,4% → 19,3% → 21,2%** (Mann-Whitney p = 0,008 dan 0,005); porsi Kulon Progo (+1,7 pp) dan Gunungkidul (+1,4 pp) naik → aktivitas bergeser ke pinggiran. Aktivitas malam tidak berubah signifikan. | `f4_ppkm4_aba.png`, `f3_kota_share_timeseries.png` |
| ⚠️ Jebakan 3 | Malioboro & Tugu tampak "melonjak" pada Tahun Baru (12,8‰ → 16,5‰), tetapi rata-rata Januari biasa lebih tinggi lagi (19,3‰) — lonjakan berimpit dengan **pergantian sampel 1 Jan**. Dalam segmen Desember, minggu Natal (11,2‰) tidak lebih ramai dari 1–23 Des. Pantai (Parangtritis, Baron) tidak dapat dianalisis karena hampir seluruh selnya tersensor (k = 5). | `f5_nataru_panel_break.png` |
| ✅ Validasi | Perangkat ber-"rumah" vs penduduk resmi: **r = 0,82** (linear), 0,69 (log-log), n = 77 tanpa Gondomanan — mendekati angka validasi di README dataset. | `f7_representativeness.png` |

Pelajaran rekayasa data: **validasi asumsi pengukuran sebelum menyimpulkan** — tiga dari lima pola "menarik" pada data mentah ternyata artefak cara data dikumpulkan.

## Pertanyaan penelitian

| # | Pertanyaan | Data |
|---|---|---|
| Q1 | Kapanewon mana yang menjadi **penarik aktivitas siang**? (indeks siang/malam terbukti bias → dijawab dengan OD) | presence per jam + OD |
| Q2 | Apakah perubahan **level PPKM (2 → 3 → 4 → 3 → 2)** sejalan dengan perubahan pola mobilitas? | presence per jam + kalender PPKM |
| Q3 | Apakah **libur Natal–Tahun Baru** menaikkan kehadiran di titik wisata? | presence sel 500 m per hari + kalender |
| Q4 | Kapanewon mana yang menjadi **tujuan kunjungan** dari wilayah lain? | OD bulanan (Des–Feb) |

## Sumber data (≥ 2)

| # | Sumber | Isi | Lisensi |
|---|---|---|---|
| 1 | **JogjaPulse** — Widyawan dkk. (2026), Zenodo, [10.5281/zenodo.23157460](https://doi.org/10.5281/zenodo.23157460) | kehadiran perangkat per sel 500 m/hari & per kapanewon/jam; aliran asal–tujuan bulanan; validasi vs penduduk | CC BY 4.0 |
| 2 | **Kalender kebijakan DIY** (disusun dari Inmendagri & Instruksi Gubernur DIY, lihat kolom `ppkm_sumber`) + hari libur nasional (pustaka `holidays`) | level PPKM harian, libur, periode Nataru & Ramadan | fakta publik |
| 3 | **Batas kapanewon DIY** — HDX/BPS 2020 via [JfrAziz/indonesia-district](https://github.com/JfrAziz/indonesia-district), di-*dissolve* dari tingkat desa | 78 poligon kapanewon + kode BPS + luas | CC BY (HDX) |

Kronologi PPKM DIY yang dipakai:

| Periode | Level | Dasar |
|---|---|---|
| 1 Des 2021 – 7 Feb 2022 | 2 | Inmendagri 67/2021 dst. (Januari diasumsikan tetap level 2) |
| 8 Feb – 7 Mar 2022 | 3 | Inmendagri 9/2022 s.d. 13/2022; Ingub DIY 5/2022 |
| 8 – 21 Mar 2022 | **4** | Inmendagri 15 & 16/2022; Ingub DIY 9/2022 |
| 22 Mar – 18 Apr 2022 | 3 | Inmendagri 18–22/2022; Ingub DIY 12/2022 |
| 19 – 30 Apr 2022 | 2 | Ingub DIY 13/INSTR/2022 |

## Arsitektur pipeline

```
Zenodo API ──► [1] ingest.py ──► data/raw/ (bronze, MD5 terverifikasi)
                                     │
Inmendagri/Ingub, holidays ──► [2] build_calendar.py ──► data/external/kalender_kebijakan_diy.csv
HDX-BPS (desa) ──► build_boundaries.py ──► data/external/kapanewon_diy.geojson
                                     │
                              [3] warehouse.py  (DuckDB)
                                  silver: s_kap_hourly, s_cell_daily, s_od, s_od_origin, s_calendar, dim_kapanewon
                                  gold  : g_daily, g_kap_hour_share, g_attractor, g_hourly_profile,
                                          g_core_share, g_cell_share, g_site_share, g_od, g_od_attract
                                     │
                              [4] quality.py  ──► outputs/tables/quality_report.csv (19 aturan)
                              [5] analysis.py ──► outputs/tables/*.csv, findings.json
                              [6] visualize.py──► outputs/figures/*.png
```

## Keputusan metodologis penting

1. **Normalisasi wajib.** README dataset (bag. 6.1) menyatakan jumlah perangkat terobservasi turun dari ±87 ribu/hari (Des) ke ±9 ribu/hari (Apr), dengan patahan mendadak **1 Jan** dan **16 Feb 2022** — akibat komposisi sampel, *bukan* mobilitas. Karena itu semua ukuran dianalisis sebagai **porsi (share) terhadap total DIY pada jam/hari yang sama**, bukan jumlah absolut (lihat `f1_panel_problem.png`).
2. **Perbandingan PPKM dengan desain A-B-A di dalam satu segmen panel**: PPKM 3 (16 Feb–7 Mar) → PPKM 4 (9–21 Mar) → PPKM 3 (22 Mar–1 Apr), hanya hari kerja, sebelum Ramadan (2 Apr). Periode PPKM 2 di akhir April tidak dipakai karena seluruhnya jatuh di bulan Ramadan. Uji Mann-Whitney; regresi OLS dengan tren waktu disimpan sebagai pembanding di `findings.json`.
3. **Ping ≠ kehadiran.** Perangkat hanya terekam saat aplikasi aktif; aktivitas malam ponsel jauh lebih tinggi di kota. Karena itu rasio siang/malam tidak dipakai sebagai ukuran penarik; pertanyaan "ke mana orang pergi" dijawab dengan data OD (setiap pengunjung dihitung sekali per bulan).
4. **Data hilang ≠ nol.** Baris dengan < 5 perangkat dihapus penyedia (k-anonymity). Indeks penarik ditandai *tidak andal* bila < 50% slot jam malam terpublikasi.
5. **Hari anomali 8 Mar 2022** dikeluarkan dari analisis.
6. **OD hanya Des 2021 – Feb 2022**; Mar–Apr ditandai `reduced_quality` oleh penyedia.
7. `n_maids` adalah hitungan *distinct* sehingga **tidak dijumlahkan** lintas wilayah sebagai jumlah orang; penjumlahan hanya dipakai sebagai penyebut porsi ("perangkat-jam").

## Keterbatasan

- Perangkat ≠ orang; sampel berasal dari aplikasi dengan izin lokasi, bukan sampel acak penduduk.
- Kenaikan level PPKM bersamaan dengan lonjakan kasus Omicron → hasil Q2 adalah **asosiasi, bukan kausalitas**.
- Batas wilayah peta (BPS 2020) sedikit berbeda dengan batas Geoportal DIY 2023 yang dipakai dataset; hanya memengaruhi tampilan peta, tidak memengaruhi angka.
- Status PPKM Januari 2022 diasumsikan level 2 (tidak ada perubahan yang diberitakan).

## Cara menjalankan

**Google Colab (disarankan):** [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ReyMindThink/jogjapulse-mobility/blob/main/notebooks/run_in_colab.ipynb) → *Runtime → Run all*.

**Lokal:**
```bash
pip install -r requirements.txt
python run_pipeline.py            # unduh data + seluruh tahap (±1 menit)
python run_pipeline.py --skip-ingest   # jika data/raw sudah ada
```
Waktu jalan seluruh tahap setelah data terunduh: ±6 detik.

**Uji tanpa internet** (data sintetis berskema identik, hanya untuk menguji kode):
```bash
python tests/make_synthetic.py /tmp/synth && JP_RAW=/tmp/synth python run_pipeline.py --skip-ingest
```

## Struktur repo

```
├── run_pipeline.py          # orchestrator
├── src/
│   ├── config.py            # path, konstanta, tanggal anomali, titik wisata
│   ├── keys.py              # normalisasi nama wilayah untuk join antar-sumber
│   ├── ingest.py            # [1] Zenodo API + MD5
│   ├── build_calendar.py    # [2] sumber data ke-2
│   ├── build_boundaries.py  #     batas kapanewon (sekali jalan)
│   ├── warehouse.py         # [3] DuckDB silver + gold (SQL)
│   ├── quality.py           # [4] data quality checks
│   ├── analysis.py          # [5] statistik Q1–Q4
│   └── visualize.py         # [6] gambar
├── data/external/           # kalender + GeoJSON (masuk repo)
├── outputs/                 # tabel & gambar hasil
├── notebooks/               # Colab
├── docs/                    # slide presentasi (.pptx)
└── tests/make_synthetic.py  # generator data uji
```

## Sitasi

Widyawan, Pratama, A. R., Ariansyah, A., Farda, N. M., Pramana, S., & Miller, O. (2026). *JogjaPulse: An Aggregated Spatio-Temporal Mobility Dataset for Yogyakarta, Indonesia* (v1) [Dataset]. Zenodo. https://doi.org/10.5281/zenodo.23157460
