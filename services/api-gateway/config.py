from decimal import Decimal
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    service_name: str = "api-gateway"
    environment: Literal["development", "production"] = "development"
    log_level: str = "INFO"
    internal_api_token: SecretStr
    hasura_admin_secret: SecretStr
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: SecretStr
    auth_service_url: str = "http://auth-service:8000"
    orders_service_url: str = "http://orders-service:8000"
    hasura_graphql_url: str = "http://hasura:8080/v1/graphql"
    cors_allowed_origins: str = "http://localhost:3000"
    session_cookie_name: str = "ws_session"
    session_cookie_secure: bool = False
    session_absolute_timeout_seconds: int = Field(default=28800, gt=0)
    graphql_max_depth: int = Field(default=8, gt=0)
    graphql_max_limit: int = Field(default=50, gt=0)
    graphql_introspection: bool = True
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    rate_limit_login: str = "5/minute"
    rate_limit_register: str = "3/minute"
    rate_limit_booking: str = "3/minute"
    rate_limit_default: str = "120/minute"

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


settings = Settings()
