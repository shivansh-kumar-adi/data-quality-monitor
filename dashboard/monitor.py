"""Streamlit dashboard for the Data Quality Monitor.

    streamlit run dashboard/app.py

Reads runs and issues from the database in DATABASE_URL (see .env.example).
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy.exc import SQLAlchemyError

from src.storage import DEFAULT_DB_URL, get_engine, init_db, load_issues, load_runs

load_dotenv(ROOT / ".env")

# One colour per quality dimension, the same in every chart (colour follows the
# entity). Red is deliberately not used: it reads as "bad", and a dimension is not bad.
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
DIM_COLORS = {"completeness": BLUE, "validity": ORANGE, "uniqueness": AQUA, "overall": "#52514e"}

   st.page_link("home.py", label="Back to home")
   st.title("Data Quality Dashboard")

# ---------- connect ----------
db_url = os.getenv("DATABASE_URL", DEFAULT_DB_URL)
if not os.getenv("DQM_PUBLIC"):          # public deploy pe box chhup jata hai
    db_url = st.sidebar.text_input("Database URL", value=db_url, help="Same value as DATABASE_URL in .env")


@st.cache_resource
def _engine(url: str):
    engine = get_engine(url)
    init_db(engine)
    return engine


try:
    engine = _engine(db_url)
    runs = load_runs(engine)
except SQLAlchemyError as exc:
    st.error("Could not connect to the database. Start PostgreSQL with `docker compose up -d`, "
             "or use a SQLite URL such as `sqlite:///dqm.db`.")
    st.caption(str(exc).splitlines()[0])
    st.stop()

if runs.empty:
    st.info("No runs yet. Create one with:\n\n`python -m src.run --file data/customers.csv`")
    st.stop()

# ---------- pick a run ----------
runs = runs.sort_values(["run_at", "run_id"]).reset_index(drop=True)
labels = {
    int(r.run_id): f"Run #{int(r.run_id)}  |  {r.file_name}  |  {pd.to_datetime(r.run_at):%Y-%m-%d %H:%M}"
    for r in runs.itertuples()
}
run_id = st.sidebar.selectbox(
    "Run", options=list(labels)[::-1], format_func=lambda i: labels[i]
)
run = runs[runs.run_id == run_id].iloc[0]
issues = load_issues(engine, int(run_id))

# ---------- scores ----------
def pct(v):
    return "n/a" if pd.isna(v) else f"{v:.1f}%"

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Overall", pct(run.overall))
c2.metric("Completeness", pct(run.completeness))
c3.metric("Validity", pct(run.validity))
c4.metric("Uniqueness", pct(run.uniqueness))
c5.metric("Issues", f"{int(run.issue_count):,}", help=f"{int(run.row_count):,} rows checked")

st.caption(
    "Each score is (values checked - values failing) / values checked. "
    "Overall is the weighted average set in config/rules.yaml."
)

# ---------- defect categories ----------
left, right = st.columns(2)

if issues.empty:
    st.success("No issues found in this run.")
else:
    by_rule = issues.groupby(["rule", "dimension"]).size().reset_index(name="issues").sort_values("issues")
    fig = px.bar(by_rule, x="issues", y="rule", color="dimension", orientation="h", title="Issues by rule",
                 color_discrete_map=DIM_COLORS)
    fig.update_layout(yaxis_title=None, legend_title=None)
    left.plotly_chart(fig, width="stretch")

    by_col = issues.groupby("column_name").size().reset_index(name="issues").sort_values("issues", ascending=False)
    fig = px.bar(by_col, x="column_name", y="issues", title="Issues by column", color_discrete_sequence=[BLUE])
    fig.update_layout(xaxis_title=None)
    right.plotly_chart(fig, width="stretch")

# ---------- trend ----------
st.subheader("Trend across runs")
if len(runs) < 2:
    st.info("Only one run so far. Run the checker again (for example on a new file) to see a trend.")
else:
    trend = runs.melt(
        id_vars=["run_id", "run_at"],
        value_vars=["overall", "completeness", "validity", "uniqueness"],
        var_name="score",
        value_name="value",
    )
    trend["run"] = "#" + trend["run_id"].astype(int).astype(str)  # one tick per run, not per timestamp
    fig = px.line(trend, x="run", y="value", color="score", markers=True, color_discrete_map=DIM_COLORS)
    fig.update_xaxes(type="category")
    fig.update_layout(yaxis_title="score (%)", xaxis_title="run", yaxis_range=[0, 100], legend_title=None)
    st.plotly_chart(fig, width="stretch")

# ---------- affected records ----------
st.subheader("Affected records")
if not issues.empty:
    f1, f2, f3 = st.columns(3)
    rules_pick = f1.multiselect("Rule", sorted(issues.rule.unique()))
    dims_pick = f2.multiselect("Dimension", sorted(issues.dimension.unique()))
    sev_pick = f3.multiselect("Severity", sorted(issues.severity.unique()))

    view = issues
    if rules_pick:
        view = view[view.rule.isin(rules_pick)]
    if dims_pick:
        view = view[view.dimension.isin(dims_pick)]
    if sev_pick:
        view = view[view.severity.isin(sev_pick)]

    st.caption("row_id = line number in the CSV file (header is line 1).")
    st.dataframe(
        view[["row_id", "column_name", "rule", "dimension", "severity", "value", "message"]],
        width="stretch",
        hide_index=True,
    )
    st.download_button(
        "Download these issues as CSV",
        view.to_csv(index=False).encode("utf-8"),
        file_name=f"issues_run_{int(run_id)}.csv",
        mime="text/csv",
    )
