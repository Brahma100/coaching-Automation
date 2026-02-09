from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    app_name: str = 'Coaching Automation'
    app_env: str = 'local'
    app_timezone: str = 'Asia/Kolkata'
    database_url: str = 'sqlite:///./coaching.db'
    telegram_bot_token: str = ''
    telegram_api_base: str = 'https://api.telegram.org'
    enable_telegram_notifications: bool = True
    app_base_url: str = 'http://127.0.0.1:8000'
    default_upi_id: str = 'coach@upi'
    enable_sheets_backup: bool = False
    sheet_id: str = ''
    google_credentials_json: str = ''
    attendance_low_threshold: float = 0.75
    default_quiet_hours_start: str = '22:00'
    default_quiet_hours_end: str = '07:00'


settings = Settings()
