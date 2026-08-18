"""
Iki ayri guncelleme yolu:

1. **yt-dlp** — YouTube sik degistigi icin yt-dlp cabuk bayatliyor. Uygulama
   surumu beklemeden PyPI'dan son yt-dlp'yi cekip kullanici klasorune acar.
   Surum basina ayri klasor kullanilir; yenisi bir sonraki aciliste devreye girer.

2. **PicaYT** — GitHub Releases yoklanir; yeni surum varsa kurulum dosyasi
   indirilip sessiz kipte calistirilir.

Ag hatalari burada yutulur: guncelleme basarisiz olsa da uygulama calismaya
devam etmeli.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

import yollar

PYPI = "https://pypi.org/pypi/yt-dlp/json"
GITHUB_DEPO = yollar.GITHUB_DEPO
GITHUB_SON = f"https://api.github.com/repos/{GITHUB_DEPO}/releases/latest"

BASLIKLAR = {"User-Agent": f"PicaYT/{yollar.SURUM}"}
ZAMAN_ASIMI = 20


def _json_al(adres: str) -> dict:
    istek = urllib.request.Request(adres, headers=BASLIKLAR)
    with urllib.request.urlopen(istek, timeout=ZAMAN_ASIMI) as cevap:
        return json.loads(cevap.read().decode("utf-8"))


def _indir(adres: str, hedef: Path) -> Path:
    hedef.parent.mkdir(parents=True, exist_ok=True)
    istek = urllib.request.Request(adres, headers=BASLIKLAR)
    with urllib.request.urlopen(istek, timeout=180) as cevap, \
            open(hedef, "wb") as dosya:
        shutil.copyfileobj(cevap, dosya)
    return hedef


# --------------------------------------------------------------------------- #
# yt-dlp
# --------------------------------------------------------------------------- #

def ytdlp_surum() -> str:
    try:
        import yt_dlp
        return yt_dlp.version.__version__
    except Exception:                            # noqa: BLE001
        return "?"


def ytdlp_son_surum() -> str:
    return _json_al(PYPI)["info"]["version"]


def ytdlp_guncelle() -> dict:
    """Gerekiyorsa son yt-dlp'yi indirir. Sonuc bir sonraki aciliste etkin olur."""
    simdiki = ytdlp_surum()
    try:
        veri = _json_al(PYPI)
    except Exception as hata:                    # noqa: BLE001
        return {"durum": "hata", "mesaj": f"PyPI'ya ulaşılamadı: {hata}"}

    son = veri["info"]["version"]
    if yollar.surum_anahtari(son) <= yollar.surum_anahtari(simdiki):
        return {"durum": "guncel", "surum": simdiki}

    tekerlek = next(
        (d for d in veri["urls"] if d["packagetype"] == "bdist_wheel"), None)
    if not tekerlek:
        return {"durum": "hata", "mesaj": "Uygun paket bulunamadı."}

    hedef = yollar.PAKETLER / f"ytdlp-{son}"
    gecici = yollar.PAKETLER / f".indirilen-{son}.whl"
    try:
        _indir(tekerlek["url"], gecici)

        # Yarim inen dosya, acilirken "error -3 while decompressing data"
        # gibi anlasilmaz bir zlib hatasi veriyor. Once boyutu ve arsivin
        # butunlugunu dogrula; bozuksa temiz bir mesajla vazgec.
        beklenen = int(tekerlek.get("size") or 0)
        inen = gecici.stat().st_size
        if beklenen and inen != beklenen:
            raise OSError(f"dosya eksik indi ({inen}/{beklenen} bayt)")

        with zipfile.ZipFile(gecici) as arsiv:
            if arsiv.testzip() is not None:
                raise zipfile.BadZipFile("arşiv bozuk")
            if hedef.is_dir():
                shutil.rmtree(hedef, ignore_errors=True)
            arsiv.extractall(hedef)
    except Exception as hata:                    # noqa: BLE001
        shutil.rmtree(hedef, ignore_errors=True)
        return {"durum": "hata",
                "mesaj": f"yt-dlp indirilemedi: {hata}. Bağlantını kontrol "
                         f"edip tekrar dene; uygulama mevcut sürümle çalışmaya "
                         f"devam eder."}
    finally:
        gecici.unlink(missing_ok=True)

    _eski_surumleri_sil(koru=son)
    return {"durum": "guncellendi", "surum": son, "onceki": simdiki}


def _eski_surumleri_sil(koru: str, adet: int = 2) -> None:
    """En yeni birkac surum disindakileri temizler."""
    klasorler = sorted(
        (p for p in yollar.PAKETLER.glob("ytdlp-*") if p.is_dir()),
        key=lambda p: yollar.surum_anahtari(p.name[6:]), reverse=True,
    )
    for eski in klasorler[adet:]:
        if eski.name != f"ytdlp-{koru}":
            shutil.rmtree(eski, ignore_errors=True)


# --------------------------------------------------------------------------- #
# PicaYT
# --------------------------------------------------------------------------- #

def _kendi_kurulumumuz(varliklar: list[dict]) -> dict | None:
    """Yayindaki dosyalar arasindan bu makineye uyani secer.

    macOS icin Apple Silicon ve Intel ayri .dmg olarak yayinlaniyor; yanlisini
    indirmek "uygulama acilmiyor" seklinde geri doner.
    """
    if yollar.WINDOWS:
        return next((v for v in varliklar
                     if v["name"].lower().endswith(".exe")), None)
    if not yollar.MACOS:
        return None

    import platform
    arm = platform.machine().lower() in ("arm64", "aarch64")
    aranan = "arm64" if arm else "intel"
    dmgler = [v for v in varliklar if v["name"].lower().endswith(".dmg")]
    return (next((v for v in dmgler if aranan in v["name"].lower()), None)
            or (dmgler[0] if len(dmgler) == 1 else None))


def uygulama_son_surum(sessiz: bool = True) -> dict:
    """GitHub'daki son yayini dondurur. Yeni surum yoksa bos sozluk.

    `sessiz` kapaliyken ag hatasi da bildirilir; kullanici dugmeye bastiginda
    "guncelsin" demek yaniltici olur.
    """
    if GITHUB_DEPO.startswith("KULLANICI/"):
        # Depo adresi ayarlanmadan derlenmis bir yapim: sessizce hic guncelleme
        # bulamamak yerine sebebini soyle.
        return {} if sessiz else {
            "hata": "Bu yapımda GitHub deposu ayarlanmamış (yollar.py → GITHUB_DEPO)."
        }
    try:
        veri = _json_al(GITHUB_SON)
    except urllib.error.HTTPError as hata:
        if sessiz:
            return {}
        if hata.code in (403, 429):
            # GitHub, oturum acmamis istekleri IP basina saatte 60 ile
            # sinirliyor. Uygulamanin arizasi degil, biraz beklemek yeterli.
            return {"hata": "GitHub sorgu sınırına takıldı (saatte 60). "
                            "Birkaç dakika sonra tekrar dene."}
        if hata.code == 404:
            return {"hata": "Depoda henüz yayınlanmış bir sürüm yok."}
        return {"hata": f"Sürüm bilgisi alınamadı (HTTP {hata.code})."}
    except Exception as hata:                    # noqa: BLE001
        return {} if sessiz else {"hata": f"Sürüm bilgisi alınamadı: {hata}"}

    etiket = str(veri.get("tag_name") or "").lstrip("vV")
    if not etiket or yollar.surum_anahtari(etiket) <= yollar.surum_anahtari(yollar.SURUM):
        return {}

    kurulum = _kendi_kurulumumuz(veri.get("assets") or [])
    if not kurulum:
        return {}

    return {
        "surum": etiket,
        "adres": kurulum["browser_download_url"],
        "boyut": kurulum.get("size", 0),
        "notlar": (veri.get("body") or "").strip()[:1500],
        "yayin": veri.get("html_url", ""),
    }


def uygulama_guncelle(adres: str) -> dict:
    """Kurulum dosyasini indirip sessiz kipte calistirir; uygulama kapanir."""
    if not yollar.DONMUS:
        return {"hata": "Kaynaktan çalışırken güncelleme kurulumu yapılamaz."}
    if not adres.startswith(f"https://github.com/{GITHUB_DEPO}/"):
        # Adres yalnizca kendi depomuzdan gelebilir.
        return {"hata": "Beklenmeyen indirme adresi."}

    hedef = yollar.INDIRME_ONBELLEK / Path(adres).name
    try:
        _indir(adres, hedef)
    except Exception as hata:                    # noqa: BLE001
        return {"hata": f"İndirme başarısız: {hata}"}

    try:
        if yollar.WINDOWS:
            subprocess.Popen(
                [str(hedef), "/SILENT", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"],
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
        else:
            # macOS'ta sessiz kurulum yok: disk kalibi acilir, kullanici
            # uygulamayi Applications'a surukler.
            subprocess.Popen(["open", str(hedef)])
            return {"tamam": True, "elle": True,
                    "mesaj": "Disk kalıbı açıldı. PicaYT'yi Applications "
                             "klasörüne sürükleyip paneli yeniden aç."}
    except OSError as hata:
        return {"hata": str(hata)}

    threading.Timer(1.5, lambda: os._exit(0)).start()
    return {"tamam": True}


# --------------------------------------------------------------------------- #
# Acilista arka plan denetimi
# --------------------------------------------------------------------------- #

def arka_planda_denetle(bildir) -> None:
    """Acilistan kisa sure sonra iki guncellemeyi de sessizce yoklar."""
    def calis() -> None:
        time.sleep(4)
        try:
            sonuc = ytdlp_guncelle()
            if sonuc.get("durum") == "guncellendi":
                bildir("ytdlp", sonuc)
        except Exception:                        # noqa: BLE001
            pass
        try:
            yeni = uygulama_son_surum()
            if yeni:
                bildir("surum", yeni)
        except Exception:                        # noqa: BLE001
            pass

    threading.Thread(target=calis, daemon=True).start()


if __name__ == "__main__":
    print("yt-dlp:", ytdlp_surum())
    print(ytdlp_guncelle())
    print("PicaYT:", yollar.SURUM, uygulama_son_surum() or "guncel")
    sys.exit(0)
