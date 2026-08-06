from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Nexora Gateway API"
    jwt_secret: str = "change-this-secret-in-production"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 480
    nine_router_base_url: str = "https://api.9router.example/v1"
    nine_router_api_key: str = ""
    nine_router_dashboard_password: str = ""
    nine_router_internal_key: str = ""
    nine_router_public_url: str = "http://localhost:20128/v1"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    database_url: str = "sqlite:///./nexora.db"
    banking_webhook_api_key: str = "change-banking-webhook-key"
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    oauth_public_url: str = "http://localhost:8080"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
