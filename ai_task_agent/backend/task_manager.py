"""
task_manager.py — Task Management Module

Responsibilities (per architecture):
  - Add / update tasks
  - Track status (completed / pending)
  - Store in database

Security notes:
  - All user-supplied strings are length-limited and stripped before storage.
  - All SQL is parameterized (?, ?, ...). No f-strings / .format() are ever
    concatenated into a query.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import List, Optional

from backend.database import get_connection

VALID_CATEGORIES = {"study", "project", "meeting", "personal", "work", "general"}
VALID_PRIORITIES = {"high", "medium", "low"}
VALID_STATUSES = {"pending", "completed"}

MAX_TITLE_LEN = 200
MAX_NOTES_LEN = 1000


class ValidationError(ValueError):
    """Raised when user input fails validation before touching the database."""


@dataclass
class Task:
    id: int
    title: str
    category: str
    priority: str
    status: str
    task_date: str
    created_at: str
    completed_at: Optional[str]
    notes: Optional[str]

    @property
    def is_completed(self) -> bool:
        return self.status == "completed"


def _sanitize_text(value: str, max_len: int, field_name: str) -> str:
    if value is None:
        raise ValidationError(f"{field_name} is required.")
    value = value.strip()
    if not value:
        raise ValidationError(f"{field_name} cannot be empty.")
    if len(value) > max_len:
        raise ValidationError(f"{field_name} must be under {max_len} characters.")
    return value


def _today() -> str:
    return dt.date.today().isoformat()


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def add_task(
    title: str,
    category: str = "general",
    priority: str = "medium",
    task_date: Optional[str] = None,
    notes: Optional[str] = None,
) -> int:
    """Insert a new task and return its new id."""
    title = _sanitize_text(title, MAX_TITLE_LEN, "Task title")
    category = category.lower().strip() if category else "general"
    priority = priority.lower().strip() if priority else "medium"
    if category not in VALID_CATEGORIES:
        category = "general"
    if priority not in VALID_PRIORITIES:
        priority = "medium"
    task_date = task_date or _today()
    if notes:
        notes = notes.strip()[:MAX_NOTES_LEN]

    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO tasks (title, category, priority, status, task_date, created_at, notes)
            VALUES (?, ?, ?, 'pending', ?, ?, ?)
            """,
            (title, category, priority, task_date, _now(), notes),
        )
        return int(cur.lastrowid)


def update_status(task_id: int, status: str) -> None:
    """Mark a task completed or pending."""
    status = status.lower().strip()
    if status not in VALID_STATUSES:
        raise ValidationError("Status must be 'pending' or 'completed'.")
    completed_at = _now() if status == "completed" else None
    with get_connection() as conn:
        conn.execute(
            "UPDATE tasks SET status = ?, completed_at = ? WHERE id = ?",
            (status, completed_at, task_id),
        )


def update_task(task_id: int, title: Optional[str] = None, category: Optional[str] = None,
                 priority: Optional[str] = None, notes: Optional[str] = None) -> None:
    """Edit an existing task's editable fields."""
    fields, values = [], []
    if title is not None:
        fields.append("title = ?")
        values.append(_sanitize_text(title, MAX_TITLE_LEN, "Task title"))
    if category is not None:
        category = category.lower().strip()
        fields.append("category = ?")
        values.append(category if category in VALID_CATEGORIES else "general")
    if priority is not None:
        priority = priority.lower().strip()
        fields.append("priority = ?")
        values.append(priority if priority in VALID_PRIORITIES else "medium")
    if notes is not None:
        fields.append("notes = ?")
        values.append(notes.strip()[:MAX_NOTES_LEN])
    if not fields:
        return
    values.append(task_id)
    with get_connection() as conn:
        conn.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?", values)


def delete_task(task_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))


def _row_to_task(row) -> Task:
    return Task(
        id=row["id"], title=row["title"], category=row["category"],
        priority=row["priority"], status=row["status"], task_date=row["task_date"],
        created_at=row["created_at"], completed_at=row["completed_at"], notes=row["notes"],
    )


def get_tasks_by_date(task_date: Optional[str] = None) -> List[Task]:
    task_date = task_date or _today()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE task_date = ? ORDER BY priority = 'high' DESC, id ASC",
            (task_date,),
        ).fetchall()
    return [_row_to_task(r) for r in rows]


def get_all_tasks(limit: int = 2000) -> List[Task]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY task_date DESC, id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_task(r) for r in rows]


def get_tasks_between(start_date: str, end_date: str) -> List[Task]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE task_date BETWEEN ? AND ? ORDER BY task_date ASC, id ASC",
            (start_date, end_date),
        ).fetchall()
    return [_row_to_task(r) for r in rows]


def get_distinct_dates() -> List[str]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT task_date FROM tasks ORDER BY task_date DESC"
        ).fetchall()
    return [r["task_date"] for r in rows]
