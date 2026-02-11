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
    frontend_base_url: str = 'http://localhost:5173'
    default_upi_id: str = 'coach@upi'
    enable_sheets_backup: bool = False
    sheet_id: str = ''
    google_credentials_json: str = ''
    attendance_low_threshold: float = 0.75
    default_quiet_hours_start: str = '22:00'
    default_quiet_hours_end: str = '07:00'
    auth_otp_expiry_minutes: int = 10
    auth_session_expiry_hours: int = 12
    auth_secret: str = 'change-me'
    auth_otp_fallback_chat_id: str = ''
    auth_admin_phone: str = ''
    auth_enable_google_login: bool = False
    auth_google_client_id: str = ''
    daily_teacher_brief_time: str = '07:30'
    attendance_auto_close_grace_minutes: int = 10
    cache_backend: str = 'memory'
    cache_redis_url: str | None = None
    default_cache_ttl: int = 60
    db_slow_query_ms: int = 100
    metrics_slow_ms: int = 200


settings = Settings()
