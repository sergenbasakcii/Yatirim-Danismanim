@echo off
title HedgeFund AI — Luxury Edition
cd /d C:\Users\MB\Desktop\HedgeFundAI
echo.
echo  ╔══════════════════════════════════════╗
echo  ║       HedgeFund AI  v2.0 Premium     ║
echo  ║   Yapay Zeka Destekli Yatırım Analizi ║
echo  ╚══════════════════════════════════════╝
echo.
echo  Uygulama başlatılıyor...
echo  Tarayıcınızda: http://localhost:8501
echo.
python -X utf8 -m streamlit run web_app.py
pause
