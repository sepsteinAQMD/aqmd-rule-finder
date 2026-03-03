@echo off
echo ============================================
echo  AQMD Rule Finder - Run Tests
echo ============================================
echo.
cd /d "%~dp0.."
python -m pytest tests/ -v --tb=short 2>&1
pause
