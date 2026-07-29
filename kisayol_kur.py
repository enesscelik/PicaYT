"""
Masaustune ve Baslat menusune "PicaYT" kisayolu koyar.

Kisayol dogrudan pythonw.exe'yi hedefler; cmd.exe araya girmedigi icin
Turkce karakterli yollar bozulmaz.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pythoncom
from win32com.client import Dispatch

KOK = Path(__file__).resolve().parent
BETIK = KOK / "picayt.py"
IKON = KOK / "picayt.ico"

# Once projenin kendi ortami, yoksa betigi calistiran yorumlayici.
_VENV = KOK / ".venv" / "Scripts" / "pythonw.exe"
PYTHONW = _VENV if _VENV.is_file() else Path(sys.executable).with_name("pythonw.exe")


def kisayol_yaz(hedef: Path) -> None:
    hedef.parent.mkdir(parents=True, exist_ok=True)
    kabuk = Dispatch("WScript.Shell")
    kisayol = kabuk.CreateShortCut(str(hedef))
    kisayol.TargetPath = str(PYTHONW)
    kisayol.Arguments = f'"{BETIK}"'
    kisayol.WorkingDirectory = str(KOK)
    kisayol.Description = "PicaYT — YouTube indirme paneli"
    if IKON.is_file():
        kisayol.IconLocation = str(IKON)
    kisayol.save()


def main() -> None:
    if not PYTHONW.is_file():
        sys.exit(f"pythonw.exe bulunamadi: {PYTHONW}")
    if not IKON.is_file():
        import ikon_uret
        ikon_uret.ico_yaz(IKON)

    pythoncom.CoInitialize()
    kabuk = Dispatch("WScript.Shell")
    masaustu = Path(kabuk.SpecialFolders("Desktop"))
    baslat = Path(kabuk.SpecialFolders("Programs"))

    for yer in (masaustu / "PicaYT.lnk", baslat / "PicaYT.lnk"):
        kisayol_yaz(yer)
        print("Kisayol:", yer)


if __name__ == "__main__":
    main()
