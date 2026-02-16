from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    app_name: str = 'Coaching Automation'
    app_env: str = 'local'
    app_timezone: str = 'Asia/Kolkata'
    database_url: str = 'sqlite:///./coaching.db'
    telegram_bot_token: str = ''
    telegram_bot_username: str = ''
    telegram_api_base: str = 'https://api.telegram.org'
    telegram_webhook_secret: str = ''
    telegram_link_polling_mode: str = 'auto'  # auto | on | off
    telegram_link_polling_interval_seconds: int = 20
    enable_telegram_notifications: bool = True
    app_base_url: str = 'http://127.0.0.1:8000'
    frontend_base_url: str = 'http://localhost:5173'
    default_upi_id: str = 'coach@upi'
    enable_sheets_backup: bool = False
    sheet_id: str = ''
    google_credentials_json: str = ''
    google_oauth_client_id: str = ''
    google_oauth_client_secret: str = ''
    google_oauth_redirect_uri: str = ''
    google_drive_folder_id: str = ''
    google_drive_oauth_scopes: str = 'https://www.googleapis.com/auth/drive.file'
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
    communication_mode: str = 'embedded'
    communication_service_url: str = 'http://localhost:9000'
    communication_tenant_id: str = 'default'
    dev_default_center_slug: str = 'default-center'
    tenant_base_domain: str = 'yourapp.com'


settings = Settings()
