"""Storage: save and read quality runs with SQLAlchemy.

Two tables
----------
runs    one row per file checked (scores, row count, issue count, timestamp)
issues  one row per bad cell/row (row_id, column, rule, value, ...)

Which database? Set DATABASE_URL in your environment or a .env file.
Default is the PostgreSQL started by docker-compose.yml. SQLite also works
(e.g. DATABASE_URL=sqlite:///dqm.db) because SQLAlchemy hides the difference.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import (
    Column, DateTime, Float, ForeignKey, Integer, MetaData, String, Table, Text,
    create_engine, insert, select,
)
from sqlalchemy.engine import Engine

load_dotenv()

DEFAULT_DB_URL = "postgresql+psycopg2://dqm:dqm_password@localhost:5432/dqm"

metadata = MetaData()

runs = Table(
    "runs", metadata,
    Column("run_id", Integer, primary_key=True, autoincrement=True),
    Column("file_name", String(255), nullable=False),
    Column("run_at", DateTime(timezone=True), nullable=False),
    Column("row_count", Integer, nullable=False),
    Column("completeness", Float),
    Column("validity", Float),
    Column("uniqueness", Float),
    Column("overall", Float),
    Column("issue_count", Integer, nullable=False),
)

issues = Table(
    "issues", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("run_id", Integer, ForeignKey("runs.run_id"), nullable=False, index=True),
    Column("row_id", Integer, nullable=False),
    Column("column_name", String(100)),
    Column("rule", String(100), nullable=False),
    Column("dimension", String(30), nullable=False),
    Column("severity", String(20), nullable=False),
    Column("message", Text),
    Column("value", Text),
)

ISSUE_FIELDS = ["row_id", "column_name", "rule", "dimension", "severity", "message", "value"]


def get_engine(url: str | None = None) -> Engine:
    return create_engine(url or os.getenv("DATABASE_URL", DEFAULT_DB_URL), future=True)


def init_db(engine: Engine) -> None:
    """Create the tables if they do not exist yet (safe to call on every run)."""
    metadata.create_all(engine)


def save_run(engine: Engine, file_name: str, row_count: int, scores: dict, issue_list: list[dict]) -> int:
    """Save one run and all its issues in a single transaction; return run_id."""
    with engine.begin() as conn:  # commits on success, rolls back on any error
        run_id = conn.execute(
            insert(runs).values(
                file_name=file_name,
                run_at=datetime.now(timezone.utc),
                row_count=row_count,
                completeness=scores.get("completeness"),
                validity=scores.get("validity"),
                uniqueness=scores.get("uniqueness"),
                overall=scores.get("overall"),
                issue_count=len(issue_list),
            )
        ).inserted_primary_key[0]

        if issue_list:
            conn.execute(
                insert(issues),
                [{**{k: i.get(k) for k in ISSUE_FIELDS}, "run_id": run_id} for i in issue_list],
            )
    return int(run_id)


def load_runs(engine: Engine) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(select(runs).order_by(runs.c.run_id), conn)


def load_issues(engine: Engine, run_id: int) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(
            select(issues).where(issues.c.run_id == run_id).order_by(issues.c.row_id, issues.c.rule), conn
        )
