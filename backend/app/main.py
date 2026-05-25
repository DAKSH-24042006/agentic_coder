import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import setup_logging
from app.api import auth, completion, indexer

# Initialize Logging
setup_logging()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Enterprise AI Coding platform combining multi-agent graphs, PEFT guidelines, and repository RAG.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Policy configuration for local IDE connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["authentication"])
app.include_router(completion.router, prefix=f"{settings.API_V1_STR}/chat", tags=["completion"])
app.include_router(indexer.router, prefix=f"{settings.API_V1_STR}/repository", tags=["indexer"])

@app.get("/health", tags=["health"])
async def health_check():
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "qdrant_host": settings.QDRANT_HOST,
        "vllm_host": settings.VLLM_API_URL
    }

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
