from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from .utils import SubjectSheet


def init_db(db_path: str = ".data/results.db") -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS learners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS section_learners (
                section_id INTEGER NOT NULL,
                learner_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (section_id, learner_id),
                FOREIGN KEY (section_id) REFERENCES sections(id),
                FOREIGN KEY (learner_id) REFERENCES learners(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS assessment_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (section_id) REFERENCES sections(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS subject_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                subject_name TEXT NOT NULL,
                learner_name TEXT NOT NULL,
                total_points INTEGER NOT NULL,
                note REAL NOT NULL,
                empty_answers INTEGER NOT NULL,
                FOREIGN KEY (run_id) REFERENCES assessment_runs(id)
            )
            """
        )


def _upsert_section(conn: sqlite3.Connection, section_name: str) -> int:
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO sections(name, created_at) VALUES (?, ?)",
        (section_name, now),
    )
    row = conn.execute("SELECT id FROM sections WHERE name = ?", (section_name,)).fetchone()
    return int(row[0])


def _upsert_learner(conn: sqlite3.Connection, learner_name: str) -> int:
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO learners(name, created_at) VALUES (?, ?)",
        (learner_name, now),
    )
    row = conn.execute("SELECT id FROM learners WHERE name = ?", (learner_name,)).fetchone()
    return int(row[0])


def save_assessment_run(
    section_name: str,
    learner_names: list[str],
    subjects: dict[str, SubjectSheet],
    source: str,
    db_path: str = ".data/results.db",
) -> int:
    init_db(db_path)
    now = datetime.now(UTC).isoformat()

    with sqlite3.connect(db_path) as conn:
        section_id = _upsert_section(conn, section_name)

        for learner_name in learner_names:
            learner_id = _upsert_learner(conn, learner_name)
            conn.execute(
                """
                INSERT OR IGNORE INTO section_learners(section_id, learner_id, created_at)
                VALUES (?, ?, ?)
                """,
                (section_id, learner_id, now),
            )

        cursor = conn.execute(
            "INSERT INTO assessment_runs(section_id, source, created_at) VALUES (?, ?, ?)",
            (section_id, source, now),
        )
        run_id = int(cursor.lastrowid)

        for subject_name, subject in subjects.items():
            for learner in subject.learners:
                conn.execute(
                    """
                    INSERT INTO subject_results(run_id, subject_name, learner_name, total_points, note, empty_answers)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        subject_name,
                        learner.name,
                        int(subject.totals.get(learner.name, 0)),
                        float(subject.notes.get(learner.name, 0.0)),
                        int(subject.empty_counts.get(learner.name, 0)),
                    ),
                )

    return run_id


def get_sections_with_counts(db_path: str = ".data/results.db") -> pd.DataFrame:
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(
            """
            SELECT s.name AS section, COUNT(sl.learner_id) AS nb_stagiaires
            FROM sections s
            LEFT JOIN section_learners sl ON sl.section_id = s.id
            GROUP BY s.id, s.name
            ORDER BY s.name
            """,
            conn,
        )


def get_recent_runs(limit: int = 20, db_path: str = ".data/results.db") -> pd.DataFrame:
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(
            """
            SELECT r.id AS run_id, s.name AS section, r.source, r.created_at,
                   COUNT(sr.id) AS nb_lignes_resultats
            FROM assessment_runs r
            JOIN sections s ON s.id = r.section_id
            LEFT JOIN subject_results sr ON sr.run_id = r.id
            GROUP BY r.id, s.name, r.source, r.created_at
            ORDER BY r.id DESC
            LIMIT ?
            """,
            conn,
            params=(limit,),
        )
