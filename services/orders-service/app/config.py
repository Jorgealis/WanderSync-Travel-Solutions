from pydantic import Field
from pydantic import SecretStr
from wandersync_common import ServiceSettings


class Settings(ServiceSettings):
    service_name: str = "orders-service"
    db_schema: str = "orders"
    flights_service_url: str = "http://flights-service:8000"
    hotels_service_url: str = "http://hotels-service:8000"
    cars_service_url: str = "http://cars-service:8000"
    saga_step_timeout_seconds: float = Field(default=3.0, gt=0)
    saga_step_delay_seconds: float = Field(default=0.0, ge=0, le=10)
    saga_max_retries: int = Field(default=3, ge=0)
    saga_retry_backoff_seconds: float = Field(default=0.5, gt=0)
    saga_compensation_max_backoff_seconds: float = Field(default=30.0, gt=0)
    tax_rate: float = Field(default=0.0, ge=0, le=1)
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: SecretStr
    rate_limit_payment: str = "10/minute"


settings = Settings()