/* PicaYT arayuz mantigi */
(() => {
"use strict";

const ANAHTAR = new URLSearchParams(location.search).get("anahtar") || "";
const $  = (s, k = document) => k.querySelector(s);
const $$ = (s, k = document) => [...k.querySelectorAll(s)];

const durum = {
  ayarlar: {},
  ortam: { ffmpeg: true, altyaziAraci: false, surum: "", ytDlp: "" },
  yeniSurum: "",
  isler: new Map(),      // kimlik -> is
  kartlar: new Map(),    // kimlik -> {kok, ...}
  gecmis: [],
  onizleme: null,
  cozuluyor: false,
};

/* ------------------------------------------------------------------ */
/* Sunucu                                                              */
/* ------------------------------------------------------------------ */

async function api(yol, govde) {
  const cevap = await fetch(yol, {
    method: govde === undefined ? "GET" : "POST",
    headers: { "X-Pica": ANAHTAR, "Content-Type": "application/json" },
    body: govde === undefined ? undefined : JSON.stringify(govde),
  });
  if (!cevap.ok) throw new Error("Sunucu yanıt vermedi (" + cevap.status + ")");
  const veri = await cevap.json();
  if (veri && veri.hata) throw new Error(veri.hata);
  return veri;
}

function olaylariDinle() {
  const kaynak = new EventSource("/api/olaylar?anahtar=" + encodeURIComponent(ANAHTAR));
  kaynak.onmessage = (e) => {
    const { tur, veri } = JSON.parse(e.data);
    if (tur === "eklendi")      veri.forEach(isYaz);
    else if (tur === "guncelle") isYaz(veri);
    else if (tur === "silindi")  isSil(veri.kimlik);
    else if (tur === "gecmis")   { durum.gecmis.unshift(veri[0]); gecmisCiz(); }
    else if (tur === "tazele")   { tumunuYukle(veri); }
    else if (tur === "guncelleme") guncellemeBildirimi(veri);
    if (tur !== "nabiz") ozetTazele();
  };
}

/* ------------------------------------------------------------------ */
/* Bicimleme                                                           */
/* ------------------------------------------------------------------ */

const say = (n, b = 1) => n.toLocaleString("tr-TR", { maximumFractionDigits: b });

function sure(sn) {
  sn = Math.round(sn || 0);
  if (!sn) return "";
  const s = sn % 60, d = Math.floor(sn / 60) % 60, sa = Math.floor(sn / 3600);
  const iki = (x) => String(x).padStart(2, "0");
  return sa ? `${sa}:${iki(d)}:${iki(s)}` : `${d}:${iki(s)}`;
}

function boyut(bayt) {
  if (!bayt) return "";
  const birim = ["B", "KB", "MB", "GB", "TB"];
  let i = 0, d = bayt;
  while (d >= 1024 && i < birim.length - 1) { d /= 1024; i++; }
  return say(d, d < 10 && i > 1 ? 1 : 0) + " " + birim[i];
}

function kalanSure(sn) {
  if (!sn || sn < 0) return "";
  if (sn < 60) return `${sn} sn`;
  if (sn < 3600) return `${Math.floor(sn / 60)} dk ${sn % 60} sn`;
  return `${Math.floor(sn / 3600)} sa ${Math.floor((sn % 3600) / 60)} dk`;
}

function izlenme(n) {
  if (!n) return "";
  if (n >= 1e6) return say(n / 1e6, 1) + " mn izlenme";
  if (n >= 1e3) return say(n / 1e3, 0) + " B izlenme";
  return n + " izlenme";
}

const kacis = (m) => m.replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

/* ------------------------------------------------------------------ */
/* Bildirim                                                            */
/* ------------------------------------------------------------------ */

function bildir(metin, tur = "iyi") {
  const el = document.createElement("div");
  el.className = "bildirim " + tur;
  el.innerHTML = `<svg class="ikon"><use href="#i-${tur === "iyi" ? "onay" : "uyari"}"/></svg><span>${kacis(metin)}</span>`;
  $("#bildirimler").append(el);
  setTimeout(() => { el.classList.add("gider"); setTimeout(() => el.remove(), 260); }, 3600);
}

/* ------------------------------------------------------------------ */
/* Cozumleme ve onizleme                                               */
/* ------------------------------------------------------------------ */

const BAGLANTI = /https?:\/\/[^\s<>"']+/gi;

function baglantilar(metin) {
  const bulunan = metin.match(BAGLANTI) || [];
  return [...new Set(bulunan.map((u) => u.replace(/[.,;)\]]+$/, "")))];
}

async function coz() {
  if (durum.cozuluyor) return;
  const urller = baglantilar($("#giris").value);
  if (!urller.length) {
    ustDurum("Geçerli bir bağlantı bulamadım.", true);
    $("#giris").focus();
    return;
  }

  durum.cozuluyor = true;
  $("#cozBtn").disabled = true;
  ustDurum(urller.length > 1 ? `${urller.length} bağlantı çözülüyor…` : "Bilgiler alınıyor…");
  iskeletGoster();

  try {
    if (urller.length === 1) {
      const bilgi = await api("/api/coz", { url: urller[0] });
      onizlemeKur(bilgi);
    } else {
      const sonuclar = await Promise.allSettled(
        urller.map((u) => api("/api/coz", { url: u })));
      const ogeler = [];
      let basarisiz = 0;
      sonuclar.forEach((s, i) => {
        if (s.status !== "fulfilled") { basarisiz++; return; }
        const b = s.value;
        if (b.tur === "liste") {
          b.ogeler.forEach((o) => ogeler.push({ ...o, listeAdi: b.baslik }));
        } else {
          ogeler.push({ url: b.url || urller[i], baslik: b.baslik, kanal: b.kanal,
                        sure: b.sure, kucukresim: b.kucukresim });
        }
      });
      if (!ogeler.length) throw new Error("Hiçbir bağlantı çözülemedi.");
      onizlemeKur({ tur: "toplu", baslik: `${ogeler.length} video`, ogeler,
                    kaliteler: VARSAYILAN_KALITE });
      if (basarisiz) bildir(`${basarisiz} bağlantı çözülemedi.`, "kotu");
    }
    ustDurum("");
  } catch (hata) {
    $("#onizleme").innerHTML = "";
    ustDurum(hata.message, true);
  } finally {
    durum.cozuluyor = false;
    $("#cozBtn").disabled = false;
    gorunumTazele();
  }
}

const VARSAYILAN_KALITE = [
  { deger: "en_iyi", etiket: "En iyi" }, { deger: "2160", etiket: "2160p 4K" },
  { deger: "1440", etiket: "1440p 2K" }, { deger: "1080", etiket: "1080p" },
  { deger: "720", etiket: "720p" }, { deger: "480", etiket: "480p" },
  { deger: "360", etiket: "360p" },
];

/** Sunucu duz metin de gonderse arayuz tek bicimle calissin. */
function kaliteNormalle(liste) {
  if (!Array.isArray(liste) || !liste.length) return VARSAYILAN_KALITE;
  return liste.map((k) => typeof k === "object"
    ? k
    : { deger: String(k), etiket: k === "en_iyi" ? "En iyi" : k + "p" });
}

/** Son kullanilan kalite bu videoda yoksa, altindaki en yuksegine duser. */
function kaliteSecim(kaliteler, istenen) {
  if (kaliteler.some((k) => String(k.deger) === String(istenen))) return istenen;
  if (istenen === "en_iyi") return "en_iyi";
  const hedef = +istenen;
  const sayilar = kaliteler.map((k) => +k.deger).filter(Boolean).sort((a, b) => a - b);
  const altta = sayilar.filter((y) => y <= hedef).pop();
  // Istenenin altinda hicbir secenek yoksa en dusuge duser; boylece "240p"
  // isteyen kullanici birden 4K indirmeye baslamaz.
  return String(altta || sayilar[0] || "en_iyi");
}

function iskeletGoster() {
  $("#onizleme").innerHTML = `
    <div class="iskelet">
      <div class="parla" style="width:168px;height:95px;border-radius:10px"></div>
      <div style="flex:1;display:flex;flex-direction:column;gap:9px;padding-top:4px">
        <div class="parla" style="height:15px;width:72%"></div>
        <div class="parla" style="height:12px;width:44%"></div>
        <div class="parla" style="height:12px;width:30%;margin-top:auto"></div>
      </div>
    </div>`;
  $("#bosDurum").hidden = true;
}

function onizlemeKur(bilgi) {
  const cok = bilgi.tur !== "video";
  const ogeler = cok ? bilgi.ogeler : [{
    url: bilgi.url, baslik: bilgi.baslik, kanal: bilgi.kanal,
    sure: bilgi.sure, kucukresim: bilgi.kucukresim,
  }];

  const kaliteler = kaliteNormalle(bilgi.kaliteler);
  durum.onizleme = {
    tur: bilgi.tur,
    listeAdi: bilgi.tur === "liste" ? bilgi.baslik : "",
    ogeler,
    secili: new Set(ogeler.map((_, i) => i)),
    kaliteler,
    bicim: durum.ayarlar.sonBicim || "video",
    kalite: kaliteSecim(kaliteler, durum.ayarlar.sonKalite || "1080"),
    altyazi: !!durum.ayarlar.sonAltyazi,
    ust: bilgi,
  };
  onizlemeCiz();
}

function onizlemeCiz() {
  const o = durum.onizleme;
  if (!o) { $("#onizleme").innerHTML = ""; gorunumTazele(); return; }

  const kaliteler = o.kaliteler.map((k) => {
    const secili = String(k.deger) === String(o.kalite) ? "selected" : "";
    const bilgiBoyut = k.boyut ? ` — ~${boyut(k.boyut)}` : "";
    return `<option value="${k.deger}" ${secili}>${kacis(k.etiket)}${bilgiBoyut}</option>`;
  }).join("");

  const kapak = o.ogeler.find((x) => x.kucukresim)?.kucukresim || "";
  const tek = o.tur === "video";
  const ilk = o.ogeler[0] || {};

  const ustBilgi = tek
    ? `<div class="on-baslik">${kacis(ilk.baslik || "")}</div>
       <div class="on-meta">
         ${ilk.kanal ? `<span>${kacis(ilk.kanal)}</span><span class="nokta">·</span>` : ""}
         <span>${sure(ilk.sure)}</span>
         ${o.ust.izlenme ? `<span class="nokta">·</span><span>${izlenme(o.ust.izlenme)}</span>` : ""}
       </div>`
    : `<div class="on-baslik">${kacis(o.ust.baslik || "")}</div>
       <div class="on-meta">
         ${o.ust.kanal ? `<span>${kacis(o.ust.kanal)}</span><span class="nokta">·</span>` : ""}
         <span>${o.ogeler.length} video</span>
         <span class="nokta">·</span>
         <span>toplam ${sure(o.ogeler.reduce((t, x) => t + (x.sure || 0), 0)) || "—"}</span>
       </div>`;

  const ogeSatirlari = tek ? "" : `
    <div class="on-ogeler">
      ${o.ogeler.map((x, i) => `
        <label class="on-oge">
          <input type="checkbox" data-sira="${i}" ${o.secili.has(i) ? "checked" : ""}>
          <span class="sira">${i + 1}</span>
          <span class="ad">${kacis(x.baslik || x.url)}</span>
          <span class="sur">${sure(x.sure)}</span>
        </label>`).join("")}
    </div>`;

  $("#onizleme").innerHTML = `
    <div class="onizleme">
      <div class="on-ust">
        ${kapak ? `<img class="kapak" src="${kacis(kapak)}" alt="" referrerpolicy="no-referrer">`
                : `<div class="kapak"></div>`}
        <div class="on-bilgi">
          ${ustBilgi}
          ${tek ? "" : `<div class="on-meta" style="margin-top:10px">
              <button class="sade" id="hepsiSec">Tümünü seç</button>
              <button class="sade" id="hicSec">Seçimi kaldır</button>
            </div>`}
        </div>
        <button class="eylem" id="onKapat" title="Kapat (Esc)">
          <svg class="ikon"><use href="#i-kapat"/></svg></button>
      </div>

      <div class="on-secim">
        <div class="alan">
          <label>Biçim</label>
          <div class="segment" id="bicimSec">
            <button data-deger="video" class="${o.bicim === "video" ? "secili" : ""}">
              <svg class="ikon"><use href="#i-video"/></svg>Video</button>
            <button data-deger="mp3" class="${o.bicim === "mp3" ? "secili" : ""}">
              <svg class="ikon"><use href="#i-muzik"/></svg>MP3</button>
            <button data-deger="m4a" class="${o.bicim === "m4a" ? "secili" : ""}">M4A</button>
          </div>
        </div>

        <div class="alan" id="kaliteAlan" ${o.bicim !== "video" ? "hidden" : ""}>
          <label>Kalite</label>
          <select class="kalite-sec" id="kaliteSec">${kaliteler}</select>
        </div>

        <div class="alan">
          <label>Ek</label>
          <label class="onay"><input type="checkbox" id="altyaziOnay" ${o.altyazi ? "checked" : ""}>
            Altyazı indir (.srt)</label>
        </div>

        <div class="on-eylem">
          <button class="birincil" id="ekleBtn">
            ${tek ? "İndir" : `<span id="ekleSayi">${o.secili.size}</span> videoyu indir`}
          </button>
        </div>
      </div>
      ${ogeSatirlari}
    </div>`;

  onizlemeBagla();
  gorunumTazele();
}

function onizlemeBagla() {
  const o = durum.onizleme;

  $("#onKapat").onclick = () => { durum.onizleme = null; onizlemeCiz(); };

  $$("#bicimSec button").forEach((b) => b.onclick = () => {
    o.bicim = b.dataset.deger;
    $$("#bicimSec button").forEach((x) => x.classList.toggle("secili", x === b));
    $("#kaliteAlan").hidden = o.bicim !== "video";
  });

  const kalite = $("#kaliteSec");
  if (kalite) kalite.onchange = () => o.kalite = kalite.value;
  $("#altyaziOnay").onchange = (e) => o.altyazi = e.target.checked;
  $("#ekleBtn").onclick = kuyrugaEkle;

  $$(".on-oge input").forEach((c) => c.onchange = () => {
    const i = +c.dataset.sira;
    c.checked ? o.secili.add(i) : o.secili.delete(i);
    sayiTazele();
  });
  if ($("#hepsiSec")) $("#hepsiSec").onclick = () => {
    o.ogeler.forEach((_, i) => o.secili.add(i));
    $$(".on-oge input").forEach((c) => c.checked = true); sayiTazele();
  };
  if ($("#hicSec")) $("#hicSec").onclick = () => {
    o.secili.clear();
    $$(".on-oge input").forEach((c) => c.checked = false); sayiTazele();
  };

  function sayiTazele() {
    const el = $("#ekleSayi");
    if (el) el.textContent = o.secili.size;
    $("#ekleBtn").disabled = o.secili.size === 0;
  }
}

async function kuyrugaEkle() {
  const o = durum.onizleme;
  if (!o) return;
  const kayitlar = o.ogeler
    .filter((_, i) => o.secili.has(i))
    .map((x) => ({
      url: x.url, baslik: x.baslik, kanal: x.kanal || "",
      sure: x.sure || 0, kucukresim: x.kucukresim || "",
      kalite: o.kalite, bicim: o.bicim, altyazi: o.altyazi,
      listeAdi: x.listeAdi || o.listeAdi || "",
    }));
  if (!kayitlar.length) return;

  try {
    await api("/api/ekle", { kayitlar });
    await api("/api/ayar", { sonKalite: o.kalite, sonBicim: o.bicim, sonAltyazi: o.altyazi });
    durum.ayarlar.sonKalite = o.kalite;
    durum.ayarlar.sonBicim = o.bicim;
    durum.ayarlar.sonAltyazi = o.altyazi;
    durum.onizleme = null;
    onizlemeCiz();
    $("#giris").value = "";
    girisBoyutla();
    bildir(kayitlar.length === 1 ? "Kuyruğa alındı." : `${kayitlar.length} video kuyruğa alındı.`);
  } catch (hata) {
    bildir(hata.message, "kotu");
  }
}

/* ------------------------------------------------------------------ */
/* Is kartlari                                                         */
/* ------------------------------------------------------------------ */

const DURUM_YAZI = {
  bekliyor: "sırada", iniyor: "iniyor", isleniyor: "işleniyor",
  bitti: "tamamlandı", hata: "hata", iptal: "iptal edildi",
  duraklatildi: "duraklatıldı",
};

function kartOlustur(is_) {
  const kok = document.createElement("div");
  kok.className = "kart";
  kok.innerHTML = `
    ${is_.kucukresim
      ? `<img class="kart-kapak" src="${kacis(is_.kucukresim)}" alt="" referrerpolicy="no-referrer">`
      : `<div class="kart-kapak bos"><svg class="ikon"><use href="#i-video"/></svg></div>`}
    <div class="kart-govde">
      <div class="kart-baslik"></div>
      <div class="kart-meta"></div>
      <div class="cubuk"><div class="cubuk-dolu" style="width:0"></div></div>
    </div>
    <div class="kart-eylem"></div>`;

  const ref = {
    kok,
    baslik: $(".kart-baslik", kok),
    meta:   $(".kart-meta", kok),
    cubuk:  $(".cubuk", kok),
    dolu:   $(".cubuk-dolu", kok),
    eylem:  $(".kart-eylem", kok),
  };
  durum.kartlar.set(is_.kimlik, ref);
  return ref;
}

function kartYaz(is_) {
  const ref = durum.kartlar.get(is_.kimlik) || kartOlustur(is_);
  const bitti = is_.durum === "bitti";

  ref.kok.classList.toggle("bitti", bitti);
  ref.kok.classList.toggle("hata", is_.durum === "hata");
  ref.baslik.textContent = is_.baslik;
  ref.baslik.title = is_.baslik;

  const parcalar = [];
  const ana = DURUM_YAZI[is_.durum] || is_.durum;
  const ek = is_.asama && is_.asama !== ana ? " · " + kacis(is_.asama) : "";
  parcalar.push(`<span class="durum-yazi ${is_.durum}">${ana}${ek}</span>`);

  if (is_.durum === "iniyor") {
    if (is_.toplam) parcalar.push(`<span>${say(is_.yuzde, 0)}% · ${boyut(is_.inen)} / ${boyut(is_.toplam)}</span>`);
    if (is_.hiz) parcalar.push(`<span>${boyut(is_.hiz)}/sn</span>`);
    if (is_.kalan) parcalar.push(`<span>${kalanSure(is_.kalan)} kaldı</span>`);
  } else if (is_.durum === "hata") {
    parcalar.push(`<span title="${kacis(is_.hata)}">${kacis(is_.hata)}</span>`);
  } else {
    if (is_.kanal) parcalar.push(`<span>${kacis(is_.kanal)}</span>`);
    if (is_.sure) parcalar.push(`<span>${sure(is_.sure)}</span>`);
    if (bitti && is_.toplam) parcalar.push(`<span>${boyut(is_.toplam)}</span>`);
  }
  const rozetler = [
    is_.bicim !== "video" ? `<span class="etiket ses">${is_.bicim.toUpperCase()}</span>`
                          : `<span class="etiket">${is_.kalite === "en_iyi" ? "EN İYİ" : is_.kalite + "P"}</span>`,
    is_.altyazi ? `<span class="etiket alt">SRT</span>` : "",
  ].join("");
  ref.meta.innerHTML = rozetler + parcalar.join('<span class="nokta">·</span>');

  const gizle = bitti || ["hata", "iptal"].includes(is_.durum);
  ref.cubuk.style.display = gizle ? "none" : "";
  ref.cubuk.classList.toggle("belirsiz",
    is_.durum === "isleniyor" || (is_.durum === "iniyor" && !is_.toplam));
  ref.dolu.style.width = (is_.durum === "bekliyor" ? 0 : is_.yuzde) + "%";
  ref.dolu.className = "cubuk-dolu" + (is_.durum === "duraklatildi" ? " durgun" : "");

  eylemleriYaz(ref, is_);
  return ref;
}

function eylemleriYaz(ref, is_) {
  const dugmeler = [];
  const dug = (ikon, baslik, sinif, islev) =>
    dugmeler.push({ ikon, baslik, sinif: sinif || "", islev });

  if (is_.durum === "bitti") {
    if (is_.dosya) {
      dug("i-oynat", "Oynat", "iyi", () => api("/api/oynat", { yol: is_.dosya })
        .catch((h) => bildir(h.message, "kotu")));
      dug("i-klasor", "Klasörde göster", "", () => api("/api/klasor", { yol: is_.dosya }));
      // Whisper boru hatti yalnizca kurulu oldugu makinede anlamli.
      if (is_.bicim === "video" && durum.ortam.altyaziAraci) {
        dug("i-altyazi", "Yerel altyazı aracına gönder", "", async () => {
          try { await api("/api/altyazi", { yol: is_.dosya }); bildir("Altyazı üretimi başladı."); }
          catch (h) { bildir(h.message, "kotu"); }
        });
      }
    }
  } else if (["iniyor", "isleniyor", "bekliyor"].includes(is_.durum)) {
    dug("i-duraklat", "Duraklat", "", () => api("/api/iptal", { kimlik: is_.kimlik, duraklat: true }));
  } else if (["duraklatildi", "iptal", "hata"].includes(is_.durum)) {
    dug("i-yenile", is_.durum === "hata" ? "Yeniden dene" : "Devam et", "",
        () => api("/api/devam", { kimlik: is_.kimlik }));
  }
  dug("i-sil", "Listeden kaldır", "tehlike", () => api("/api/sil", { kimlik: is_.kimlik }));

  const imza = dugmeler.map((d) => d.ikon).join(",");
  if (ref.imza === imza) {
    [...ref.eylem.children].forEach((el, i) => el.onclick = dugmeler[i].islev);
    return;
  }
  ref.imza = imza;
  ref.eylem.innerHTML = dugmeler.map((d) =>
    `<button class="eylem ${d.sinif}" title="${d.baslik}">
       <svg class="ikon"><use href="#${d.ikon}"/></svg></button>`).join("");
  [...ref.eylem.children].forEach((el, i) => el.onclick = dugmeler[i].islev);
}

function isYaz(is_) {
  durum.isler.set(is_.kimlik, is_);
  const ref = kartYaz(is_);
  if (!ref.kok.isConnected) $("#liste").prepend(ref.kok);
}

function isSil(kimlik) {
  durum.isler.delete(kimlik);
  const ref = durum.kartlar.get(kimlik);
  if (ref) { ref.kok.remove(); durum.kartlar.delete(kimlik); }
}

/* ------------------------------------------------------------------ */
/* Gecmis                                                              */
/* ------------------------------------------------------------------ */

function gecmisCiz() {
  const kap = $("#gecmisListe");
  $("#gecmisSayi").textContent = durum.gecmis.length ? `(${durum.gecmis.length})` : "";
  if (!durum.gecmis.length) {
    kap.innerHTML = `<div class="bos"><div class="bos-im">
      <svg class="ikon"><use href="#i-gecmis"/></svg></div>
      <h3>Geçmiş boş</h3><p>Tamamlanan indirmeler burada birikir.</p></div>`;
    return;
  }
  kap.innerHTML = durum.gecmis.map((g, i) => `
    <div class="kart" data-sira="${i}">
      ${g.kucukresim
        ? `<img class="kart-kapak" src="${kacis(g.kucukresim)}" alt="" referrerpolicy="no-referrer">`
        : `<div class="kart-kapak bos"><svg class="ikon"><use href="#i-video"/></svg></div>`}
      <div class="kart-govde">
        <div class="kart-baslik" title="${kacis(g.baslik)}">${kacis(g.baslik)}</div>
        <div class="kart-meta">
          <span class="etiket ${g.bicim !== "video" ? "ses" : ""}">${
            g.bicim === "video" ? (g.kalite === "en_iyi" ? "EN İYİ" : g.kalite + "P") : g.bicim.toUpperCase()}</span>
          ${g.kanal ? `<span>${kacis(g.kanal)}</span><span class="nokta">·</span>` : ""}
          <span>${sure(g.sure)}</span>
          <span class="nokta">·</span>
          <span>${new Date((g.zaman || 0) * 1000).toLocaleString("tr-TR",
            { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" })}</span>
        </div>
      </div>
      <div class="kart-eylem">
        <button class="eylem iyi" data-is="oynat" title="Oynat"><svg class="ikon"><use href="#i-oynat"/></svg></button>
        <button class="eylem" data-is="klasor" title="Klasörde göster"><svg class="ikon"><use href="#i-klasor"/></svg></button>
        <button class="eylem" data-is="tekrar" title="Yeniden indir"><svg class="ikon"><use href="#i-yenile"/></svg></button>
      </div>
    </div>`).join("");

  $$("#gecmisListe .eylem").forEach((b) => b.onclick = async () => {
    const g = durum.gecmis[+b.closest(".kart").dataset.sira];
    try {
      if (b.dataset.is === "oynat") await api("/api/oynat", { yol: g.dosya });
      else if (b.dataset.is === "klasor") await api("/api/klasor", { yol: g.dosya });
      else {
        await api("/api/ekle", { kayitlar: [{ ...g, altyazi: false }] });
        gorunumSec("kuyruk");
        bildir("Yeniden kuyruğa alındı.");
      }
    } catch (hata) { bildir(hata.message, "kotu"); }
  });
}

/* ------------------------------------------------------------------ */
/* Gorunum / ozet                                                      */
/* ------------------------------------------------------------------ */

function gorunumSec(ad) {
  $$(".gez").forEach((b) => b.classList.toggle("etkin", b.dataset.gorunum === ad));
  $("#gorunumKuyruk").hidden = ad !== "kuyruk";
  $("#gorunumGecmis").hidden = ad !== "gecmis";
  $("#gorunumAyarlar").hidden = ad !== "ayarlar";
  if (ad === "gecmis") gecmisCiz();
}

function gorunumTazele() {
  const varMi = durum.isler.size > 0;
  $("#listeBasi").hidden = !varMi;
  $("#bosDurum").hidden = varMi || !!durum.onizleme || durum.cozuluyor;
  $("#kuyrukSayi").textContent = varMi ? `(${durum.isler.size})` : "";
}

function ozetTazele() {
  const etkin = [...durum.isler.values()]
    .filter((i) => ["iniyor", "isleniyor", "bekliyor"].includes(i.durum)).length;
  const rozet = $("#rozetKuyruk");
  rozet.hidden = !etkin;
  rozet.textContent = etkin;
  const inen = [...durum.isler.values()].filter((i) => i.durum === "iniyor");
  document.title = inen.length
    ? `↓ ${say(inen.reduce((t, i) => t + i.yuzde, 0) / inen.length, 0)}% — PicaYT`
    : "PicaYT";
  gorunumTazele();
}

function ustDurum(metin, hataMi = false) {
  const el = $("#ustDurum");
  el.textContent = metin;
  el.classList.toggle("hata", hataMi);
}

/* ------------------------------------------------------------------ */
/* Bantlar ve guncelleme                                               */
/* ------------------------------------------------------------------ */

const bantlar = new Map();   // anahtar -> {tur, metin, eylem}

function bantCiz() {
  const kap = $("#bantlar");
  kap.innerHTML = [...bantlar.entries()].map(([anahtar, b]) => `
    <div class="bant ${b.tur}" data-anahtar="${anahtar}">
      <svg class="ikon"><use href="#i-${b.tur === "uyari" ? "uyari" : "indir"}"/></svg>
      <div class="bant-metin">${b.metin}</div>
      ${b.eylem ? `<button class="bant-dugme">${kacis(b.eylem.etiket)}</button>` : ""}
      <button class="eylem bant-kapat" title="Kapat">
        <svg class="ikon"><use href="#i-kapat"/></svg></button>
    </div>`).join("");

  $$("#bantlar .bant").forEach((el) => {
    const b = bantlar.get(el.dataset.anahtar);
    const dugme = $(".bant-dugme", el);
    if (dugme) dugme.onclick = () => b.eylem.calistir(dugme);
    $(".bant-kapat", el).onclick = () => { bantlar.delete(el.dataset.anahtar); bantCiz(); };
  });
}

function bantKoy(anahtar, tur, metin, eylem) {
  bantlar.set(anahtar, { tur, metin, eylem });
  bantCiz();
}

function ortamiDegerlendir() {
  // JS calistiricisi olmadan YouTube dogrulamasi cozulemiyor ve videolar
  // "bulunamadi" gibi yaniltici bir hatayla basarisiz oluyor.
  if (!durum.ortam.jsCalistirici) {
    bantKoy("js", "uyari",
      "<b>JavaScript çalıştırıcısı yok.</b> YouTube doğrulaması çözülemediği için " +
      "bazı videolar indirilemez. Ayarlar → Hakkında'dan güncellemeyi dene.");
  } else {
    bantlar.delete("js");
  }
  if (!durum.ortam.ffmpeg) {
    bantKoy("ffmpeg", "uyari",
      "<b>ffmpeg bulunamadı.</b> Video ve ses birleştirme yapılamaz; " +
      "indirmeler yarım kalabilir. Kurmak için: <code>winget install Gyan.FFmpeg</code>");
  } else {
    bantlar.delete("ffmpeg");
    bantCiz();
  }
}

function guncellemeBildirimi(veri) {
  if (veri.ne === "ytdlp") {
    durum.ortam.ytDlp = veri.surum;
    hakkindaCiz();
    bildir(`yt-dlp ${veri.surum} indirildi — panel yeniden açılınca etkin olacak.`);
    return;
  }
  if (veri.ne === "surum") yeniSurumBandi(veri);
}

function yeniSurumBandi(veri) {
  durum.yeniSurum = veri.surum;
  hakkindaCiz();
  bantKoy("surum", "bilgi",
    `<b>PicaYT ${kacis(veri.surum)} yayınlandı.</b> ` +
    (veri.notlar ? kacis(veri.notlar.split("\n")[0]).slice(0, 120) : "Yeni sürüme geçebilirsin."),
    {
      etiket: "Güncelle",
      calistir: async (dugme) => {
        dugme.disabled = true;
        dugme.textContent = "İndiriliyor…";
        try {
          const s = await api("/api/uygulama-guncelle", { adres: veri.adres });
          // macOS'ta sessiz kurulum yok; kullanicinin suruklemesi gerekiyor.
          if (s && s.elle) { dugme.textContent = "Açıldı"; bildir(s.mesaj); }
          else dugme.textContent = "Kurulum başlıyor…";
        } catch (hata) {
          dugme.disabled = false;
          dugme.textContent = "Güncelle";
          bildir(hata.message, "kotu");
        }
      },
    });
}

function hakkindaCiz() {
  const o = durum.ortam;
  // Kurulu surum ile yayindaki surumu birlikte goster; yalniz kurulu olani
  // gostermek "guncelleme buldu ama bir sey degismedi" izlenimi veriyordu.
  $("#aSurum").textContent = durum.yeniSurum
    ? `${o.surum} → ${durum.yeniSurum} var`
    : (o.surum || "—");
  $("#surumNot").textContent = durum.yeniSurum
    ? "Yeni sürüm hazır — yukarıdaki banttan güncelleyebilirsin."
    : "Kurulu sürüm. Panel açılışta yeni sürüm olup olmadığına bakar.";
  $("#aYtDlp").textContent = o.ytDlp || "—";
  $("#aFfmpeg").textContent = o.ffmpeg ? "bulundu" : "yok";
  $("#aFfmpegYol").textContent = o.ffmpegYol || "Bulunamadı — birleştirme yapılamaz.";
  if (o.ytDlpYol) $("#aYtDlpYol").textContent = o.ytDlpYol;
  $("#aJs").textContent = o.jsCalistirici || "yok";
  $("#aJsYol").textContent = o.jsYol
    || "Bulunamadı — bazı videolar çözülemez. PicaYT'yi güncelle.";
}

function guncellemeBagla() {
  $("#aSurumKontrol").onclick = async (e) => {
    const d = e.target;
    d.disabled = true; d.textContent = "Aranıyor…";
    try {
      const s = await api("/api/surum-kontrol", {});
      if (s.surum) { yeniSurumBandi(s); bildir(`Yeni sürüm: ${s.surum}`); }
      else bildir("En güncel sürümü kullanıyorsun.");
    } catch (hata) { bildir(hata.message, "kotu"); }
    d.disabled = false; d.textContent = "Güncelleme ara";
  };

  $("#aYtDlpGuncelle").onclick = async (e) => {
    const d = e.target;
    d.disabled = true; d.textContent = "Aranıyor…";
    try {
      const s = await api("/api/ytdlp-guncelle", {});
      if (s.durum === "guncellendi") {
        durum.ortam.ytDlp = s.surum; hakkindaCiz();
        bildir(`yt-dlp ${s.surum} indirildi — panel yeniden açılınca etkin olacak.`);
      } else if (s.durum === "guncel") bildir("yt-dlp zaten güncel.");
      else bildir(s.mesaj || "Güncellenemedi.", "kotu");
    } catch (hata) { bildir(hata.message, "kotu"); }
    d.disabled = false; d.textContent = "Güncelle";
  };
}

/* ------------------------------------------------------------------ */
/* Ayarlar arayuzu                                                     */
/* ------------------------------------------------------------------ */

function ayarlariCiz() {
  const a = durum.ayarlar;
  $("#aHedef").value = a.hedef;
  $("#klasorYol").textContent = a.hedef;
  $("#klasorAc").title = a.hedef;
  $("#aHiz").value = a.hizSiniri;
  $("#aSablon").value = a.sablon;
  $("#aDiller").value = (a.altyaziDiller || []).join(", ");
  $("#aOtoAltyazi").checked = !!a.otomatikAltyazi;
  $("#aNazik").checked = !!a.nazikMod;
  $("#aCerez").value = a.cerezTarayici || "";
  $("#aKapak").checked = !!a.kucukresimGom;
  $("#aUstveri").checked = !!a.ustveriGom;
  $("#aListeKlasor").checked = !!a.playlistKlasor;
  $$("#aEsZamanli button").forEach((b) =>
    b.classList.toggle("secili", +b.dataset.deger === +a.esZamanli));
  $$("#aTema button").forEach((b) => b.classList.toggle("secili", b.dataset.deger === a.tema));
  document.documentElement.dataset.tema = a.tema;
}

async function ayarYaz(yeni) {
  Object.assign(durum.ayarlar, yeni);
  ayarlariCiz();
  try { durum.ayarlar = await api("/api/ayar", yeni); ayarlariCiz(); }
  catch (hata) { bildir(hata.message, "kotu"); }
}

function ayarlariBagla() {
  $("#aGozat").onclick = async () => {
    const { yol } = await api("/api/gozat", {});
    if (yol) { await ayarYaz({ hedef: yol }); bildir("İndirme klasörü güncellendi."); }
  };
  $$("#aEsZamanli button").forEach((b) => b.onclick = () => ayarYaz({ esZamanli: +b.dataset.deger }));
  $$("#aTema button").forEach((b) => b.onclick = () => ayarYaz({ tema: b.dataset.deger }));
  $("#aHiz").onchange = (e) => ayarYaz({ hizSiniri: Math.max(0, +e.target.value || 0) });
  $("#aSablon").onchange = (e) => ayarYaz({ sablon: e.target.value.trim() || "%(title).150B.%(ext)s" });
  $("#aDiller").onchange = (e) => ayarYaz({
    altyaziDiller: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) });
  $("#aOtoAltyazi").onchange = (e) => ayarYaz({ otomatikAltyazi: e.target.checked });
  $("#aNazik").onchange = (e) => ayarYaz({ nazikMod: e.target.checked });
  $("#aCerez").onchange = (e) => {
    ayarYaz({ cerezTarayici: e.target.value });
    if (e.target.value) bildir("Tarayıcı oturumu kullanılacak. Tarayıcının kapalı olması gerekebilir.");
  };
  $("#aKapak").onchange = (e) => ayarYaz({ kucukresimGom: e.target.checked });
  $("#aUstveri").onchange = (e) => ayarYaz({ ustveriGom: e.target.checked });
  $("#aListeKlasor").onchange = (e) => ayarYaz({ playlistKlasor: e.target.checked });
}

/* ------------------------------------------------------------------ */
/* Giris kutusu ve kisayollar                                          */
/* ------------------------------------------------------------------ */

function girisBoyutla() {
  const el = $("#giris");
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 132) + "px";
}

function kisayollar() {
  const giris = $("#giris");

  giris.oninput = girisBoyutla;
  giris.onkeydown = (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.ctrlKey) { e.preventDefault(); coz(); }
    if (e.key === "Enter" && e.ctrlKey) { e.preventDefault(); hizliIndir(); }
  };
  $("#cozBtn").onclick = coz;

  document.addEventListener("paste", (e) => {
    if (e.target === giris) { setTimeout(() => { girisBoyutla(); coz(); }, 0); return; }
    const metin = (e.clipboardData || window.clipboardData).getData("text");
    if (!metin || !baglantilar(metin).length) return;
    e.preventDefault();
    giris.value = metin.trim();
    girisBoyutla();
    coz();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && durum.onizleme) { durum.onizleme = null; onizlemeCiz(); }
    if (e.ctrlKey && e.key.toLowerCase() === "k") { e.preventDefault(); giris.focus(); giris.select(); }
    if (e.ctrlKey && e.key === ",") { e.preventDefault(); gorunumSec("ayarlar"); }
    if (e.ctrlKey && e.key === "Enter" && durum.onizleme) { e.preventDefault(); kuyrugaEkle(); }
  });

  document.addEventListener("dragover", (e) => e.preventDefault());
  document.addEventListener("drop", (e) => {
    const metin = e.dataTransfer.getData("text");
    if (!metin) return;
    e.preventDefault();
    giris.value = metin.trim();
    girisBoyutla();
    coz();
  });

  $$(".gez").forEach((b) => b.onclick = () => gorunumSec(b.dataset.gorunum));
  $("#klasorAc").onclick = () => api("/api/klasor", {});
  $("#temizleBitti").onclick = () => api("/api/temizle", { kapsam: "bitti" });
  $("#temizleHepsi").onclick = () => api("/api/temizle", { kapsam: "hepsi" });
  $("#gecmisTemizle").onclick = async () => {
    await api("/api/gecmis-temizle", {}); durum.gecmis = []; gecmisCiz();
  };
}

/** Onizlemeyi beklemeden, kayitli varsayilanlarla dogrudan kuyruga alir. */
async function hizliIndir() {
  const urller = baglantilar($("#giris").value);
  if (!urller.length) return;
  const a = durum.ayarlar;
  try {
    await api("/api/ekle", {
      kayitlar: urller.map((u) => ({
        url: u, baslik: u, kalite: a.sonKalite || "1080",
        bicim: a.sonBicim || "video", altyazi: !!a.sonAltyazi,
      })),
    });
    $("#giris").value = "";
    girisBoyutla();
    $("#onizleme").innerHTML = "";
    durum.onizleme = null;
    bildir("Varsayılan ayarlarla kuyruğa alındı.");
  } catch (hata) { bildir(hata.message, "kotu"); }
}

/* ------------------------------------------------------------------ */
/* Baslangic                                                           */
/* ------------------------------------------------------------------ */

function tumunuYukle(veri) {
  durum.isler.clear();
  durum.kartlar.clear();
  $("#liste").innerHTML = "";
  (veri.isler || []).forEach(isYaz);
  if (veri.gecmis) durum.gecmis = veri.gecmis;
  ozetTazele();
}

async function baslat() {
  kisayollar();
  ayarlariBagla();
  guncellemeBagla();
  try {
    const veri = await api("/api/durum");
    durum.ayarlar = veri.ayarlar;
    if (veri.ortam) durum.ortam = veri.ortam;
    ayarlariCiz();
    hakkindaCiz();
    ortamiDegerlendir();
    tumunuYukle(veri);
  } catch (hata) {
    ustDurum("Sunucuya bağlanılamadı: " + hata.message, true);
  }
  olaylariDinle();
  $("#giris").focus();
}

baslat();
})();
