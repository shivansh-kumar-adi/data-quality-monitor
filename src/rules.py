"""Rules engine.

A rule is a small dict (from config/rules.yaml). Each rule *type* is one small
checker function that returns:

    checked : how many values (or rows) the rule looked at
    bad     : list of (column, boolean Series) - True marks a failing row

`run_rules` runs every rule and returns

    {"issues":   [one dict per bad cell/row],
     "per_rule": [one dict per rule: checked, failed, pass_rate, ...]}

Conventions
-----------
* Validity rules skip empty values. Emptiness is the *completeness* rule's job,
  so one missing email is not also counted as an invalid email.
* row_id is the line number in the CSV file (header = line 1, first data row =
  line 2), so you can open the file and jump straight to the problem.
* The data is expected as text (see run.load_csv): we judge the raw values.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

# rule type -> quality dimension
DIMENSIONS = {
    "required": "completeness",
    "regex": "validity",
    "date_format": "validity",
    "not_future": "validity",
    "range": "validity",
    "allowed_values": "validity",
    "unique_key": "uniqueness",
    "exact_duplicates": "uniqueness",
}

DEFAULT_MESSAGES = {
    "required": "value is missing",
    "regex": "value does not match the expected format",
    "date_format": "value is not a valid date",
    "not_future": "date is in the future",
    "range": "value is outside the allowed range or not a number",
    "allowed_values": "value is not in the allowed list",
    "unique_key": "value is duplicated (an earlier row has the same value)",
    "exact_duplicates": "row is an exact duplicate of an earlier row",
}


def _blank(s: pd.Series) -> pd.Series:
    """True where a value is missing or only whitespace."""
    return s.isna() | s.astype(str).str.strip().eq("")


def _columns(rule: dict) -> list[str]:
    cols = rule.get("columns") or ([rule["column"]] if rule.get("column") else [])
    return list(cols)


# ---------------------------------------------------------------- checkers
def check_required(df, rule):
    cols = _columns(rule)
    return len(df) * len(cols), [(c, _blank(df[c])) for c in cols]


def check_regex(df, rule):
    col = rule["column"]
    present = ~_blank(df[col])
    ok = df[col].astype(str).str.fullmatch(rule["pattern"])
    return int(present.sum()), [(col, present & ~ok.fillna(False))]


def _dates(s: pd.Series, fmt: str) -> pd.Series:
    return pd.to_datetime(s, format=fmt, errors="coerce")


def check_date_format(df, rule):
    col = rule["column"]
    present = ~_blank(df[col])
    parsed = _dates(df[col], rule.get("format", "%Y-%m-%d"))
    return int(present.sum()), [(col, present & parsed.isna())]


def check_not_future(df, rule):
    col = rule["column"]
    parsed = _dates(df[col], rule.get("format", "%Y-%m-%d"))
    valid = parsed.notna()  # unparseable dates are date_format's problem
    today = pd.Timestamp(str(rule["today"])).date() if rule.get("today") else date.today()
    return int(valid.sum()), [(col, valid & (parsed.dt.date > today))]


def check_range(df, rule):
    col = rule["column"]
    present = ~_blank(df[col])
    nums = pd.to_numeric(df[col], errors="coerce")
    out = pd.Series(False, index=df.index)
    if "min" in rule:
        out |= nums < rule["min"]
    if "max" in rule:
        out |= nums > rule["max"]
    return int(present.sum()), [(col, present & (nums.isna() | out))]  # non-numeric fails too


def check_allowed_values(df, rule):
    col = rule["column"]
    present = ~_blank(df[col])
    allowed = [str(v) for v in rule["values"]]
    return int(present.sum()), [(col, present & ~df[col].astype(str).isin(allowed))]


def check_unique_key(df, rule):
    """Flags the 2nd, 3rd... copy of a repeated value; the first copy is kept."""
    col = rule["column"]
    present = ~_blank(df[col])
    return int(present.sum()), [(col, present & df[col].duplicated(keep="first"))]


def check_exact_duplicates(df, rule):
    """Flags extra copies of a row that is identical in every column."""
    return len(df), [(None, df.duplicated(keep="first"))]


CHECKERS = {
    "required": check_required,
    "regex": check_regex,
    "date_format": check_date_format,
    "not_future": check_not_future,
    "range": check_range,
    "allowed_values": check_allowed_values,
    "unique_key": check_unique_key,
    "exact_duplicates": check_exact_duplicates,
}


# ------------------------------------------------------------------ engine
def validate_rules(df: pd.DataFrame, rules: list[dict]) -> None:
    """Fail early, with a readable message, if the rule config is wrong."""
    names = set()
    for rule in rules:
        name = rule.get("name")
        if not name:
            raise ValueError(f"Every rule needs a 'name': {rule}")
        if name in names:
            raise ValueError(f"Duplicate rule name '{name}'")
        names.add(name)
        if rule.get("type") not in CHECKERS:
            raise ValueError(
                f"Rule '{name}' has unknown type '{rule.get('type')}'. Known types: {sorted(CHECKERS)}"
            )
        for c in _columns(rule):
            if c not in df.columns:
                raise ValueError(
                    f"Rule '{name}' refers to column '{c}', which is not in the data. "
                    f"Columns found: {list(df.columns)}"
                )


def run_rules(df: pd.DataFrame, rules: list[dict]) -> dict:
    validate_rules(df, rules)
    issues: list[dict] = []
    per_rule: list[dict] = []

    for rule in rules:
        rtype = rule["type"]
        dimension = DIMENSIONS[rtype]
        severity = rule.get("severity", "medium")
        message = rule.get("message", DEFAULT_MESSAGES[rtype])

        checked, bad = CHECKERS[rtype](df, rule)
        failed = 0
        for col, mask in bad:
            for idx in df.index[mask.fillna(False).astype(bool)]:
                raw = df.at[idx, col] if col else ""
                issues.append(
                    {
                        "row_id": int(idx) + 2,  # CSV line number (header is line 1)
                        "column_name": col,
                        "rule": rule["name"],
                        "dimension": dimension,
                        "severity": severity,
                        "value": "" if pd.isna(raw) else str(raw),
                        "message": message,
                    }
                )
                failed += 1

        per_rule.append(
            {
                "rule": rule["name"],
                "type": rtype,
                "dimension": dimension,
                "severity": severity,
                "checked": int(checked),
                "failed": failed,
                "pass_rate": round(100 * (checked - failed) / checked, 2) if checked else None,
            }
        )

    issues.sort(key=lambda i: (i["row_id"], i["rule"]))
    return {"issues": issues, "per_rule": per_rule}
