from wandersync_common import ServiceSettings


class Settings(ServiceSettings):
    service_name: str = "flights-service"
    db_schema: str = "flights"


settings = Settings()
