import getpass
import sqlite3
import uuid
from enum import Enum

from . import get_project_root, _marker
from .models import *


def __initialize():
    with sqlite3.connect(get_project_root() / _marker / "sys.db") as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS quiz_scoring(
                pid INTEGER PRIMARY KEY,
                uuid VARCHAR(36) NOT NULL,
                label TEXT,
                score REAL NOT NULL,
                source_url TEXT,
                source_label TEXT,
                source_uuid TEXT NOT NULL,
                group_id INTEGER,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS quiz_sys(
                uuid VARCHAR(36) NOT NULL,
                alias TEXT UNIQUE,
                synched_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        cursor.executemany(
            """
            INSERT OR IGNORE INTO quiz_sys(uuid, alias)
            VALUES(?,?)
            """,
            [(str(uuid.uuid4()), getpass.getuser())],
        )


__initialize()


def insert_score(
    quiz: Quiz,
    score: float,
):
    with sqlite3.connect(get_project_root() / _marker / "sys.db") as conn:
        cursor = conn.cursor()
        cursor.executemany(
            """
            INSERT INTO quiz_scoring(
                uuid,
                score,
                label,
                source_url,
                source_label,
                source_uuid,
                group_id
            )
            VALUES(?,?,?,?,?,?,?)
            """,
            [
                (
                    quiz.uuid,
                    score,
                    quiz.label,
                    quiz.context.source,
                    quiz.context.label,
                    quiz.context.uuid,
                    quiz.context.group,
                )
            ],
        )


class FetchMode(Enum):
    OLDEST = 1
    NEWEST = 2
    ALL = 3


def fetch_score(
    after: str = "0001-01-01",
    before: str = "9999-12-31",
    uuid: str = "%",
    source_uuid: str = "%",
    limit: int = 100,
    mode: FetchMode = FetchMode.ALL,
) -> list[dict]:
    with sqlite3.connect(get_project_root() / _marker / "sys.db") as conn:
        conn.row_factory = sqlite3.Row
        result: list[dict] = []
        cursor = conn.cursor()

        if mode == FetchMode.ALL:
            cursor.execute(
                """
                SELECT * FROM quiz_scoring
                WHERE created_at > ?
                AND created_at < ?
                AND uuid LIKE ?
                AND source_uuid LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (
                    after,
                    before,
                    uuid,
                    source_uuid,
                    limit,
                ),
            )
        else:
            if mode == FetchMode.OLDEST:
                op = "MIN"
            else:
                op = "MAX"
            cursor.execute(
                f"""
                WITH t1 AS (
                        SELECT uuid,{op}(created_at) AS min_created_at
                        FROM quiz_scoring 
                        WHERE created_at > ?
                        AND created_at < ?
                        AND uuid LIKE ?
                        AND source_uuid LIKE ?
                        GROUP BY uuid
                )
                SELECT t2.*
                FROM quiz_scoring t2 
                INNER JOIN t1
                ON t1.uuid == t2.uuid
                AND t2.created_at = t1.min_created_at
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (
                    after,
                    before,
                    uuid,
                    source_uuid,
                    limit,
                ),
            )
        for row in cursor:
            result.append(dict(row))

    return result


def synch_scores(url: str):
    pass
