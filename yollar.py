"""
Calisma ortamina gore yollari cozer.

Ayni kod uc bicimde calisiyor: kaynaktan (gelistirme), PyInstaller ile
paketlenmis exe olarak, ve baskasinin bilgisayarinda kurulu olarak. Makineye
ozel hicbir yol baska dosyalarda gecmemeli; hepsi burada.

Onemli: bu modul ice aktarilirken kullanici klasorundeki guncel yt-dlp
sys.path'in basina eklenir. Bu yuzden `import yollar` her zaman
`import yt_dlp`den ONCE gelmelidir.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

SURUM = "1.0.0"

# Guncellemelerin cekildigi GitHub deposu. Tek dogruluk kaynagi burasi;
# guncelleyici.py ve kurulum.iss bunu kullanir.
GITHUB_DEPO = os.environ.get("PICAYT_DEPO") or "enesscelik/PicaYT"

DONMUS = bool(getattr(sys, "frozen", False))

# Salt okunur kaynaklar (ui/, ikon). Paketlenmis halde gecici cikarma klasoru.
KAYNAK = Path(getattr(sys, "_MEIPASS", "")) if DONMUS and hasattr(sys, "_MEIPASS") \
    else Path(__file__).resolve().parent

# Uygulamanin kurulu oldugu klasor; ffmpeg burada aranir.
UYGULAMA = Path(sys.executable).resolve().parent if DONMUS else KAYNAK

# Yazilabilir kullanici verisi. Program Files'a kurulsa bile buraya yazilir.
VERI = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "PicaYT"
PAKETLER = VERI / "paketler"          # kendini guncelleyen yt-dlp buraya
AYAR_DOSYA = VERI / "ayarlar.json"
GECMIS_DOSYA = VERI / "gecmis.json"
OTURUM = VERI / ".oturum"
INDIRME_ONBELLEK = VERI / "gecici"    # guncelleme dosyalari

for _klasor in (VERI, PAKETLER):
    _klasor.mkdir(parents=True, exist_ok=True)


def surum_anahtari(metin: str) -> tuple:
    """'2026.07.04' gibi surumleri karsilastirilabilir hale getirir."""
    parcalar = []
    for parca in str(metin).replace("-", ".").split("."):
        parcalar.append(int(parca) if parca.isdigit() else 0)
    return tuple(parcalar)


def indirilen_ytdlp() -> Path | None:
    """En yeni yt-dlp surumunu bulur.

    Iki yerde aranir: uygulamayla gelen kopya ve kullanicinin indirdikleri.
    Surum basina ayri klasor tutuluyor; boylece guncelleme, o an ice aktarilmis
    dosyalarin uzerine yazmaya calismiyor — yenisi bir sonraki aciliste devreye
    girer.

    yt-dlp bilerek exe'nin icine gomulmuyor: PyInstaller'in ice aktarici
    onceligi gomulu surumu her zaman kazandirirdi ve kendini guncelleme
    calismazdi.
    """
    adaylar: list[Path] = []
    for kok in (PAKETLER, UYGULAMA / "paketler"):
        if kok.is_dir():
            adaylar += [p for p in kok.glob("ytdlp-*") if (p / "yt_dlp").is_dir()]
    if not adaylar:
        return None
    return max(adaylar, key=lambda p: surum_anahtari(p.name[6:]))


class _YtDlpBulucu:
    """Indirilen yt-dlp'yi gomulu olana tercih ettirir.

    Paketlenmis uygulamada PyInstaller'in ice aktaricisi `sys.meta_path`in
    basinda durur ve `sys.path`ten once davranir; bu yuzden yalnizca yola
    eklemek yetmez. Bu bulucu `yt_dlp` ve alt modullerini uzerine alip diskteki
    surumden yukler. Gomulu kopya yedek olarak kalir.
    """

    def __init__(self, kok: Path) -> None:
        self.kok = [str(kok)]

    def find_spec(self, ad, yol=None, hedef=None):        # noqa: ANN001
        if ad != "yt_dlp" and not ad.startswith("yt_dlp."):
            return None
        from importlib.machinery import PathFinder
        return PathFinder.find_spec(ad, list(yol) if yol else self.kok, hedef)


_indirilen = indirilen_ytdlp()
if _indirilen:
    if str(_indirilen) not in sys.path:
        sys.path.insert(0, str(_indirilen))
    if DONMUS:
        sys.meta_path.insert(0, _YtDlpBulucu(_indirilen))


def varsayilan_indirme() -> Path:
    """Ilk calistirmada kullanilacak indirme klasoru."""
    videolar = Path.home() / "Videos"
    kok = videolar if videolar.is_dir() else Path.home()
    return kok / "PicaYT"


# --------------------------------------------------------------------------- #
# ffmpeg
# --------------------------------------------------------------------------- #

def _winget_adaylari() -> list[Path]:
    """Winget kurulumunu surum numarasina bagli kalmadan bulur."""
    bulunan: list[Path] = []
    kokler = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/WinGet/Packages",
        Path(os.environ.get("PROGRAMFILES", "")) / "WinGet/Packages",
    ]
    for kok in kokler:
        if not kok.is_dir():
            continue
        for paket in kok.glob("Gyan.FFmpeg*"):
            bulunan += sorted(paket.glob("ffmpeg-*/bin/ffmpeg.exe"), reverse=True)
    return bulunan


def ffmpeg_bul() -> Path | None:
    """ffmpeg.exe'yi bulur; ffprobe'un da yaninda oldugu bir kurulum arar."""
    adaylar: list[Path] = []

    ozel = os.environ.get("FFMPEG_PATH")
    if ozel:
        yol = Path(ozel)
        adaylar.append(yol if yol.suffix else yol / "ffmpeg.exe")

    # Uygulamayla birlikte gelen kopya her zaman once denenir.
    adaylar.append(UYGULAMA / "ffmpeg" / "ffmpeg.exe")
    adaylar.append(UYGULAMA / "ffmpeg" / "bin" / "ffmpeg.exe")

    yolda = shutil.which("ffmpeg")
    if yolda:
        adaylar.append(Path(yolda))

    adaylar += _winget_adaylari()
    adaylar += [
        Path("C:/ProgramData/chocolatey/bin/ffmpeg.exe"),
        Path(os.environ.get("PROGRAMFILES", "")) / "ffmpeg/bin/ffmpeg.exe",
        Path("C:/ffmpeg/bin/ffmpeg.exe"),
    ]

    for aday in adaylar:
        try:
            if aday.is_file() and (aday.parent / "ffprobe.exe").is_file():
                return aday
        except OSError:
            continue
    # ffprobe bulunamadiysa yine de ffmpeg'i dondur; bazi islemler calisir.
    for aday in adaylar:
        try:
            if aday.is_file():
                return aday
        except OSError:
            continue
    return None


def ffmpeg_klasor() -> str | None:
    """yt-dlp'ye verilecek klasor; ffmpeg ve ffprobe birlikte bulunur."""
    yol = ffmpeg_bul()
    return str(yol.parent) if yol else None


# --------------------------------------------------------------------------- #
# Istege bagli yerel altyazi boru hatti
# --------------------------------------------------------------------------- #

ALTYAZI_ARACI = Path.home() / "altyazi" / "altyazi.py"
ALTYAZI_PYTHON = Path.home() / "altyazi" / "venv" / "Scripts" / "pythonw.exe"


def altyazi_araci_var() -> bool:
    """Whisper boru hatti sadece kuruldugu makinede gosterilir."""
    return ALTYAZI_ARACI.is_file() and ALTYAZI_PYTHON.is_file()


# --------------------------------------------------------------------------- #
# Eski surumden tasima
# --------------------------------------------------------------------------- #

def eski_veriyi_tasi() -> None:
    """1.0 oncesi ayar/gecmis dosyalari program klasorundeydi; bir kez tasinir."""
    for eski, yeni in ((KAYNAK / "ayarlar.json", AYAR_DOSYA),
                       (KAYNAK / "gecmis.json", GECMIS_DOSYA)):
        try:
            if eski.is_file() and not yeni.is_file():
                yeni.write_bytes(eski.read_bytes())
                eski.unlink()
        except OSError:
            pass


eski_veriyi_tasi()
