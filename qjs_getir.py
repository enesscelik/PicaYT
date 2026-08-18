"""
Paketlemede kullanilacak QuickJS ikilisini (qjs.exe) indirir.

YouTube 2026'da "n challenge" adli bir dogrulama getirdi; yt-dlp bunu cozmek
icin bir JavaScript calistiricisi ister. Yoksa gercek video/ses formatlari hic
donmuyor ve hata "This video is not available" olarak gorunuyor.

QuickJS bu is icin en kucuk secenek: ~2 MB. (Deno ~110 MB, Node ~50 MB.)
Cozucu betigin kendisi `yt-dlp-ejs` paketiyle gomulu geliyor, yani calisma
aninda internetten bir sey indirilmiyor.

    python qjs_getir.py [--zorla]
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

KOK = Path(__file__).resolve().parent
HEDEF = KOK / "js"
IKILI = HEDEF / "qjs.exe"
DEPO = "quickjs-ng/quickjs"
VARLIK = "qjs-windows-x86_64.exe"
BASLIKLAR = {"User-Agent": "PicaYT-build"}

for _akis in (sys.stdout, sys.stderr):
    try:
        _akis.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass


def _son_surum() -> tuple[str, str]:
    istek = urllib.request.Request(
        f"https://api.github.com/repos/{DEPO}/releases/latest", headers=BASLIKLAR)
    with urllib.request.urlopen(istek, timeout=60) as cevap:
        veri = json.loads(cevap.read().decode("utf-8"))
    for varlik in veri.get("assets", []):
        if varlik["name"] == VARLIK:
            return veri.get("tag_name", "?"), varlik["browser_download_url"]
    raise LookupError(f"{VARLIK} bulunamadi")


def surum() -> str:
    try:
        sonuc = subprocess.run([str(IKILI), "--help"], capture_output=True,
                               text=True, timeout=30)
        ciktilar = (sonuc.stdout or "") + (sonuc.stderr or "")
        return ciktilar.splitlines()[0] if ciktilar.strip() else "?"
    except (OSError, subprocess.SubprocessError, IndexError):
        return "?"


def main() -> int:
    if IKILI.is_file() and "--zorla" not in sys.argv:
        print("QuickJS zaten hazir:", surum())
        return 0

    print("QuickJS indiriliyor...")
    try:
        etiket, adres = _son_surum()
        HEDEF.mkdir(parents=True, exist_ok=True)
        istek = urllib.request.Request(adres, headers=BASLIKLAR)
        with urllib.request.urlopen(istek, timeout=180) as cevap:
            IKILI.write_bytes(cevap.read())
    except (urllib.error.URLError, LookupError, OSError, TimeoutError) as hata:
        print(f"HATA: indirilemedi: {hata}", file=sys.stderr)
        return 1

    boyut = IKILI.stat().st_size / 1048576
    print(f"tamam - {etiket} - {boyut:.1f} MB - {surum()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
