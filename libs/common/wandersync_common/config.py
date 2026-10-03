from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class ServiceSettings(BaseSettings):
    """Configuración común a todos los microservicios.

    Se lee de variables de entorno (las define docker-compose.yml). Cada servicio
    recibe credenciales genéricas DB_USER / DB_PASSWORD / DB_SCHEMA con los
    valores de SU usuario de base de datos, nunca los de otro servicio.
    """

    model_config = SettingsConfigDict(extra="ignore")

    service_name: str
    environment: Literal["development", "production"] = "development"
    log_level: str = "INFO"

    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "wandersync"
    db_user: str
    db_password: SecretStr
    db_schema: str
    db_pool_size: int = 5
    db_max_overflow: int = 5

    internal_api_token: SecretStr
    enable_fault_injection: bool = False

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def database_url(self) -> URL:
        # URL.create escapa correctamente contraseñas con caracteres especiales.
        return URL.create(
            "postgresql+asyncpg",
            username=self.db_user,
            password=self.db_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )
