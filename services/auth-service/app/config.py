from wandersync_common import ServiceSettings
from pydantic import Field, SecretStr

class Settings(ServiceSettings):
    service_name: str = "auth-service"
    db_schema: str = "auth"
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: SecretStr
    session_idle_timeout_seconds: int = Field(default=1800, gt=0)
    session_absolute_timeout_seconds: int = Field(default=28800, gt=0)
    argon2_time_cost: int = Field(default=3, gt=0)
    argon2_memory_cost_kib: int = Field(default=65536, gt=0)
    argon2_parallelism: int = Field(default=4, gt=0)
    password_min_length: int = Field(default=10, ge=10)

settings = Settings()