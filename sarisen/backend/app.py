"""
SariSense API  —  Flask + Waitress + PostgreSQL (Supabase)
==========================================================

Endpoints
---------
GET    /api/health
POST   /api/auth/register
POST   /api/auth/login
GET    /api/me

GET    /api/products
POST   /api/products
PATCH  /api/products/<product_id>
DELETE /api/products/<product_id>

POST   /api/sales
GET    /api/sales?days=7

GET    /api/dashboard
GET    /api/forecast/<product_id>?days=7
GET    /api/restock
GET    /api/alerts
POST   /api/alerts/<alert_id>/verify
POST   /api/assistant
"""
import math
import os
import re
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from dotenv import load_dotenv

load_dotenv()

from flask import Flask, g, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException

from auth import hash_password, make_token, require_auth, verify_password
from db import db_cursor, healthcheck, init_pool
from ml.engine import (
    build_series,
    detect_anomalies,
    forecast_product,
    model_info,
)

# ---------------------------------------------------------------------
# App configuration
# ---------------------------------------------------------------------
app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024      # 1 MB request cap

_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
CORS(app, resources={r"/api/*": {"origins": _origins or "*"}}, max_age=600)

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-4-hydrogen")

_restock_cache: dict = {}
RESTOCK_TTL = 300        # 5 minutes


# ---------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------
def clean(value):
    """Make psycopg2 types JSON-serialisable."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    return value


def ok(payload=None, **kwargs):
    data = payload if payload is not None else {}
    if kwargs:
        data = {**data, **kwargs}
    return jsonify(clean(data))


def bad(message: str, status: int = 400):
    return jsonify({"error": message}), status


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _product_series(store_id: str, product_id: str, days: int = 120):
    with db_cursor() as cur:
        cur.execute(
            """
            select sold_at, sum(quantity)::int as quantity
            from sales
            where store_id = %s and product_id = %s and sold_at >= %s
            group by sold_at
            order by sold_at
            """,
            (store_id, product_id, date.today() - timedelta(days=days)),
        )
        rows = cur.fetchall()
    return build_series(rows, days=days)


# ---------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------
@app.get("/api/health")
def health():
    return ok({
        "status": "ok",
        "database": healthcheck(),
        "model": model_info(),
        "time": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    })


# ---------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------
@app.post("/api/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    store_name = (data.get("store_name") or "").strip()
    owner_name = (data.get("owner_name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    language = (data.get("language") or "en").lower()

    if len(store_name) < 2:
        return bad("Store name is required.")
    if not EMAIL_RE.match(email):
        return bad("Please enter a valid email address.")
    if len(password) < 6:
        return bad("Password must be at least 6 characters.")
    if language not in ("en", "tl", "ceb"):
        language = "en"

    with db_cursor(commit=True) as cur:
        cur.execute("select 1 from users where lower(email) = %s", (email,))
        if cur.fetchone():
            return bad("That email is already registered.", 409)

        cur.execute(
            "insert into stores (name, owner_name, language) values (%s,%s,%s) returning id",
            (store_name, owner_name, language),
        )
        store_id = cur.fetchone()["id"]

        cur.execute(
            "insert into users (store_id, email, password_hash) values (%s,%s,%s) returning id",
            (store_id, email, hash_password(password)),
        )
        user_id = cur.fetchone()["id"]

    return ok({
        "token": make_token(user_id, store_id),
        "store": {"id": str(store_id), "name": store_name, "language": language},
    }), 201


@app.post("/api/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    with db_cursor() as cur:
        cur.execute(
            """
            select u.id as user_id, u.password_hash,
                   s.id as store_id, s.name as store_name, s.language
            from users u
            join stores s on s.id = u.store_id
            where lower(u.email) = %s
            """,
            (email,),
        )
        row = cur.fetchone()

    if not row or not verify_password(password, row["password_hash"]):
        return bad("Incorrect email or password.", 401)

    return ok({
        "token": make_token(row["user_id"], row["store_id"]),
        "store": {
            "id": str(row["store_id"]),
            "name": row["store_name"],
            "language": row["language"],
        },
    })


@app.get("/api/me")
@require_auth
def me():
    with db_cursor() as cur:
        cur.execute(
            "select id, name, owner_name, language, created_at from stores where id = %s",
            (g.store_id,),
        )
        store = cur.fetchone()
    if not store:
        return bad("Store not found.", 404)
    return ok({"store": store})


# ---------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------
@app.get("/api/products")
@require_auth
def list_products():
    with db_cursor() as cur:
        cur.execute(
            """
            select id, name, category, cost_price, sell_price, stock,
                   lead_time_days, is_active, created_at
            from products
            where store_id = %s and is_active = true
            order by name
            """,
            (g.store_id,),
        )
        products = cur.fetchall()
    return ok({"products": products})


@app.post("/api/products")
@require_auth
def create_product():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if len(name) < 2:
        return bad("Product name is required.")

    try:
        cost = float(data.get("cost_price") or 0)
        sell = float(data.get("sell_price") or 0)
        stock = int(data.get("stock") or 0)
        lead = int(data.get("lead_time_days") or 3)
    except (TypeError, ValueError):
        return bad("Prices, stock and lead time must be numbers.")

    if cost < 0 or sell < 0 or stock < 0 or lead < 0:
        return bad("Values cannot be negative.")

    with db_cursor(commit=True) as cur:
        cur.execute(
            """
            insert into products
                (store_id, name, category, cost_price, sell_price, stock, lead_time_days)
            values (%s,%s,%s,%s,%s,%s,%s)
            returning id, name, category, cost_price, sell_price, stock, lead_time_days
            """,
            (g.store_id, name, (data.get("category") or "General").strip(),
             cost, sell, stock, lead),
        )
        product = cur.fetchone()

    _restock_cache.pop(g.store_id, None)
    return ok({"product": product}), 201


@app.patch("/api/products/<product_id>")
@require_auth
def update_product(product_id):
    data = request.get_json(silent=True) or {}
    fields, values = [], []

    for column, cast in (
        ("name", str), ("category", str),
        ("cost_price", float), ("sell_price", float),
        ("stock", int), ("lead_time_days", int),
    ):
        if column in data and data[column] is not None:
            fields.append(f"{column} = %s")
            values.append(cast(data[column]))

    if not fields:
        return bad("Nothing to update.")

    values.extend([product_id, g.store_id])
    with db_cursor(commit=True) as cur:
        cur.execute(
            f"update products set {', '.join(fields)} "
            "where id = %s and store_id = %s returning id",
            values,
        )
        if not cur.fetchone():
            return bad("Product not found.", 404)

    _restock_cache.pop(g.store_id, None)
    return ok({"updated": True})


@app.delete("/api/products/<product_id>")
@require_auth
def delete_product(product_id):
    with db_cursor(commit=True) as cur:
        cur.execute(
            "update products set is_active = false where id = %s and store_id = %s returning id",
            (product_id, g.store_id),
        )
        if not cur.fetchone():
            return bad("Product not found.", 404)

    _restock_cache.pop(g.store_id, None)
    return ok({"deleted": True})


# ---------------------------------------------------------------------
# Sales
# ---------------------------------------------------------------------
@app.post("/api/sales")
@require_auth
def create_sale():
    data = request.get_json(silent=True) or {}
    product_id = data.get("product_id")
    try:
        quantity = int(data.get("quantity") or 0)
    except (TypeError, ValueError):
        return bad("Quantity must be a whole number.")

    if not product_id:
        return bad("Product is required.")
    if quantity <= 0:
        return bad("Quantity must be greater than zero.")

    sold_at = data.get("sold_at") or date.today().isoformat()
    try:
        date.fromisoformat(sold_at)
    except ValueError:
        return bad("Invalid date format. Use YYYY-MM-DD.")

    with db_cursor(commit=True) as cur:
        cur.execute(
            "select sell_price, stock from products where id = %s and store_id = %s",
            (product_id, g.store_id),
        )
        product = cur.fetchone()
        if not product:
            return bad("Product not found.", 404)

        cur.execute(
            """
            insert into sales (store_id, product_id, quantity, unit_price, sold_at)
            values (%s,%s,%s,%s,%s)
            returning id, quantity, unit_price, sold_at
            """,
            (g.store_id, product_id, quantity, product["sell_price"], sold_at),
        )
        sale = cur.fetchone()

        cur.execute(
            "update products set stock = greatest(0, stock - %s) "
            "where id = %s and store_id = %s",
            (quantity, product_id, g.store_id),
        )

    _restock_cache.pop(g.store_id, None)
    return ok({"sale": sale}), 201


@app.get("/api/sales")
@require_auth
def list_sales():
    try:
        days = max(1, min(int(request.args.get("days", 7)), 90))
    except ValueError:
        days = 7

    with db_cursor() as cur:
        cur.execute(
            """
            select s.id, s.quantity, s.unit_price, s.sold_at,
                   p.name as product_name
            from sales s
            join products p on p.id = s.product_id
            where s.store_id = %s and s.sold_at >= %s
            order by s.created_at desc
            limit 200
            """,
            (g.store_id, date.today() - timedelta(days=days)),
        )
        rows = cur.fetchall()
    return ok({"sales": rows})


# ---------------------------------------------------------------------
# Restock engine (the core AI feature)
# ---------------------------------------------------------------------
def _compute_restock(store_id: str, horizon: int = 7):
    """Forecast every product once, then rank restock urgency."""
    with db_cursor() as cur:
        cur.execute(
            """
            select id, name, category, cost_price, sell_price, stock, lead_time_days
            from products
            where store_id = %s and is_active = true
            order by name
            """,
            (store_id,),
        )
        products = cur.fetchall()

        cur.execute(
            """
            select product_id, sold_at, sum(quantity)::int as quantity
            from sales
            where store_id = %s and sold_at >= %s
            group by product_id, sold_at
            """,
            (store_id, date.today() - timedelta(days=120)),
        )
        sales_rows = cur.fetchall()

    by_product = defaultdict(list)
    for row in sales_rows:
        by_product[row["product_id"]].append(row)

    items = []
    for product in products:
        series = build_series(by_product.get(product["id"], []), days=120)
        forecast = forecast_product(series, horizon)
        predicted_total = sum(p["predicted"] for p in forecast)
        avg_daily = predicted_total / horizon if horizon else 0.0

        stock = int(product["stock"])
        lead = int(product["lead_time_days"])

        days_left = (stock / avg_daily) if avg_daily > 0.01 else 999.0
        suggested = max(0, math.ceil(predicted_total + avg_daily * lead - stock))
        capital = suggested * float(product["cost_price"])

        if avg_daily <= 0.01:
            urgency = "low"
        elif days_left <= lead:
            urgency = "critical"
        elif days_left <= lead * 2:
            urgency = "high"
        elif days_left <= 7:
            urgency = "medium"
        else:
            urgency = "low"

        items.append({
            "product_id": str(product["id"]),
            "name": product["name"],
            "category": product["category"],
            "stock": stock,
            "predicted_demand": round(predicted_total, 1),
            "avg_daily": round(avg_daily, 2),
            "days_until_stockout": round(days_left, 1) if days_left < 900 else None,
            "suggested_quantity": suggested,
            "capital_needed": round(capital, 2),
            "urgency": urgency,
        })

    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    items.sort(key=lambda i: (rank[i["urgency"]], i["days_until_stockout"] or 999))

    return {
        "horizon_days": horizon,
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "items": items,
        "summary": {
            "total_capital": round(sum(i["capital_needed"] for i in items), 2),
            "critical_count": sum(1 for i in items if i["urgency"] == "critical"),
            "high_count": sum(1 for i in items if i["urgency"] == "high"),
            "products": len(items),
        },
    }


def _restock_cached(store_id: str, horizon: int = 7):
    key = (store_id, horizon)
    cached = _restock_cache.get(key)
    if cached and (time.time() - cached[0]) < RESTOCK_TTL:
        return cached[1]

    payload = _compute_restock(store_id, horizon)
    _restock_cache[key] = (time.time(), payload)
    return payload


@app.get("/api/restock")
@require_auth
def restock():
    try:
        horizon = int(request.args.get("days", 7))
    except ValueError:
        horizon = 7
    horizon = 7 if horizon not in (7, 14, 30) else horizon
    return ok(_restock_cached(g.store_id, horizon))


@app.get("/api/forecast/<product_id>")
@require_auth
def forecast(product_id):
    try:
        horizon = int(request.args.get("days", 7))
    except ValueError:
        horizon = 7
    horizon = 7 if horizon not in (7, 14, 30) else horizon

    with db_cursor() as cur:
        cur.execute(
            "select id, name, stock, sell_price, cost_price "
            "from products where id = %s and store_id = %s",
            (product_id, g.store_id),
        )
        product = cur.fetchone()
    if not product:
        return bad("Product not found.", 404)

    series = _product_series(g.store_id, product_id, days=120)
    predictions = forecast_product(series, horizon)

    history = [
        {"date": ts.strftime("%Y-%m-%d"), "quantity": float(v)}
        for ts, v in series.tail(30).items()
    ]

    return ok({
        "product": product,
        "history": history,
        "forecast": predictions,
        "total_predicted": round(sum(p["predicted"] for p in predictions), 1),
        "model": model_info(),
    })


# ---------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------
@app.get("/api/dashboard")
@require_auth
def dashboard():
    today = date.today()
    week_start = today - timedelta(days=6)
    month_start = today - timedelta(days=29)

    with db_cursor() as cur:
        cur.execute(
            """
            select coalesce(sum(quantity * unit_price), 0) as revenue,
                   coalesce(sum(quantity), 0)          as units,
                   count(*)                            as transactions
            from sales
            where store_id = %s and sold_at = %s
            """,
            (g.store_id, today),
        )
        today_stats = cur.fetchone()

        cur.execute(
            """
            select coalesce(sum(quantity * unit_price), 0) as revenue,
                   coalesce(sum(quantity), 0)          as units
            from sales
            where store_id = %s and sold_at >= %s
            """,
            (g.store_id, week_start),
        )
        week_stats = cur.fetchone()

        cur.execute(
            """
            select sold_at,
                   sum(quantity)::int                as units,
                   sum(quantity * unit_price)        as revenue
            from sales
            where store_id = %s and sold_at >= %s
            group by sold_at
            order by sold_at
            """,
            (g.store_id, today - timedelta(days=13)),
        )
        trend_rows = cur.fetchall()

        cur.execute(
            """
            select p.id, p.name, sum(s.quantity)::int as units,
                   sum(s.quantity * s.unit_price)     as revenue
            from sales s
            join products p on p.id = s.product_id
            where s.store_id = %s and s.sold_at >= %s
            group by p.id, p.name
            order by units desc
            limit 5
            """,
            (g.store_id, month_start),
        )
        top_products = cur.fetchall()

        cur.execute(
            """
            select id, name, stock
            from products
            where store_id = %s and is_active = true and stock <= 5
            order by stock asc
            limit 10
            """,
            (g.store_id,),
        )
        low_stock = cur.fetchall()

        cur.execute(
            "select count(*) as n from alerts where store_id = %s and is_verified = false",
            (g.store_id,),
        )
        alert_count = cur.fetchone()["n"]

    trend_map = {r["sold_at"]: r for r in trend_rows}
    trend = []
    for i in range(13, -1, -1):
        day = today - timedelta(days=i)
        row = trend_map.get(day)
        trend.append({
            "date": day.isoformat(),
            "units": int(row["units"]) if row else 0,
            "revenue": float(row["revenue"]) if row else 0.0,
        })

    restock_payload = _restock_cached(g.store_id, 7)

    return ok({
        "today": today_stats,
        "week": week_stats,
        "trend": trend,
        "top_products": top_products,
        "low_stock": low_stock,
        "unverified_alerts": alert_count,
        "restock": restock_payload["summary"],
        "model": model_info(),
    })


# ---------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------
@app.get("/api/alerts")
@require_auth
def alerts():
    """Recompute anomalies for the most active products, then return them."""
    with db_cursor() as cur:
        cur.execute(
            """
            select p.id, p.name,
                   coalesce(sum(s.quantity), 0)::int as units
            from products p
            left join sales s
                   on s.product_id = p.id and s.sold_at >= %s
            where p.store_id = %s and p.is_active = true
            group by p.id, p.name
            order by units desc
            limit 8
            """,
            (date.today() - timedelta(days=30), g.store_id),
        )
        products = cur.fetchall()

    found = []
    for product in products:
        series = _product_series(g.store_id, product["id"], days=120)
        for anomaly in detect_anomalies(series, lookback=30):
            found.append({
                "product_id": str(product["id"]),
                "product_name": product["name"],
                **anomaly,
            })

    found.sort(key=lambda a: (a["severity"] != "high", a["date"]), reverse=False)

    if found:
        with db_cursor(commit=True) as cur:
            for anomaly in found:
                cur.execute(
                    """
                    insert into alerts
                        (store_id, product_id, alert_date, severity, message)
                    values (%s,%s,%s,%s,%s)
                    on conflict (product_id, alert_date, message) do nothing
                    """,
                    (g.store_id, anomaly["product_id"], anomaly["date"],
                     anomaly["severity"], anomaly["message"]),
                )

    with db_cursor() as cur:
        cur.execute(
            """
            select a.id, a.product_id, a.alert_date, a.severity, a.message,
                   a.is_verified, a.created_at,
                   p.name as product_name
            from alerts a
            left join products p on p.id = a.product_id
            where a.store_id = %s
            order by a.alert_date desc, a.id desc
            limit 50
            """,
            (g.store_id,),
        )
        stored = cur.fetchall()

    return ok({"detected": found, "alerts": stored})


@app.post("/api/alerts/<int:alert_id>/verify")
@require_auth
def verify_alert(alert_id: int):
    with db_cursor(commit=True) as cur:
        cur.execute(
            "update alerts set is_verified = true "
            "where id = %s and store_id = %s returning id",
            (alert_id, g.store_id),
        )
        if not cur.fetchone():
            return bad("Alert not found.", 404)
    return ok({"verified": True})


# ---------------------------------------------------------------------
# Gemini assistant
# ---------------------------------------------------------------------
_gemini_client = None


def _get_gemini():
    global _gemini_client
    if _gemini_client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return None
        from google import genai
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


def _assistant_context(store_id: str) -> str:
    restock_payload = _restock_cached(store_id, 7)
    items = restock_payload["items"][:8]
    summary = restock_payload["summary"]

    lines = [
        f"Store summary: {summary['products']} active products, "
        f"{summary['critical_count']} critical and {summary['high_count']} high urgency items, "
        f"total restocking capital needed PHP {summary['total_capital']:.2f}.",
        "Top restock priorities:",
    ]
    for item in items:
        days = item["days_until_stockout"]
        days_text = f"{days} days left" if days is not None else "no recent sales"
        lines.append(
            f"- {item['name']}: stock {item['stock']}, predicted 7-day demand "
            f"{item['predicted_demand']}, {days_text}, urgency {item['urgency']}, "
            f"suggested order {item['suggested_quantity']} "
            f"(PHP {item['capital_needed']:.2f})."
        )
    return "\n".join(lines)


def _fallback_answer(context: str) -> str:
    return (
        "Here is the current restocking summary from your sales data:\n\n" + context +
        "\n\nTip: items marked critical should be bought first because they may run out "
        "before your next delivery."
    )


@app.post("/api/assistant")
@require_auth
@limiter.limit("10 per minute")
def assistant():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return bad("Please type a question.")
    if len(question) > 500:
        return bad("Question is too long (max 500 characters).")

    context = _assistant_context(g.store_id)
    client = _get_gemini()

    if client is None:
        return ok({"answer": _fallback_answer(context), "source": "rules"})

    try:
        from google.genai import types

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=f"STORE DATA\n{context}\n\nOWNER QUESTION\n{question}",
            config=types.GenerateContentConfig(
                system_instruction=(
                    "You are SariSense, a friendly assistant for a Filipino sari-sari "
                    "store owner. Answer ONLY using the STORE DATA provided. "
                    "Reply in the same language the owner used (Tagalog, Cebuano, or "
                    "English). Be short, practical and specific with numbers. "
                    "If the data does not contain the answer, say so plainly."
                ),
                temperature=0.3,
                max_output_tokens=600,
            ),
        )
        return ok({"answer": response.text, "source": "gemini"})
    except Exception as exc:                      # noqa: BLE001
        app.logger.warning("Gemini call failed: %s", exc)
        return ok({"answer": _fallback_answer(context), "source": "fallback"})


# ---------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------
@app.errorhandler(404)
def not_found(_):
    return jsonify({"error": "Endpoint not found."}), 404


@app.errorhandler(429)
def rate_limited(_):
    return jsonify({"error": "Too many requests. Please slow down."}), 429


@app.errorhandler(Exception)
def unhandled(exc):                              # noqa: BLE001
    # Let Flask handle normal HTTP errors (400, 405, ...) as themselves.
    if isinstance(exc, HTTPException):
        return jsonify({"error": exc.description}), exc.code
    app.logger.exception("Unhandled error")
    return jsonify({"error": "Something went wrong on the server."}), 500


# ---------------------------------------------------------------------
# Entry point (local development only - Render uses waitress)
# ---------------------------------------------------------------------
if __name__ == "__main__":
    try:
        init_pool()
        print("Database pool ready.")
    except Exception as exc:                      # noqa: BLE001
        print(f"[warn] Database not ready: {exc}")

    print(f"Gemini model: {GEMINI_MODEL}")
    app.run(host="127.0.0.1", port=5000, debug=True)
