from wandersync_common import ServiceSettings


class Settings(ServiceSettings):
    service_name: str = "auth-service"
    db_schema: str = "auth"


settings = Settings()
