import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from src.api.routes import router

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting rxn_extractor API (CSV backend)")
    # CSV store initialises its data/ directory on first access — nothing to do here.
    yield
    logger.info("Shutting down rxn_extractor API")

app = FastAPI(
    title="Rxn Extractor API",
    description="API for validating and managing schema-driven LLM extractions",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve UI index.html if exists, otherwise return API guide."""
    ui_path = os.path.join("src", "auto_generated", "ui", "index.html")
    if os.path.exists(ui_path):
        return FileResponse(ui_path)
    
    return """
    <html>
        <head>
            <title>Rxn Extractor API</title>
        </head>
        <body>
            <h1>Welcome to Rxn Extractor API</h1>
            <p>UI not found. Refer to <a href="/docs">/docs</a> for API documentation.</p>
        </body>
    </html>
    """

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
