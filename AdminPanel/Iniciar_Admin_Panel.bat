@echo off
title ACC Dedicated Server - Admin Control Panel
cd /d "%~dp0"

echo ======================================================================
echo    ASSETTO CORSA COMPETIZIONE - PANEL DE CONTROL Y ORQUESTADOR
echo ======================================================================

if exist "%~dp0ACC_AdminPanel.exe" (
    echo [*] Iniciando binario standalone ACC_AdminPanel.exe...
    "%~dp0ACC_AdminPanel.exe"
    goto end
)

if exist "%~dp0..\ACC_AdminPanel.exe" (
    echo [*] Iniciando binario standalone ACC_AdminPanel.exe...
    "%~dp0..\ACC_AdminPanel.exe"
    goto end
)

if exist "%~dp0panel_server.py" (
    echo [*] Iniciando panel de control web con Python...
    python panel_server.py
    goto end
)

echo [!] Error: No se encontro ACC_AdminPanel.exe ni panel_server.py.
pause

:end
