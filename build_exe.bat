@echo off
echo ============================================
echo  AQMD Rule Finder - Build Executable
echo ============================================
echo.
echo This will create a standalone .exe in the dist\ folder.
echo Requires: pip install pyinstaller (included in requirements.txt)
echo.

:: ── Locate Python (same logic as run.bat) ─────────────────
set PYTHON_EXE=
for /f "usebackq delims=" %%i in (".python_path.txt") do set PYTHON_EXE=%%i
set PYTHON_EXE=%PYTHON_EXE:"=%

if not defined PYTHON_EXE (
    python --version >nul 2>&1 && set PYTHON_EXE=python
)
if not defined PYTHON_EXE (
    echo ERROR: Python not found. Run setup.bat first.
    pause
    exit /b 1
)

:: ── Find miniconda/anaconda DLL directory ─────────────────
:: These DLLs are miniconda-specific and must be bundled explicitly
set DLL_DIR=
for %%P in (
    "%LOCALAPPDATA%\miniconda3\Library\bin"
    "%LOCALAPPDATA%\anaconda3\Library\bin"
    "%ProgramData%\miniconda3\Library\bin"
    "%ProgramData%\anaconda3\Library\bin"
) do (
    if exist "%%~P\ffi.dll" (
        set DLL_DIR=%%~P
        goto :found_dlls
    )
)

:found_dlls
:: ── Clean previous build ──────────────────────────────────
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

:: ── Build ────────────────────────────────────────────────
if defined DLL_DIR (
    echo Bundling miniconda DLLs from: %DLL_DIR%
    echo.
    "%PYTHON_EXE%" -m PyInstaller ^
      --name "AQMD Rule Finder" ^
      --onedir ^
      --windowed ^
      --add-data "templates;templates" ^
      --add-data "static;static" ^
      --add-binary "%DLL_DIR%\ffi.dll;." ^
      --add-binary "%DLL_DIR%\sqlite3.dll;." ^
      --add-binary "%DLL_DIR%\liblzma.dll;." ^
      --add-binary "%DLL_DIR%\libbz2.dll;." ^
      --add-binary "%DLL_DIR%\libexpat.dll;." ^
      --add-binary "%DLL_DIR%\libmpdec-4.dll;." ^
      --hidden-import flask ^
      --hidden-import requests ^
      --hidden-import bs4 ^
      --hidden-import fitz ^
      --hidden-import sqlite3 ^
      --collect-all fitz ^
      app.py
) else (
    echo Note: miniconda DLL directory not found - building without extra DLLs.
    echo If the .exe fails on other machines, re-run setup.bat first.
    echo.
    "%PYTHON_EXE%" -m PyInstaller ^
      --name "AQMD Rule Finder" ^
      --onedir ^
      --windowed ^
      --add-data "templates;templates" ^
      --add-data "static;static" ^
      --hidden-import flask ^
      --hidden-import requests ^
      --hidden-import bs4 ^
      --hidden-import fitz ^
      --hidden-import sqlite3 ^
      --collect-all fitz ^
      app.py
)

if errorlevel 1 (
    echo.
    echo ERROR: Build failed. Check the output above.
    pause
    exit /b 1
)

:: ── Copy user guide into the dist folder ──────────────────
copy /Y "EXE-USER-GUIDE.md" "dist\AQMD Rule Finder\User Guide.md" >nul
echo Copied User Guide.md to dist folder.

echo.
echo ============================================
echo  Build complete!
echo  Executable is in: dist\AQMD Rule Finder\
echo  Share the entire "AQMD Rule Finder" folder.
echo ============================================
pause
