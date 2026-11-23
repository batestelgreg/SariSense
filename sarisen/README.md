# SariSense

**An AI-Powered Demand Forecasting and Smart Restocking Web Platform for Sari-Sari Stores**

SariSense turns a sari-sari store's daily sales into decisions: how much of each
product will sell in the next 7–30 days, which items are about to run out, how
much capital is needed to restock, and which days show suspicious sales.

Built for **Applications Development and Emerging Technologies** — Web
Development Application with AI.

---

## Features

| Feature | What it does | AI involved |
|---|---|---|
| **Sales recording** | Tap-to-sell product grid, auto stock deduction | — |
| **Demand forecasting** | 7 / 14 / 30-day per-product predictions with confidence bands | GradientBoostingRegressor |
| **Anomaly detection** | Flags unusual sales days (theft, spoilage, encoding errors) | IsolationForest |
| **Smart restock list** | Ranked by urgency, with suggested quantity and capital needed | Forecast + rules |
| **AI assistant** | Answers questions in Tagalog, Cebuano, or English | Gemini `gemini-4-hydrogen` |
| **Dashboard** | KPIs, 14-day trend, top sellers, low stock | — |

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3, Vanilla JavaScript, Bootstrap 5 (CDN), Chart.js (CDN) |
| Backend | Python 3.11+, Flask, Waitress |
| Database | Supabase (PostgreSQL), psycopg2-binary |
| AI / ML | scikit-learn, pandas, NumPy, joblib |
| AI Assistant | Google Gemini API (`gemini-4-hydrogen`) via `google-genai` SDK |
| Hosting | GitHub Pages (frontend), Render (backend), Supabase (database) |

---

## Project structure

```
sarisen/
├── backend/
│   ├── app.py               # all API routes
│   ├── auth.py              # password hashing + signed tokens
│   ├── db.py                # connection pool + query helper
│   ├── schema.sql           # tables, indexes, view
│   ├── requirements.txt
│   ├── .env.example
│   ├── Procfile             # Render start command
│   └── ml/
│       ├── engine.py        # feature engineering + forecasting + anomalies
│       ├── train.py         # trains and saves forecast_model.pkl
│       └── seed_demo.py     # creates the demo store with 12 months of sales
│
├── frontend/
│   ├── index.html           # login / register
│   ├── dashboard.html       # forecasts, restock list, assistant
│   ├── sales.html           # record sales, add products
│   ├── alerts.html          # anomaly alerts
│   ├── css/style.css
│   └── js/
│       ├── config.js        # ⚠️ API base URL lives here
│       ├── api.js           # fetch wrapper + auth helpers
│       ├── auth.js
│       ├── dashboard.js
│       ├── sales.js
│       └── alerts.js
│
├── DATABASE_SETUP.md        # full PostgreSQL / Supabase guide
└── README.md
```

---

## Local setup (Windows)

### 1. Backend

```powershell
cd backend

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

> If PowerShell blocks activation:
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

### 2. Configure the database

Follow **[DATABASE_SETUP.md](DATABASE_SETUP.md)** — create the Supabase
project, run `schema.sql`, and fill in `.env`.

### 3. Train the model (once)

```powershell
python -m ml.train
```

Produces `ml/forecast_model.pkl` and prints the accuracy:

```
Hold-out MAE : 5.615 units/day
Hold-out MAPE: 19.83 %
```

(MAPE varies slightly per run. Anything under ~20 % is normal for noisy
sari-sari sales data.)

### 4. Seed the demo data

```powershell
python -m ml.seed_demo
```

### 5. Run the API

```powershell
python app.py
```

API → **http://127.0.0.1:5000**
Docs → **http://127.0.0.1:5000/api/health**

### 6. Serve the frontend

The frontend must be served over HTTP (not opened as a file), otherwise the
browser blocks requests to the API.

```powershell
cd ..\frontend
python -m http.server 5500
```

Open **http://127.0.0.1:5500**

**Demo login:** `demo@sarisen.app` / `demo1234`

---

## API reference

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Service + DB + model status |
| `POST` | `/api/auth/register` | Create store + owner |
| `POST` | `/api/auth/login` | Get bearer token |
| `GET` | `/api/me` | Current store |
| `GET` | `/api/products` | List products |
| `POST` | `/api/products` | Add product |
| `PATCH` | `/api/products/<id>` | Update product |
| `DELETE` | `/api/products/<id>` | Soft-delete product |
| `POST` | `/api/sales` | Record a sale |
| `GET` | `/api/sales?days=7` | Recent sales |
| `GET` | `/api/dashboard` | KPIs, trend, top sellers |
| `GET` | `/api/forecast/<id>?days=7` | Per-product forecast |
| `GET` | `/api/restock?days=7` | Ranked restock list |
| `GET` | `/api/alerts` | Run + list anomaly alerts |
| `POST` | `/api/alerts/<id>/verify` | Mark alert reviewed |
| `POST` | `/api/assistant` | Ask Gemini (rate-limited 10/min) |

All endpoints except `/api/health` and the two auth routes require
`Authorization: Bearer <token>`.

---

## AI assistant notes

`/api/assistant` degrades gracefully in three steps, so the chat never shows
an empty bubble:

| Situation | `source` value | What the owner sees |
|---|---|---|
| No key, or still the `.env.example` placeholder | `rules` | Restock summary built from the database |
| Key present but Gemini errors / times out / returns nothing | `fallback` | Same restock summary |
| Gemini answered | `gemini` | Conversational answer in their language |

Implementation details worth knowing:

- **`gemini-4-hydrogen` is the verified model.** `gemini-2.0-flash` and
  `gemini-2.5-flash` now return `404 ... no longer available to new users`,
  so do not downgrade `GEMINI_MODEL`.
- `gemini-4-*` are *thinking* models. If the thinking budget is unbounded it
  eats the entire output allowance and returns empty text. The code therefore
  requests `thinking_budget=0` first and retries with a plain 2048-token
  config if the API rejects that field.
- Transient `503` / `429` responses are retried briefly before falling back.
- Only the retrieved `STORE DATA` block is sent to Gemini — never the whole
  table, and never another store's rows.

---

## Deployment

### Backend → Render

1. Push the repo to GitHub.
2. Render → **New → Web Service** → connect the repo.
3. Settings:

   | Field | Value |
   |---|---|
   | Root Directory | `sarisen/backend` |
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `waitress-serve --host=0.0.0.0 --port=$PORT app:app` |

   > **Python version:** `backend/runtime.txt` pins **3.12**. This matters —
   > `numpy 1.26.4` and `scikit-learn 1.5.0` have no wheels for Python 3.13,
   > so a default Render runtime would try to compile them from source and
   > fail. If the build still complains, add the environment variable
   > `PYTHON_VERSION = 3.12.8` and delete `runtime.txt`.

4. **Environment variables** (Environment tab):

   ```
   DATABASE_URL      = postgresql://postgres.<ref>:<pw>@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres
   SECRET_KEY        = <long random string>
   GEMINI_API_KEY    = <your key>
   GEMINI_MODEL      = gemini-4-hydrogen
   ALLOWED_ORIGINS   = https://<username>.github.io
   ```

5. Copy the live URL, e.g. `https://sarisen-api.onrender.com`.
6. Open `/api/health` once to confirm `"database": true`.

### Frontend → GitHub Pages

1. Edit `frontend/js/config.js`:

   ```js
   window.SARISENSE_API = "https://sarisen-api.onrender.com";
   ```

2. Repo → **Settings → Pages** → **Source: Deploy from a branch** →
   Branch `main`, folder **`/ (root)`**.

   > GitHub Pages only offers `/ (root)` or `/docs` — you **cannot** point it
   > at `/sarisen/frontend` directly. The repository root therefore contains a
   > small `index.html` that redirects to `sarisen/frontend/index.html`, so the
   > public URL stays clean.

3. Your live site becomes:

   ```
   https://<username>.github.io/SariSense/
   ```

4. Add that origin to `ALLOWED_ORIGINS` on Render (comma-separated), then
   redeploy:

   ```
   ALLOWED_ORIGINS = http://127.0.0.1:5500,https://<username>.github.io
   ```

   > Use the **origin only** — no path, no trailing slash. A missing entry here
   > shows up as `blocked by CORS policy` in the browser console.

### Keep the free instance awake

Render free services sleep after ~15 minutes idle (30–60 s cold start).
Create a free **UptimeRobot** HTTP monitor on `/api/health` every 10 minutes.

---

## Security notes

- API keys live only in `backend/.env` locally and in Render environment
  variables in production. `.env` is git-ignored.
- The Gemini key never reaches the browser — every AI call is proxied through
  the backend.
- Passwords are hashed with `pbkdf2:sha256` (260,000 iterations).
- Sessions are signed, time-limited tokens (7 days) — not guessable IDs.
- Every SQL statement is parameterised; every query is scoped by `store_id`
  taken from the token.
- CORS is restricted to the deployed frontend origin.
- `/api/assistant` is rate-limited to 10 requests/minute per IP.
- Request bodies are capped at 1 MB.

---

## Testing checklist

- [ ] Register a new store, log out, log back in
- [ ] Add a product, record a sale, confirm stock decreases
- [ ] Dashboard shows today's revenue and the 14-day trend
- [ ] Restock list shows urgency badges and total capital
- [ ] Forecast page returns 7 / 14 / 30-day predictions
- [ ] Alerts page lists anomalies; "Mark reviewed" persists
- [ ] Assistant answers in Tagalog / Cebuano / English
- [ ] Layout works on a phone (bottom nav appears)
- [ ] `/api/health` returns `"database": true` in production
