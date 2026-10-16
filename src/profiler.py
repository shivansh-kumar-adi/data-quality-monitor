"""Profiler: a quick factual summary of a DataFrame.

The profiler does NOT judge quality (that is the rules engine's job). It only
describes the data: how many rows, what each column looks like, how many
values are missing. Data is expected as text (see run.load_csv).
"""
from __future__ import annotations

import pandas as pd


def _blank(s: pd.Series) -> pd.Series:
    return s.isna() | s.astype(str).str.strip().eq("")


def infer_type(s: pd.Series) -> str:
    """Guess a column's type from its non-blank values.

    integer / float : every value is a number
    text            : no value is a number
    mixed           : some are numbers, some are not (often a data problem)
    empty           : nothing but blanks
    """
    values = s[~_blank(s)]
    if values.empty:
        return "empty"
    nums = pd.to_numeric(values, errors="coerce")
    n_num = int(nums.notna().sum())
    if n_num == 0:
        return "text"
    if n_num < len(values):
        return "mixed"
    return "integer" if bool((nums % 1 == 0).all()) and not values.astype(str).str.contains(r"[.eE]").any() else "float"


def profile(df: pd.DataFrame) -> dict:
    n = len(df)
    columns = []
    numeric_summary = {}

    for col in df.columns:
        s = df[col]
        blank = _blank(s)
        values = s[~blank]
        ctype = infer_type(s)
        nulls = int(blank.sum())
        columns.append(
            {
                "name": col,
                "type": ctype,
                "nulls": nulls,
                "null_pct": round(100 * nulls / n, 2) if n else 0.0,
                "unique": int(values.nunique()),
                "examples": values.astype(str).head(3).tolist(),
            }
        )
        if ctype in ("integer", "float", "mixed"):
            nums = pd.to_numeric(values, errors="coerce").dropna()
            if len(nums):
                numeric_summary[col] = {
                    "min": float(nums.min()),
                    "max": float(nums.max()),
                    "mean": round(float(nums.mean()), 2),
                }

    return {
        "row_count": n,
        "column_count": len(df.columns),
        "duplicate_rows": int(df.duplicated().sum()),
        "columns": columns,
        "numeric_summary": numeric_summary,
    }
