import pandas as pd

from src.profiler import infer_type, profile
from src.scorer import score


# ---------- scorer ----------

def test_dimension_scores():
    stats = {
        "completeness": {"checked": 100, "failed": 10},
        "validity": {"checked": 200, "failed": 20},
        "uniqueness": {"checked": 50, "failed": 0},
    }
    s = score(stats)
    assert s["completeness"] == 90.0
    assert s["validity"] == 90.0
    assert s["uniqueness"] == 100.0


def test_overall_is_weighted_average():
    stats = {
        "completeness": {"checked": 10, "failed": 0},   # 100
        "validity": {"checked": 10, "failed": 5},       # 50
        "uniqueness": {"checked": 10, "failed": 10},    # 0
    }
    # 0.4*100 + 0.4*50 + 0.2*0 = 60
    assert score(stats)["overall"] == 60.0
    # custom weights: only validity counts
    assert score(stats, {"completeness": 0, "validity": 1, "uniqueness": 0})["overall"] == 50.0


def test_dimension_with_no_checks_is_left_out():
    s = score({"completeness": {"checked": 10, "failed": 1}})
    assert s["validity"] is None and s["uniqueness"] is None
    assert s["overall"] == 90.0                          # only completeness contributes


def test_no_checks_at_all():
    assert score({})["overall"] is None


# ---------- profiler ----------

def test_infer_type():
    assert infer_type(pd.Series(["1", "2", "3"])) == "integer"
    assert infer_type(pd.Series(["1.5", "2"])) == "float"
    assert infer_type(pd.Series(["a", "b"])) == "text"
    assert infer_type(pd.Series(["1", "2", "3", "4", "x"])) == "mixed"
    assert infer_type(pd.Series([None, " "])) == "empty"


def test_profile_counts():
    df = pd.DataFrame({"id": ["1", "2", "2"], "name": ["a", None, None]}, dtype=str)
    p = profile(df)
    assert p["row_count"] == 3 and p["column_count"] == 2
    cols = {c["name"]: c for c in p["columns"]}
    assert cols["name"]["nulls"] == 2 and cols["name"]["null_pct"] == 66.67
    assert cols["id"]["unique"] == 2
    assert p["numeric_summary"]["id"]["max"] == 2.0
