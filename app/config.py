from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SLACK_WEBHOOK_URL: str
    API_KEY: str

    class Config:
        env_file = ".env"

settings = Settings()