# Database Setup — PostgreSQL (Supabase)

This is the complete, step-by-step guide for creating the database and
connecting the SariSense backend to it.

---

## 1. Create the Supabase project

1. Go to **https://supabase.com** → sign in → **New project**.
2. Fill in:
   - **Name**: `sarisen`
   - **Database password**: choose a strong password and **save it somewhere safe**
   - **Region**: `Southeast Asia (Singapore)` — closest to the Philippines
3. Wait ~2 minutes for provisioning.

---

## 2. Get the connection string

Supabase gives you two ways to connect. **They are not the same** — pick the
right one for where the code is running.

Go to **Project Settings → Database → Connection string → URI**.

### Option A — Connection Pooler (use this EVERYWHERE — local and Render)

```
postgresql://postgres.<PROJECT-REF>:<PASSWORD>@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres
```

- Port **5432** (session pooler) or **6543** (transaction pooler)
- Username is `postgres.<PROJECT-REF>`, **not** just `postgres`
- This host has an **IPv4** address, so it works on any home/office network

### Option B — Direct connection

```
postgresql://postgres:<PASSWORD>@db.<PROJECT-REF>.supabase.co:5432/postgres
```

- Port **5432**
- ⚠️ **This host is IPv6-only.** Many home ISPs (and some Windows setups) cannot
  resolve or route to it, producing
  `could not translate host name ... No such host is known`.
- Only use it if `Resolve-DnsName db.<PROJECT-REF>.supabase.co` returns an
  `A` record.

> **Why two?** Free-tier Postgres allows a limited number of simultaneous
> connections. The pooler shares them, so a cloud host never exhausts the limit.

### ⚠️ Which one does SariSense use?

**The pooler, in both places.** The direct host returned IPv6-only DNS on the
machine this project was built on, so `.env` and Render both use:

```
DATABASE_URL=postgresql://postgres.<PROJECT-REF>:<PASSWORD>@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres
```

If your region is not Singapore, the `aws-1-ap-southeast-1` part changes. Click
**Connect** in the Supabase dashboard and copy whichever host it prints.

---

## 3. Put it in `.env`

In `backend/`, copy `.env.example` to `.env`:

```powershell
cd backend
copy .env.example .env
```

Then edit `.env`:

```env
DATABASE_URL=postgresql://postgres.<ref>:<pw>@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres
SECRET_KEY=some-long-random-string
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-4-hydrogen
ALLOWED_ORIGINS=http://127.0.0.1:5500,http://localhost:5500
```

Generate a strong `SECRET_KEY`:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

> ⚠️ `.env` must **never** be committed. Only `.env.example` goes to GitHub.

---

## 4. Create the tables

1. Open your Supabase project → **SQL Editor** → **New query**
2. Paste the entire contents of `backend/schema.sql`
3. Click **Run**

You should now see 5 tables + 1 view in **Table Editor**:

```
stores      users      products      sales      alerts      v_daily_sales
```

To confirm:

```sql
select table_name
from information_schema.tables
where table_schema = 'public';
```

---

## 5. Seed the demo store

From the `backend` folder, with your virtual environment active:

```powershell
python -m ml.seed_demo
```

Expected output:

```
Demo store created: 3f7c1e9a-...
  Login    : demo@sarisen.app
  Password : demo1234
  Sales    : 4,380 rows across 12 products
```

This inserts **12 months of realistic sales** so the forecasting model has
something to learn from immediately.

---

## 6. Verify the connection

```powershell
python -c "from db import healthcheck; print('DB OK' if healthcheck() else 'DB FAILED')"
```

Then start the API and open **http://127.0.0.1:5000/api/health**:

```json
{
  "status": "ok",
  "database": true,
  "model": { "loaded": true, "model": "GradientBoostingRegressor" }
}
```

`"database": true` means the pool connected successfully.

---

## How the connection actually works

`backend/db.py` does three things:

### 1. A connection pool (not one connection per request)

```python
_pool = pool.SimpleConnectionPool(1, 8, dsn=dsn, sslmode="require")
```

Opening a fresh TLS connection to a cloud Postgres costs **200–800 ms**.
Reusing pooled connections brings a query down to **10–30 ms**.

### 2. SSL is mandatory

Supabase rejects unencrypted connections. `sslmode="require"` is enforced in
code so you cannot accidentally connect insecurely.

### 3. Context manager = no leaked connections

```python
with db_cursor(commit=True) as cur:
    cur.execute("insert into sales ...")
```

This always commits or rolls back, and **always** returns the connection to the
pool — even when an exception is raised. Leaked connections are the #1 cause of
"too many clients already" errors.

---

## Tenant isolation (important for the demo)

SariSense does **not** use Supabase Auth. It has its own auth layer, so every
query is scoped by the store ID taken from the signed token:

```python
@require_auth
def list_products():
    ...
    where store_id = %s   # <- from the token, never from the request body
```

A store owner can therefore never read another store's data, even by guessing
a UUID. Every SQL statement is parameterised (`%s`), which blocks SQL injection.

---

## Performance choices

| Choice | Why |
|---|---|
| Indexes on `(store_id, sold_at)` and `(product_id, sold_at)` | Dashboard and forecast queries filter on exactly these columns |
| `v_daily_sales` view | Pre-aggregates per-day quantities so the ML layer does not re-aggregate raw rows |
| Restock cache (5 min, in memory) | Forecasting 20 products takes ~300 ms; the cache makes repeat dashboard loads instant |
| Model loaded once at startup | `joblib.load()` is cached, not repeated per request |
| Batch insert in the seeder | `execute_values` instead of 4,000 single inserts |

---

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `connection refused` / timeout | Wrong host or port | Use port `6543` + `pooler.supabase.com` on Render |
| `password authentication failed` | Wrong password, or username missing the project ref | Username must be `postgres.<PROJECT-REF>` when using the pooler |
| `SSL connection is required` | `sslmode` missing | Already forced in `db.py`; make sure you are using that module |
| `too many clients already` | Pool too large or connections leaking | Lower `DB_POOL_MAX` to `4`; never create connections outside `db_cursor()` |
| `relation "stores" does not exist` | `schema.sql` never ran | Run it in the SQL Editor |
| `could not translate host name` | Either the project is paused (free tier) **or** you used the IPv6-only `db.<ref>.supabase.co` host | Wake the project in the dashboard, **and switch to the `aws-1-...pooler.supabase.com` host** |
| `DATABASE_URL is not set` | `.env` missing or not loaded | Confirm `backend/.env` exists and `load_dotenv()` runs before `db.py` is used |
