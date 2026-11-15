Write-Host "Starting E-Commerce AI Data Analytics Agent FastAPI Server..." -ForegroundColor Magenta
Write-Host "Interactive Swagger Docs available at http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "ReDoc available at http://localhost:8000/redoc" -ForegroundColor Yellow
python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
