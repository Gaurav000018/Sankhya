from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # The API runs from /app (container) and the worker from backend/ on the
    # host, so look in both places for the same file.
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    app_env: str = "dev"

    database_url: str = "postgresql+psycopg://sankhya:sankhya@localhost:5433/sankhya"
    redis_url: str = "redis://localhost:6380/0"

    # Placeholder only — .env supplies the real one. Long enough to satisfy the
    # HMAC-SHA256 minimum so tests do not drown in key-length warnings, but the
    # name says what it is.
    jwt_secret: str = "dev-only-change-me-before-any-real-deployment"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 720

    email_enabled: bool = False
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_name: str = "SANKHYA"

    # Vosk supplies the disfluency pass. Whisper strips "um" and "uh" as noise,
    # so without this there is no filler measurement and fluency is reported as
    # unscoreable rather than as a flattering zero.
    vosk_model_path: str = ""

    ollama_base_url: str = "http://localhost:11434"
    judge_model: str = "qwen2.5:3b-instruct-q4_K_M"

    # Handover point between the API (in a container) and the speech worker (on
    # the host, next to the GPU). Bind-mounted so both see the same files.
    # Recordings are deleted the moment analysis finishes — nothing here persists.
    audio_dir: str = "/data/audio"
    analysis_queue: str = "sankhya:analysis"
    max_answer_seconds: int = 90
    max_upload_bytes: int = 25 * 1024 * 1024

    # OTP policy. Reusing an unexpired code on resend is what keeps us far below
    # any free-tier sending cap.
    otp_ttl_seconds: int = 600
    otp_resend_cooldown_seconds: int = 60
    otp_max_per_hour: int = 5
    otp_max_attempts: int = 5

    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
