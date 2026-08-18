# PicaYT

Windows için yerel YouTube indirme paneli. Kurulum dosyasını çalıştır, masaüstündeki
**PicaYT** kısayoluna çift tıkla. Python, ffmpeg ya da başka bir şey kurman gerekmez —
hepsi kurulumun içinde gelir.

---

## Kullanıcı için

### Kurulum

[Releases](https://github.com/enesscelik/PicaYT/releases) sayfasından en son
`PicaYT-Kurulum-x.y.z.exe` dosyasını indir ve çalıştır. Yönetici hakkı istemez.

> Windows "Bilinmeyen yayımcı" uyarısı verirse **Ek bilgi → Yine de çalıştır** de.
> Kurulum dosyası imzalı olmadığı için normaldir.

### Kullanım

1. Bağlantıyı panele yapıştır — `Ctrl+V` pencerenin herhangi bir yerinde çalışır.
2. Biçim ve kaliteyi seç, `İndir`e bas.
3. İnenler soldaki klasör kartından tek tıkla açılır.

Alt alta birden fazla bağlantı yapıştırabilirsin; hepsi tek listede çözülür,
istediklerini seçip toplu kuyruğa alırsın. Oynatma listesi ve kanal bağlantıları da
çalışır — videolar tek tek işaretlenebilir.

| Tuş | İş |
|---|---|
| `Ctrl+V` | Bağlantıyı yapıştır ve çöz |
| `Enter` | Çöz |
| `Ctrl+Enter` | Önizlemeyi atla, son kullanılan ayarlarla doğrudan indir |
| `Ctrl+K` | Giriş kutusuna dön |
| `Ctrl+,` | Ayarlar |
| `Esc` | Önizlemeyi kapat |

### Özellikler

- **Kuyruk** — eş zamanlı indirme sayısı (1–4), hız sınırı, duraklat/devam
  (kaldığı yerden sürer).
- **Ses** — MP3 veya M4A olarak yalnızca ses.
- **Altyazı** — YouTube altyazılarını ayrı `.srt` olarak indirir; kanal altyazı
  koymamışsa otomatik altyazıya düşer.
- **Geçmiş** — tamamlananlar saklanır, tek tıkla yeniden indirilir.
- Kapak resmi ve üstveri (başlık, kanal, bölüm işaretleri) dosyaya gömülür.
- Geçici ağ hataları (403, kopan bağlantı) iki kez kendiliğinden yeniden denenir.
- Aynı adlı dosya varsa yeniden indirmez, **"dosya zaten vardı"** der.

### Güncelleme

Panel açılışta yeni sürüm olup olmadığına bakar. Varsa üstte bir bant çıkar;
**Güncelle**'ye basınca indirip kurar ve yeniden açılır. Ayarlar ve geçmiş korunur.
Elle bakmak için: **Ayarlar → Hakkında → Güncelleme ara**.

**yt-dlp ayrıca güncellenir.** YouTube sık değiştiği için indirme motoru olan yt-dlp
çabuk bayatlar; panel bunu kendi başına günceller, PicaYT sürümü beklemez. Bu yüzden
YouTube kaynaklı bozulmalar genellikle paneli kapatıp açınca düzelir.

### Nerede ne tutulur

| Ne | Nerede |
|---|---|
| Program | `%LOCALAPPDATA%\Programs\PicaYT` |
| Ayarlar, geçmiş, güncel yt-dlp | `%LOCALAPPDATA%\PicaYT` |
| İndirilen dosyalar | Ayarlardan seçilir (varsayılan `Videolar\PicaYT`) |

Kaldırma: **Ayarlar → Uygulamalar → PicaYT**. İndirdiğin videolar silinmez;
ayar ve geçmişin silinip silinmeyeceğini kaldırma sırasında sorar.

---

## Geliştirici için

### Kaynaktan çalıştırma

```bash
python -m venv .venv
.venv\Scripts\pip install yt-dlp mutagen pywin32 pyinstaller
.venv\Scripts\python picayt.py
```

Kaynaktan çalışırken de kurulu sürümle aynı ayar klasörünü kullanır.
Masaüstü kısayolu için `python kisayol_kur.py`.

### Yapı

| Dosya | İş |
|---|---|
| `picayt.py` | Yerel sunucu, HTTP API, pencere açıcı |
| `motor.py` | İndirme kuyruğu, yt-dlp sarmalayıcısı, ayarlar |
| `yollar.py` | **Sürüm numarası** ve tüm yol çözümlemesi (ffmpeg, veri klasörü) |
| `guncelleyici.py` | yt-dlp ve uygulama güncellemeleri |
| `ui/` | Arayüz — dış bağımlılık yok, tek HTML + CSS + JS |
| `paketle.py` | PyInstaller + Inno Setup ile dağıtım çıktısı |
| `kurulum.iss` | Inno Setup betiği |
| `ffmpeg_getir.py` | Pakete girecek ffmpeg ikililerini indirir |
| `qjs_getir.py` | Pakete girecek QuickJS ikilisini indirir |
| `yayinla.py` | Sürüm yükseltip etiketleyerek yayını tetikler |
| `ikon_uret.py` | `picayt.ico` üretir (bağımlılıksız) |

Makineye özel hiçbir yol `yollar.py` dışında geçmez. Yeni bir sabit yola ihtiyaç
duyarsan oraya ekle.

### Kurulum dosyası üretme

```bash
.venv\Scripts\python paketle.py --kurulum
```

`dagitim\PicaYT-Kurulum-x.y.z.exe` çıkar (~71 MB). Inno Setup gerekir:
`winget install JRSoftware.InnoSetup`. ffmpeg ilk çalıştırmada kendiliğinden iner
(194 MB, depoya girmez).

### Yeni sürüm yayınlama

```bash
python yayinla.py 1.0.1 -m "Kısa açıklama"
```

Bu komut sürümü yükseltir, işler, `v1.0.1` etiketini iter. Sonrası kendiliğinden:
GitHub Actions kurulum dosyasını derler ve Release'e yükler; kullanıcıların paneli
bir sonraki açılışta güncellemeyi teklif eder.

Etiket ile `yollar.py` içindeki `SURUM` uyuşmazsa iş akışı bilerek durur.

### Neden yt-dlp exe'ye gömülmüyor

PyInstaller'ın içe aktarıcısı `sys.meta_path`in başında durur ve gömülü sürümü her
zaman kazandırır. Bu, kendini güncellemeyi imkânsız kılardı. `yollar.py` içindeki
`_YtDlpBulucu`, diskteki güncel yt-dlp'yi öne alır; gömülü kopya yedek olarak kalır.

### YouTube "n challenge" doğrulaması

YouTube 2026'da her istekte çözülmesi gereken bir JavaScript bilmecesi
(*n challenge*) getirdi. Çözülemezse YouTube gerçek video/ses akışlarını hiç
göndermiyor; geriye yalnızca storyboard kalıyor ve yt-dlp bunu
**"This video is not available"** diye bildiriyor — asıl sebebi söylemeyen,
videoyu silinmiş gibi gösteren yanıltıcı bir mesaj.

Çözmek için iki parça gerekiyor, ikisi de kurulumun içinde geliyor:

| Parça | Ne işe yarar | Nerede |
|---|---|---|
| **QuickJS** (`qjs.exe`, ~2 MB) | JavaScript çalıştırıcısı | `{app}\js\` |
| **yt-dlp-ejs** | Bilmeceyi çözen betik | exe'ye gömülü |

Böylece çalışma anında internetten ek bileşen indirilmiyor
(`remote_components` bilerek boş bırakılıyor). Çalıştırıcı bulunamazsa panel
üstte uyarı bandı gösterir; **Ayarlar → Hakkında** bölümünde hangi
çalıştırıcının kullanıldığı yazar.

`yollar.js_calistirici_bul()` önce uygulamayla gelen `qjs.exe`'ye, sonra
sistemde kurulu deno/node/bun'a bakar.

### Bilinen sınırlar

- Kurulum dosyası imzasız — SmartScreen uyarısı çıkar. Kod imzalama sertifikası
  alınırsa `kurulum.iss` içine `SignTool` eklenebilir.
- Yalnızca Windows. Sunucu ve arayüz platformdan bağımsız; `os.startfile`,
  `explorer /select` ve kısayol üretimi Windows'a özgüdür.
