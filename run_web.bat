@echo off
chcp 65001 > nul
title AI Data Analytics Agent Web Dashboard
echo ============================================================
echo   Starting AI Data Analytics Agent Web Dashboard (Streamlit)
echo ============================================================
echo.
echo Opening browser at http://localhost:8501 ...
python -m streamlit run app.py
pause
