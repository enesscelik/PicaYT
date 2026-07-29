"""
Paketlemede kullanilacak ffmpeg.exe + ffprobe.exe ikililerini indirir.

Kurulum dosyasi bunlari icine alir; boylece karsi tarafta ffmpeg kurulu
olmasa da PicaYT calisir. Zaten indirilmisse tekrar indirmez.

    python ffmpeg_getir.py [--zorla]

Kaynaklar sirayla denenir. Ilk ikisi GitHub uzerinde barinir; gyan.dev'in
kendi sunucusu CI makinelerinden gelen istekleri reddedebiliyor, o yuzden
en sona birakildi.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

KOK = Path(__file__).resolve().parent
HEDEF = KOK / "ffmpeg"
GEREKENLER = ("ffmpeg.exe", "ffprobe.exe")
BASLIKLAR = {"User-Agent": "PicaYT-build"}

# Windows konsolunun varsayilan kod sayfasi (cp1252) Turkce'nin noktasiz
# "ı" harfini tasimiyor; ciktiyi UTF-8'e sabitlemezsek derleme betikleri
# sirf bir mesaj yazarken cokuyor.
for _akis in (sys.stdout, sys.stderr):
    try:
        _akis.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass


def _json_al(adres: str) -> dict:
    istek = urllib.request.Request(adres, headers=BASLIKLAR)
    with urllib.request.urlopen(istek, timeout=60) as cevap:
        return json.loads(cevap.read().decode("utf-8"))


def _yayindan_sec(depo: str, desen: str) -> str:
    """GitHub'daki son yayindan adi desene uyan dosyanin adresini bulur."""
    veri = _json_al(f"https://api.github.com/repos/{depo}/releases/latest")
    for varlik in veri.get("assets", []):
        if varlik["name"].endswith(desen):
            return varlik["browser_download_url"]
    raise LookupError(f"{depo} yayininda {desen} bulunamadi")


def kaynaklar() -> list[tuple[str, callable]]:
    return [
        # gyan.dev'in resmi GitHub aynasi — yerelde denenen yapimin ayni surumu
        ("GyanD/codexffmpeg (GitHub)",
         lambda: _yayindan_sec("GyanD/codexffmpeg", "-essentials_build.zip")),
        ("BtbN/FFmpeg-Builds (GitHub)",
         lambda: _yayindan_sec("BtbN/FFmpeg-Builds", "win64-gpl.zip")),
        ("gyan.dev (dogrudan)",
         lambda: "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"),
    ]


def _ilerleme(inen: int, toplam: int) -> None:
    if toplam <= 0:
        return
    sys.stdout.write(
        f"\r    %{inen * 100 // toplam} ({inen // 1048576} / {toplam // 1048576} MB)")
    sys.stdout.flush()


def indir(adres: str, hedef_zip: Path) -> None:
    istek = urllib.request.Request(adres, headers=BASLIKLAR)
    with urllib.request.urlopen(istek, timeout=300) as cevap, open(hedef_zip, "wb") as dosya:
        toplam = int(cevap.headers.get("Content-Length") or 0)
        inen = 0
        while parca := cevap.read(1 << 20):
            dosya.write(parca)
            inen += len(parca)
            _ilerleme(inen, toplam)
    print()


def cikar(zip_yolu: Path) -> list[str]:
    HEDEF.mkdir(parents=True, exist_ok=True)
    cikanlar = []
    with zipfile.ZipFile(zip_yolu) as arsiv:
        for ad in arsiv.namelist():
            dosya_adi = Path(ad).name
            if dosya_adi in GEREKENLER:
                with arsiv.open(ad) as kaynak, open(HEDEF / dosya_adi, "wb") as cikti:
                    shutil.copyfileobj(kaynak, cikti)
                cikanlar.append(dosya_adi)
    return cikanlar


def surum() -> str:
    try:
        sonuc = subprocess.run([str(HEDEF / "ffmpeg.exe"), "-version"],
                               capture_output=True, text=True, timeout=60)
        return sonuc.stdout.splitlines()[0] if sonuc.stdout else "?"
    except (OSError, subprocess.SubprocessError, IndexError):
        return "?"


def getir() -> bool:
    for ad, adres_bul in kaynaklar():
        print(f"  kaynak: {ad}")
        try:
            adres = adres_bul()
            print(f"    {adres.rsplit('/', 1)[-1]}")
            with tempfile.TemporaryDirectory() as gecici:
                zip_yolu = Path(gecici) / "ffmpeg.zip"
                indir(adres, zip_yolu)
                cikanlar = cikar(zip_yolu)
            if all(a in cikanlar for a in GEREKENLER):
                return True
            print(f"    eksik dosya: {set(GEREKENLER) - set(cikanlar)}")
        except (urllib.error.URLError, LookupError, OSError,
                zipfile.BadZipFile, TimeoutError) as hata:
            print(f"    başarısız: {hata}")
        print("    sıradaki kaynak deneniyor…")
    return False


def main() -> int:
    zorla = "--zorla" in sys.argv
    if all((HEDEF / a).is_file() for a in GEREKENLER) and not zorla:
        print("ffmpeg zaten hazır:", surum())
        return 0

    print("ffmpeg indiriliyor…")
    if not getir():
        print("HATA: hiçbir kaynaktan indirilemedi.", file=sys.stderr)
        return 1

    toplam = sum((HEDEF / a).stat().st_size for a in GEREKENLER)
    print(f"tamam · {toplam / 1048576:.0f} MB · {surum()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
