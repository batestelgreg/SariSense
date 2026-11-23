"""
Seed a demo store so the instructor can test SariSense immediately.

Run from the backend folder AFTER running schema.sql in Supabase:

    python -m ml.seed_demo

Creates:
    store  : "Sari-Sari ni Aling Nena" (demo)
    login  : demo@sarisen.app  /  demo1234
    products: 12 common sari-sari items
    sales  : ~12 months of realistic daily sales
"""
import random
from datetime import date, timedelta

from dotenv import load_dotenv

load_dotenv()

from auth import hash_password
from db import db_cursor
from psycopg2.extras import execute_values

DEMO_EMAIL = "demo@sarisen.app"
DEMO_PASSWORD = "demo1234"

PRODUCTS = [
    # name, category, cost, sell, stock, lead_time, base_demand
    ("Coca-Cola 1.5L", "Beverages", 58.00, 72.00, 24, 3, 6.0),
    ("Lucky Me Pancit Canton", "Noodles", 12.50, 17.00, 60, 2, 14.0),
    ("Kopiko 3-in-1", "Beverages", 6.50, 9.00, 80, 2, 18.0),
    ("Skyflakes Crackers", "Snacks", 6.00, 9.00, 45, 3, 8.0),
    ("Piattos Cheese", "Snacks", 15.00, 20.00, 30, 3, 7.0),
    ("Safeguard Soap", "Household", 32.00, 42.00, 18, 5, 3.0),
    ("Tide Bar 380g", "Household", 28.00, 38.00, 15, 5, 2.5),
    ("Egg (per piece)", "Fresh", 7.50, 9.00, 90, 2, 22.0),
    ("Bear Brand 320ml", "Beverages", 27.00, 34.00, 36, 3, 5.0),
    ("Rice 1kg", "Staples", 48.00, 58.00, 40, 4, 9.0),
    ("Cooking Oil 250ml", "Staples", 38.00, 48.00, 20, 4, 2.0),
    ("Chippy BBQ", "Snacks", 13.00, 17.00, 35, 3, 6.5),
]


def seasonal_demand(base: float, day: date, rng: random.Random) -> int:
    v = base
    if day.weekday() >= 5:
        v *= 1.30
    if day.day in (15, 30, 31):
        v *= 1.50
    if day.month == 12:
        v *= 1.20
    v += rng.gauss(0, max(0.5, base * 0.22))
    return max(0, int(round(v)))


def main() -> None:
    rng = random.Random(2026)
    today = date.today()
    start = today - timedelta(days=365)

    with db_cursor(commit=True) as cur:
        cur.execute("select id from users where lower(email) = lower(%s)", (DEMO_EMAIL,))
        existing = cur.fetchone()
        if existing:
            print(f"Demo user already exists ({DEMO_EMAIL}). Nothing to do.")
            return

        cur.execute(
            "insert into stores (name, owner_name, language) values (%s,%s,%s) returning id",
            ("Sari-Sari ni Aling Nena (Demo)", "Aling Nena", "ceb"),
        )
        store_id = cur.fetchone()["id"]

        cur.execute(
            "insert into users (store_id, email, password_hash) values (%s,%s,%s)",
            (store_id, DEMO_EMAIL, hash_password(DEMO_PASSWORD)),
        )

        rows = []
        for name, category, cost, sell, stock, lead, base in PRODUCTS:
            cur.execute(
                """insert into products
                   (store_id, name, category, cost_price, sell_price, stock, lead_time_days)
                   values (%s,%s,%s,%s,%s,%s,%s) returning id""",
                (store_id, name, category, cost, sell, stock, lead),
            )
            pid = cur.fetchone()["id"]

            day = start
            while day <= today:
                qty = seasonal_demand(base, day, rng)
                if qty:
                    rows.append((store_id, pid, qty, sell, day))
                day += timedelta(days=1)

        execute_values(
            cur,
            """insert into sales (store_id, product_id, quantity, unit_price, sold_at)
               values %s""",
            rows,
            page_size=2000,
        )

    print(f"Demo store created: {store_id}")
    print(f"  Login    : {DEMO_EMAIL}")
    print(f"  Password : {DEMO_PASSWORD}")
    print(f"  Sales    : {len(rows):,} rows across {len(PRODUCTS)} products")


if __name__ == "__main__":
    main()
