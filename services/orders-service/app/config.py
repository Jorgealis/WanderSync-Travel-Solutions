from wandersync_common import ServiceSettings


class Settings(ServiceSettings):
    service_name: str = "orders-service"
    db_schema: str = "orders"


settings = Settings()
