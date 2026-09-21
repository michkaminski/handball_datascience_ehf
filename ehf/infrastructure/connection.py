from __future__ import annotations

import psycopg
from psycopg import Connection

from ehf.settings import Settings


def open_connection(settings: Settings | None = None) -> Connection:
    resolved = settings or Settings.from_env()
    if resolved.database_url:
        return psycopg.connect(resolved.database_url)
    return psycopg.connect(
        host=resolved.pg_host,
        port=resolved.pg_port,
        dbname=resolved.pg_database,
        user=resolved.pg_user,
        password=resolved.pg_password,
    )
