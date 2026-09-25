"""
app.py — Frontend (Streamlit)

Provides:
  - Add daily tasks
  - Mark tasks as completed / incomplete
  - View real-time progress
  - See daily & weekly summaries
  - Get AI suggestions

Run with:  streamlit run app.py
"""

from __future__ import annotations

import datetime as dt

import streamlit as st
from dotenv import load_dotenv

load_dotenv()  # Load ANTHROPIC_API_KEY from a local .env file, if present.

from backend.ai_agent import categorize_task, is_ai_enabled, suggest_priority
from backend.database import init_db
from backend.monitoring import get_stored_summary, split_tasks, trigger_end_of_day_analysis
from backend.task_manager import (
    ValidationError,
    add_task,
    delete_task,
    get_distinct_dates,
    get_tasks_between,
    get_tasks_by_date,
    update_status,
)
from backend.ai_agent import generate_weekly_report

# ------------------------------------------------------------------ #
# Page config + "classy" theme
# ------------------------------------------------------------------ #
st.set_page_config(
    page_title="AI Daily Task Monitoring Agent",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap');

    html, body, [class*="css"]  { font-family: 'Inter', sans-serif; }
    h1, h2, h3, h4 { font-family: 'Poppins', sans-serif !important; }

    .main { background: radial-gradient(circle at top left, #f7f5ff 0%, #f4f7fb 45%, #fbfbfd 100%); }

    .hero-card {
        background: linear-gradient(135deg, #6c63ff 0%, #8b7bff 55%, #a89bff 100%);
        border-radius: 20px;
        padding: 1.8rem 2.2rem;
        color: white;
        margin-bottom: 1.5rem;
        box-shadow: 0 10px 30px rgba(108, 99, 255, 0.25);
    }
    .hero-card h1 { color: white; margin-bottom: 0.2rem; font-weight: 700; }
    .hero-card p { color: rgba(255,255,255,0.9); margin: 0; }

    .metric-card {
        background: white;
        border-radius: 16px;
        padding: 1.1rem 1.3rem;
        box-shadow: 0 4px 18px rgba(30, 30, 60, 0.06);
        border: 1px solid rgba(108, 99, 255, 0.08);
    }

    .task-card {
        background: white;
        border-radius: 14px;
        padding: 0.9rem 1.1rem;
        margin-bottom: 0.6rem;
        border-left: 5px solid #6c63ff;
        box-shadow: 0 2px 10px rgba(30, 30, 60, 0.05);
    }
    .task-card.completed { border-left-color: #33c48d; opacity: 0.75; }
    .task-card.high { border-left-color: #ff6b6b; }

    .pill {
        display: inline-block;
        padding: 0.15rem 0.6rem;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 600;
        margin-right: 0.35rem;
        background: #f0eeff;
        color: #6c63ff;
    }
    .pill.high { background: #ffe9e9; color: #e04848; }
    .pill.low { background: #eafaf1; color: #1f9d64; }

    .suggestion-item {
        background: #fff9ec;
        border-left: 4px solid #f5b942;
        padding: 0.6rem 0.9rem;
        border-radius: 10px;
        margin-bottom: 0.5rem;
        font-size: 0.92rem;
    }

    footer, #MainMenu {visibility: hidden;}
    .stButton>button {
        border-radius: 10px;
        font-weight: 600;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ------------------------------------------------------------------ #
# Init
# ------------------------------------------------------------------ #
init_db()

if "selected_date" not in st.session_state:
    st.session_state.selected_date = dt.date.today()

# ------------------------------------------------------------------ #
# Hero header
# ------------------------------------------------------------------ #
ai_badge = "🟢 AI-enhanced mode" if is_ai_enabled() else "⚪ Offline smart-rules mode"
st.markdown(
    f"""
    <div class="hero-card">
        <h1>✨ AI Daily Task Monitoring Agent</h1>
        <p>Plan → Monitor → Check → Analyze → Improve &nbsp;|&nbsp; {ai_badge}</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------ #
# Sidebar — navigation & quick add
# ------------------------------------------------------------------ #
with st.sidebar:
    st.markdown("### 📅 Select day")
    st.session_state.selected_date = st.date_input("Viewing tasks for", st.session_state.selected_date)
    view_date = st.session_state.selected_date.isoformat()

    st.markdown("---")
    st.markdown("### ➕ Add a task")
    with st.form("add_task_form", clear_on_submit=True):
        title = st.text_input("What do you need to do?", max_chars=200, placeholder="e.g. Study DBMS for 2 hours")
        col_a, col_b = st.columns(2)
        with col_a:
            category = st.selectbox(
                "Category",
                ["auto-detect", "study", "project", "meeting", "work", "personal", "general"],
            )
        with col_b:
            priority = st.selectbox("Priority", ["auto-detect", "high", "medium", "low"])
        notes = st.text_area("Notes (optional)", max_chars=1000, height=70)
        submitted = st.form_submit_button("Add Task", use_container_width=True)

        if submitted:
            try:
                final_category = categorize_task(title) if category == "auto-detect" else category
                final_priority = suggest_priority(title) if priority == "auto-detect" else priority
                add_task(
                    title=title,
                    category=final_category,
                    priority=final_priority,
                    task_date=view_date,
                    notes=notes,
                )
                st.success(f"Added: {title}  ·  {final_category} / {final_priority} priority")
                st.rerun()
            except ValidationError as e:
                st.error(str(e))

    st.markdown("---")
    st.caption(
        "🔒 Your data stays local in a SQLite database. "
        "No task content is sent anywhere unless AI-enhanced mode is enabled "
        "via your own API key."
    )

# ------------------------------------------------------------------ #
# Tabs
# ------------------------------------------------------------------ #
tab_today, tab_summary, tab_weekly = st.tabs(["📋 Today's Tasks", "🧠 Daily Summary", "📊 Weekly Report"])

# ---------------- Today's Tasks tab -------------------------------- #
with tab_today:
    tasks = get_tasks_by_date(view_date)
    completed, incomplete = split_tasks(tasks)
    total = len(tasks)
    rate = round((len(completed) / total) * 100) if total else 0

    c1, c2, c3, c4 = st.columns(4)
    for col, label, value in [
        (c1, "Total tasks", total),
        (c2, "Completed", len(completed)),
        (c3, "Pending", len(incomplete)),
        (c4, "Completion", f"{rate}%"),
    ]:
        with col:
            st.markdown(f'<div class="metric-card"><h3>{value}</h3>{label}</div>', unsafe_allow_html=True)

    st.progress(rate / 100 if total else 0)
    st.markdown("<br/>", unsafe_allow_html=True)

    if not tasks:
        st.info("No tasks for this day yet. Add one from the sidebar. ✨")
    else:
        for t in tasks:
            css_class = "task-card completed" if t.is_completed else "task-card"
            if t.priority == "high" and not t.is_completed:
                css_class += " high"
            colA, colB, colC = st.columns([0.08, 0.72, 0.2])
            with colA:
                checked = st.checkbox("", value=t.is_completed, key=f"chk_{t.id}")
                if checked != t.is_completed:
                    update_status(t.id, "completed" if checked else "pending")
                    st.rerun()
            with colB:
                priority_pill = f'<span class="pill {t.priority if t.priority != "medium" else ""}">{t.priority}</span>'
                category_pill = f'<span class="pill">{t.category}</span>'
                strike = "text-decoration: line-through;" if t.is_completed else ""
                notes_html = f"<br/><small style='color:#888'>{t.notes}</small>" if t.notes else ""
                st.markdown(
                    f'<div class="{css_class}"><b style="{strike}">{t.title}</b><br/>'
                    f'{priority_pill}{category_pill}{notes_html}</div>',
                    unsafe_allow_html=True,
                )
            with colC:
                if st.button("🗑️ Delete", key=f"del_{t.id}", use_container_width=True):
                    delete_task(t.id)
                    st.rerun()

# ---------------- Daily Summary tab --------------------------------- #
with tab_summary:
    st.markdown("#### End-of-day analysis")
    st.caption("Runs the AI Agent Module + Monitoring & Checking Logic for the selected date.")

    if st.button("▶️ Run / Refresh Analysis", type="primary"):
        with st.spinner("Analyzing today's progress..."):
            trigger_end_of_day_analysis(view_date)
        st.rerun()

    stored = get_stored_summary(view_date)
    if not stored:
        st.info("No analysis yet for this date. Click **Run / Refresh Analysis** above.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Completed", stored["completed_count"])
        c2.metric("Incomplete", stored["incomplete_count"])
        c3.metric("Completion rate", f"{stored['completion_rate']}%")

        st.markdown("##### 📝 Summary")
        st.write(stored["ai_summary"])

        st.markdown("##### 💡 AI Suggestions")
        for s in stored["ai_suggestions"]:
            if s.strip():
                st.markdown(f'<div class="suggestion-item">💡 {s}</div>', unsafe_allow_html=True)

        st.caption(f"Last generated: {stored['created_at']}")

# ---------------- Weekly Report tab --------------------------------- #
with tab_weekly:
    st.markdown("#### Weekly progress report")
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=6)
    st.caption(f"Showing {start_date.isoformat()} → {end_date.isoformat()}")

    weekly_tasks = get_tasks_between(start_date.isoformat(), end_date.isoformat())
    if not weekly_tasks:
        st.info("No tasks logged in the past 7 days yet.")
    else:
        report = generate_weekly_report(weekly_tasks)
        analysis = report["analysis"]

        c1, c2, c3 = st.columns(3)
        c1.metric("Total tasks (7d)", analysis["total"])
        c2.metric("Completed (7d)", analysis["completed_count"])
        c3.metric("Overall completion", f"{analysis['completion_rate']}%")

        st.markdown("##### 📈 Daily completion rate")
        chart_data = {"date": list(report["daily_rates"].keys()), "rate": list(report["daily_rates"].values())}
        if chart_data["date"]:
            import pandas as pd
            df = pd.DataFrame(chart_data).sort_values("date")
            st.line_chart(df.set_index("date"))

        if report["best_day"]:
            st.success(f"🏆 Best day: {report['best_day']} ({report['daily_rates'][report['best_day']]}% completion)")

        st.markdown("##### 🗂️ Tasks by category (7 days)")
        st.bar_chart(analysis["by_category"])

    all_dates = get_distinct_dates()
    if all_dates:
        st.markdown("---")
        st.caption(f"Historical data available for {len(all_dates)} day(s) total.")
