from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def load_env() -> None:
    load_dotenv(ROOT / ".env", override=True)


@dataclass(frozen=True)
class Settings:
    secret_key: str
    database_url: str | None
    pg_host: str
    pg_port: int
    pg_database: str
    pg_user: str
    pg_password: str | None

    @classmethod
    def from_env(cls) -> Settings:
        load_env()
        return cls(
            secret_key=os.environ.get("SECRET_KEY", "ehf-local"),
            database_url=os.environ.get("EHF_DATABASE_URL") or os.environ.get("DATABASE_URL"),
            pg_host=os.environ.get("PGHOST", "localhost"),
            pg_port=int(os.environ.get("PGPORT", "5432")),
            pg_database=os.environ.get("PGDATABASE", "ehf"),
            pg_user=os.environ.get("PGUSER", "postgres"),
            pg_password=os.environ.get("PGPASSWORD"),
        )
