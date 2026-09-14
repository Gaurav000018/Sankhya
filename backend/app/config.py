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

    # --- email ------------------------------------------------------------ #
    # Resend is the delivery path. `email_enabled=False` keeps the dev
    # behaviour: codes and links are logged rather than sent, so a demo never
    # waits on a message arriving over venue wifi.
    email_enabled: bool = False
    resend_api_key: str = ""
    # Must be a verified domain in the Resend dashboard, or delivery 403s.
    email_from: str = "SANKHYA <onboarding@resend.dev>"
    email_reply_to: str = ""

    # Where links in emails point. Must be the browser-facing origin, not the
    # API's — a verification link to the API host lands on JSON.
    public_app_url: str = "http://localhost:3000"

    # Comma-separated browser origins allowed to call the API. Empty in dev
    # means "the local Vite server"; in production this must be set explicitly,
    # and `_require_production_settings` refuses to boot without it.
    cors_origins: str = ""

    # --- registration ------------------------------------------------------ #
    # Self-registration is restricted to government addresses: this platform
    # holds officers' competency records, so an arbitrary address must not be
    # able to create one. Comma-separated, matched on the domain suffix.
    allowed_email_domains: str = "gov.in,nic.in"
    # Off by default. A deployment that provisions officers through an admin
    # rather than self-service leaves this false and nothing else changes.
    registration_open: bool = True
    email_token_ttl_hours: int = 24
    password_reset_ttl_hours: int = 2
    password_min_length: int = 10

    # --- abuse limits ------------------------------------------------------ #
    # Password login is the one endpoint an attacker can grind offline-style,
    # and it had no limit at all before. Counted per email and per client IP.
    login_max_per_15min: int = 10
    register_max_per_hour: int = 5
    reset_max_per_hour: int = 5

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

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def allowed_domains(self) -> tuple[str, ...]:
        return tuple(
            d.strip().lower().lstrip("@")
            for d in self.allowed_email_domains.split(",")
            if d.strip()
        )

    @property
    def cors_origin_list(self) -> list[str]:
        explicit = [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]
        if explicit:
            return explicit
        # Dev convenience only. Production cannot reach this branch — the
        # startup check below refuses to boot without an explicit list.
        return ["http://localhost:3000", "http://127.0.0.1:3000"]

    def email_domain_allowed(self, email: str) -> bool:
        """True when self-registration is permitted for this address.

        An empty allow-list means "any domain" — a deliberate opt-out for a
        deployment that wants open registration, not an accident.
        """
        domains = self.allowed_domains
        if not domains:
            return True
        host = email.strip().lower().rpartition("@")[2]
        # Suffix match so `mospi.gov.in` is covered by `gov.in`, while
        # `nic.in.evil.com` is not.
        return any(host == d or host.endswith("." + d) for d in domains)


DEV_JWT_SECRET = "dev-only-change-me-before-any-real-deployment"


def _require_production_settings(s: Settings) -> list[str]:
    """Configuration that must be present before serving real traffic.

    Returned rather than raised so the caller decides the severity: `main`
    refuses to start on these, while tooling can report them.
    """
    problems: list[str] = []
    if s.jwt_secret in (DEV_JWT_SECRET, "", "dev-only-change-me"):
        problems.append(
            "JWT_SECRET is still the development placeholder. Generate one with: "
            'python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )
    if len(s.jwt_secret) < 32:
        problems.append("JWT_SECRET must be at least 32 characters.")
    if not s.cors_origins.strip():
        problems.append(
            "CORS_ORIGINS is empty. Set it to the browser origin(s) that may call "
            "this API, e.g. https://sankhya.example.gov.in"
        )
    if s.email_enabled and not s.resend_api_key:
        problems.append("EMAIL_ENABLED is true but RESEND_API_KEY is not set.")
    if not s.email_enabled and s.registration_open:
        # Fatal only in this combination: self-registration is advertised on the
        # sign-in page, and without delivery the confirmation link goes to the
        # log instead of the officer — so every new account is created and then
        # stranded unverified.
        problems.append(
            "EMAIL_ENABLED is false while REGISTRATION_OPEN is true. Confirmation "
            "links would be written to the log instead of sent, so nobody could "
            "finish signing up. Set RESEND_API_KEY and EMAIL_ENABLED=true, or set "
            "REGISTRATION_OPEN=false to run with provisioned accounts only."
        )
    if s.public_app_url.startswith("http://") and "localhost" not in s.public_app_url:
        problems.append("PUBLIC_APP_URL must use https outside local development.")
    return problems


def production_warnings(s: Settings) -> list[str]:
    """Degraded but serviceable. Logged, never fatal."""
    notes: list[str] = []
    if not s.email_enabled and not s.registration_open:
        notes.append(
            "Email is off and registration is closed: sign-in works for provisioned "
            "accounts, but password reset and email codes do not. An administrator "
            "is the only route back into a locked-out account."
        )
    return notes


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
