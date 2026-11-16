"""Gabungkan poligon desa (HDX-BPS 2020) menjadi poligon kapanewon DIY."""
import glob, sys, os
import geopandas as gpd, pandas as pd
from config import EXTERNAL
from keys import kap_key
# argumen: folder hasil clone github.com/JfrAziz/indonesia-district (subfolder id34_...)
src = sys.argv[1]
out = EXTERNAL / "kapanewon_diy.geojson"
files = [f for f in glob.glob(os.path.join(src, "*", "*.geojson"))
         if len(os.path.basename(f).split("_")[0]) == 9]
g = pd.concat([gpd.read_file(f) for f in files], ignore_index=True)
k = g.dissolve(by=["regency_code","regency","district_code","district"], as_index=False)[
    ["regency_code","regency","district_code","district","geometry"]]
k["kode_bps"] = k["district_code"].str.replace("id","",regex=False)
k["kap_key"] = [kap_key(a, b) for a, b in zip(k.regency, k.district)]
k["luas_km2"] = k.to_crs(32749).area/1e6
k.to_file(out, driver="GeoJSON")
print(len(k), "kapanewon;", k.groupby("regency").size().to_dict())
print(k[["kode_bps","district","regency","luas_km2"]].head(8).to_string())
