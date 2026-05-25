import os
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # API Metadata
    PROJECT_NAME: str = "Enterprise AI Coding Platform"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False

    # Security & Auth
    SECRET_KEY: str = Field(default="SUPER_SECRET_ENTERPRISE_KEY_CHANGE_ME_IN_PRODUCTION", description="JWT Signing Key")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    ALLOWED_HOSTS: List[str] = ["*"]

    # Inference (vLLM)
    VLLM_API_URL: str = Field(default="http://localhost:11434/v1", description="LLM server base URL")
    VLLM_API_KEY: Optional[str] = None
    PRIMARY_MODEL: str = Field(default="mock-model")
    TEMPERATURE: float = 0.2

    # Vector DB (Qdrant)
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION: str = "enterprise_codebase"

    # Embeddings
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384

    # Database (MySQL for logs/history tracking)
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "rootpass"
    MYSQL_SERVER: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_DB: str = "ai_coder_platform"

    @property
    def sqlalchemy_database_uri(self) -> str:
        return f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_SERVER}:{self.MYSQL_PORT}/{self.MYSQL_DB}"

    # Sandbox Configuration
    SANDBOX_DOCKER_IMAGE: str = "python:3.12-slim"
    SANDBOX_TIMEOUT_SECONDS: int = 30
    SANDBOX_WORKSPACE_DIR: str = "/workspace"

settings = Settings()
