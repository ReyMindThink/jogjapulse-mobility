"""Normalisasi nama wilayah supaya dua sumber (Geoportal DIY 2023 di JogjaPulse vs
HDX-BPS 2020 untuk peta) bisa di-join. Kunci = KAB|KAPANEWON, huruf besar, tanpa spasi/tanda baca."""
import re

KAB_ALIAS = {"GUNUNGKIDUL": "GUNUNGKIDUL", "KOTAYOGYAKARTA": "YOGYAKARTA", "YOGYAKARTA": "YOGYAKARTA",
             "KULONPROGO": "KULONPROGO", "BANTUL": "BANTUL", "SLEMAN": "SLEMAN"}
# variasi ejaan kapanewon antar-sumber (ditambah bila quality check menemukan yang tidak cocok)
KAP_ALIAS = {"KERATON": "KRATON", "PAKUALAMAN": "PAKUALAMAN", "GEDONGTENGEN": "GEDONGTENGEN",
             "SAPTOSARI": "SAPTOSARI", "GEDANGSARI": "GEDANGSARI", "BAMBANGLIPURO": "BAMBANGLIPURO"}


def _clean(s):
    return re.sub(r"[^A-Z]", "", str(s).upper())


def kab_key(s):
    c = _clean(s)
    return KAB_ALIAS.get(c, c)


def kap_key(kab, kap):
    c = _clean(kap)
    return f"{kab_key(kab)}|{KAP_ALIAS.get(c, c)}"
