"""Environment-based configuration for the local analytics warehouse."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    """Runtime paths and database settings loaded from environment variables."""

    database_url: str
    raw_data_path: Path
    schema_path: Path
    integrity_sql_path: Path

    @property
    def psycopg_dsn(self) -> str:
        """Return the configured URL in the format accepted by psycopg."""
        return self.database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> Settings:
        """Load local `.env` values without overriding exported environment values."""
        load_dotenv(env_file or PROJECT_ROOT / ".env", override=False)
        database_url = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://sales_app:change_me_locally@localhost:5432/"
            "sales_analytics",
        )
        return cls(
            database_url=database_url,
            raw_data_path=Path(
                os.getenv("RAW_DATA_PATH", PROJECT_ROOT / "data/raw/sales.csv")
            ),
            schema_path=Path(
                os.getenv("SCHEMA_PATH", PROJECT_ROOT / "sql/ddl/001_schema.sql")
            ),
            integrity_sql_path=Path(
                os.getenv(
                    "INTEGRITY_SQL_PATH",
                    PROJECT_ROOT / "sql/tests/001_integrity_checks.sql",
                )
            ),
        )
