"""Entry point: landing page first, dashboard second.

    streamlit run dashboard/app.py
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

st.set_page_config(page_title="Data Quality Monitor", page_icon="📊", layout="wide")

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap');
html, body, .stApp, button, input, textarea { font-family: 'DM Sans', sans-serif; }
.block-container { max-width: 1150px; padding-top: 2.5rem; }
[data-testid="stMetric"] { background:#fff; border:1px solid #E4E1DA; border-radius:14px; padding:14px 18px; }
[data-testid="stMetricLabel"] p { color:#52606a; }
h1 { color:#17323B; font-weight:700; letter-spacing:-0.02em; }
</style>""", unsafe_allow_html=True)

pages = [
    st.Page("home.py", title="Home", default=True),
    st.Page("monitor.py", title="Dashboard", url_path="dashboard"),
]
st.navigation(pages, position="hidden").run()
