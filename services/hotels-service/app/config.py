from wandersync_common import ServiceSettings


class Settings(ServiceSettings):
    service_name: str = "hotels-service"
    db_schema: str = "hotels"


settings = Settings()
