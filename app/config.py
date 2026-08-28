"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


def _optional_int(name: str) -> int | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    return int(raw)


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    database_url: str
    admin_id: int
    master_id: int | None


def load_settings() -> Settings:
    return Settings(
        bot_token=_require("BOT_TOKEN"),
        database_url=_require("DATABASE_URL"),
        admin_id=int(_require("ADMIN_ID")),
        master_id=_optional_int("MASTER_ID"),
    )


def load_database_url() -> str:
    load_dotenv()
    return _require("DATABASE_URL")
