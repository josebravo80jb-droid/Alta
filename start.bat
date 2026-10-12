@echo off
title Alta - Servidor
cd /d "%~dp0"
echo.
echo ========================================
echo   Alta - Iniciando servidor
echo ========================================
echo.
echo Directorio: %CD%
echo.
python run.py
echo.
echo ========================================
echo   Servidor detenido
echo ========================================
echo.
pause