"""
PicaYT'yi dagitilabilir hale getirir.

    python paketle.py            # exe uret
    python paketle.py --kurulum  # exe + Inno Setup kurulum dosyasi

Adimlar:
  1. ffmpeg ikililerini hazirla (yoksa indirir)
  2. PyInstaller ile `dagitim/PicaYT/` klasorunu uret
  3. yt-dlp'yi exe'ye GOMMEDEN yanina koy (kendini guncelleyebilsin diye)
  4. ffmpeg'i cikti klasorune kopyala
  5. istenirse Inno Setup ile kurulum dosyasini derle
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

KOK = Path(__file__).resolve().parent
DAGITIM = KOK / "dagitim"
CALISMA = KOK / "derleme"
CIKTI = DAGITIM / "PicaYT"

sys.path.insert(0, str(KOK))
import yollar                                    # noqa: E402

# Windows konsolunun varsayilan kod sayfasi (cp1252) Turkce'nin noktasiz
# "ı" harfini tasimiyor; UTF-8'e sabitlenmezse derleme, sirf bir mesaj
# yazarken cokuyor. GitHub Actions'ta tam olarak bu oldu.
for _akis in (sys.stdout, sys.stderr):
    try:
        _akis.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

INNO_ADAYLARI = (
    Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Inno Setup 6/ISCC.exe",
    Path(os.environ.get("PROGRAMFILES", "")) / "Inno Setup 6/ISCC.exe",
    # winget kullanici bazli kurdugunda buraya geliyor
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Inno Setup 6/ISCC.exe",
)


def adim(metin: str) -> None:
    print(f"\n=== {metin} ===", flush=True)


def calistir(komut: list[str], **ek) -> None:
    sonuc = subprocess.run(komut, **ek)
    if sonuc.returncode != 0:
        raise SystemExit(f"Komut basarisiz ({sonuc.returncode}): {komut[0]}")


# --------------------------------------------------------------------------- #

def ffmpeg_hazirla() -> None:
    adim("ffmpeg")
    calistir([sys.executable, str(KOK / "ffmpeg_getir.py")])


def quickjs_hazirla() -> None:
    adim("QuickJS")
    calistir([sys.executable, str(KOK / "qjs_getir.py")])


def ikon_hazirla() -> None:
    if not (KOK / "picayt.ico").is_file():
        adim("ikon")
        calistir([sys.executable, str(KOK / "ikon_uret.py")])


def exe_uret() -> None:
    adim("PyInstaller")
    shutil.rmtree(DAGITIM, ignore_errors=True)
    shutil.rmtree(CALISMA, ignore_errors=True)

    komut = [
        sys.executable, "-m", "PyInstaller",
        "--name", "PicaYT",
        "--noconfirm", "--clean", "--windowed",
        "--icon", str(KOK / "picayt.ico"),
        "--distpath", str(DAGITIM),
        "--workpath", str(CALISMA),
        "--specpath", str(CALISMA),
        "--add-data", f"{KOK / 'ui'}{os.pathsep}ui",
        "--add-data", f"{KOK / 'picayt.ico'}{os.pathsep}.",
        # yt-dlp analize dahil: yoksa yalnizca onun kullandigi stdlib
        # modulleri (glob, sqlite3, http.cookiejar...) pakete girmiyor.
        # Calisma aninda yollar.py diskteki guncel surumu one aliyor;
        # gomulu kopya yedek olarak kaliyor.
        "--collect-submodules", "yt_dlp",
        # YouTube dogrulamasini cozen betik; gomulu geldigi icin calisma
        # aninda internetten bilesen indirmeye gerek kalmiyor.
        "--collect-all", "yt_dlp_ejs",
        "--hidden-import", "mutagen",
        "--hidden-import", "tkinter",
        "--hidden-import", "tkinter.filedialog",
        "--collect-all", "mutagen",
        str(KOK / "picayt.py"),
    ]
    calistir(komut)


def ytdlp_koy() -> None:
    """Derleme ortamindaki yt-dlp'yi cikti klasorune surumlu olarak kopyalar."""
    adim("yt-dlp")
    import yt_dlp
    surum = yt_dlp.version.__version__
    kaynak = Path(yt_dlp.__file__).resolve().parent
    hedef = CIKTI / "paketler" / f"ytdlp-{surum}" / "yt_dlp"
    shutil.rmtree(hedef.parent, ignore_errors=True)
    shutil.copytree(kaynak, hedef,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    print(f"  yt-dlp {surum} -> {hedef.parent.name}")


def ffmpeg_koy() -> None:
    adim("ffmpeg kopyalama")
    hedef = CIKTI / "ffmpeg"
    hedef.mkdir(parents=True, exist_ok=True)
    for ad in ("ffmpeg.exe", "ffprobe.exe"):
        shutil.copy2(KOK / "ffmpeg" / ad, hedef / ad)
        print(f"  {ad} · {(hedef / ad).stat().st_size / 1048576:.0f} MB")


def quickjs_koy() -> None:
    adim("QuickJS kopyalama")
    hedef = CIKTI / "js"
    hedef.mkdir(parents=True, exist_ok=True)
    shutil.copy2(KOK / "js" / "qjs.exe", hedef / "qjs.exe")
    print(f"  qjs.exe · {(hedef / 'qjs.exe').stat().st_size / 1048576:.1f} MB")


def belgeler_koy() -> None:
    for ad in ("OKUBENI.md", "LISANS.txt"):
        if (KOK / ad).is_file():
            shutil.copy2(KOK / ad, CIKTI / ad)


def kurulum_uret() -> None:
    adim("Inno Setup")
    iscc = next((p for p in INNO_ADAYLARI if p.is_file()), None)
    if not iscc:
        raise SystemExit(
            "Inno Setup bulunamadi. Kurmak icin:\n"
            "  winget install JRSoftware.InnoSetup"
        )
    calistir([str(iscc), f"/DSURUM={yollar.SURUM}", str(KOK / "kurulum.iss")])


def ozet() -> None:
    toplam = sum(f.stat().st_size for f in CIKTI.rglob("*") if f.is_file())
    print(f"\nÇıktı: {CIKTI}  ({toplam / 1048576:.0f} MB)")
    kurulumlar = sorted(DAGITIM.glob("PicaYT-Kurulum-*.exe"))
    for k in kurulumlar:
        print(f"Kurulum: {k}  ({k.stat().st_size / 1048576:.0f} MB)")


def main() -> None:
    ikon_hazirla()
    ffmpeg_hazirla()
    quickjs_hazirla()
    exe_uret()
    ytdlp_koy()
    ffmpeg_koy()
    quickjs_koy()
    belgeler_koy()
    if "--kurulum" in sys.argv:
        kurulum_uret()
    ozet()


if __name__ == "__main__":
    main()
