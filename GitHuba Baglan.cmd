@echo off
rem PicaYT'yi GitHub'a baglar. Bir kez calistirilir; ciftt tikla yeterli.
rem Yalnizca ASCII: %~dp0 yolu isletim sisteminden gelir, Turkce klasor
rem adlari bozulmaz.
chcp 65001 >nul
title PicaYT - GitHub kurulumu
"%~dp0.venv\Scripts\python.exe" "%~dp0depo_kur.py"
