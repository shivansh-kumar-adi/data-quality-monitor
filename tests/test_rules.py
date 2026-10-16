import pandas as pd
import pytest

from src.rules import run_rules


def frame(**cols):
    return pd.DataFrame(cols, dtype=str)


def one(df, rule):
    """Run a single rule, return (issues, checked, failed)."""
    result = run_rules(df, [rule])
    r = result["per_rule"][0]
    return result["issues"], r["checked"], r["failed"]


def test_required_flags_nan_and_whitespace():
    df = frame(name=["Asha", None, "  ", "Ravi"])
    issues, checked, failed = one(df, {"name": "req", "type": "required", "columns": ["name"]})
    assert failed == 2 and checked == 4
    assert [i["row_id"] for i in issues] == [3, 4]          # CSV line numbers (header = 1)
    assert issues[0]["dimension"] == "completeness"


def test_regex_skips_blanks_and_flags_bad_values():
    df = frame(email=["a@b.com", "not-an-email", None, "x@y"])
    rule = {"name": "email", "type": "regex", "column": "email", "pattern": r"[^@\s]+@[^@\s]+\.[^@\s]+"}
    issues, checked, failed = one(df, rule)
    assert checked == 3                                       # the blank is not checked here
    assert failed == 2
    assert {i["value"] for i in issues} == {"not-an-email", "x@y"}


def test_regex_requires_full_match():
    df = frame(phone=["9876543210", "98765432101", "598765432"])
    rule = {"name": "phone", "type": "regex", "column": "phone", "pattern": r"[6-9]\d{9}"}
    _, _, failed = one(df, rule)
    assert failed == 2                                        # too long, and wrong first digit


def test_date_format_rejects_impossible_dates():
    df = frame(d=["2024-02-29", "2024-02-30", "31/02/2024", "2024-13-45", "yesterday"])
    rule = {"name": "d", "type": "date_format", "column": "d", "format": "%Y-%m-%d"}
    _, checked, failed = one(df, rule)
    assert checked == 5 and failed == 4


def test_not_future_uses_given_today_and_ignores_unparseable():
    df = frame(d=["2024-01-01", "2030-01-01", "garbage"])
    rule = {"name": "f", "type": "not_future", "column": "d", "today": "2025-06-01"}
    issues, checked, failed = one(df, rule)
    assert checked == 2                                       # "garbage" belongs to date_format
    assert failed == 1 and issues[0]["value"] == "2030-01-01"


def test_range_flags_out_of_range_and_non_numeric():
    df = frame(age=["17", "18", "80", "81", "abc", None])
    rule = {"name": "age", "type": "range", "column": "age", "min": 18, "max": 80}
    issues, checked, failed = one(df, rule)
    assert checked == 5
    assert {i["value"] for i in issues} == {"17", "81", "abc"}


def test_allowed_values():
    df = frame(country=["IN", "US", "XX", None])
    rule = {"name": "c", "type": "allowed_values", "column": "country", "values": ["IN", "US"]}
    issues, checked, failed = one(df, rule)
    assert checked == 3 and failed == 1 and issues[0]["value"] == "XX"


def test_unique_key_flags_later_copies_only():
    df = frame(id=["1", "2", "1", "1", None, None])
    issues, checked, failed = one(df, {"name": "pk", "type": "unique_key", "column": "id"})
    assert failed == 2                                        # 2nd and 3rd copy of "1"
    assert [i["row_id"] for i in issues] == [4, 5]
    assert checked == 4                                       # blank keys are not counted


def test_exact_duplicates():
    df = frame(a=["1", "1", "2"], b=["x", "x", "x"])
    issues, checked, failed = one(df, {"name": "dup", "type": "exact_duplicates"})
    assert checked == 3 and failed == 1 and issues[0]["row_id"] == 3


def test_severity_and_custom_message_are_carried_through():
    df = frame(c=["bad"])
    rule = {"name": "r", "type": "allowed_values", "column": "c", "values": ["ok"],
            "severity": "high", "message": "custom text"}
    issues, _, _ = one(df, rule)
    assert issues[0]["severity"] == "high" and issues[0]["message"] == "custom text"


def test_unknown_column_gives_clear_error():
    with pytest.raises(ValueError, match="refers to column 'nope'"):
        run_rules(frame(a=["1"]), [{"name": "x", "type": "regex", "column": "nope", "pattern": "."}])


def test_unknown_rule_type_gives_clear_error():
    with pytest.raises(ValueError, match="unknown type"):
        run_rules(frame(a=["1"]), [{"name": "x", "type": "magic"}])
