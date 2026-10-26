from __future__ import annotations

import argparse
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 20260115


def generate(path: Path, users_count: int = 1200) -> None:
    rng = random.Random(SEED)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    channels = ["organic", "paid_search", "social", "referral", "partner"]
    countries = ["US", "CA", "GB", "DE", "AU"]
    devices = ["mobile", "desktop", "tablet"]
    event_weights = ["app_open", "view_product", "add_to_cart", "checkout_started", "purchase"]
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)

    with sqlite3.connect(path) as db:
        db.execute("PRAGMA foreign_keys = ON")
        db.executescript("""
            CREATE TABLE users (
              user_id INTEGER PRIMARY KEY, signup_date TEXT NOT NULL,
              acquisition_channel TEXT NOT NULL, country TEXT NOT NULL, device_type TEXT NOT NULL
            );
            CREATE TABLE sessions (
              session_id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL,
              session_start TEXT NOT NULL, session_end TEXT NOT NULL,
              FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
            CREATE TABLE events (
              event_id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, event_type TEXT NOT NULL,
              event_timestamp TEXT NOT NULL, session_id INTEGER NOT NULL,
              FOREIGN KEY (user_id) REFERENCES users(user_id), FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            );
            CREATE TABLE orders (
              order_id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, order_timestamp TEXT NOT NULL,
              revenue REAL NOT NULL CHECK (revenue >= 0), FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
            CREATE TABLE experiments (
              experiment_id INTEGER PRIMARY KEY, experiment_name TEXT NOT NULL,
              start_date TEXT NOT NULL, end_date TEXT NOT NULL
            );
            CREATE TABLE experiment_assignments (
              experiment_id INTEGER NOT NULL, user_id INTEGER NOT NULL, variant TEXT NOT NULL,
              assigned_at TEXT NOT NULL, PRIMARY KEY (experiment_id, user_id),
              FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id), FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
            CREATE INDEX idx_events_user_time ON events(user_id, event_timestamp);
            CREATE INDEX idx_events_time_type ON events(event_timestamp, event_type);
            CREATE INDEX idx_orders_user_time ON orders(user_id, order_timestamp);
        """)
        db.execute("INSERT INTO experiments VALUES (1, 'Streamlined onboarding', '2026-01-15', '2026-03-15')")
        session_id = event_id = order_id = 1
        for user_id in range(1, users_count + 1):
            signup = start + timedelta(days=rng.randrange(0, 90), hours=rng.randrange(0, 24))
            channel = rng.choices(channels, weights=[34, 25, 18, 15, 8])[0]
            country = rng.choices(countries, weights=[46, 14, 15, 13, 12])[0]
            device = rng.choices(devices, weights=[62, 32, 6])[0]
            db.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)", (user_id, signup.date().isoformat(), channel, country, device))
            variant = 'unassigned'
            if datetime(2026, 1, 15, tzinfo=timezone.utc) <= signup <= datetime(2026, 3, 15, tzinfo=timezone.utc):
                variant = "treatment" if rng.random() < 0.5 else "control"
                db.execute("INSERT INTO experiment_assignments VALUES (1, ?, ?, ?)", (user_id, variant, signup.isoformat()))
            visits = min(24, 1 + int(rng.expovariate(0.23)))
            for visit in range(visits):
                when = signup + timedelta(days=visit * rng.uniform(0.6, 4.2), hours=rng.uniform(0, 12))
                if when > start + timedelta(days=119):
                    break
                duration = max(45, int(rng.lognormvariate(5.1, 0.65)))
                db.execute("INSERT INTO sessions VALUES (?, ?, ?, ?)", (session_id, user_id, when.isoformat(), (when + timedelta(seconds=duration)).isoformat()))
                weights = [8, 25, 28, 22, 17] if variant == 'treatment' else [12, 32, 28, 18, 10]
                depth = rng.choices([1, 2, 3, 4, 5], weights=weights)[0]
                for offset, event_type in enumerate(event_weights[:depth]):
                    event_time = when + timedelta(seconds=offset * rng.randint(25, 100))
                    db.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?)", (event_id, user_id, event_type, event_time.isoformat(), session_id))
                    event_id += 1
                    if event_type == "purchase":
                        revenue = round(max(5, rng.lognormvariate(3.6, 0.55)), 2)
                        db.execute("INSERT INTO orders VALUES (?, ?, ?, ?)", (order_id, user_id, event_time.isoformat(), revenue))
                        order_id += 1
                session_id += 1
        db.commit()
    print(f"Generated {users_count:,} users at {path.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate VEYRA's reproducible SQLite demo dataset")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "datasets" / "veyra.db")
    parser.add_argument("--users", type=int, default=1200)
    args = parser.parse_args()
    if not 10 <= args.users <= 100_000:
        parser.error("--users must be between 10 and 100000")
    generate(args.output, args.users)


if __name__ == "__main__":
    main()

