"""
PicaYT — yerel YouTube indirme paneli.

Calistirma:
    venv\\Scripts\\pythonw.exe picayt.py

Yerel bir HTTP sunucusu acar ve arayuzu Edge/Chrome uygulama penceresinde
gosterir. Disariya acik degildir: yalnizca 127.0.0.1 dinler ve her istek
oturuma ozel bir anahtar ister.
"""

from __future__ import annotations

import json
import mimetypes
import os
import queue
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yollar
import motor
import guncelleyici

ARAYUZ = yollar.KAYNAK / "ui"
OTURUM = yollar.OTURUM

ANAHTAR = secrets.token_urlsafe(24)
AYARLAR = motor.Ayarlar()
OLAYLAR = motor.Olaylar()
KUYRUK = motor.Kuyruk(AYARLAR, OLAYLAR)


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #

class Sunucu(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "PicaYT"

    # ---- yardimcilar ---- #

    def log_message(self, *_args) -> None:      # sessiz
        pass

    def _yetkili(self, sorgu: dict) -> bool:
        basli = self.headers.get("X-Pica")
        return basli == ANAHTAR or (sorgu.get("anahtar", [""])[0] == ANAHTAR)

    def _json(self, veri, kod: int = 200) -> None:
        govde = json.dumps(veri, ensure_ascii=False).encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(govde)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(govde)

    def _govde(self) -> dict:
        uzunluk = int(self.headers.get("Content-Length") or 0)
        if not uzunluk:
            return {}
        try:
            return json.loads(self.rfile.read(uzunluk).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def _dosya(self, yol: Path) -> None:
        if not yol.is_file():
            self.send_error(404)
            return
        veri = yol.read_bytes()
        tur = mimetypes.guess_type(yol.name)[0] or "application/octet-stream"
        if tur.startswith("text/") or tur.endswith(("javascript", "json")):
            tur += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", tur)
        self.send_header("Content-Length", str(len(veri)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(veri)

    # ---- yonlendirme ---- #

    def do_GET(self) -> None:                    # noqa: N802
        parca = urlparse(self.path)
        sorgu = parse_qs(parca.query)
        yol = parca.path

        if yol == "/canli":
            self._json({"canli": True})
            return

        if yol in ("/", "/index.html"):
            if sorgu.get("anahtar", [""])[0] != ANAHTAR:
                self.send_error(403, "Gecersiz anahtar")
                return
            self._dosya(ARAYUZ / "index.html")
            return

        if yol.startswith("/ui/"):
            hedef = (ARAYUZ / yol[4:]).resolve()
            if ARAYUZ.resolve() in hedef.parents:
                self._dosya(hedef)
            else:
                self.send_error(403)
            return

        if not self._yetkili(sorgu):
            self.send_error(403)
            return

        if yol == "/api/durum":
            self._json({
                "ayarlar": AYARLAR.veri,
                "ortam": {
                    "surum": yollar.SURUM,
                    "ffmpeg": bool(motor.FFMPEG_KLASOR),
                    "ffmpegYol": motor.FFMPEG_KLASOR or "",
                    "altyaziAraci": yollar.altyazi_araci_var(),
                    "ytDlp": motor.yt_dlp.version.__version__,
                    "ytDlpYol": str(Path(motor.yt_dlp.__file__).parent),
                    "jsCalistirici": (yollar.js_calistirici_bul() or ("", ""))[0],
                    "jsYol": (yollar.js_calistirici_bul() or ("", ""))[1],
                },
                **KUYRUK.durum(),
            })
            return

        if yol == "/api/olaylar":
            self._akis()
            return

        self.send_error(404)

    def do_POST(self) -> None:                   # noqa: N802
        parca = urlparse(self.path)
        if not self._yetkili(parse_qs(parca.query)):
            self.send_error(403)
            return

        istek = self._govde()
        yol = parca.path

        try:
            if yol == "/api/coz":
                self._json(motor.coz(istek.get("url", "").strip()))

            elif yol == "/api/ekle":
                self._json(KUYRUK.ekle(istek.get("kayitlar") or []))

            elif yol == "/api/iptal":
                KUYRUK.iptal(istek.get("kimlik", ""), bool(istek.get("duraklat")))
                self._json({"tamam": True})

            elif yol == "/api/devam":
                KUYRUK.devam(istek.get("kimlik", ""))
                self._json({"tamam": True})

            elif yol == "/api/sil":
                KUYRUK.sil(istek.get("kimlik", ""))
                self._json({"tamam": True})

            elif yol == "/api/temizle":
                KUYRUK.temizle(istek.get("kapsam", "bitti"))
                self._json({"tamam": True})

            elif yol == "/api/gecmis-temizle":
                KUYRUK.gecmis_temizle()
                self._json({"tamam": True})

            elif yol == "/api/ayar":
                self._json(AYARLAR.guncelle(istek))

            elif yol == "/api/klasor":
                self._json(_klasor_ac(istek.get("yol", "")))

            elif yol == "/api/oynat":
                self._json(_dosya_ac(istek.get("yol", "")))

            elif yol == "/api/gozat":
                self._json({"yol": _klasor_sec(AYARLAR["hedef"])})

            elif yol == "/api/altyazi":
                self._json(_altyazi_baslat(istek.get("yol", "")))

            elif yol == "/api/ytdlp-guncelle":
                self._json(guncelleyici.ytdlp_guncelle())

            elif yol == "/api/surum-kontrol":
                self._json(guncelleyici.uygulama_son_surum(sessiz=False)
                           or {"durum": "guncel"})

            elif yol == "/api/uygulama-guncelle":
                self._json(guncelleyici.uygulama_guncelle(istek.get("adres", "")))

            elif yol == "/api/kapat":
                self._json({"tamam": True})
                threading.Timer(0.4, lambda: os._exit(0)).start()

            else:
                self.send_error(404)
        except Exception as hata:                # noqa: BLE001
            self._json({"hata": motor._hata_sadelestir(str(hata))}, 200)

    # ---- SSE ---- #

    def _akis(self) -> None:
        kanal = OLAYLAR.abone()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            while True:
                try:
                    paket = kanal.get(timeout=15)
                    govde = json.dumps(paket, ensure_ascii=False)
                except queue.Empty:
                    govde = json.dumps({"tur": "nabiz", "veri": None})
                self.wfile.write(f"data: {govde}\n\n".encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            OLAYLAR.ayril(kanal)


# --------------------------------------------------------------------------- #
# Isletim sistemi islemleri
# --------------------------------------------------------------------------- #

def _klasor_ac(yol: str) -> dict:
    hedef = Path(yol) if yol else Path(AYARLAR["hedef"])
    try:
        if hedef.is_file():
            subprocess.Popen(["explorer", "/select,", str(hedef)])
        else:
            hedef.mkdir(parents=True, exist_ok=True)
            os.startfile(str(hedef))            # noqa: S606
        return {"tamam": True}
    except OSError as hata:
        return {"hata": str(hata)}


def _dosya_ac(yol: str) -> dict:
    hedef = Path(yol)
    if not hedef.is_file():
        return {"hata": "Dosya bulunamadı; taşınmış olabilir."}
    try:
        os.startfile(str(hedef))                # noqa: S606
        return {"tamam": True}
    except OSError as hata:
        return {"hata": str(hata)}


def klasor_sec_penceresi(baslangic: str, cikti: str) -> None:
    """Klasor secme penceresini gosterir; ayri surecte cagrilir.

    Sonuc stdout yerine dosyaya yazilir: penceresiz (windowed) exe'de
    `sys.stdout` guvenilir degil.
    """
    import tkinter as tk
    from tkinter import filedialog

    kok = tk.Tk()
    kok.withdraw()
    kok.attributes("-topmost", True)
    secim = filedialog.askdirectory(
        initialdir=baslangic or str(Path.home()),
        title="İndirme klasörünü seç",
    )
    kok.destroy()
    try:
        Path(cikti).write_text(secim or "", "utf-8")
    except OSError:
        pass


def _klasor_sec(baslangic: str) -> str:
    """Tkinter ana is parcacigi istedigi icin ayri bir surec baslatilir.

    Paketlenmis halde `sys.executable` PicaYT.exe olur; bir Python yorumlayicisi
    aramak yerine uygulama kendini `--klasor-sec` ile cagirir.
    """
    yollar.INDIRME_ONBELLEK.mkdir(parents=True, exist_ok=True)
    cikti = yollar.INDIRME_ONBELLEK / f"klasor-{secrets.token_hex(6)}.txt"
    temel = ([str(Path(sys.executable))] if yollar.DONMUS
             else [sys.executable.replace("pythonw.exe", "python.exe"),
                   str(Path(__file__).resolve())])
    try:
        subprocess.run(
            temel + ["--klasor-sec", baslangic, str(cikti)],
            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=300,
        )
        return cikti.read_text("utf-8").strip() if cikti.is_file() else ""
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError):
        return ""
    finally:
        cikti.unlink(missing_ok=True)


def _altyazi_baslat(yol: str) -> dict:
    """Indirilen videoyu yerel altyazi boru hattina yollar (varsa)."""
    if not yollar.altyazi_araci_var():
        return {"hata": "Bu bilgisayarda yerel altyazı aracı kurulu değil."}
    if not Path(yol).is_file():
        return {"hata": "Video dosyası bulunamadı."}
    try:
        subprocess.Popen(
            [str(yollar.ALTYAZI_PYTHON), str(yollar.ALTYAZI_ARACI), yol],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return {"tamam": True}
    except OSError as hata:
        return {"hata": str(hata)}


# --------------------------------------------------------------------------- #
# Pencere
# --------------------------------------------------------------------------- #

def _tarayici_ac(adres: str) -> None:
    adaylar = [
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    ]
    for aday in adaylar:
        if aday.is_file():
            try:
                subprocess.Popen([
                    str(aday),
                    f"--app={adres}",
                    "--window-size=1240,860",
                    "--disable-features=Translate,ChromeWhatsNewUI",
                ])
                return
            except OSError:
                continue
    webbrowser.open(adres)


def _bos_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _acik_oturum() -> str | None:
    """Panel zaten aciksa adresini dondurur."""
    if not OTURUM.is_file():
        return None
    try:
        kayit = json.loads(OTURUM.read_text("utf-8"))
        adres = f"http://127.0.0.1:{kayit['port']}"
        with urllib.request.urlopen(adres + "/canli", timeout=1):
            return f"{adres}/?anahtar={kayit['anahtar']}"
    except Exception:                            # noqa: BLE001
        return None


def _bekci() -> None:
    """Pencere kapaninca ve is kalmayinca sureci sonlandirir."""
    son_gorulme = time.time() + 25          # ilk acilis icin sure tani
    while True:
        time.sleep(5)
        with OLAYLAR.kilit:
            izleyici = len(OLAYLAR.aboneler)
        calisan = any(
            i.durum in ("iniyor", "isleniyor", "bekliyor")
            for i in list(KUYRUK.isler.values())
        )
        if izleyici or calisan:
            son_gorulme = time.time()
        elif time.time() - son_gorulme > 20:
            OTURUM.unlink(missing_ok=True)
            os._exit(0)


def main() -> None:
    # Klasor secme penceresi ayri surecte acilir; uygulama kendini cagirir.
    if len(sys.argv) > 3 and sys.argv[1] == "--klasor-sec":
        klasor_sec_penceresi(sys.argv[2], sys.argv[3])
        return

    onceki = _acik_oturum()
    if onceki:
        _tarayici_ac(onceki)
        return

    port = int(os.environ.get("PICAYT_PORT") or 0) or _bos_port()
    sunucu = ThreadingHTTPServer(("127.0.0.1", port), Sunucu)
    sunucu.daemon_threads = True
    threading.Thread(target=sunucu.serve_forever, daemon=True).start()

    OTURUM.write_text(json.dumps({"port": port, "anahtar": ANAHTAR}), "utf-8")
    guncelleyici.arka_planda_denetle(
        lambda tur, veri: OLAYLAR.yayin("guncelleme", {"ne": tur, **veri}))
    adres = f"http://127.0.0.1:{port}/?anahtar={ANAHTAR}"
    if os.environ.get("PICAYT_SESSIZ"):          # gelistirme/test kipi
        print(adres, flush=True)
    else:
        threading.Thread(target=_bekci, daemon=True).start()
        _tarayici_ac(adres)

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        OTURUM.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
