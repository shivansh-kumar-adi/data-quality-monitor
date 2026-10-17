"""Landing page. Shows what the project is, a live snapshot of the latest run,
and a button into the dashboard."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st
from dotenv import load_dotenv

from src.storage import DEFAULT_DB_URL, get_engine, load_runs

load_dotenv(ROOT / ".env")

REPO = "https://github.com/shivansh-kumar-adi/data-quality-monitor"
INK, STONE, CORAL, BLUE, AQUA = "#17323B", "#EEECE7", "#EB6834", "#2A78D6", "#1BAF7A"

st.markdown(f"""<style>
section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {{ display:none; }}
.st-key-hero {{ background:{STONE}; border-radius:24px; padding:56px 56px 48px; }}
.st-key-cta {{ background:{INK}; border-radius:24px; padding:64px 40px; text-align:center; }}
.st-key-cta h2 {{ color:#fff !important; font-size:2.6rem; margin-bottom:.4rem; }}
.st-key-cta p {{ color:#B9C7CC; font-size:1.1rem; }}
.st-key-cta [data-testid="stButton"] {{ display:flex; justify-content:center; }}
.hero-title {{ font-size:4rem; line-height:1.02; font-weight:700; color:{INK}; letter-spacing:-0.03em; margin:0 0 18px; }}
.hero-sub {{ font-size:1.35rem; line-height:1.45; color:{INK}; max-width:30ch; margin-bottom:28px; }}
.h2 {{ font-size:2.2rem; font-weight:700; color:{INK}; letter-spacing:-0.02em; margin:64px 0 14px; }}
.lead {{ font-size:1.12rem; line-height:1.65; color:#33474f; max-width:70ch; }}
.card {{ background:#fff; border:1px solid #E4E1DA; border-radius:16px; padding:22px 22px 20px; height:100%; color:{INK}; }}
.card b {{ font-size:1.1rem; display:block; margin-bottom:6px; }}
.card span {{ color:#4a5d65; line-height:1.5; font-size:.97rem; }}
.card .big {{ font-size:2.4rem; font-weight:700; line-height:1.1; display:block; margin:4px 0; }}
.card a {{ color:{BLUE}; text-decoration:none; font-weight:500; }}
.step {{ background:{STONE}; border-radius:14px; padding:16px; text-align:center; color:{INK}; font-weight:500; }}
.step small {{ display:block; font-weight:400; color:#52606a; margin-top:4px; }}
@media (max-width: 800px) {{ .hero-title {{ font-size:2.6rem; }} .st-key-hero {{ padding:28px; }} }}
</style>""", unsafe_allow_html=True)


@st.cache_data(ttl=300, show_spinner=False)
def latest_run(url: str):
    """Scores of the newest run, or None if the database is unreachable or empty."""
    try:
        runs = load_runs(get_engine(url))
        if runs.empty:
            return None
        r = runs.sort_values(["run_at", "run_id"]).iloc[-1]
        out = {k: float(r[k]) for k in ("overall", "completeness", "validity", "uniqueness")}
        return out | {"issues": int(r.issue_count), "rows": int(r.row_count), "run": int(r.run_id)}
    except Exception:
        return None


def pct(v):
    return "n/a" if v != v else f"{v:.1f}%"


def art(score):
    dash = 239 * max(0, min(score, 100)) / 100
    return f"""<svg viewBox="0 0 320 250" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Quality score gauge and three dimension bars">
<rect width="320" height="250" rx="26" fill="{INK}"/>
<circle cx="160" cy="88" r="38" fill="none" stroke="#2c4b56" stroke-width="12"/>
<circle cx="160" cy="88" r="38" fill="none" stroke="{AQUA}" stroke-width="12" stroke-linecap="round"
 stroke-dasharray="{dash:.0f} 239" transform="rotate(-90 160 88)"/>
<text x="160" y="97" text-anchor="middle" fill="#fff" font-size="26" font-weight="700" font-family="DM Sans, sans-serif">{score:.0f}</text>
<rect x="48" y="158" width="64" height="62" rx="8" fill="{BLUE}"/>
<rect x="128" y="140" width="64" height="80" rx="8" fill="{CORAL}"/>
<rect x="208" y="150" width="64" height="70" rx="8" fill="{AQUA}"/></svg>"""


snap = latest_run(os.getenv("DATABASE_URL", DEFAULT_DB_URL))

# ---------- hero ----------
with st.container(key="hero"):
    left, right = st.columns([3, 2], vertical_alignment="center", gap="large")
    with left:
        st.markdown('<h1 class="hero-title">Data Quality Monitor</h1>'
                    '<p class="hero-sub">Know how healthy your customer data is, and exactly which rows to fix.</p>',
                    unsafe_allow_html=True)
        b1, b2, _ = st.columns([1.3, 1.3, 2])
        if b1.button("Open dashboard", type="primary", key="open_top"):
            st.switch_page("monitor.py")
        b2.link_button("View on GitHub", REPO)
    right.markdown(art(snap["overall"] if snap else 96), unsafe_allow_html=True)

# ---------- what it is ----------
st.markdown('<h2 class="h2">What is Data Quality Monitor?</h2>'
            '<p class="lead">Customer files rarely arrive clean. Missing emails, impossible ages and duplicate '
            'customers lead to wrong reports and bounced messages. Data Quality Monitor checks a CSV against '
            'rules you configure, scores it from 0 to 100, saves every run, and shows what failed, '
            'on which line, and whether quality is improving.</p>', unsafe_allow_html=True)

# ---------- capabilities ----------
st.markdown('<h2 class="h2">What it does</h2>', unsafe_allow_html=True)
caps = [
    ("Rule engine", "Eight rule types set in one YAML file. Change a threshold and re-run, with no code."),
    ("Data profiling", "Column types, null counts, unique counts and numeric ranges for every file."),
    ("Quality scores", "Completeness, validity and uniqueness from 0 to 100, plus a weighted overall score."),
    ("Run history", "Every run and every failing record is stored, so trends and bad rows stay traceable."),
]
for col, (title, text) in zip(st.columns(4, gap="medium"), caps):
    col.markdown(f'<div class="card"><b>{title}</b><span>{text}</span></div>', unsafe_allow_html=True)

# ---------- live snapshot ----------
if snap:
    st.markdown(f'<h2 class="h2">Latest run</h2><p class="lead">Run #{snap["run"]}: '
                f'{snap["rows"]:,} rows checked, {snap["issues"]:,} issues found.</p>', unsafe_allow_html=True)
    tiles = [("Overall", snap["overall"]), ("Completeness", snap["completeness"]),
             ("Validity", snap["validity"]), ("Uniqueness", snap["uniqueness"])]
    for col, (label, v) in zip(st.columns(4, gap="medium"), tiles):
        col.markdown(f'<div class="card"><span>{label}</span><span class="big">{pct(v)}</span></div>',
                     unsafe_allow_html=True)

# ---------- how it works ----------
st.markdown('<h2 class="h2">How it works</h2>', unsafe_allow_html=True)
flow = [("CSV", "read as text"), ("Profile", "column facts"), ("Rules", "from rules.yaml"),
        ("Score", "0 to 100"), ("Dashboard", "charts and bad rows")]
for i, (col, (title, sub)) in enumerate(zip(st.columns(5, gap="small"), flow), 1):
    col.markdown(f'<div class="step">{i}. {title}<small>{sub}</small></div>', unsafe_allow_html=True)

# ---------- resources ----------
st.markdown('<h2 class="h2">Resources</h2>', unsafe_allow_html=True)
res = [
    ("Source code", "Python, Pandas, SQLAlchemy and Streamlit, with 25 tests.", REPO, "Open the repository"),
    ("Documentation", "Architecture diagrams, scoring formula and deploy guide.", f"{REPO}#readme", "Read the README"),
    ("Rules file", "See every rule and score weight the demo uses.", f"{REPO}/blob/main/config/rules.yaml", "View rules.yaml"),
]
for col, (title, text, url, label) in zip(st.columns(3, gap="medium"), res):
    col.markdown(f'<div class="card"><b>{title}</b><span>{text}</span><br><br>'
                 f'<a href="{url}" target="_blank">{label}</a></div>', unsafe_allow_html=True)

# ---------- closing banner ----------
st.markdown("<div style='height:56px'></div>", unsafe_allow_html=True)
with st.container(key="cta"):
    st.markdown("<h2>Ready to explore the data?</h2><p>Open the dashboard to see scores, trends and every failing record.</p>",
                unsafe_allow_html=True)
    if st.button("Open dashboard", type="primary", key="open_bottom"):
        st.switch_page("monitor.py")
