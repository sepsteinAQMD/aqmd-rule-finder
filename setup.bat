@echo off
echo ============================================
echo  AQMD Rule Finder - Setup
echo ============================================
echo.

:: ── Try to find Python on PATH ───────────────────────
set PYTHON_EXE=
python --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_EXE=python
    goto :run_setup
)

python3 --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_EXE=python3
    goto :run_setup
)

:: ── Python not on PATH — check common install locations ──
echo Python was not found on PATH. Checking common install locations...
echo.

for %%V in (313 312 311 310 39) do (
    for %%P in (
        "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
        "%LOCALAPPDATA%\miniconda3\python.exe"
        "%LOCALAPPDATA%\anaconda3\python.exe"
        "C:\Python%%V\python.exe"
        "C:\Program Files\Python%%V\python.exe"
        "%ProgramData%\anaconda3\python.exe"
        "%ProgramData%\miniconda3\python.exe"
    ) do (
        if exist %%P (
            echo Found Python at: %%P
            :: Store path without outer quotes so we can re-quote consistently
            set PYTHON_EXE=%%~P
            goto :run_setup
        )
    )
)

:: ── Not found automatically — ask the user ───────────
echo Python could not be found automatically.
echo.
echo Please enter the full path to your python.exe.
echo Example: C:\Users\YourName\AppData\Local\Programs\Python\Python312\python.exe
echo.
echo (Press Enter without typing anything to cancel.)
echo.
set /p USER_PATH="Path to python.exe: "

if "%USER_PATH%"=="" (
    echo.
    echo Cancelled. See USER-GUIDE.md for help finding and installing Python.
    pause
    exit /b 1
)

:: Strip any quotes the user may have typed
set USER_PATH=%USER_PATH:"=%

if not exist "%USER_PATH%" (
    echo.
    echo ERROR: File not found: %USER_PATH%
    echo Please check the path and try again.
    pause
    exit /b 1
)

set PYTHON_EXE=%USER_PATH%

:: ── Run setup ────────────────────────────────────────
:run_setup
echo.
echo Using Python: %PYTHON_EXE%
"%PYTHON_EXE%" --version 2>nul || %PYTHON_EXE% --version
echo.
echo Installing dependencies...
echo.

"%PYTHON_EXE%" -m pip install -r requirements.txt 2>nul || %PYTHON_EXE% -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: Failed to install dependencies.
    echo Try running: "%PYTHON_EXE%" -m pip install --upgrade pip
    pause
    exit /b 1
)

:: ── Save the Python path for run.bat ─────────────────
:: Write without surrounding quotes and without a trailing space.
:: run.bat will add quotes when it uses the path.
(echo %PYTHON_EXE%)>.python_path.txt

echo.
echo ============================================
echo  Setup complete! Run run.bat to start.
echo ============================================
pause
