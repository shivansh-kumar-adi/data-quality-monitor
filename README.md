# Data Quality Monitor

A Python tool that checks a customer CSV for data-quality problems (missing values, bad formats, impossible dates and ages, duplicates), scores the file from 0 to 100, stores every run in PostgreSQL, and shows the results on a dashboard.

![Dashboard](docs/dashboard.png)

## Problem

Companies receive customer data from many sources and it is rarely clean. Bad data means wrong reports, bounced emails and duplicate customers. This project answers three questions: *how healthy is this file, what exactly is wrong (and on which line), and is quality getting better or worse over time?*

**Intended user:** a data analyst or data steward who needs a repeatable quality check instead of a one-off script.

## How it works

```
CSV --> load as text --> Profiler --> Rules engine --> Scorer --> PostgreSQL --> Streamlit dashboard
                         (facts)     (rules.yaml)      (0-100)    (runs+issues)
```

| Step | File | What it does |
|---|---|---|
| Generate | `src/generator.py` | Builds fake customers and injects known problems |
| Load | `src/run.py` | Reads the CSV **as text**, so `007` stays `007` and a bad age stays visible |
| Profile | `src/profiler.py` | Row count, per-column type guess, nulls, unique counts, numeric min/max/mean |
| Check | `src/rules.py` | Runs each rule in `config/rules.yaml`; returns one issue per bad cell/row |
| Score | `src/scorer.py` | Turns pass/fail counts into dimension scores and a weighted overall score |
| Save | `src/storage.py` | Writes the run and its issues to the database (SQLAlchemy) |
| View | `dashboard/app.py` | Scores, issues by rule/column, trend across runs, filterable bad rows |

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env                   # Windows: copy .env.example .env
docker compose up -d                   # starts PostgreSQL

python -m src.generator --rows 1000    # creates data/customers.csv
python -m src.run --file data/customers.csv
streamlit run dashboard/app.py
```

**No Docker?** Use a local SQLite file instead. Everything works the same:

```bash
python -m src.run --file data/customers.csv --db-url sqlite:///dqm.db
```

and set `DATABASE_URL=sqlite:///dqm.db` in `.env` (or paste it in the dashboard sidebar). To only print the report without saving, add `--no-db`.

Run it on a second, messier file to see the trend chart move:

```bash
python -m src.generator --rows 1000 --seed 7 --rate 0.12 --out data/customers_messy.csv
python -m src.run --file data/customers_messy.csv
```

## Rules

Rules live in `config/rules.yaml`. Add or change one and re-run; no Python needed.

| Type | Dimension | Fails when | Options |
|---|---|---|---|
| `required` | completeness | value is empty or only spaces | `columns` (list) |
| `regex` | validity | value does not match the **whole** pattern | `column`, `pattern` |
| `date_format` | validity | value is not a real date (`2024-02-30` fails) | `column`, `format` |
| `not_future` | validity | date is after today | `column`, `format`, optional `today` |
| `range` | validity | number is outside min/max, or not a number | `column`, `min`, `max` |
| `allowed_values` | validity | value is not in the list | `column`, `values` |
| `unique_key` | uniqueness | value already appeared on an earlier row | `column` |
| `exact_duplicates` | uniqueness | row is identical to an earlier row | none |

Every rule also takes `name`, `severity` (high / medium / low) and an optional custom `message`.

Two conventions to know:
- **Validity rules skip empty values.** A missing email is a completeness problem, so it is not also counted as an invalid email.
- **`row_id` is the line number in the CSV** (header is line 1). Open the file, jump to that line, see the problem.

For duplicates, the *first* occurrence is kept and the later copies are flagged.

## Scoring

- **Dimension score** = (values checked - values failing) / values checked x 100, summed over all rules in that dimension.
- **Overall** = weighted average of the three dimensions. Default weights: completeness 0.4, validity 0.4, uniqueness 0.2 (set in `rules.yaml`; they are normalised, so they need not add up to 1).
- A dimension with no rules is left out and the remaining weights are re-normalised.

Example on the bundled sample (1,025 rows, 430 issues): completeness 96.39, validity 95.96, uniqueness 96.34, overall 96.21.

## Database

Two tables, created automatically on the first run:

- `runs`: `run_id`, `file_name`, `run_at`, `row_count`, `completeness`, `validity`, `uniqueness`, `overall`, `issue_count`
- `issues`: `run_id`, `row_id`, `column_name`, `rule`, `dimension`, `severity`, `value`, `message`

A run and all its issues are saved in one transaction, so you never get a run without its issues.

Useful queries:

```sql
-- quality over time
SELECT run_id, file_name, overall FROM runs ORDER BY run_id;

-- worst rules in the latest run
SELECT rule, COUNT(*) FROM issues
WHERE run_id = (SELECT MAX(run_id) FROM runs)
GROUP BY rule ORDER BY 2 DESC;
```

The credentials in `docker-compose.yml` and `.env.example` are for local development only.

## Sample data

All data is synthetic (Faker). The generator corrupts about 5% of rows per problem type so the rules have something to find; `--seed` makes the file reproducible.

| Column | Meaning | Valid |
|---|---|---|
| customer_id | primary key | unique, present |
| name, email | customer details | present; email must look like an email |
| phone | mobile number | 10 digits starting 6-9 |
| signup_date | signup date | `YYYY-MM-DD`, real date, not in the future |
| age | years | 18-80 |
| country | country code | IN, US, UK, DE, SG |

## Tests

```bash
pytest
```

25 tests cover every rule type (including edge cases such as whitespace-only values, `2024-02-30`, and the first-copy-is-kept duplicate rule), the scorer, the profiler, and the full pipeline from generator to database. They use SQLite, so no Docker is needed.

## Project structure

```
data-quality-monitor/
├── config/rules.yaml        # rules and score weights
├── src/
│   ├── generator.py         # synthetic data with injected problems
│   ├── profiler.py
│   ├── rules.py
│   ├── scorer.py
│   ├── storage.py
│   └── run.py               # command-line entry point
├── dashboard/app.py         # Streamlit dashboard
├── tests/
├── docs/dashboard.png
├── docker-compose.yml       # PostgreSQL 16
├── .env.example
├── pytest.ini
├── requirements.txt
└── README.md
```

## Reading the code (suggested order)

1. `config/rules.yaml`, to see what is being checked.
2. `src/rules.py`: each rule type is one small function; `run_rules` ties them together.
3. `src/scorer.py`: about 40 lines; the scoring formula in code.
4. `src/run.py`: how the pieces connect (`analyze` is the whole pipeline without files or DB).
5. `src/storage.py` and `dashboard/app.py`.
6. `tests/test_rules.py`: each test is a one-line statement of what a rule should do.

## Known limitations

- Synthetic data only; real data has messier patterns.
- Phone validation assumes 10-digit Indian mobile numbers.
- No fuzzy duplicate detection ("Jon Smith" vs "John Smith"), only exact matches.
- A run is not tied to a dataset identity: the trend chart compares all runs, so run the same dataset repeatedly if you want a like-for-like trend.
- The dashboard reads the database; it does not run checks itself.

## Ideas to extend

Add a rule type (write one function and register it in `CHECKERS` in `src/rules.py`), per-rule pass-rate history, a `--fail-under 90` flag so a CI job can fail on bad data, or fuzzy duplicate detection with `rapidfuzz`.
