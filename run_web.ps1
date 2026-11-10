# PowerShell Launcher for Streamlit Web Dashboard
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Starting AI Data Analytics Agent Web Dashboard (Streamlit)" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Connecting to MySQL ecommerce_db and launching web browser..." -ForegroundColor Yellow
python -m streamlit run app.py
