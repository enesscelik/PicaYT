"""
PicaYT'yi GitHub'a baglar. Bir kez calistirilir.

Yaptigi isler:
  1. Depo adresini sorar, koddaki yer tutucularin hepsini gunceller
  2. Git kimligini ayarlar (eksikse)
  3. Ilk islemeyi yapar ve GitHub'a iter
  4. Istenirse ilk surumu etiketleyip yayini baslatir

GitHub CLI gerektirmez; giris, Git'in kendi tarayici penceresiyle yapilir.
"""

from __future__ import annotations

import re
import subprocess
import sys
import webbrowser
from pathlib import Path

KOK = Path(__file__).resolve().parent
YER_TUTUCU = "KULLANICI/PicaYT"

# Windows konsolunun varsayilan kod sayfasi (cp1252) Turkce'nin noktasiz
# "ı" harfini tasimiyor; sabitlemezsek betik sirf bir mesaj yazarken
# UnicodeEncodeError ile cokuyor.
for _akis in (sys.stdout, sys.stderr):
    try:
        _akis.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass


def yaz(metin: str = "") -> None:
    print(metin, flush=True)


def sor(soru: str, varsayilan: str = "") -> str:
    ek = f" [{varsayilan}]" if varsayilan else ""
    cevap = input(f"{soru}{ek}: ").strip()
    return cevap or varsayilan


def git(*komut: str, sessiz: bool = False) -> tuple[int, str]:
    sonuc = subprocess.run(("git",) + komut, cwd=KOK, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
    if not sessiz and sonuc.returncode != 0:
        yaz(f"  ! git {' '.join(komut)}\n  {sonuc.stderr.strip()}")
    return sonuc.returncode, (sonuc.stdout or "").strip()


# --------------------------------------------------------------------------- #

def mevcut_depo() -> str:
    """origin zaten ayarliysa depoyu tekrar sormaya gerek yok."""
    kod, adres = git("remote", "get-url", "origin", sessiz=True)
    if kod != 0:
        return ""
    eslesme = re.search(r"github\.com[/:]([\w.-]+/[\w.-]+?)(?:\.git)?/?$", adres)
    return eslesme.group(1) if eslesme else ""


def depo_adi_al() -> tuple[str, str]:
    hazir = mevcut_depo()
    if hazir:
        yaz(f"  Depo zaten ayarlı: github.com/{hazir}")
        cevap = sor("  Bununla devam edeyim mi? (e/h)", "e")
        if cevap.lower() in ("e", "evet", "y", "yes"):
            kullanici, ad = hazir.split("/", 1)
            return kullanici, ad
        yaz()

    yaz("=" * 62)
    yaz("  1. ADIM — GitHub'da boş bir depo aç")
    yaz("=" * 62)
    yaz()
    yaz("  Tarayıcıda github.com/new sayfasını açıyorum. Orada:")
    yaz()
    yaz("    • Repository name : PicaYT")
    yaz("    • Public seçili olsun")
    yaz()
    yaz("    Sayfanın altındaki 3 seçeneğin ÜÇÜNÜ DE boş bırak:")
    yaz("      · Add a README file      → işaretleme")
    yaz("      · Add .gitignore         → None")
    yaz("      · Choose a license       → None")
    yaz()
    yaz("    Depo tamamen boş olmalı; bizim .gitignore ve OKUBENI.md")
    yaz("    dosyalarımız zaten hazır. GitHub kendi kopyasını oluşturursa")
    yaz("    depo boş kalmaz ve gönderme reddedilir.")
    yaz()
    yaz("    • Create repository")
    yaz()
    input("  Hazır olduğunda Enter'a bas… ")
    try:
        webbrowser.open("https://github.com/new")
    except Exception:                            # noqa: BLE001
        yaz("  (Tarayıcı açılamadı; adresi elle gir: https://github.com/new)")
    yaz()
    input("  Depoyu oluşturduysan Enter'a bas… ")
    yaz()

    while True:
        girdi = sor("  Depo adresini yapıştır (https://github.com/AD/PicaYT)")
        eslesme = re.search(r"github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?/?$", girdi)
        if eslesme:
            return eslesme.group(1), eslesme.group(2)
        if re.fullmatch(r"[\w-]+", girdi):
            yaz(f"  → github.com/{girdi}/PicaYT olarak kabul ediyorum.")
            return girdi, "PicaYT"
        yaz("  Anlayamadım. Örnek: https://github.com/enes/PicaYT")


def yer_tutuculari_degistir(depo: str) -> None:
    kullanici = depo.split("/")[0]
    degisiklikler = [
        (KOK / "yollar.py", YER_TUTUCU, depo),
        (KOK / "kurulum.iss", YER_TUTUCU, depo),
        (KOK / "OKUBENI.md", "KULLANICI/PicaYT", depo),
    ]
    for dosya, eski, yeni in degisiklikler:
        if not dosya.is_file():
            continue
        metin = dosya.read_text("utf-8")
        if eski in metin:
            dosya.write_text(metin.replace(eski, yeni), "utf-8")
            yaz(f"  güncellendi: {dosya.name}")
    yaz(f"  depo adresi: github.com/{depo}  (kullanıcı: {kullanici})")


def kimlik_ayarla(kullanici: str) -> None:
    """Islemelerde gorunecek ad ve e-posta.

    Depo herkese acik olacagi icin varsayilan olarak GitHub'in gizlilik
    korumali noreply adresi onerilir; gercek e-posta zorunlu degil.
    """
    _, mevcut_ad = git("config", "user.name", sessiz=True)
    _, mevcut_posta = git("config", "user.email", sessiz=True)
    if mevcut_ad and mevcut_posta:
        yaz(f"  kimlik: {mevcut_ad} <{mevcut_posta}>")
        return

    ad = sor("  İşlemelerde görünecek ad", mevcut_ad or kullanici)
    posta = sor("  E-posta (herkese açık depoda görünür)",
                mevcut_posta or f"{kullanici}@users.noreply.github.com")
    git("config", "user.name", ad)
    git("config", "user.email", posta)
    yaz(f"  kimlik: {ad} <{posta}>")


def it(depo: str) -> bool:
    adres = f"https://github.com/{depo}.git"
    git("branch", "-M", "main", sessiz=True)
    git("remote", "remove", "origin", sessiz=True)
    kod, _ = git("remote", "add", "origin", adres)
    if kod != 0:
        return False

    git("add", "-A", sessiz=True)
    kod, _ = git("commit", "-m", "PicaYT ilk sürüm", sessiz=True)
    if kod != 0:
        git("commit", "-m", "Depo adresi güncellendi", sessiz=True)

    yaz()
    yaz("  GitHub'a itiliyor…")
    yaz("  İLK SEFERDE tarayıcı açılıp GitHub girişi isteyecek — izin ver.")
    yaz()
    sonuc = subprocess.run(["git", "push", "-u", "origin", "main"], cwd=KOK)
    return sonuc.returncode == 0


def surum_yayinla(depo: str) -> None:
    sys.path.insert(0, str(KOK))
    import yollar
    surum = yollar.SURUM

    yaz()
    cevap = sor(f"  İlk sürümü ({surum}) şimdi yayınlayayım mı? (e/h)", "e")
    if cevap.lower() not in ("e", "evet", "y", "yes"):
        yaz(f"  Atlandı. Sonra: python yayinla.py {surum}")
        return

    git("tag", "-a", f"v{surum}", "-m", f"PicaYT {surum}", sessiz=True)
    kod, _ = git("push", "origin", f"v{surum}")
    if kod == 0:
        yaz()
        yaz(f"  Etiket itildi. GitHub Actions kurulum dosyasını derliyor (~5 dk).")
        yaz(f"  İzle: https://github.com/{depo}/actions")


def main() -> None:
    yaz()
    yaz("  PicaYT — GitHub kurulumu")
    yaz()

    kullanici, ad = depo_adi_al()
    depo = f"{kullanici}/{ad}"

    yaz()
    yaz("=" * 62)
    yaz("  2. ADIM — kod hazırlanıyor")
    yaz("=" * 62)
    yer_tutuculari_degistir(depo)
    kimlik_ayarla(kullanici)

    yaz()
    yaz("=" * 62)
    yaz("  3. ADIM — GitHub'a gönderiliyor")
    yaz("=" * 62)
    if not it(depo):
        yaz()
        yaz("  Gönderilemedi. En sık nedenler:")
        yaz("    • Depo GitHub'da henüz oluşturulmadı")
        yaz("    • Girişte iptal edildi — betiği yeniden çalıştır")
        yaz("    • Depo boş değil: README, .gitignore veya lisans ile")
        yaz("      oluşturulmuş. Depoyu silip boş olarak yeniden aç,")
        yaz("      ya da şunu çalıştır:  git pull --rebase origin main")
        return

    yaz()
    yaz("  Kod GitHub'da.")
    surum_yayinla(depo)

    yaz()
    yaz("=" * 62)
    yaz(f"  Bitti — https://github.com/{depo}")
    yaz("=" * 62)
    yaz()
    yaz("  Bundan sonra yeni sürüm çıkarmak için tek komut:")
    yaz("      python yayinla.py 1.0.1 -m \"Ne değişti\"")
    yaz()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        yaz("\n  İptal edildi.")
    input("\n  Kapatmak için Enter… ")
