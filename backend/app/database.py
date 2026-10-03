import json
import os
import sqlite3
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = BASE_DIR / "data" / "pettrace.db"
REPORTS_PATH = BASE_DIR / "data" / "reports.json"


def _database_path() -> Path:
    path = Path(os.getenv("PETTRACE_DB_PATH", str(DEFAULT_DB_PATH)))
    if not path.is_absolute():
        path = (BASE_DIR.parent / path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(_database_path())
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                pet_name TEXT NOT NULL,
                report_type TEXT NOT NULL CHECK (report_type IN ('lost', 'found')),
                description TEXT NOT NULL,
                location TEXT NOT NULL,
                report_date TEXT NOT NULL,
                characteristics TEXT NOT NULL
            )
            """
        )
        count = connection.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
        if count == 0:
            reports = json.loads(REPORTS_PATH.read_text(encoding="utf-8"))
            connection.executemany(
                """
                INSERT INTO reports
                    (id, pet_name, report_type, description, location, report_date, characteristics)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        report["id"],
                        report["pet_name"],
                        report["report_type"],
                        report["description"],
                        report["location"],
                        report["report_date"],
                        json.dumps(report["characteristics"]),
                    )
                    for report in reports
                ],
            )


def get_reports() -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, pet_name, report_type, description, location, report_date, characteristics
            FROM reports
            ORDER BY report_date DESC
            """
        ).fetchall()
    return [
        {
            **dict(row),
            "characteristics": json.loads(row["characteristics"]),
        }
        for row in rows
    ]

