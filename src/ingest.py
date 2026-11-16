"""TAHAP 1 - INGEST (bronze).
Mengunduh semua file record Zenodo lewat API, memverifikasi MD5, dan mencatat log.
Idempoten: file yang sudah ada dan checksum-nya cocok tidak diunduh ulang."""
import hashlib, json, sys
import requests
from config import RAW, ZENODO_RECORD


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    meta = requests.get(f"https://zenodo.org/api/records/{ZENODO_RECORD}", timeout=60).json()
    log = []
    for f in meta["files"]:
        path = RAW / f["key"]
        expected = f["checksum"].split(":")[-1]
        if not (path.exists() and md5(path) == expected):
            with requests.get(f["links"]["self"], stream=True, timeout=300) as r:
                r.raise_for_status()
                with open(path, "wb") as out:
                    for chunk in r.iter_content(1 << 20):
                        out.write(chunk)
        ok = md5(path) == expected
        log.append({"file": f["key"], "bytes": path.stat().st_size, "md5_ok": ok})
        print(f"{'OK ' if ok else 'BAD'} {f['key']}")
    (RAW / "_ingest_log.json").write_text(json.dumps(log, indent=1))
    if not all(x["md5_ok"] for x in log):
        sys.exit("Checksum gagal - unduh ulang.")


if __name__ == "__main__":
    main()
