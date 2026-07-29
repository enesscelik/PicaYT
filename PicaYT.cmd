@echo off
rem PicaYT baslatici (kaynaktan calistirma). Bu dosya bilerek yalnizca ASCII
rem karakter icerir: %~dp0 yolu isletim sisteminden gelir, Turkce klasor
rem adlari bozulmaz.
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0picayt.py"
