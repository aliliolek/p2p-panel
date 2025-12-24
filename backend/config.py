import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _get_list(name: str, fallback: str = "") -> List[str]:
    raw_value = os.getenv(name, fallback)
    if not raw_value:
        return []
    return [item.strip() for item in raw_value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    supabase_url: str = _require_env("SUPABASE_URL")
    supabase_service_role_key: str = _require_env("SUPABASE_SERVICE_ROLE_KEY")
    encryption_key: str = _require_env("ENCRYPTION_KEY")
    server_public_ip: str | None = os.getenv("SERVER_PUBLIC_IP")
    credential_check_interval_seconds: int = int(
        os.getenv("CREDENTIAL_CHECK_INTERVAL_SECONDS", "30")
    )
    allowed_origins: List[str] = field(
        default_factory=lambda: _get_list("ALLOWED_ORIGINS", "*")
    )


settings = Settings()
