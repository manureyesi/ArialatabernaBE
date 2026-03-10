from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str

    admin_username: str
    admin_password: str

    cors_origins: str = ""
    reservation_slot_capacity: int = 3

    admin_email: str | None = None
    mail_from: str | None = None

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
