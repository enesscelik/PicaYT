"""
Yeni surum yayinlar: surum numarasini yukseltir, isler, etiketler, iter.

    python yayinla.py 1.0.1              # yama
    python yayinla.py 1.1.0 -m "Kuyruk hizlandirildi"
    python yayinla.py --dene 1.0.1       # hicbir sey yapmadan ne olacagini goster

Etiket GitHub'a itildiginde `.github/workflows/yayin.yml` devreye girer:
kurulum dosyasini derler ve Release'e yukler. Kullanicilarin paneli acilista
yeni surumu gorup guncelleme teklif eder.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent
YOLLAR_PY = KOK / "yollar.py"
SURUM_DESEN = re.compile(r'^SURUM = "([\d.]+)"$', re.MULTILINE)

# Windows konsolunun varsayilan kod sayfasi (cp1252) Turkce'nin noktasiz
# "ı" harfini tasimiyor; sabitlemezsek betik sirf bir mesaj yazarken
# UnicodeEncodeError ile cokuyor.
for _akis in (sys.stdout, sys.stderr):
    try:
        _akis.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass


def calistir(*komut: str, dene: bool = False) -> str:
    if dene:
        print("  [deneme]", " ".join(komut))
        return ""
    sonuc = subprocess.run(komut, cwd=KOK, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    if sonuc.returncode != 0:
        raise SystemExit(f"Komut basarisiz: {' '.join(komut)}\n{sonuc.stderr}")
    return (sonuc.stdout or "").strip()


def simdiki_surum() -> str:
    eslesme = SURUM_DESEN.search(YOLLAR_PY.read_text("utf-8"))
    if not eslesme:
        raise SystemExit("yollar.py icinde SURUM bulunamadi.")
    return eslesme.group(1)


def surum_yaz(yeni: str) -> None:
    metin = YOLLAR_PY.read_text("utf-8")
    YOLLAR_PY.write_text(SURUM_DESEN.sub(f'SURUM = "{yeni}"', metin, count=1), "utf-8")


def dogrula(yeni: str) -> None:
    if not re.fullmatch(r"\d+\.\d+\.\d+", yeni):
        raise SystemExit("Surum 1.2.3 biciminde olmali.")
    simdiki = simdiki_surum()
    if tuple(map(int, yeni.split("."))) <= tuple(map(int, simdiki.split("."))):
        raise SystemExit(f"Yeni surum {simdiki} surumunden buyuk olmali.")


def main() -> None:
    argumanlar = [a for a in sys.argv[1:] if not a.startswith("-")]
    dene = "--dene" in sys.argv
    mesaj = ""
    if "-m" in sys.argv:
        mesaj = sys.argv[sys.argv.index("-m") + 1]

    if not argumanlar:
        print(f"Şu anki sürüm: {simdiki_surum()}")
        print(__doc__)
        return

    yeni = argumanlar[0]
    dogrula(yeni)

    kirli = calistir("git", "status", "--porcelain")
    if kirli and not dene:
        print("Kaydedilmemiş değişiklikler var; sürümle birlikte işlenecek:")
        print(kirli)

    print(f"\n{simdiki_surum()} → {yeni}")
    if not dene:
        surum_yaz(yeni)

    baslik = f"PicaYT {yeni}" + (f" — {mesaj}" if mesaj else "")
    calistir("git", "add", "-A", dene=dene)
    calistir("git", "commit", "-m", baslik, dene=dene)
    calistir("git", "tag", "-a", f"v{yeni}", "-m", baslik, dene=dene)
    # Dalin takip ayari olmayabilir (orn. gecmis yeniden yazildiysa);
    # hedefi acikca vererek buna bagimli kalmiyoruz.
    calistir("git", "push", "-u", "origin", "HEAD:main", dene=dene)
    calistir("git", "push", "origin", f"v{yeni}", dene=dene)

    if dene:
        print("\nDeneme kipiydi, hiçbir şey değişmedi.")
        return

    print(f"""
v{yeni} itildi. Bundan sonrası kendiliğinden:

  1. GitHub Actions kurulum dosyasını derler (~5 dk)
  2. Release'e yükler
  3. Kullanıcıların paneli açılışta görür ve "Güncelle" düğmesi çıkar

İlerlemeyi izle: https://github.com/{_depo()}/actions
""")


def _depo() -> str:
    sys.path.insert(0, str(KOK))
    import yollar
    return yollar.GITHUB_DEPO


if __name__ == "__main__":
    main()
