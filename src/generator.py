"""Synthetic customer data generator.

Creates a CSV of fake customers and then deliberately injects data-quality
problems (missing values, bad formats, duplicates, impossible dates) so the
Data Quality Monitor has something real to catch.

Usage:
    python -m src.generator --rows 1000 --seed 42 --out data/customers.csv
"""
import argparse
import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from faker import Faker


def make_clean_customers(n: int, fake: Faker) -> pd.DataFrame:
    """Step 1: build n perfectly valid customer rows."""
    rows = []
    for i in range(1, n + 1):
        rows.append(
            {
                "customer_id": i,
                "name": fake.name(),
                "email": fake.unique.email(),
                # Indian-style 10 digit mobile starting 6-9
                "phone": str(random.choice("6789")) + "".join(random.choices("0123456789", k=9)),
                "signup_date": fake.date_between(start_date="-3y", end_date="today").isoformat(),
                "age": random.randint(18, 80),
                "country": random.choice(["IN", "US", "UK", "DE", "SG"]),
            }
        )
    return pd.DataFrame(rows)


def inject_problems(df: pd.DataFrame, rate: float = 0.05) -> pd.DataFrame:
    """Step 2: corrupt ~rate of rows per problem type.

    Each block below = one rule your monitor should later detect.
    """
    df = df.copy()
    n = len(df)
    k = max(1, int(n * rate))

    def pick(count):
        return random.sample(range(n), count)

    # Missing required fields (completeness)
    for idx in pick(k):
        df.loc[idx, "email"] = None
    for idx in pick(k):
        df.loc[idx, "name"] = None

    # Bad email format (validity)
    for idx in pick(k):
        df.loc[idx, "email"] = random.choice(["not-an-email", "user@", "@domain.com", "a b@c.com"])

    # Bad phone format (validity)
    for idx in pick(k):
        df.loc[idx, "phone"] = random.choice(["12345", "abcdefghij", "+91-98", "00000000000000"])

    # Bad date format (validity)
    for idx in pick(k):
        df.loc[idx, "signup_date"] = random.choice(["31/02/2024", "yesterday", "2024-13-45", ""])

    # Future signup date (cross-field / business rule)
    for idx in pick(k):
        df.loc[idx, "signup_date"] = (date.today() + timedelta(days=random.randint(30, 400))).isoformat()

    # Impossible age (business rule)
    for idx in pick(k):
        df.loc[idx, "age"] = random.choice([-5, 0, 150, 999])

    # Duplicate primary keys (uniqueness)
    for idx in pick(max(1, k // 2)):
        df.loc[idx, "customer_id"] = df.loc[random.randrange(n), "customer_id"]

    # Exact duplicate rows (uniqueness)
    dupes = df.sample(max(1, k // 2), random_state=1)
    df = pd.concat([df, dupes], ignore_index=True)

    return df.sample(frac=1, random_state=7).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate messy synthetic customers")
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42, help="same seed = same file")
    parser.add_argument("--rate", type=float, default=0.05, help="fraction corrupted per problem type")
    parser.add_argument("--out", type=str, default="data/customers.csv")
    args = parser.parse_args()

    random.seed(args.seed)
    fake = Faker("en_IN")
    Faker.seed(args.seed)

    clean = make_clean_customers(args.rows, fake)
    messy = inject_problems(clean, args.rate)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    messy.to_csv(out, index=False)
    print(f"Wrote {len(messy)} rows to {out}")


if __name__ == "__main__":
    main()
