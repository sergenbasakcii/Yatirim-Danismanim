@echo off
title HedgeFund AI
cd /d "%~dp0"

REM Streamlit zaten çalışıyor mu kontrol et (port 8501)
netstat -an | findstr ":8501" | findstr "LISTENING" >nul
if %errorlevel%==0 (
    echo Uygulama zaten çalışıyor. Tarayıcı açılıyor...
    start "" http://localhost:8501
    timeout /t 2 /nobreak >nul
    exit /b 0
)

REM Streamlit'i başlat — server hazır olunca tarayıcı otomatik açılır
python -m streamlit run web_app.py --server.port 8501 --browser.gatherUsageStats false
