from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "swp1_db"
    jwt_secret: str = "bpm-super-secret-key-2026-debe-tener-256-bits-minimo-cambiar-produccion"
    jwt_expiration_hours: int = 8
    ai_service_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:4200,http://localhost:3000,http://localhost:5173,http://localhost:8100"

    # Azure Blob Storage — Ciclo 2
    azure_storage_connection_string: str = ""
    azure_storage_account_name: str = ""
    azure_storage_account_key: str = ""
    azure_storage_container: str = "documentos"

    # OpenRouter LLM — Ciclo 2 (Agente + Reportes)
    openrouter_api_key: str = ""
    openrouter_model: str = "google/gemini-2.5-flash"

    # OnlyOffice Document Server
    onlyoffice_url: str = "http://localhost:8088"
    onlyoffice_public_url: str = "http://localhost:8088"
    onlyoffice_secret: str = "sp1-onlyoffice-jwt-secret-2026"
    # URL que OnlyOffice usa para llamar al callback del backend
    # - Nativo:  http://host.docker.internal:8080  (Mac/Windows con Docker Desktop)
    # - Docker:  http://backend:8080               (dentro de docker-compose)
    backend_url: str = "http://host.docker.internal:8080"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
