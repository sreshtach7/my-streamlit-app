"""
ai_agent.py — AI Agent Module (LLM / AI Model integration point)

Responsibilities (per architecture):
  - Understands task context (NLU)
  - Analyzes completion patterns
  - Generates summaries & suggestions
  - Prioritizes remaining tasks
  - Task categorization, motivational feedback

Design:
  - Works fully offline out of the box using transparent rule-based logic,
    so the app is functional with zero configuration.
  - If an ANTHROPIC_API_KEY is present in the environment, richer natural-
    language summaries/suggestions are generated via the Claude API.
    The key is read only from the environment (never hard-coded, logged,
    or echoed back to the user) and requests fail safe: any API error
    silently falls back to the rule-based engine so the app never breaks.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from typing import List, Optional

from backend.task_manager import Task

# --- Optional LLM client -----------------------------------------------------
_client = None
_AI_ENABLED = False
try:
    import anthropic  # type: ignore

    _api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if _api_key:
        _client = anthropic.Anthropic(api_key=_api_key)
        _AI_ENABLED = True
except Exception:
    # Library not installed or client failed to init — safe fallback mode.
    _client = None
    _AI_ENABLED = False

MODEL_NAME = "claude-sonnet-4-6"

# --- Rule-based categorization (used as default, and as a fallback) --------
_CATEGORY_KEYWORDS = {
    "study": ["study", "read", "revise", "exam", "homework", "assignment", "lecture", "learn", "course", "class"],
    "project": ["project", "build", "code", "develop", "deploy", "debug", "feature", "app", "repo", "design"],
    "meeting": ["meeting", "call", "sync", "standup", "discussion", "interview", "presentation"],
    "personal": ["gym", "workout", "family", "shopping", "clean", "cook", "rest", "sleep", "walk", "self"],
    "work": ["report", "email", "client", "task", "deadline", "review", "submit", "office"],
}


def categorize_task(title: str) -> str:
    """Return a best-guess category for a task title using keyword matching."""
    text = title.lower()
    scores = Counter()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if re.search(rf"\b{re.escape(kw)}", text):
                scores[category] += 1
    if not scores:
        return "general"
    return scores.most_common(1)[0][0]


def suggest_priority(title: str) -> str:
    """Very lightweight heuristic priority suggestion based on urgency words."""
    text = title.lower()
    if any(w in text for w in ["urgent", "asap", "deadline", "exam", "today", "important"]):
        return "high"
    if any(w in text for w in ["someday", "later", "optional", "maybe"]):
        return "low"
    return "medium"


# --- Analysis -----------------------------------------------------------------

def analyze_completion(tasks: List[Task]) -> dict:
    """Analyze completion patterns for a list of tasks (Analyze stage)."""
    total = len(tasks)
    completed = [t for t in tasks if t.is_completed]
    incomplete = [t for t in tasks if not t.is_completed]
    rate = round((len(completed) / total) * 100, 1) if total else 0.0

    by_category = Counter(t.category for t in tasks)
    completed_by_category = Counter(t.category for t in completed)

    high_priority_incomplete = [t for t in incomplete if t.priority == "high"]

    return {
        "total": total,
        "completed_count": len(completed),
        "incomplete_count": len(incomplete),
        "completion_rate": rate,
        "by_category": dict(by_category),
        "completed_by_category": dict(completed_by_category),
        "high_priority_incomplete": [t.title for t in high_priority_incomplete],
    }


def _rule_based_summary(analysis: dict, completed: List[Task], incomplete: List[Task]) -> str:
    rate = analysis["completion_rate"]
    if analysis["total"] == 0:
        return "No tasks were logged today. Plan a few tasks tomorrow to get started."
    if rate == 100:
        tone = "Excellent work — every task was completed today!"
    elif rate >= 70:
        tone = "Solid progress today, with most tasks completed."
    elif rate >= 40:
        tone = "A mixed day — some tasks completed, several still pending."
    else:
        tone = "Today was tougher, with most tasks left incomplete."

    parts = [
        f"{tone} You completed {analysis['completed_count']} of {analysis['total']} tasks "
        f"({rate}% completion rate)."
    ]
    if incomplete:
        top_incomplete = ", ".join(t.title for t in incomplete[:3])
        parts.append(f"Still pending: {top_incomplete}.")
    return " ".join(parts)


def _rule_based_suggestions(analysis: dict, incomplete: List[Task]) -> List[str]:
    suggestions = []
    if analysis["high_priority_incomplete"]:
        names = ", ".join(analysis["high_priority_incomplete"][:3])
        suggestions.append(f"Carry high-priority tasks to tomorrow first: {names}.")
    if analysis["completion_rate"] < 50 and analysis["total"] > 0:
        suggestions.append("Consider breaking large pending tasks into smaller, 25–30 minute chunks.")
    if analysis["completion_rate"] == 100 and analysis["total"] > 0:
        suggestions.append("Great momentum — try adding one stretch task tomorrow to keep growing.")
    if not incomplete and analysis["total"] > 0:
        suggestions.append("All clear! Use any extra time to review or get ahead on upcoming work.")
    if not suggestions:
        suggestions.append("Keep logging tasks daily — patterns become clearer after a few days of data.")
    return suggestions


def generate_daily_summary(tasks: List[Task]) -> dict:
    """Generate a natural-language summary and suggestions for one day's tasks."""
    completed = [t for t in tasks if t.is_completed]
    incomplete = [t for t in tasks if not t.is_completed]
    analysis = analyze_completion(tasks)

    if _AI_ENABLED and tasks:
        try:
            return _llm_daily_summary(analysis, completed, incomplete)
        except Exception:
            pass  # Fail safe -> rule-based fallback below

    return {
        "summary": _rule_based_summary(analysis, completed, incomplete),
        "suggestions": _rule_based_suggestions(analysis, incomplete),
        "analysis": analysis,
        "source": "rule-based",
    }


def _llm_daily_summary(analysis: dict, completed: List[Task], incomplete: List[Task]) -> dict:
    """Use the Claude API for a richer, more personalized summary. Raises on failure
    so the caller can fall back safely; never logs or exposes the API key."""
    completed_titles = "; ".join(t.title for t in completed) or "none"
    incomplete_titles = "; ".join(t.title for t in incomplete) or "none"

    prompt = (
        "You are a concise, encouraging productivity coach reviewing one day of tasks.\n"
        f"Completed tasks: {completed_titles}\n"
        f"Incomplete tasks: {incomplete_titles}\n"
        f"Completion rate: {analysis['completion_rate']}%\n\n"
        "Respond ONLY with JSON, no other text, in exactly this shape:\n"
        '{"summary": "<2-3 sentence encouraging summary>", '
        '"suggestions": ["<short actionable suggestion>", "<short actionable suggestion>"]}'
    )

    resp = _client.messages.create(
        model=MODEL_NAME,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")
    text = text.strip().strip("`").replace("json\n", "", 1)

    import json
    data = json.loads(text)
    return {
        "summary": str(data.get("summary", "")).strip() or _rule_based_summary(analysis, completed, incomplete),
        "suggestions": [str(s).strip() for s in data.get("suggestions", [])][:5] or _rule_based_suggestions(analysis, incomplete),
        "analysis": analysis,
        "source": "ai",
    }


def generate_weekly_report(all_tasks: List[Task]) -> dict:
    """Aggregate multiple days of tasks into a weekly progress report."""
    analysis = analyze_completion(all_tasks)
    by_date = Counter(t.task_date for t in all_tasks)
    completed_by_date = Counter(t.task_date for t in all_tasks if t.is_completed)

    daily_rates = {}
    for date, total in by_date.items():
        done = completed_by_date.get(date, 0)
        daily_rates[date] = round((done / total) * 100, 1) if total else 0.0

    best_day = max(daily_rates, key=daily_rates.get) if daily_rates else None
    trend = "improving" if len(daily_rates) >= 2 and list(daily_rates.values())[-1] >= list(daily_rates.values())[0] else "steady"

    return {
        "analysis": analysis,
        "daily_rates": daily_rates,
        "best_day": best_day,
        "trend": trend,
    }


def is_ai_enabled() -> bool:
    return _AI_ENABLED
