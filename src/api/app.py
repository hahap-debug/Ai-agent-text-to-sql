"""
FastAPI Application Entrypoint for CSR Architecture.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.controllers import api_router

def create_app() -> FastAPI:
    """Factory function for FastAPI application."""
    app = FastAPI(
        title="E-Commerce AI Data Analytics Agent API",
        description=(
            "Controller-Service-Repository (CSR) Architecture for Autonomous "
            "Natural Language to SQL Data Agent operating on ecommerce_db."
        ),
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.app:app", host="0.0.0.0", port=8000, reload=True)
