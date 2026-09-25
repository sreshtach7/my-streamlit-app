# ✨ AI Daily Task Monitoring Agent

A fully working task tracker with an AI agent layer, built to match the
**Plan → Monitor → Check → Analyze → Improve** architecture:

```
User → Frontend (Streamlit) → Backend (Python)
                                 ├── Task Management Module
                                 ├── AI Agent Module (LLM-ready, offline-capable)
                                 └── Monitoring & Checking Logic
                              → Database (SQLite, local file)
                              → Outputs: completed/incomplete lists,
                                daily summary, AI insights, weekly report
```

## 1. Quick start

**Requirements:** Python 3.10+

```bash
# 1. Unzip the project, then from inside the folder:
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt

# 2. (Optional) enable AI-enhanced summaries
cp .env.example .env
# then open .env and paste your own Anthropic API key

# 3. Run it
streamlit run app.py
```

Or simply run `./run.sh` (macOS/Linux) which does all of the above for you.

The app opens at **http://localhost:8501**.

> No API key? No problem. The app runs a transparent, rule-based AI Agent
> out of the box (categorization, priority suggestions, daily summaries,
> and suggestions) — everything works fully offline. Adding an
> `ANTHROPIC_API_KEY` simply upgrades the summaries/suggestions to
> LLM-generated natural language.

## 2. What's inside

| File | Role (from the architecture diagram) |
|---|---|
| `app.py` | Frontend (Streamlit) — add tasks, mark complete, view progress, summaries |
| `backend/database.py` | Database layer — SQLite, parameterized queries only |
| `backend/task_manager.py` | Task Management Module — add/update/delete, validation |
| `backend/ai_agent.py` | AI Agent Module — categorization, analysis, summaries, suggestions |
| `backend/monitoring.py` | Monitoring & Checking Logic — split completed/incomplete, end-of-day trigger |

Data is stored locally in `data/tasks.db` (created automatically on first run).

## 3. Features

- **Add daily tasks** with auto-detected category & priority (or set manually)
- **Mark tasks completed/incomplete** in real time with instant progress bar
- **Daily summary** — one-click AI analysis of the day, with actionable suggestions
- **Weekly report** — 7-day completion trend chart + category breakdown
- **Classy, distraction-free UI** with a custom theme, cards, and pill tags

## 4. Security & privacy notes

- All database queries are **parameterized** — no SQL injection surface.
- User input (task titles/notes) is length-limited and sanitized before storage.
- All data stays in a **local SQLite file** — nothing leaves your machine unless
  you opt in to AI-enhanced mode with your own API key.
- The API key is read **only** from the environment (`.env`, git-ignored) —
  it is never hard-coded, logged, or displayed in the UI.
- If the AI API call fails for any reason (no key, no network, rate limit),
  the app **fails safe** and silently uses the built-in rule-based engine —
  it never crashes or blocks task tracking.
- `.gitignore` excludes `.env` and the local database file by default.

## 5. Extending it

- Swap SQLite for a hosted Postgres/MySQL database by changing `backend/database.py`
  only — the rest of the app is unaffected.
- The AI Agent Module (`backend/ai_agent.py`) is the single integration point
  for any LLM — swap providers by editing `_llm_daily_summary()`.
- Add authentication (e.g. `streamlit-authenticator`) if you plan to deploy this
  for multiple users on a shared server.

Enjoy — **Smarter Tasks → Better Days** ✨
