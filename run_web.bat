@echo off
cd /d %~dp0

if not exist .venv\Scripts\activate (
  py -m venv .venv
)

call .venv\Scripts\activate
pip install -r requirements.txt
streamlit run web_app.py
pause
