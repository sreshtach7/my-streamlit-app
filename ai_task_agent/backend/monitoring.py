"""
monitoring.py — Monitoring & Checking Logic

Responsibilities (per architecture):
  - Tracks daily progress
  - Separates completed & incomplete tasks
  - Triggers end-of-day analysis and stores it for weekly reporting
"""

from __future__ import annotations

import datetime as dt
from typing import List, Tuple

from backend.ai_agent import generate_daily_summary
from backend.database import get_connection
from backend.task_manager import Task, get_tasks_by_date


def split_tasks(tasks: List[Task]) -> Tuple[List[Task], List[Task]]:
    """Separate completed & incomplete tasks."""
    completed = [t for t in tasks if t.is_completed]
    incomplete = [t for t in tasks if not t.is_completed]
    return completed, incomplete


def progress_ratio(tasks: List[Task]) -> float:
    if not tasks:
        return 0.0
    completed, _ = split_tasks(tasks)
    return round(len(completed) / len(tasks), 4)


def trigger_end_of_day_analysis(task_date: str | None = None) -> dict:
    """Run AI analysis for a given day and persist the result for history/weekly use."""
    task_date = task_date or dt.date.today().isoformat()
    tasks = get_tasks_by_date(task_date)
    result = generate_daily_summary(tasks)
    analysis = result["analysis"]

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO daily_summaries
                (summary_date, completed_count, incomplete_count, completion_rate,
                 ai_summary, ai_suggestions, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(summary_date) DO UPDATE SET
                completed_count=excluded.completed_count,
                incomplete_count=excluded.incomplete_count,
                completion_rate=excluded.completion_rate,
                ai_summary=excluded.ai_summary,
                ai_suggestions=excluded.ai_suggestions,
                created_at=excluded.created_at
            """,
            (
                task_date,
                analysis["completed_count"],
                analysis["incomplete_count"],
                analysis["completion_rate"],
                result["summary"],
                "\n".join(result["suggestions"]),
                dt.datetime.now().isoformat(timespec="seconds"),
            ),
        )
    return result


def get_stored_summary(task_date: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM daily_summaries WHERE summary_date = ?", (task_date,)
        ).fetchone()
    if not row:
        return None
    return {
        "summary_date": row["summary_date"],
        "completed_count": row["completed_count"],
        "incomplete_count": row["incomplete_count"],
        "completion_rate": row["completion_rate"],
        "ai_summary": row["ai_summary"],
        "ai_suggestions": (row["ai_suggestions"] or "").split("\n") if row["ai_suggestions"] else [],
        "created_at": row["created_at"],
    }
