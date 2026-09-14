import logging
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("sporty.lab")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Sporty OTP Lab"
    cors_origins: str = (
        "http://localhost:5273,http://127.0.0.1:5273,"
        "http://localhost:5173,http://127.0.0.1:5173"
    )
    database_url: str = "sqlite:///./sporty.db"

    provider: str = "sportybet"

    api_token: str | None = None
    encrypt_key: str | None = None

    # OTP lifecycle + generated-password strength.
    otp_ttl_seconds: int = 300
    otp_attempts_max: int = 5
    password_length: int = 16

    # ---- SportyBet real browser registration (NG + KE only) ---------------
    # The per-country URL also fixes the phone dial-code prepend on the
    # register form (+234 on /ng/, +254 on /ke/).
    sportybet_headless: bool = False
    sportybet_onboarding_url: str = "https://www.sportybet.com/ng/"
    sportybet_onboarding_url_ng: str | None = None
    sportybet_onboarding_url_ke: str | None = None
    # Human-likeness (ms).
    sportybet_keystroke_min_ms: int = 40
    sportybet_keystroke_max_ms: int = 120
    sportybet_form_delay_ms: int = 600
    # Settle (ms) after clicking "Create New Account" before we engage the
    # delivery chooser — lets SportyBet's anti-bot CAPTCHA materialize so we
    # detect it instead of racing an invisible overlay.
    sportybet_post_submit_delay_ms: int = 2500
    # Randomized wait after the real OTP request before reporting "delivered".
    sportybet_after_send_min_ms: int = 30000
    sportybet_after_send_max_ms: int = 60000
    # Timeouts (seconds).
    sportybet_send_timeout_seconds: int = 120
    sportybet_otp_window_seconds: int = 600
    sportybet_captcha_timeout_seconds: int = 600

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()