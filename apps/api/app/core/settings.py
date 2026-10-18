from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    api_cors_origins: str = "http://localhost:3000"
    database_url: str = "postgresql+asyncpg://edu:edu_local_password@localhost:5432/edu_dawnsynch"
    alembic_database_url: str = (
        "postgresql+psycopg://edu:edu_local_password@localhost:5432/edu_dawnsynch"
    )
    redis_url: str = "redis://localhost:6379/8"
    celery_broker_url: str = "redis://localhost:6379/9"
    celery_result_backend: str = "redis://localhost:6379/10"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection_prefix: str = "edu_dawnsynch"
    litellm_base_url: str = "http://localhost:4000"
    litellm_master_key: str | None = None
    litellm_model: str = "edu-default"
    litellm_embedding_model: str = "edu-embedding"
    ai_prompt_version: str = "content-enrichment-v3"
    ai_schema_version: str = "1.0.0"
    ai_min_confidence: float = 0.65
    ai_http_timeout_seconds: float = 30.0
    ai_max_retries: int = 3
    enrichment_batch_size: int = 50
    qdrant_api_key: SecretStr | None = None
    admin_api_key: SecretStr | None = None
    youtube_api_key: SecretStr | None = None
    ingestion_http_timeout_seconds: float = 15.0
    ingestion_lock_seconds: int = 900
    ingestion_max_retries: int = 4
    recommendation_cache_ttl_seconds: int = 300
    recommendation_candidate_limit: int = 500

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
