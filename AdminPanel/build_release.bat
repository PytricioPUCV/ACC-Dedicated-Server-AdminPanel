@echo off
title ACC Admin Panel - Compilar Release 1.0
cd /d "%~dp0"

echo ======================================================================
echo    ASSETTO CORSA COMPETIZIONE - COMPILADOR Y GENERADOR DE RELEASE
echo ======================================================================
echo [*] Iniciando script de construcción automatizado...
echo.

python build_exe.py

echo.
pause
