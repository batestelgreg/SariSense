# SariSense

### An AI-Powered Demand Forecasting and Smart Restocking Web Platform for Sari-Sari Stores

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-000000?logo=flask&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase-4169E1?logo=postgresql&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-1.5-F7931E?logo=scikitlearn&logoColor=white)
![Gemini](https://img.shields.io/badge/AI-Gemini%204%20Hydrogen-4285F4?logo=google&logoColor=white)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-7952B3?logo=bootstrap&logoColor=white)

> **Final Project** — Applications Development and Emerging Technologies
> Category: **Web Development Application with AI**

---

## What is SariSense?

Sari-sari store owners usually restock by memory. That leads to two expensive
mistakes: **capital tied up in slow movers** and **fast movers running out**.

SariSense records daily sales and uses machine learning to answer the questions
an owner actually asks:

| Question | SariSense answer |
|---|---|
| How much of this will sell next week? | 7 / 14 / 30-day per-product forecast with confidence bands |
| What should I buy first? | Restock list ranked by urgency (critical → low) |
| How much cash do I need? | Suggested quantity × cost price, totalled |
| Did something odd happen? | Unusual sales days flagged automatically |
| *"Unsa akong paliton para sa sunod semana?"* | Gemini answers in **Cebuano, Tagalog, or English** |

---

## How it works

```
┌──────────────────────────┐
│  GitHub Pages            │
│  HTML + CSS + Vanilla JS │
│  Bootstrap 5 · Chart.js  │
└────────────┬─────────────┘
             │  HTTPS + Bearer token
             ▼
┌──────────────────────────┐        ┌──────────────────┐
│  Render                  │        │  Google Gemini   │
│  Python · Flask          │◄──────►│  gemini-4-       │
│  Waitress                │        │  hydrogen        │
│                          │        └──────────────────┘
│  ┌────────────────────┐  │
│  │ GradientBoosting   │  │  demand forecast
│  │ IsolationForest    │  │  anomaly detection
│  └────────────────────┘  │
└────────────┬─────────────┘
             │  psycopg2 · SSL · pooled
             ▼
┌──────────────────────────┐
│  Supabase (PostgreSQL)   │
│  stores · users          │
│  products · sales        │
│  alerts · v_daily_sales  │
└──────────────────────────┘
```

---

## Features

| Feature | Description | AI involved |
|---|---|---|
| **Sales recording** | Tap-to-sell product grid, stock deducts automatically | — |
| **Demand forecasting** | Recursive multi-step forecast with 80% confidence bands | `GradientBoostingRegressor` |
| **Anomaly detection** | Flags spikes and drops — theft, spoilage, encoding errors | `IsolationForest` |
| **Smart restock list** | Urgency ranking from days-until-stockout + capital needed | Forecast + rules |
| **AI assistant** | Plain-language answers in Cebuano, Tagalog, or English | Gemini 4 Hydrogen |
| **Dashboard** | KPIs, 14-day trend, top sellers, low stock | — |

### Model quality

Trained on 7,720 samples across 20 product series:

```
Hold-out MAE  : 5.615 units/day
Hold-out MAPE : 19.83 %
```

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3, Vanilla JavaScript, Bootstrap 5 (CDN), Chart.js (CDN) |
| Backend | Python 3.12, Flask, Waitress |
| Database | Supabase (PostgreSQL), psycopg2-binary |
| ML | scikit-learn, pandas, NumPy, joblib |
| AI assistant | Google Gemini API (`gemini-4-hydrogen`) via `google-genai` |
| Hosting | GitHub Pages · Render · Supabase |

**No build step. No npm. No bundler.** The frontend is static files.

---

## Repository layout

```
SariSense/
├── sarisen/                      ← the application
│   ├── backend/                  ← Python + Flask API
│   │   ├── app.py                ← 16 endpoints
│   │   ├── auth.py               ← hashing + signed tokens
│   │   ├── db.py                 ← pooled PostgreSQL access
│   │   ├── schema.sql            ← 3NF schema, indexes, view
│   │   ├── requirements.txt
│   │   ├── Procfile              ← Render start command
│   │   ├── runtime.txt           ← pins Python 3.12
│   │   ├── .env.example
│   │   └── ml/
│   │       ├── engine.py         ← forecasting + anomaly detection
│   │       ├── train.py          ← trains forecast_model.pkl
│   │       └── seed_demo.py      ← 12 months of demo sales
│   │
│   ├── frontend/                 ← static site
│   │   ├── index.html            ← login / register
│   │   ├── dashboard.html
│   │   ├── sales.html
│   │   ├── alerts.html
│   │   ├── css/style.css
│   │   └── js/                   ← config, api, auth, dashboard, sales, alerts
│   │
│   ├── README.md                 ← full setup + API reference
│   └── DATABASE_SETUP.md         ← PostgreSQL / Supabase guide
│
├── build/proposal.html           ← project proposal
├── SariSense_Project_Conceptualization.pdf
└── Project_Conceptualization_DRAFT.md
```

---

## Quick start

```powershell
# 1. Backend
cd sarisen\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Configure  (see sarisen\DATABASE_SETUP.md for the full guide)
copy .env.example .env
notepad .env          # add DATABASE_URL, SECRET_KEY, GEMINI_API_KEY

# 3. Seed + run
python -m ml.seed_demo
python app.py         # http://127.0.0.1:5000

# 4. Frontend  (new terminal)
cd sarisen\frontend
python -m http.server 5500
# open http://127.0.0.1:5500
```

**Demo login:** `demo@sarisen.app` / `demo1234`

---

## Documentation

| Document | Contents |
|---|---|
| [`sarisen/README.md`](sarisen/README.md) | Full setup, API reference, deployment, security notes |
| [`sarisen/DATABASE_SETUP.md`](sarisen/DATABASE_SETUP.md) | Create the Supabase project, connect via PostgreSQL, troubleshooting |
| [`sarisen/backend/schema.sql`](sarisen/backend/schema.sql) | Schema with normalization notes |
| [`build/proposal.html`](build/proposal.html) | Project proposal |

---

## Security

- Passwords hashed with `pbkdf2:sha256` (260,000 iterations)
- Signed, time-limited bearer tokens — not guessable IDs or cookies
- Every query parameterised (`%s`) and scoped by `store_id` taken from the token
- CORS restricted to the deployed frontend origin
- AI assistant rate-limited; request bodies capped at 1 MB
- The Gemini key never reaches the browser — all AI calls are proxied
- `.env` is git-ignored; only `.env.example` is committed

---

## Deployment target

| Part | Host | Setting |
|---|---|---|
| Frontend | GitHub Pages | Source folder `/sarisen/frontend` |
| Backend | Render | Root Directory `sarisen/backend` |
| Database | Supabase | Pooler host, `sslmode=require` |

> The Supabase direct host `db.<ref>.supabase.co` is **IPv6-only** on many
> networks. Use the connection pooler (`aws-1-<region>.pooler.supabase.com`).
