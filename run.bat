@echo off
echo ============================================
echo  AQMD Rule Finder
echo ============================================
echo.

set PYTHON_EXE=

:: ── Read the Python path saved by setup.bat ──────────
:: "for /f" reads the file cleanly, handling any trailing whitespace.
if exist ".python_path.txt" (
    for /f "usebackq delims=" %%i in (".python_path.txt") do set PYTHON_EXE=%%i
)

:: Strip any quotes that may have been written by an older version of setup.bat.
if defined PYTHON_EXE set PYTHON_EXE=%PYTHON_EXE:"=%

:: If the saved value looks like a full file path (contains a backslash),
:: verify it still exists on disk before trusting it.
if defined PYTHON_EXE (
    echo %PYTHON_EXE% | findstr /C:"\" >nul 2>&1
    if not errorlevel 1 (
        if not exist "%PYTHON_EXE%" (
            echo Saved Python path no longer exists. Searching PATH...
            set PYTHON_EXE=
        )
    )
)

:: ── Fall back to searching PATH if needed ────────────
if not defined PYTHON_EXE (
    where python >nul 2>&1
    if not errorlevel 1 set PYTHON_EXE=python
)
if not defined PYTHON_EXE (
    where python3 >nul 2>&1
    if not errorlevel 1 set PYTHON_EXE=python3
)

if not defined PYTHON_EXE (
    echo ERROR: Python could not be found.
    echo Please run setup.bat first.
    echo.
    pause
    exit /b 1
)

:: ── Launch the app ────────────────────────────────────
echo Starting... a browser window will open shortly.
echo Keep this window open while using the tool.
echo Press Ctrl+C to stop.
echo.
echo Using Python: %PYTHON_EXE%
echo.

:: Quote the exe only when it is a full file path (contains a backslash).
echo %PYTHON_EXE% | findstr /C:"\" >nul 2>&1
if not errorlevel 1 (
    "%PYTHON_EXE%" app.py
) else (
    %PYTHON_EXE% app.py
)

:: ── Always pause on exit so the user can read any error messages ──
echo.
if errorlevel 1 (
    echo ============================================
    echo  The app stopped with an error (see above).
    echo  Common causes:
    echo    - A dependency is missing: run setup.bat again
    echo    - Port 5731 is in use: close other instances
    echo ============================================
) else (
    echo  AQMD Rule Finder has stopped.
)
echo.
pause
