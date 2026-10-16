"""Entry point: check one CSV file and (optionally) save the result.

    python -m src.run --file data/customers.csv
    python -m src.run --file data/customers.csv --no-db          # print only
    python -m src.run --file data/customers.csv --db-url sqlite:///dqm.db
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

from .profiler import profile
from .rules import run_rules
from .scorer import score, stats_from_per_rule
from .storage import get_engine, init_db, save_run

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RULES = ROOT / "config" / "rules.yaml"


def load_config(path: str | Path | None = None) -> dict:
    with open(path or DEFAULT_RULES, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_csv(path: str | Path) -> pd.DataFrame:
    # dtype=str: read everything as text so we judge the raw values.
    # (Otherwise pandas would turn "007" into 7 and hide bad ages in a float column.)
    return pd.read_csv(path, dtype=str)


def analyze(df: pd.DataFrame, config: dict) -> dict:
    """Profile -> rules -> score. Pure function: no files, no database."""
    result = run_rules(df, config["rules"])
    scores = score(stats_from_per_rule(result["per_rule"]), config.get("weights"))
    return {
        "profile": profile(df),
        "issues": result["issues"],
        "per_rule": result["per_rule"],
        "scores": scores,
    }


def _fmt(v) -> str:
    return "n/a" if v is None else f"{v:6.2f}"


def print_report(file_label: str, result: dict) -> None:
    p = result["profile"]
    print(f"\nFile: {file_label}  |  {p['row_count']} rows, {p['column_count']} columns, "
          f"{p['duplicate_rows']} exact duplicate rows")

    print("\nColumns:")
    print(f"  {'name':<14}{'type':<9}{'nulls':>6}{'null%':>8}{'unique':>8}")
    for c in p["columns"]:
        print(f"  {c['name']:<14}{c['type']:<9}{c['nulls']:>6}{c['null_pct']:>8}{c['unique']:>8}")

    print("\nRules (most failures first):")
    print(f"  {'rule':<26}{'dimension':<14}{'checked':>8}{'failed':>8}{'pass%':>8}")
    for r in sorted(result["per_rule"], key=lambda r: -r["failed"]):
        print(f"  {r['rule']:<26}{r['dimension']:<14}{r['checked']:>8}{r['failed']:>8}{_fmt(r['pass_rate']):>8}")

    s = result["scores"]
    print("\nScores (0-100):")
    for k in ("completeness", "validity", "uniqueness"):
        print(f"  {k.upper():<13}{_fmt(s[k])}")
    print(f"  {'OVERALL':<13}{_fmt(s['overall'])}")
    print(f"\n{len(result['issues'])} issues found.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run data-quality checks on a CSV file")
    ap.add_argument("--file", default="data/customers.csv", help="CSV to check")
    ap.add_argument("--rules", default=None, help="rules YAML (default: config/rules.yaml)")
    ap.add_argument("--db-url", default=None, help="override DATABASE_URL")
    ap.add_argument("--no-db", action="store_true", help="print results, do not save")
    args = ap.parse_args(argv)

    try:
        df = load_csv(args.file)
        config = load_config(args.rules)
        result = analyze(df, config)
    except (OSError, ValueError, KeyError, yaml.YAMLError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print_report(args.file, result)

    if not args.no_db:
        try:
            engine = get_engine(args.db_url)
            init_db(engine)
            run_id = save_run(engine, Path(args.file).name, len(df), result["scores"], result["issues"])
        except Exception as exc:  # connection refused, bad URL, ...
            print(f"Error: could not save to the database: {str(exc).splitlines()[0]}\n"
                  "Start PostgreSQL with `docker compose up -d`, or use --db-url sqlite:///dqm.db, "
                  "or pass --no-db.", file=sys.stderr)
            return 1
        print(f"Saved as run #{run_id}. View it: streamlit run dashboard/app.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
