# Project Conceptualization (Draft for PDF)

## A. Choice of Project Type
**Web Development Application with Artificial Intelligence**

---

## B. Project Proposal

### 1. Project Title
**SariSense: An AI-Powered Demand Forecasting and Smart Restocking Web Platform for Sari-Sari Stores**

*Alternate titles (same system, if the title is already taken in the GC):*
- TindaForecast: AI-Driven Sales Prediction and Inventory Advisor for Micro-Retailers
- SariIQ: A Machine Learning Demand Forecasting Dashboard for Neighborhood Stores

---

### 2. Proposal Paragraph (1 paragraph)

Most of the country's estimated 1.3 million sari-sari stores still decide what to restock through memory and guesswork, which results in dead stock, repeated stockouts of fast-moving items, and lost income for micro-retailers operating on very thin margins. **SariSense** is a responsive, AI-enhanced web application that converts a store's everyday sales records into actionable business decisions. Store owners record sales through a lightweight point-of-sale module — manual entry, barcode scan, or a photo of a handwritten list — and the system applies a machine-learning demand-forecasting model to each product's sales history to predict the next 7 to 30 days of demand. A second model performs anomaly detection to flag unusual sales patterns such as unrecorded withdrawals, sudden stockouts, or encoding errors, while a prioritized restock list ranks items by predicted urgency and shows the capital needed to replenish them. A conversational AI assistant built on the Google Gemini API and grounded in the store's own forecast data answers plain-language questions in Tagalog, Cebuano, or English — for example, "Unsa akong paliton para sa sunod semana?" — and explains every recommendation in simple terms. The goal is to give micro-retailers enterprise-grade analytics through a mobile-first interface they can actually use.

---

### 3. Technology Stack and Tools

**Architecture: separated frontend and backend (client–server)**

| Layer | Technology | Cost |
|---|---|---|
| **Frontend** | HTML5, CSS3, Vanilla JavaScript (ES6), Bootstrap 5 (CDN), Chart.js (CDN) | Free (CDN) |
| **Backend** | Python 3.11, Flask, Waitress | Free (open-source) |
| **Database** | Supabase (managed PostgreSQL), psycopg2-binary | Free tier |
| **Machine Learning** | scikit-learn (GradientBoostingRegressor, IsolationForest), pandas, NumPy, joblib | Free (open-source) |
| **AI Service** | Google Gemini API (`gemini-4-hydrogen`) via the `google-genai` Python SDK | Free tier |
| **Hosting — Frontend** | GitHub Pages | Free |
| **Hosting — Backend** | Render (Free instance, 512 MB RAM) | Free |
| **Hosting — Database** | Supabase | Free tier |
| **Development Tools** | VS Code, GitHub Desktop, browser DevTools | Free |

**Total project cost: ₱0.** All tools are free, open-source, or on free tiers with no payment method required.

*Deliberately scoped: no frontend framework, no build tooling, no ORM — to maximize reliability within the project timeline.*

---

### 4. Outline of Main Features and Functionalities

**Module 1 — Store Setup & Onboarding**
- Owner registers and creates a store profile; selects preferred language (Tagalog / Cebuano / English).
- Quick-add products with category, cost price, selling price, and current stock.

**Module 2 — Sales Recording (POS-Lite)**
- Fast mobile-friendly sales entry: tap-to-sell product grid plus quantity input.
- Automatic stock deduction and daily sales log.

**Module 3 — AI Forecasting Dashboard**
- Per-product forecast graph for 7 / 14 / 30 days (Chart.js), with lower/upper bounds.
- "Restock Priority" table: predicted demand, days-until-stockout, suggested order quantity, required capital.
- Store summary cards: fast movers, slow movers, projected weekly revenue.

**Module 4 — Anomaly & Loss Detection**
- Isolation Forest flags days or products with statistically abnormal sales (possible theft, spoilage, or encoding error).
- Alert cards with plain-language explanation and a one-tap "verify" action.

**Module 5 — Conversational AI Assistant**
- Gemini-powered chat grounded in the store's own forecast and stock data.
- Answers restocking and trend questions; generates a printable shopping list.

**Module 6 — Reports & Export**
- Weekly/monthly sales and profit summaries, exportable to CSV/PDF.

**User workflow:** Owner logs in → records today's sales → dashboard shows updated forecast and alerts → reviews restock list → asks the assistant for clarification → exports shopping list.

---

### 5. AI Component Description

**a) Machine Learning Model / Algorithm**
- **Demand Forecasting:** GradientBoostingRegressor (scikit-learn), trained on engineered features — day of week, payday proximity, holiday flags, and rolling 7/14/28-day averages. Evaluated with MAE and MAPE on a held-out period; target MAPE below 20%. Model serialized with joblib and loaded by the Flask API at startup.
- **Anomaly Detection:** IsolationForest (unsupervised), trained on daily sales volume, basket size, and product mix to surface statistically unusual behavior.
- **Prioritization Logic:** Rule-based scoring layer combining forecast output, current stock, and supplier lead time to rank restock urgency.

**b) AI API / Service**
- **Google Gemini API — `gemini-4-hydrogen`**, accessed through the current `google-genai` Python SDK, with structured context injection. The model receives only computed store aggregates (never raw customer data), keeping answers grounded in real values. A lightweight fallback (`gemini-3.5-flash-lite`) is configured for high-volume or free-tier limits.

**c) Purpose and Function of AI**
- **Prediction** — forecast short-term product demand.
- **Anomaly detection** — identify unusual sales patterns indicating loss or data error.
- **Recommendation** — generate an optimized restock list and order quantities.
- **Natural-language analysis** — allow non-technical owners to interrogate their own data conversationally.

*Design note: the core intelligence is a trained, evaluated ML model, not a generic chatbot wrapper — the LLM layer only translates model output into human language.*

---

### 6. Deployment / Hosting Platform

| Component | Platform | Notes |
|---|---|---|
| Frontend (static files) | **GitHub Pages** | Free, public URL, no build step, served over HTTPS |
| Backend API (Flask) | **Render** (free web service) | Auto-deploy from GitHub; secrets stored as environment variables; 512 MB RAM free tier |
| Database | **Supabase** | Managed PostgreSQL with Row-Level Security |

**Live URL:** `https://<username>.github.io/sarisen/`
**API endpoint:** `https://sarisen-api.onrender.com`

**Demo access:** a seeded demo store with 12 months of realistic synthetic sales data and a read-only demo account, so the instructor can test immediately without signing up.

---

### 7. Security & Data Handling
- API keys (`GEMINI_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`) stored only in Render environment variables and a local `.env` file; `.env.example` with placeholders is committed instead.
- All AI calls are proxied through the backend — keys never reach the browser.
- Supabase Row-Level Security so a store owner can only read/write their own store's records.
- Passwords hashed; all traffic over HTTPS.
- Assistant requests send aggregated figures only, never personal customer data.

---

### 8. Team Roles (equal contribution)
- **Member 1:** Database schema, Flask API endpoints, ML model training/evaluation, backend deployment.
- **Member 2:** UI/UX design, frontend pages (HTML/CSS/JS), Chart.js visualizations, documentation and demo video.
- *Both:* system architecture, testing, presentation.
