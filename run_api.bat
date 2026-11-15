@echo off
echo Starting E-Commerce AI Data Analytics Agent FastAPI Server...
echo Interactive Swagger Docs available at http://localhost:8000/docs
echo ReDoc available at http://localhost:8000/redoc
python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
