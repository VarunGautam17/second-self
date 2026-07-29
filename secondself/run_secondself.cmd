@echo off
title SecondSelf AI Brain Launcher
cd /d "%~dp0"

echo ============================================================
echo   🧠 Launching SecondSelf AI Knowledge Brain Platform
echo ============================================================
echo.

:: Locate Virtual Environment Python & Streamlit executables
if exist "%~dp0venv\Scripts\python.exe" (
    set "VENV_PYTHON=%~dp0venv\Scripts\python.exe"
    set "VENV_STREAMLIT=%~dp0venv\Scripts\streamlit.exe"
    set "APP_DIR=%~dp0"
) else if exist "%~dp0..\secondself\venv\Scripts\python.exe" (
    set "VENV_PYTHON=%~dp0..\secondself\venv\Scripts\python.exe"
    set "VENV_STREAMLIT=%~dp0..\secondself\venv\Scripts\streamlit.exe"
    set "APP_DIR=%~dp0"
) else (
    echo [ERROR] Virtual environment python.exe not found!
    echo Please make sure secondself\venv directory exists.
    pause
    exit /b 1
)

echo [1/3] Environment check OK.
echo.
echo [2/3] Processing Knowledge Pipeline...
cd /d "%APP_DIR%"
"%VENV_PYTHON%" pipeline.py process --threshold 0.4

echo.
echo [3/3] Launching Local Streamlit Dashboard...
echo ============================================================
echo   App URL: http://localhost:8501
echo ============================================================
echo.

"%VENV_STREAMLIT%" run app.py --server.port 8501 --server.address localhost

pause
