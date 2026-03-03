@echo off
echo ============================================
echo  AQMD Rule Finder - Build Executable
echo ============================================
echo.
echo This will create a standalone .exe in the dist\ folder.
echo Requires: pip install pyinstaller (included in requirements.txt)
echo.

:: Clean previous build
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

pyinstaller ^
  --name "AQMD Rule Finder" ^
  --onedir ^
  --windowed ^
  --icon NONE ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --hidden-import flask ^
  --hidden-import requests ^
  --hidden-import bs4 ^
  --hidden-import fitz ^
  --hidden-import sqlite3 ^
  --collect-all fitz ^
  app.py

if errorlevel 1 (
    echo.
    echo ERROR: Build failed. Check the output above.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Build complete!
echo  Executable is in: dist\AQMD Rule Finder\
echo  Share the entire "AQMD Rule Finder" folder.
echo ============================================
pause
