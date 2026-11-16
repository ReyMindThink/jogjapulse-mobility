"""Sumber data ke-2: kalender kebijakan (PPKM DIY) + hari libur nasional, 1 Des 2021 - 30 Apr 2022.
PPKM disusun manual dari Inmendagri/berita (lihat kolom sumber)."""
import pandas as pd, holidays
from config import EXTERNAL, ANOMALY_DATES, PANEL_BREAKS
out = EXTERNAL / "kalender_kebijakan_diy.csv"
ppkm = [  # (mulai, selesai, level, dasar_hukum)
 ("2021-12-01","2022-02-07",2,"Inmendagri 67/2021 dst. (Des: level 2; Jan: diasumsikan tetap level 2)"),
 ("2022-02-08","2022-03-07",3,"Inmendagri 9/2022 s.d. 13/2022; Ingub DIY 5/2022"),
 ("2022-03-08","2022-03-21",4,"Inmendagri 15/2022 & 16/2022; Ingub DIY 9/2022"),
 ("2022-03-22","2022-04-18",3,"Inmendagri 18/2022 s.d. 22/2022; Ingub DIY 12/2022"),
 ("2022-04-19","2022-04-30",2,"Ingub DIY 13/INSTR/2022"),
]
d = pd.DataFrame({"date": pd.date_range("2021-12-01","2022-04-30")})
for a,b,lv,src in ppkm:
    m = d.date.between(a,b); d.loc[m,"ppkm_level"]=lv; d.loc[m,"ppkm_sumber"]=src
d["ppkm_level"]=d.ppkm_level.astype(int)
hol = holidays.Indonesia(years=[2021,2022])
d["libur_nasional"] = d.date.map(lambda x: hol.get(x.date()) or "")
d["is_libur"] = (d.libur_nasional!="") | (d.date.dt.dayofweek>=5)
d["periode_nataru"] = d.date.between("2021-12-24","2022-01-02")   # Inmendagri 66/2021
d["periode_ramadan"] = d.date>= "2022-04-02"                     # awal Ramadan 1443 H (2-3 Apr 2022)
d["hari"] = d.date.dt.day_name()
d["is_anomali"] = d.date.isin(pd.to_datetime(ANOMALY_DATES))
# segmen panel: sampel perangkat berubah mendadak di tanggal ini (README bag. 6)
d["panel_segment"] = 1 + sum((d.date >= b).astype(int) for b in PANEL_BREAKS)
d.to_csv(out, index=False)
print(d.ppkm_level.value_counts().sort_index().to_dict())
print(d[d.libur_nasional!=""][["date","libur_nasional"]].to_string(index=False))
