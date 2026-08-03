"""
Logger SQLite pour les résultats d'appel.
DB : data/calls.db
"""
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "calls.db"
logger = logging.getLogger(__name__)


class CallLogger:
    def __init__(self):
        DB_PATH.parent.mkdir(exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS calls (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    call_sid        TEXT UNIQUE,
                    prospect_name   TEXT,
                    prospect_phone  TEXT,
                    company         TEXT,
                    call_timestamp  TEXT,
                    duration_sec    INTEGER DEFAULT 0,
                    outcome         TEXT,
                    callback_date   TEXT,
                    notes           TEXT,
                    transcript      TEXT,
                    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    async def log(
        self,
        call_sid: str,
        prospect: dict,
        outcome: str,
        notes: str,
        transcript: str,
        duration: int = 0,
        callback_date: str = "",
    ):
        name = (
            f"{prospect.get('Contact First Name', '')} "
            f"{prospect.get('Contact Last Name', '')}"
        ).strip()
        phone = prospect.get("Phone", "")
        company = prospect.get("Account Name", "")

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO calls
                   (call_sid, prospect_name, prospect_phone, company,
                    call_timestamp, duration_sec, outcome, callback_date, notes, transcript)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    call_sid, name, phone, company,
                    datetime.now().isoformat(), duration,
                    outcome, callback_date, notes, transcript,
                ),
            )
            conn.commit()

        logger.info(f"Call logged: {name} ({company}) → {outcome}")

    def get_stats(self) -> dict:
        """Retourne le compte par outcome."""
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute(
                "SELECT outcome, COUNT(*) FROM calls GROUP BY outcome"
            ).fetchall()
        return {row[0]: row[1] for row in rows}

    def get_recent_calls(self, limit: int = 20) -> list[dict]:
        """Retourne les N derniers appels."""
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM calls ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]
