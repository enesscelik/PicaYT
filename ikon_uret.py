"""
picayt.ico dosyasini disariya bagimlilik olmadan uretir.

Yuvarlak koseli kirmizi-turuncu zemin uzerine beyaz indirme oku.
4x asiri ornekleme ile kenarlar yumusatilir.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

KOK = Path(__file__).resolve().parent
BOYUTLAR = (16, 24, 32, 48, 64, 128, 256)
ORNEK = 4                      # asiri ornekleme carpani

VURGU_1 = (255, 77, 77)
VURGU_2 = (255, 120, 71)


def _karisim(a: tuple, b: tuple, t: float) -> tuple:
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _yuvarlak_icinde(x: float, y: float, kenar: float, yaricap: float) -> bool:
    if x < 0 or y < 0 or x > kenar or y > kenar:
        return False
    ix = min(max(x, yaricap), kenar - yaricap)
    iy = min(max(y, yaricap), kenar - yaricap)
    return (x - ix) ** 2 + (y - iy) ** 2 <= yaricap * yaricap


def _ok_icinde(u: float, v: float) -> bool:
    """u, v: 0..1 normalize koordinat."""
    if 0.452 <= u <= 0.548 and 0.215 <= v <= 0.545:          # govde
        return True
    if 0.475 <= v <= 0.735:                                   # ok basi
        genislik = 0.175 * (0.735 - v) / 0.26
        if abs(u - 0.5) <= genislik:
            return True
    if 0.775 <= v <= 0.845:                                   # alt cizgi
        kavis = 0.035
        if 0.275 + kavis <= u <= 0.725 - kavis:
            return True
        for merkez in (0.275 + kavis, 0.725 - kavis):
            if (u - merkez) ** 2 + (v - 0.81) ** 2 <= kavis * kavis:
                return True
    return False


def piksel_uret(boyut: int) -> bytes:
    buyuk = boyut * ORNEK
    yaricap = buyuk * 0.225
    pay = buyuk * 0.02                     # kenar boslugu
    kenar = buyuk - 2 * pay

    satirlar = bytearray()
    for y in range(boyut):
        satirlar.append(0)                 # PNG filtre baytı
        for x in range(boyut):
            r = g = b = a = 0
            for oy in range(ORNEK):
                for ox in range(ORNEK):
                    bx = x * ORNEK + ox + 0.5
                    by = y * ORNEK + oy + 0.5
                    if not _yuvarlak_icinde(bx - pay, by - pay, kenar, yaricap):
                        continue
                    u, v = bx / buyuk, by / buyuk
                    if _ok_icinde(u, v):
                        renk = (255, 255, 255)
                    else:
                        renk = _karisim(VURGU_1, VURGU_2, (u * 0.45 + v * 0.55))
                    r += renk[0]; g += renk[1]; b += renk[2]; a += 255
            n = ORNEK * ORNEK
            if a:
                kapsam = a / (255 * n)
                satirlar += bytes((
                    round(r / (a / 255)), round(g / (a / 255)), round(b / (a / 255)),
                    round(255 * kapsam),
                ))
            else:
                satirlar += b"\0\0\0\0"
    return bytes(satirlar)


def png_yaz(boyut: int, ham: bytes) -> bytes:
    def parca(tur: bytes, veri: bytes) -> bytes:
        govde = tur + veri
        return struct.pack(">I", len(veri)) + govde + struct.pack(">I", zlib.crc32(govde))

    basli = struct.pack(">IIBBBBB", boyut, boyut, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + parca(b"IHDR", basli)
            + parca(b"IDAT", zlib.compress(ham, 9))
            + parca(b"IEND", b""))


def ico_yaz(hedef: Path) -> Path:
    resimler = [(b, png_yaz(b, piksel_uret(b))) for b in BOYUTLAR]
    basli = struct.pack("<HHH", 0, 1, len(resimler))
    kayitlar = bytearray()
    veri = bytearray()
    kaydirma = 6 + 16 * len(resimler)
    for boyut, png in resimler:
        kayitlar += struct.pack(
            "<BBBBHHII",
            0 if boyut >= 256 else boyut, 0 if boyut >= 256 else boyut,
            0, 0, 1, 32, len(png), kaydirma + len(veri),
        )
        veri += png
    hedef.write_bytes(basli + bytes(kayitlar) + bytes(veri))
    return hedef


if __name__ == "__main__":
    yol = ico_yaz(KOK / "picayt.ico")
    print("Ikon yazildi:", yol)
