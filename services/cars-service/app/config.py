from wandersync_common import ServiceSettings


class Settings(ServiceSettings):
    service_name: str = "cars-service"
    db_schema: str = "cars"


settings = Settings()
