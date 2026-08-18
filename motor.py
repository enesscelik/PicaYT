"""
PicaYT indirme motoru: ayarlar, is kuyrugu, yt-dlp sarmalayicisi.

Arayuz (picayt.py) bu modulu kullanir; burada HTTP/UI bilgisi yoktur.
"""

from __future__ import annotations

import json
import os
import queue
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yollar          # yt_dlp'den ONCE: guncel surumu sys.path'e koyar
import yt_dlp

AYAR_DOSYA = yollar.AYAR_DOSYA
GECMIS_DOSYA = yollar.GECMIS_DOSYA

# yt-dlp'ye klasor verilir: ffmpeg'in yanindaki ffprobe de boylece bulunur.
FFMPEG_KLASOR = yollar.ffmpeg_klasor()

VARSAYILAN = {
    "hedef": str(yollar.varsayilan_indirme()),
    "esZamanli": 2,
    "sablon": "%(title).150B.%(ext)s",
    "playlistKlasor": True,
    "kucukresimGom": True,
    "ustveriGom": True,
    "bolumler": True,
    "altyaziDiller": ["tr", "en"],
    "otomatikAltyazi": True,
    "hizSiniri": 0,          # KB/s, 0 = sinirsiz
    "tema": "koyu",
    "sonKalite": "1080",
    "sonBicim": "video",
    "sonAltyazi": False,
}


JS_CALISTIRICI = yollar.js_secenekleri()


class IptalEdildi(Exception):
    """Progress hook icinden yukselir, indirmeyi durdurur."""


class Gunlukcu:
    """yt-dlp'nin uyarilarini toplar.

    Uyarilar eskiden `no_warnings` ile tamamen bastiriliyordu; bu yuzden
    "This video is not available" gibi yaniltici bir hata gorunurken asil
    sebebi soyleyen uyari ("n challenge solving failed" gibi) kayboluyordu.
    """

    def __init__(self) -> None:
        self.uyarilar: list[str] = []
        self.hatalar: list[str] = []

    def debug(self, mesaj: str) -> None:
        pass

    def info(self, mesaj: str) -> None:
        pass

    def warning(self, mesaj: str) -> None:
        temiz = _kacis_temizle(mesaj)
        if temiz and temiz not in self.uyarilar:
            self.uyarilar.append(temiz)

    def error(self, mesaj: str) -> None:
        temiz = _kacis_temizle(mesaj)
        if temiz and temiz not in self.hatalar:
            self.hatalar.append(temiz)


# --------------------------------------------------------------------------- #
# Ayarlar
# --------------------------------------------------------------------------- #

class Ayarlar:
    def __init__(self) -> None:
        self.kilit = threading.Lock()
        self.veri = dict(VARSAYILAN)
        if AYAR_DOSYA.is_file():
            try:
                self.veri.update(json.loads(AYAR_DOSYA.read_text("utf-8")))
            except (json.JSONDecodeError, OSError):
                pass
        Path(self.veri["hedef"]).mkdir(parents=True, exist_ok=True)
        self.kaydet()

    def guncelle(self, yeni: dict) -> dict:
        with self.kilit:
            for anahtar, deger in yeni.items():
                if anahtar in VARSAYILAN:
                    self.veri[anahtar] = deger
            Path(self.veri["hedef"]).mkdir(parents=True, exist_ok=True)
            self.kaydet()
            return dict(self.veri)

    def kaydet(self) -> None:
        try:
            AYAR_DOSYA.write_text(
                json.dumps(self.veri, ensure_ascii=False, indent=2), "utf-8"
            )
        except OSError:
            pass

    def __getitem__(self, anahtar: str) -> Any:
        return self.veri[anahtar]


# --------------------------------------------------------------------------- #
# Olay yayini (SSE icin)
# --------------------------------------------------------------------------- #

class Olaylar:
    def __init__(self) -> None:
        self.aboneler: list[queue.Queue] = []
        self.kilit = threading.Lock()

    def abone(self) -> queue.Queue:
        kanal: queue.Queue = queue.Queue(maxsize=500)
        with self.kilit:
            self.aboneler.append(kanal)
        return kanal

    def ayril(self, kanal: queue.Queue) -> None:
        with self.kilit:
            if kanal in self.aboneler:
                self.aboneler.remove(kanal)

    def yayin(self, tur: str, veri: Any) -> None:
        paket = {"tur": tur, "veri": veri}
        with self.kilit:
            hedefler = list(self.aboneler)
        for kanal in hedefler:
            try:
                kanal.put_nowait(paket)
            except queue.Full:
                pass


# --------------------------------------------------------------------------- #
# Is
# --------------------------------------------------------------------------- #

@dataclass
class Is:
    url: str
    baslik: str = ""
    kanal: str = ""
    sure: int = 0
    kucukresim: str = ""
    kalite: str = "1080"
    bicim: str = "video"          # video | mp3 | m4a
    altyazi: bool = False
    liste_adi: str = ""
    kimlik: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    durum: str = "bekliyor"       # bekliyor|iniyor|isleniyor|bitti|hata|iptal|duraklatildi
    yuzde: float = 0.0
    hiz: float = 0.0
    kalan: int = 0
    inen: int = 0
    toplam: int = 0
    asama: str = ""
    dosya: str = ""
    hata: str = ""
    eklendi: float = field(default_factory=time.time)
    bitti_zaman: float = 0.0
    deneme: int = 0
    _iptal: bool = False

    def sozluk(self) -> dict:
        return {
            k: v for k, v in self.__dict__.items() if not k.startswith("_")
        }


# --------------------------------------------------------------------------- #
# Kuyruk
# --------------------------------------------------------------------------- #

class Kuyruk:
    def __init__(self, ayarlar: Ayarlar, olaylar: Olaylar) -> None:
        self.ayarlar = ayarlar
        self.olaylar = olaylar
        self.isler: dict[str, Is] = {}
        self.sira: list[str] = []
        self.kilit = threading.RLock()
        self.uyandir = threading.Event()
        self.calisan: set[str] = set()
        self.gecmis: list[dict] = self._gecmis_oku()
        for _ in range(4):
            threading.Thread(target=self._isci, daemon=True).start()

    # ---------------- genel API ---------------- #

    def ekle(self, kayitlar: list[dict]) -> list[dict]:
        yeni = []
        with self.kilit:
            for kayit in kayitlar:
                is_ = Is(
                    url=kayit["url"],
                    baslik=kayit.get("baslik") or kayit["url"],
                    kanal=kayit.get("kanal", ""),
                    sure=int(kayit.get("sure") or 0),
                    kucukresim=kayit.get("kucukresim", ""),
                    kalite=str(kayit.get("kalite", "1080")),
                    bicim=kayit.get("bicim", "video"),
                    altyazi=bool(kayit.get("altyazi", False)),
                    liste_adi=kayit.get("listeAdi", ""),
                )
                self.isler[is_.kimlik] = is_
                self.sira.append(is_.kimlik)
                yeni.append(is_.sozluk())
        self.olaylar.yayin("eklendi", yeni)
        self.uyandir.set()
        return yeni

    def iptal(self, kimlik: str, duraklat: bool = False) -> None:
        with self.kilit:
            is_ = self.isler.get(kimlik)
            if not is_:
                return
            if is_.durum in ("bekliyor",):
                is_.durum = "duraklatildi" if duraklat else "iptal"
                self._bildir(is_)
                return
            if is_.durum in ("iniyor", "isleniyor"):
                is_._iptal = True
                is_.asama = "durduruluyor…"
                is_.durum = "duraklatildi" if duraklat else "iptal"
                self._bildir(is_)

    def devam(self, kimlik: str) -> None:
        with self.kilit:
            is_ = self.isler.get(kimlik)
            if not is_ or is_.durum in ("iniyor", "isleniyor", "bekliyor"):
                return
            is_._iptal = False
            is_.durum = "bekliyor"
            is_.hata = ""
            is_.asama = ""
            is_.deneme = 0
            if kimlik not in self.sira:
                self.sira.append(kimlik)
            self._bildir(is_)
        self.uyandir.set()

    def sil(self, kimlik: str) -> None:
        with self.kilit:
            is_ = self.isler.get(kimlik)
            if not is_:
                return
            if is_.durum in ("iniyor", "isleniyor"):
                is_._iptal = True
            self.isler.pop(kimlik, None)
            if kimlik in self.sira:
                self.sira.remove(kimlik)
        self.olaylar.yayin("silindi", {"kimlik": kimlik})

    def temizle(self, kapsam: str) -> None:
        with self.kilit:
            for kimlik, is_ in list(self.isler.items()):
                bitmis = is_.durum in ("bitti", "hata", "iptal")
                if kapsam == "hepsi" or bitmis:
                    if is_.durum in ("iniyor", "isleniyor"):
                        is_._iptal = True
                    self.isler.pop(kimlik, None)
                    if kimlik in self.sira:
                        self.sira.remove(kimlik)
        self.olaylar.yayin("tazele", self.durum())

    def durum(self) -> dict:
        with self.kilit:
            return {
                "isler": [i.sozluk() for i in self.isler.values()],
                "gecmis": self.gecmis[:200],
            }

    def gecmis_temizle(self) -> None:
        self.gecmis = []
        self._gecmis_yaz()
        self.olaylar.yayin("tazele", self.durum())

    # ---------------- ic isleyis ---------------- #

    def _bildir(self, is_: Is) -> None:
        # Listeden silinmis bir is hakkinda haber vermeyelim; yoksa iptal
        # sirasindaki son guncelleme karti geri diriltiyor.
        with self.kilit:
            if is_.kimlik not in self.isler:
                return
        self.olaylar.yayin("guncelle", is_.sozluk())

    def _isci(self) -> None:
        while True:
            kimlik = self._sonraki()
            if kimlik is None:
                self.uyandir.wait(0.4)
                self.uyandir.clear()
                continue
            try:
                self._indir(self.isler[kimlik])
            except Exception as hata:            # noqa: BLE001 - isci olmemeli
                with self.kilit:
                    is_ = self.isler.get(kimlik)
                    if is_:
                        is_.durum = "hata"
                        is_.hata = str(hata)[:400]
                        self._bildir(is_)
            finally:
                with self.kilit:
                    self.calisan.discard(kimlik)
                self.uyandir.set()

    def _sonraki(self) -> str | None:
        with self.kilit:
            if len(self.calisan) >= max(1, int(self.ayarlar["esZamanli"])):
                return None
            # Ayni videoyu iki isci birden indirirse gecici dosyalar cakisiyor.
            yurutulen = {self.isler[k].url for k in self.calisan if k in self.isler}
            for kimlik in list(self.sira):
                is_ = self.isler.get(kimlik)
                if is_ is None:
                    self.sira.remove(kimlik)
                    continue
                if is_.url in yurutulen:
                    continue
                if is_.durum == "bekliyor":
                    self.sira.remove(kimlik)
                    self.calisan.add(kimlik)
                    is_.durum = "iniyor"
                    is_.asama = "başlatılıyor"
                    self._bildir(is_)
                    return kimlik
            return None

    def _indir(self, is_: Is) -> None:
        son_bildirim = 0.0

        def ilerleme(d: dict) -> None:
            nonlocal son_bildirim
            if is_._iptal:
                raise IptalEdildi
            if d["status"] != "downloading":
                return
            toplam = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            inen = d.get("downloaded_bytes") or 0
            is_.inen, is_.toplam = int(inen), int(toplam)
            is_.yuzde = (inen / toplam * 100) if toplam else 0.0
            is_.hiz = float(d.get("speed") or 0)
            is_.kalan = int(d.get("eta") or 0)
            tur = (d.get("info_dict") or {}).get("vcodec")
            is_.asama = "ses" if tur in (None, "none") else "video"
            simdi = time.time()
            if simdi - son_bildirim > 0.25:
                son_bildirim = simdi
                self._bildir(is_)

        def son_islem(d: dict) -> None:
            if is_._iptal:
                raise IptalEdildi
            if d["status"] == "started":
                ad = d.get("postprocessor", "")
                is_.durum = "isleniyor"
                is_.asama = ISLEM_ADLARI.get(ad, "işleniyor")
                self._bildir(is_)

        gunlukcu = Gunlukcu()
        secenekler = self._secenekler(is_, ilerleme, son_islem, gunlukcu)
        try:
            with yt_dlp.YoutubeDL(secenekler) as ydl:
                bilgi = yt_dlp.YoutubeDL.sanitize_info(
                    ydl.extract_info(is_.url, download=True)
                ) or {}
        except (IptalEdildi, yt_dlp.utils.DownloadError) as hata:
            # yt-dlp hook icinden yukselen istisnayi kendi hatasina sarabiliyor;
            # iptal bayragi tek guvenilir isaret.
            if is_._iptal or isinstance(hata, IptalEdildi):
                with self.kilit:
                    if is_.durum != "duraklatildi":
                        is_.durum = "iptal"
                    is_.asama = ""
                    is_.hiz = 0
                    self._bildir(is_)
            elif is_.deneme < 2 and _gecici_hata(str(hata)):
                # YouTube ara sira 403 / kopuk baglanti veriyor; yeni bir
                # cozumlemeyle taze baglanti alip kendiliginden tekrar dener.
                is_.deneme += 1
                is_.asama = f"yeniden deneniyor ({is_.deneme}/2)"
                is_.yuzde = 0
                self._bildir(is_)
                time.sleep(2.5)
                self._indir(is_)
            else:
                is_.durum = "hata"
                is_.hata = _hata_sadelestir(str(hata), gunlukcu.uyarilar)
                is_.asama = ""
                is_.hiz = 0
                self._bildir(is_)
            return

        is_.dosya = _cikti_yolu(bilgi)
        is_.baslik = bilgi.get("title") or is_.baslik
        is_.kanal = bilgi.get("uploader") or is_.kanal
        is_.sure = int(bilgi.get("duration") or is_.sure)
        is_.kucukresim = is_.kucukresim or (bilgi.get("thumbnail") or "")
        is_.durum = "bitti"
        is_.yuzde = 100.0
        is_.hiz = 0
        is_.kalan = 0
        # Ayni ada sahip dosya varsa yt-dlp indirmeyi atlar; bunu sessizce
        # "tamamlandi" diye gostermek yaniltici olur.
        is_.asama = ""
        try:
            if is_.dosya:
                bilgi_dosya = Path(is_.dosya).stat()
                if bilgi_dosya.st_mtime < is_.eklendi:
                    is_.asama = "dosya zaten vardı"
                # Video+ses birlestirilince son akisin boyutu gercek dosyayi
                # yansitmiyor; diskteki boyut okunur.
                is_.toplam = bilgi_dosya.st_size
                is_.inen = bilgi_dosya.st_size
        except OSError:
            pass
        is_.bitti_zaman = time.time()
        self._bildir(is_)
        self._gecmise_ekle(is_)

    def _secenekler(
        self,
        is_: Is,
        ilerleme: Callable,
        son_islem: Callable,
        gunlukcu: "Gunlukcu | None" = None,
    ) -> dict:
        a = self.ayarlar.veri
        hedef = Path(a["hedef"])
        if is_.liste_adi and a["playlistKlasor"]:
            hedef = hedef / _dosya_adi_temizle(is_.liste_adi)

        sonrakiler: list[dict] = []
        opts: dict[str, Any] = {
            "paths": {"home": str(hedef)},
            "outtmpl": {"default": a["sablon"]},
            "progress_hooks": [ilerleme],
            "postprocessor_hooks": [son_islem],
            "quiet": True,
            "no_warnings": False,      # uyarilar gunlukcuye gidiyor, gizlenmiyor
            "logger": gunlukcu,
            "noprogress": True,
            "noplaylist": True,
            "consoletitle": False,
            # macOS/Linux'ta gereksiz yere karakter kirpmasin
            "windowsfilenames": yollar.WINDOWS,
            "continuedl": True,
            "retries": 10,
            "fragment_retries": 10,
            "concurrent_fragment_downloads": 5,
            "ignoreerrors": False,
            "overwrites": False,
        }
        # ffmpeg her makinede ayni yerde degil; bulunamazsa yt-dlp kendi
        # arayisina birakilir, kullaniciya da arayuzde uyari cikar.
        if FFMPEG_KLASOR:
            opts["ffmpeg_location"] = FFMPEG_KLASOR

        # YouTube'un "n challenge" dogrulamasi icin JS calistiricisi sart;
        # cozucu betik yt-dlp-ejs ile gomulu geldigi icin uzaktan bilesen
        # indirmeye gerek yok.
        if JS_CALISTIRICI:
            opts["js_runtimes"] = JS_CALISTIRICI
            opts["remote_components"] = []
        if a["hizSiniri"]:
            opts["ratelimit"] = int(a["hizSiniri"]) * 1024

        if is_.bicim in ("mp3", "m4a"):
            opts["format"] = "bestaudio/best"
            sonrakiler.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": is_.bicim,
                "preferredquality": "0" if is_.bicim == "mp3" else "192",
            })
        else:
            if is_.kalite == "en_iyi":
                opts["format"] = "bestvideo*+bestaudio/best"
            else:
                y = int(is_.kalite)
                opts["format"] = (
                    f"bestvideo[height<={y}]+bestaudio/"
                    f"best[height<={y}]/bestvideo*+bestaudio/best"
                )
            opts["merge_output_format"] = "mp4"

        if is_.altyazi:
            opts["writesubtitles"] = True
            opts["writeautomaticsub"] = bool(a["otomatikAltyazi"])
            opts["subtitleslangs"] = list(a["altyaziDiller"]) or ["tr"]
            opts["subtitlesformat"] = "srt/vtt/best"
            sonrakiler.append({"key": "FFmpegSubtitlesConvertor", "format": "srt"})

        if a["ustveriGom"]:
            sonrakiler.append({
                "key": "FFmpegMetadata",
                "add_metadata": True,
                "add_chapters": bool(a["bolumler"]),
            })
        if a["kucukresimGom"]:
            opts["writethumbnail"] = True
            # YouTube kucuk resimleri webp geliyor; m4a/mp4 kabina webp
            # gomulemedigi icin once jpg'ye cevriliyor.
            sonrakiler.append({"key": "FFmpegThumbnailsConvertor", "format": "jpg"})
            sonrakiler.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})

        opts["postprocessors"] = sonrakiler
        return opts

    # ---------------- gecmis ---------------- #

    def _gecmis_oku(self) -> list[dict]:
        if GECMIS_DOSYA.is_file():
            try:
                return json.loads(GECMIS_DOSYA.read_text("utf-8"))
            except (json.JSONDecodeError, OSError):
                return []
        return []

    def _gecmis_yaz(self) -> None:
        try:
            GECMIS_DOSYA.write_text(
                json.dumps(self.gecmis[:500], ensure_ascii=False, indent=1), "utf-8"
            )
        except OSError:
            pass

    def _gecmise_ekle(self, is_: Is) -> None:
        self.gecmis.insert(0, {
            "baslik": is_.baslik,
            "kanal": is_.kanal,
            "url": is_.url,
            "dosya": is_.dosya,
            "kucukresim": is_.kucukresim,
            "bicim": is_.bicim,
            "kalite": is_.kalite,
            "sure": is_.sure,
            "zaman": is_.bitti_zaman,
        })
        self._gecmis_yaz()
        self.olaylar.yayin("gecmis", self.gecmis[:1])


ISLEM_ADLARI = {
    "Merger": "birleştiriliyor",
    "FFmpegMerger": "birleştiriliyor",
    "ExtractAudio": "ses çıkarılıyor",
    "FFmpegExtractAudio": "ses çıkarılıyor",
    "FFmpegMetadata": "üstveri yazılıyor",
    "EmbedThumbnail": "kapak gömülüyor",
    "FFmpegSubtitlesConvertor": "altyazı dönüştürülüyor",
    "FFmpegVideoConvertor": "dönüştürülüyor",
    "MoveFiles": "taşınıyor",
}


# --------------------------------------------------------------------------- #
# Cozumleme (metadata)
# --------------------------------------------------------------------------- #

def _cozum_secenek(gunlukcu: Gunlukcu) -> dict:
    secenek = {
        "quiet": True,
        "no_warnings": False,
        "logger": gunlukcu,
        "noprogress": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "playlistend": 300,
    }
    # Cozumleme de indirme kadar dogrulamaya bagli: calistirici olmadan
    # video hic acilmiyor.
    if JS_CALISTIRICI:
        secenek["js_runtimes"] = JS_CALISTIRICI
        secenek["remote_components"] = []
    return secenek


def coz(url: str) -> dict:
    """Tek video ya da oynatma listesi bilgisini dondurur."""
    gunlukcu = Gunlukcu()
    try:
        with yt_dlp.YoutubeDL(_cozum_secenek(gunlukcu)) as ydl:
            ham = ydl.extract_info(url, download=False)
            bilgi = ydl.sanitize_info(ham)
    except yt_dlp.utils.DownloadError as hata:
        raise RuntimeError(_hata_sadelestir(str(hata), gunlukcu.uyarilar)) from hata

    if bilgi.get("_type") == "playlist":
        ogeler = []
        for giris in bilgi.get("entries") or []:
            if not giris:
                continue
            ogeler.append({
                "url": giris.get("url") or giris.get("webpage_url") or "",
                "baslik": giris.get("title") or "Adsız",
                "sure": int(giris.get("duration") or 0),
                "kucukresim": _kucukresim(giris),
                "kanal": giris.get("uploader") or bilgi.get("uploader") or "",
            })
        return {
            "tur": "liste",
            "baslik": bilgi.get("title") or "Oynatma listesi",
            "kanal": bilgi.get("uploader") or bilgi.get("channel") or "",
            "sayi": len(ogeler),
            "ogeler": ogeler,
            # Kalite listesi yok: arayuz genel varsayilanlari gosterir, cunku
            # liste ogelerinin bicimleri tek tek cozulmedi.
            "kaliteler": [],
        }

    return {
        "tur": "video",
        "url": bilgi.get("webpage_url") or url,
        "baslik": bilgi.get("title") or "Adsız",
        "kanal": bilgi.get("uploader") or bilgi.get("channel") or "",
        "sure": int(bilgi.get("duration") or 0),
        "kucukresim": _kucukresim(bilgi),
        "izlenme": int(bilgi.get("view_count") or 0),
        "kaliteler": _kaliteler(bilgi),
        "altyaziVar": bool(bilgi.get("subtitles") or bilgi.get("automatic_captions")),
    }


def _kaliteler(bilgi: dict) -> list[dict]:
    """Videoda gercekten bulunan cozunurlukleri, tahmini boyutlariyla dondurur."""
    ses_boyut = 0
    en_iyi_ses = 0
    for f in bilgi.get("formats") or []:
        if f.get("vcodec") == "none" and f.get("acodec") != "none":
            oran = f.get("abr") or 0
            if oran >= en_iyi_ses:
                en_iyi_ses = oran
                ses_boyut = f.get("filesize") or f.get("filesize_approx") or 0

    yukseklikler: dict[int, int] = {}
    for f in bilgi.get("formats") or []:
        y = f.get("height")
        if not y or f.get("vcodec") == "none":
            continue
        boyut = f.get("filesize") or f.get("filesize_approx") or 0
        if boyut >= yukseklikler.get(y, 0):
            yukseklikler[y] = boyut

    liste = [{"deger": "en_iyi", "etiket": "En iyi", "boyut": 0}]
    for y in sorted(yukseklikler, reverse=True):
        if y < 240:
            continue
        liste.append({
            "deger": str(y),
            "etiket": f"{y}p" + (" 4K" if y >= 2160 else " 2K" if y >= 1440 else ""),
            "boyut": (yukseklikler[y] + ses_boyut) if yukseklikler[y] else 0,
        })
    return liste


def _kucukresim(bilgi: dict) -> str:
    if bilgi.get("thumbnail"):
        return bilgi["thumbnail"]
    kucukler = bilgi.get("thumbnails") or []
    return kucukler[-1]["url"] if kucukler else ""


def _cikti_yolu(bilgi: dict) -> str:
    istekler = bilgi.get("requested_downloads") or []
    if istekler:
        return istekler[0].get("filepath") or istekler[0].get("_filename") or ""
    return bilgi.get("filepath") or bilgi.get("_filename") or ""


def _dosya_adi_temizle(ad: str) -> str:
    return re.sub(r'[<>:"/\\|?*]+', "-", ad).strip(" .")[:120] or "liste"


_GECICI = (
    "403", "429", "500", "502", "503", "timed out", "timeout",
    "connection", "reset by peer", "fragment", "incomplete read",
    "unable to download video data",
)


def _gecici_hata(metin: str) -> bool:
    kucuk = metin.lower()
    return any(im in kucuk for im in _GECICI)


def _kacis_temizle(metin: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", str(metin)).strip()


def _hata_sadelestir(metin: str, uyarilar: list[str] | None = None) -> str:
    metin = _kacis_temizle(metin).replace("ERROR: ", "")
    uyarilar = uyarilar or []
    tum = metin + " " + " ".join(uyarilar)

    # YouTube'un dogrulamasi cozulemediginde hata "This video is not available"
    # olarak geliyor; asil sebep uyarilarda saklı. Kullaniciya dogrusunu soyle.
    if "challenge" in tum.lower() or "JavaScript runtime" in tum:
        if not JS_CALISTIRICI:
            return ("YouTube doğrulaması çözülemedi: JavaScript çalıştırıcısı "
                    "bulunamadı. PicaYT'yi güncelle (Ayarlar → Hakkında).")
        return ("YouTube doğrulaması çözülemedi. yt-dlp'yi güncelleyip "
                "(Ayarlar → Hakkında) paneli yeniden aç.")

    if "Private video" in metin:
        return "Video gizli, indirilemiyor."
    if "Video unavailable" in metin:
        return "Video kaldırılmış veya bu bölgede yok."
    if "DRM" in metin:
        return "Video DRM korumalı, indirilemez."
    if "members-only" in metin.lower() or "join this channel" in metin.lower():
        return "Yalnızca kanal üyelerine açık video."
    if "Sign in to confirm" in metin or ("age" in metin.lower() and "restrict" in metin.lower()):
        return "Yaş sınırlı video; oturum gerekiyor."
    if "ffmpeg" in metin.lower():
        return "ffmpeg hatası: " + metin[:200]
    return metin[:300]
