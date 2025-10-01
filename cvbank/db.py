"""Database layer for the CV bank application."""
from __future__ import annotations

import shutil
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence


@dataclass
class Candidate:
    """A candidate entry stored in the database."""

    id: int
    name: str
    email: Optional[str]
    phone: Optional[str]
    job_title: Optional[str]
    company: Optional[str]
    location: Optional[str]
    notes: Optional[str]
    cv_text: Optional[str]
    file_name: Optional[str]
    created_at: str
    skills: Sequence[str]


class CVDatabase:
    """High level helper around the SQLite database."""

    def __init__(self, db_path: Path | str = "cv_bank.db", storage_dir: Path | str | None = None) -> None:
        self.db_path = Path(db_path)
        if storage_dir is None:
            self.storage_dir = self.db_path.parent / "cv_files"
        else:
            self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        """Create the database schema if it does not already exist."""

        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT,
                    phone TEXT,
                    job_title TEXT,
                    company TEXT,
                    location TEXT,
                    notes TEXT,
                    cv_text TEXT,
                    file_name TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS skills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                );

                CREATE TABLE IF NOT EXISTS candidate_skills (
                    candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
                    skill_id INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
                    UNIQUE(candidate_id, skill_id)
                );
                """
            )

    # ------------------------------------------------------------------
    # Candidate helpers
    # ------------------------------------------------------------------
    def add_candidate(
        self,
        *,
        name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        job_title: Optional[str] = None,
        company: Optional[str] = None,
        location: Optional[str] = None,
        notes: Optional[str] = None,
        cv_text: Optional[str] = None,
        skills: Optional[Iterable[str]] = None,
        source_file: Optional[Path] = None,
    ) -> int:
        """Store a new candidate in the database."""

        normalized_skills = self._prepare_skills(skills)
        stored_file_name = None
        if source_file is not None:
            stored_file_name = self._store_file(source_file)

        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO candidates (
                    name, email, phone, job_title, company, location, notes, cv_text, file_name, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    email,
                    phone,
                    job_title,
                    company,
                    location,
                    notes,
                    cv_text,
                    stored_file_name,
                    datetime.utcnow().isoformat(timespec="seconds"),
                ),
            )
            candidate_id = cursor.lastrowid
            if normalized_skills:
                self._attach_skills(conn, candidate_id, normalized_skills)

        return candidate_id

    def list_candidates(
        self,
        *,
        skill: Optional[str] = None,
        location: Optional[str] = None,
        company: Optional[str] = None,
        job_title: Optional[str] = None,
    ) -> List[Candidate]:
        """Retrieve candidates optionally filtered by metadata fields."""

        clauses: List[str] = []
        params: List[str] = []

        joins = ""
        if skill:
            joins += (
                " JOIN candidate_skills cs ON cs.candidate_id = c.id"
                " JOIN skills s ON s.id = cs.skill_id"
            )
            clauses.append("LOWER(s.name) = LOWER(?)")
            params.append(skill)

        if location:
            clauses.append("LOWER(c.location) = LOWER(?)")
            params.append(location)
        if company:
            clauses.append("LOWER(c.company) = LOWER(?)")
            params.append(company)
        if job_title:
            clauses.append("LOWER(c.job_title) = LOWER(?)")
            params.append(job_title)

        where_clause = ""
        if clauses:
            where_clause = " WHERE " + " AND ".join(clauses)

        query = (
            "SELECT DISTINCT c.* FROM candidates c" + joins + where_clause + " ORDER BY datetime(c.created_at) DESC"
        )

        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            skills_map = self._fetch_skills_for_candidates(conn, [row["id"] for row in rows])

        return [self._row_to_candidate(row, skills_map) for row in rows]

    def search_candidates(self, keywords: Sequence[str]) -> List[Candidate]:
        """Search for candidates by matching keywords across multiple fields."""

        if not keywords:
            return self.list_candidates()

        conditions: List[str] = []
        params: List[str] = []
        for keyword in keywords:
            token = f"%{keyword.lower()}%"
            conditions.append(
                "(" + " OR ".join(
                    [
                        "LOWER(c.name) LIKE ?",
                        "LOWER(c.email) LIKE ?",
                        "LOWER(c.phone) LIKE ?",
                        "LOWER(c.job_title) LIKE ?",
                        "LOWER(c.company) LIKE ?",
                        "LOWER(c.location) LIKE ?",
                        "LOWER(c.notes) LIKE ?",
                        "LOWER(c.cv_text) LIKE ?",
                        "LOWER(s.name) LIKE ?",
                    ]
                ) + ")"
            )
            params.extend([token] * 9)

        where_clause = " WHERE " + " AND ".join(conditions)
        query = (
            "SELECT DISTINCT c.* FROM candidates c "
            "LEFT JOIN candidate_skills cs ON cs.candidate_id = c.id "
            "LEFT JOIN skills s ON s.id = cs.skill_id "
            f"{where_clause} ORDER BY datetime(c.created_at) DESC"
        )

        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            skills_map = self._fetch_skills_for_candidates(conn, [row["id"] for row in rows])

        return [self._row_to_candidate(row, skills_map) for row in rows]

    def get_candidate(self, candidate_id: int) -> Optional[Candidate]:
        """Return a single candidate entry by ID."""

        with self.connect() as conn:
            row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
            if row is None:
                return None
            skills_map = self._fetch_skills_for_candidates(conn, [row["id"]])
        return self._row_to_candidate(row, skills_map)

    def delete_candidate(self, candidate_id: int) -> bool:
        """Delete a candidate from the database."""

        with self.connect() as conn:
            row = conn.execute("SELECT file_name FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
            if row is None:
                return False
            file_name = row["file_name"]
            conn.execute("DELETE FROM candidates WHERE id = ?", (candidate_id,))
        if file_name:
            stored_file = self.storage_dir / file_name
            if stored_file.exists():
                stored_file.unlink()
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _row_to_candidate(self, row: sqlite3.Row, skills_map: Dict[int, Sequence[str]]) -> Candidate:
        return Candidate(
            id=row["id"],
            name=row["name"],
            email=row["email"],
            phone=row["phone"],
            job_title=row["job_title"],
            company=row["company"],
            location=row["location"],
            notes=row["notes"],
            cv_text=row["cv_text"],
            file_name=row["file_name"],
            created_at=row["created_at"],
            skills=skills_map.get(row["id"], ()),
        )

    def _fetch_skills_for_candidates(
        self, conn: sqlite3.Connection, candidate_ids: Sequence[int]
    ) -> Dict[int, Sequence[str]]:
        if not candidate_ids:
            return {}
        placeholders = ",".join("?" for _ in candidate_ids)
        rows = conn.execute(
            f"""
            SELECT c.id as candidate_id, s.name as skill
            FROM candidates c
            JOIN candidate_skills cs ON cs.candidate_id = c.id
            JOIN skills s ON s.id = cs.skill_id
            WHERE c.id IN ({placeholders})
            ORDER BY s.name COLLATE NOCASE
            """,
            tuple(candidate_ids),
        ).fetchall()
        result: Dict[int, List[str]] = {}
        for row in rows:
            result.setdefault(row["candidate_id"], []).append(row["skill"])
        return result

    def _prepare_skills(self, skills: Optional[Iterable[str]]) -> List[str]:
        if not skills:
            return []
        normalized = []
        for skill in skills:
            stripped = skill.strip()
            if stripped:
                normalized.append(stripped)
        return normalized

    def _attach_skills(
        self, conn: sqlite3.Connection, candidate_id: int, skills: Sequence[str]
    ) -> None:
        for skill in skills:
            skill_id = self._ensure_skill(conn, skill)
            conn.execute(
                "INSERT OR IGNORE INTO candidate_skills (candidate_id, skill_id) VALUES (?, ?)",
                (candidate_id, skill_id),
            )

    def _ensure_skill(self, conn: sqlite3.Connection, skill: str) -> int:
        row = conn.execute("SELECT id FROM skills WHERE LOWER(name) = LOWER(?)", (skill,)).fetchone()
        if row:
            return row["id"]
        cursor = conn.execute("INSERT INTO skills (name) VALUES (?)", (skill,))
        return cursor.lastrowid

    def _store_file(self, source_file: Path) -> str:
        source = Path(source_file)
        if not source.exists():
            raise FileNotFoundError(f"CV file not found: {source}")
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        destination_name = f"{timestamp}_{source.name}"
        destination = self.storage_dir / destination_name
        shutil.copy2(source, destination)
        return destination_name


__all__ = ["CVDatabase", "Candidate"]
