#!/usr/bin/env bash
# Convenience launcher for the AI Daily Task Monitoring Agent.
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo "Starting app at http://localhost:8501 ..."
streamlit run app.py
