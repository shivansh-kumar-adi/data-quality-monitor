"""End-to-end tests: generator -> analyze -> storage (SQLite, no Docker needed)."""
import random

import pytest
from faker import Faker

from src.generator import inject_problems, make_clean_customers
from src.run import analyze, load_config, load_csv, main
from src.storage import get_engine, init_db, load_issues, load_runs, save_run


@pytest.fixture(scope="module")
def config():
    return load_config()


def _clean(n=200, seed=1):
    random.seed(seed)
    Faker.seed(seed)
    return make_clean_customers(n, Faker("en_IN"))


def test_clean_data_scores_100(config):
    df = _clean().astype(str)
    result = analyze(df, config)
    assert result["issues"] == []
    assert result["scores"]["overall"] == 100.0


def test_messy_data_is_caught(config):
    random.seed(3)
    messy = inject_problems(_clean(), rate=0.05).astype(str).replace("None", None)
    result = analyze(messy, config)
    failed = {r["rule"]: r["failed"] for r in result["per_rule"]}
    # every injected problem type must be detected by its rule
    for rule in ["required_fields", "email_format", "phone_format", "signup_date_format",
                 "signup_date_not_future", "age_range", "customer_id_unique", "exact_duplicate_rows"]:
        assert failed[rule] > 0, rule
    assert result["scores"]["overall"] < 100


def test_same_input_gives_same_result(config):
    df = _clean().astype(str)
    assert analyze(df, config)["scores"] == analyze(df.copy(), config)["scores"]


def test_storage_roundtrip(tmp_path, config):
    engine = get_engine(f"sqlite:///{tmp_path / 'test.db'}")
    init_db(engine)
    random.seed(5)
    messy = inject_problems(_clean(), rate=0.05).astype(str).replace("None", None)
    result = analyze(messy, config)

    run_id = save_run(engine, "x.csv", len(messy), result["scores"], result["issues"])

    runs = load_runs(engine)
    assert len(runs) == 1 and runs.iloc[0].run_id == run_id
    assert runs.iloc[0].issue_count == len(result["issues"])
    assert runs.iloc[0].overall == result["scores"]["overall"]
    assert len(load_issues(engine, run_id)) == len(result["issues"])


def test_cli_end_to_end(tmp_path, capsys):
    csv = tmp_path / "c.csv"
    csv.write_text("customer_id,name,email,phone,signup_date,age,country\n"
                   "1,Asha,a@b.com,9876543210,2024-01-01,30,IN\n"
                   "1,,bad,123,2999-01-01,5,XX\n")
    db = f"sqlite:///{tmp_path / 'cli.db'}"
    assert main(["--file", str(csv), "--db-url", db]) == 0
    out = capsys.readouterr().out
    assert "OVERALL" in out and "Saved as run #1" in out
    assert len(load_runs(get_engine(db))) == 1


def test_cli_missing_file_is_a_clean_error(capsys):
    assert main(["--file", "nope.csv", "--no-db"]) == 1
    assert "Error" in capsys.readouterr().err


def test_load_csv_keeps_leading_zeros(tmp_path):
    p = tmp_path / "z.csv"
    p.write_text("id\n007\n")
    assert load_csv(p).iloc[0, 0] == "007"
