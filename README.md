# Accounts Payable Workflow AI Agent

An intelligent, end-to-end accounts payable automation system. Invoices arrive by email, upload, or webhook and flow through OCR extraction, three-way matching, anomaly detection, and a role-based approval workflow — all with real-time updates and AI-generated explanations.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Role-Based Access](#role-based-access)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Demo Data](#demo-data)
- [Testing](#testing)
- [Screenshots](#screenshots)

---

## Features

### Invoice Processing Pipeline
- **Multi-channel ingestion** — email (Gmail IMAP), file upload, webhook, and manual entry
- **OCR extraction** — Tesseract-powered text extraction with confidence scoring per field
- **Three-way matching** — Invoice ↔ Purchase Order ↔ Goods Receipt with line-item comparison
- **Duplicate detection** — exact hash matching and fuzzy similarity (RapidFuzz) within a 72-hour window
- **Anomaly detection** — Z-Score statistical analysis + Isolation Forest ML model per vendor baseline
- **Auto-approval** — touchless processing for invoices within configured thresholds

### Approval Workflow
- **Three-tier escalation** — AP Clerk → Manager → CFO based on invoice amount
- **SLA tracking** — automatic escalation when deadlines are missed
- **Role enforcement** — both frontend UI and backend API reject unauthorized actions
- **Audit trail** — immutable log of every state change with actor, timestamp, and before/after state

### AI & Intelligence
- **LLM explanations** — NVIDIA NIM (Nemotron / Llama) generates plain-English explanations for every exception
- **Explanation caching** — Redis-backed cache prevents redundant LLM calls
- **Fallback templates** — rule-based explanations when LLM is unavailable
- **Vendor baselines** — statistical profiles (mean, std dev, P95) updated on a 6-hour schedule

### Financial Operations
- **Payment scheduling** — discount-optimized payment dates based on vendor payment terms
- **Cash flow forecasting** — 30-day projected outflow with $50k safety threshold alerts
- **Discount capture** — early payment discount identification and one-click capture
- **FX handling** — ECB exchange rates with stale-rate detection

### Platform
- **Real-time WebSocket** — live exception feed pushed to all connected clients
- **Circuit breakers** — automatic fallback for LLM, ERP, and payment processor integrations
- **Structured logging** — JSON logs with correlation IDs
- **Health monitoring** — per-component health checks with queue depth metrics

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12, FastAPI 0.111, SQLAlchemy 2.0, Pydantic v2 |
| **Database** | PostgreSQL 15 |
| **Cache / Queue** | Redis 7 |
| **OCR** | Tesseract 5, pdf2image, pdfplumber |
| **ML** | scikit-learn (Isolation Forest), numpy, pandas |
| **LLM** | NVIDIA NIM (Nemotron-3 / Llama-3.3) via REST |
| **Frontend** | React 18, TypeScript 5, Vite 5 |
| **UI** | Tailwind CSS 3, Recharts, Lucide React |
| **State** | TanStack Query v5, React Router v6 |
| **Auth** | JWT (python-jose), HTTPBearer |
| **Testing** | pytest, Hypothesis (property-based), pytest-cov |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (React)                      │
│  Dashboard │ Payments │ Exception Detail │ Settings          │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST + WebSocket
┌──────────────────────────▼──────────────────────────────────┐
│                    FastAPI Backend                           │
│                                                             │
│  /auth  /invoices  /exceptions  /approvals                  │
│  /vendors  /payments  /settings  /metrics  /health          │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Ingestion   │  │  Processing  │  │    Workflow      │  │
│  │  Service     │→ │  Pipeline    │→ │    Engine        │  │
│  │              │  │  OCR         │  │  Decision Engine │  │
│  │  email       │  │  Matching    │  │  Approval Mgmt   │  │
│  │  upload      │  │  Duplicate   │  │  Payment Sched.  │  │
│  │  webhook     │  │  Anomaly     │  │  Audit Logger    │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  PostgreSQL  │  │    Redis     │  │   NVIDIA NIM     │  │
│  │  (primary)   │  │  cache+queue │  │   LLM API        │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Invoice Processing Flow

```
Invoice arrives
    │
    ▼
[Ingestion] → file hash, dedup check, store raw
    │
    ▼
[OCR] → extract fields, confidence scores
    │
    ▼
[Matching] → 3-way match vs PO + Receipt
    │
    ▼
[Anomaly Detection] → Z-Score + Isolation Forest
    │
    ├── No exceptions + within threshold → AUTO-APPROVED ✓
    │
    └── Exception found → create InvoiceException
            │
            ▼
        [LLM Explainer] → generate plain-English explanation
            │
            ▼
        [Decision Engine] → route to correct approval queue
            │
            ├── amount ≤ $5k  → AP_CLERK_QUEUE
            ├── amount ≤ $25k → MANAGER_QUEUE
            └── amount > $25k → CFO_ESCALATION_QUEUE
                    │
                    ▼
                [Approval] → APPROVED / REJECTED / ESCALATED
                    │
                    ▼
                [Payment Scheduler] → optimize payment date
```

---

## Role-Based Access

Three roles with distinct approval authority and UI access:

| | AP Clerk | Manager | CFO |
|---|---|---|---|
| **Email** | clerk@example.com | manager@example.com | cfo@example.com |
| **Password** | password | password | password |
| **Approve up to** | $5,000 | $25,000 | Unlimited |
| **Dashboard** | Queue view | Cash flow + KPIs | Cash flow + KPIs |
| **Payments** | ✅ Full access | ✅ Full access | ✅ Full access |
| **Settings** | ❌ Blocked | 👁 View only | ✅ Full edit |
| **Escalate to** | Manager | CFO | — |

The backend enforces these limits independently — a Clerk cannot approve a $10k invoice even via direct API call (returns HTTP 403).

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- PostgreSQL 15+
- Redis 7+
- Tesseract OCR

### 1. Clone and set up environment

```bash
git clone <repo-url>
cd Accounts-Payable-Workflow-AI-Agent

# Copy environment file
cp .env.example backend/.env
# Edit backend/.env with your database credentials
```

### 2. Start databases

```bash
# Using Docker (recommended)
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres --name postgres postgres:15
docker run -d -p 6379:6379 --name redis redis:7
```

### 3. Install backend dependencies

```bash
python -m venv .venv

# Windows
.\.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r backend/requirements.txt
```

### 4. Start the backend

```bash
python start_backend.py
# OR
python -m uvicorn ap_workflow.main:app --reload --port 8000
# (run from the backend/ directory)
```

### 5. Install and start the frontend

```bash
cd frontend
npm install
npm run dev
```

### 6. Seed demo data

```bash
# From the backend/ directory
python seed_demo_data.py
```

### 7. Open the app

| URL | Description |
|-----|-------------|
| http://localhost:5173 | Frontend application |
| http://localhost:8000/docs | Swagger API documentation |
| http://localhost:8000/redoc | ReDoc API documentation |
| http://localhost:8000/health | Health check endpoint |

---

## Environment Variables

Copy `.env.example` to `backend/.env` and configure:

```env
# Required
DATABASE_URL=postgresql://postgres:password@localhost:5432/ap_workflow
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=your-secret-key-change-in-production

# Optional — LLM (AI explanations)
LLM_API_KEY=your-nvidia-nim-api-key
LLM_API_URL=https://integrate.api.nvidia.com/v1/chat/completions
LLM_MODEL=nvidia/nemotron-3-super-120b-a12b

# Optional — Email ingestion
GMAIL_IMAP_HOST=imap.gmail.com
GMAIL_IMAP_PORT=993

# Optional — ERP integration
ERP_API_URL=https://your-erp.example.com
ERP_API_KEY=your-erp-key

# Approval thresholds (defaults shown)
AP_CLERK_SLA_HOURS=24
MANAGER_SLA_HOURS=8
CFO_SLA_HOURS=2
DEFAULT_AUTO_APPROVE_MAX_AMOUNT=10000.0
```

The app runs without LLM, email, and ERP keys — those features degrade gracefully with fallback templates and circuit breakers.

---

## API Reference

Full interactive docs at **http://localhost:8000/docs**

### Key endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/auth/login` | Login, returns JWT |
| `GET` | `/api/v1/auth/me` | Current user profile |
| `GET` | `/api/v1/invoices/` | List invoices with filters |
| `GET` | `/api/v1/invoices/{id}` | Invoice detail |
| `POST` | `/api/v1/invoices/upload` | Upload invoice PDF |
| `GET` | `/api/v1/exceptions/` | List exceptions |
| `GET` | `/api/v1/exceptions/{id}` | Exception detail |
| `GET` | `/api/v1/approvals/queue/{queue}` | Get approval queue |
| `POST` | `/api/v1/approvals/{id}/action` | Submit approval decision |
| `GET` | `/api/v1/vendors/{key}/baseline` | Vendor baseline stats |
| `GET` | `/api/v1/vendors/baselines` | All vendor baselines |
| `GET` | `/api/v1/payments/schedule` | Payment schedule |
| `GET` | `/api/v1/payments/cashflow-forecast` | 30-day forecast |
| `GET` | `/api/v1/metrics/dashboard` | Dashboard KPIs |
| `GET` | `/api/v1/settings/workflow` | Workflow config |
| `PUT` | `/api/v1/settings/workflow` | Update workflow config (CFO only) |
| `GET` | `/api/v1/health` | System health check |
| `WS` | `/ws/stream` | Real-time exception feed |

### Authentication

All protected endpoints require `Authorization: Bearer <token>`.

```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "clerk@example.com", "password": "password"}'

# Use the returned token
curl http://localhost:8000/api/v1/invoices/ \
  -H "Authorization: Bearer <token>"
```

---

## Project Structure

```
Accounts-Payable-Workflow-AI-Agent/
├── backend/
│   ├── ap_workflow/
│   │   ├── core/           # Config, security, JWT, deps
│   │   ├── database/       # SQLAlchemy session, Base
│   │   ├── models/         # ORM models (Invoice, Payment, Approval…)
│   │   ├── schemas/        # Pydantic request/response schemas
│   │   ├── routes/         # FastAPI routers
│   │   │   ├── auth.py
│   │   │   ├── invoices.py
│   │   │   ├── exceptions.py
│   │   │   ├── approvals.py
│   │   │   ├── vendors.py
│   │   │   ├── payments.py
│   │   │   ├── settings.py
│   │   │   ├── health.py
│   │   │   └── websocket.py
│   │   ├── services/       # Business logic
│   │   │   ├── ingestion.py
│   │   │   ├── ocr.py
│   │   │   ├── matching.py
│   │   │   ├── duplicate_detection.py
│   │   │   ├── anomaly_detection.py
│   │   │   ├── decision_engine.py
│   │   │   ├── approval_management.py
│   │   │   ├── llm_explainer.py
│   │   │   ├── payment_scheduler.py
│   │   │   ├── vendor_baseline.py
│   │   │   ├── audit_logger.py
│   │   │   ├── health_monitoring.py
│   │   │   └── circuit_breaker.py
│   │   └── main.py         # FastAPI app, lifespan, middleware
│   ├── seed_demo_data.py   # Demo data seeder
│   └── requirements.txt
│
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── Layout.tsx
│       │   └── Navigation.tsx
│       ├── context/
│       │   └── AuthContext.tsx
│       ├── hooks/
│       │   └── useRole.ts      # Role-based access hook
│       ├── lib/
│       │   ├── api.ts          # Axios client with JWT interceptor
│       │   └── queryClient.ts
│       └── pages/
│           ├── DashboardPage.tsx
│           ├── ExceptionDetailPage.tsx
│           ├── InvoiceDetailPage.tsx
│           ├── PaymentSchedulePage.tsx
│           ├── SettingsPage.tsx
│           ├── VendorAnalyticsPage.tsx
│           └── LoginPage.tsx
│
├── tests/                  # Property-based and unit tests
├── seed_demo_data.py       # (also at backend root)
├── TEST_GUIDE.md           # Manual test checklist per role
├── start_backend.py        # Backend launcher script
├── run.ps1                 # PowerShell one-command start
└── run.bat                 # Batch one-command start
```

---

## Demo Data

The seed script creates a realistic dataset with guaranteed items in every approval queue:

```bash
cd backend
python seed_demo_data.py
```

**What gets created:**

| Data | Count |
|------|-------|
| Vendors with baselines | 8 |
| Historical invoices | ~50 |
| AP Clerk queue (pending) | 6 |
| Manager queue (pending) | 4 |
| CFO queue (pending) | 3 |
| Scheduled/executed payments | ~30 |

**Demo vendors:** Acme Office Supplies, TechPro IT Solutions, Global Logistics Co., Premier Catering Ltd., Skyline Realty Group, Delta Consulting Inc., Rapid Print & Design, Nexus Cloud Services.

The script is idempotent — re-running it skips existing records and only adds new ones.

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=ap_workflow --cov-report=html

# Run property-based tests only
pytest tests/ -v -k "hypothesis"

# Run a specific test file
pytest tests/test_matching.py -v
```

The test suite uses [Hypothesis](https://hypothesis.readthedocs.io/) for property-based testing — it generates hundreds of random inputs to verify correctness properties like:
- Duplicate detection is symmetric
- Anomaly scores are bounded [0, 1]
- Payment scheduling never schedules past due dates
- Approval escalation always moves to a higher queue

---

## Known Limitations

- **PDF viewer** — shows a placeholder; actual PDF rendering requires Supabase Storage to be configured
- **Email ingestion** — requires Gmail IMAP credentials in `.env`
- **LLM explanations** — require an NVIDIA NIM API key; fallback templates are used otherwise
- **ERP integration** — stub implementation; connect your ERP via `ERP_API_URL` and `ERP_API_KEY`
- **Real-time exceptions** — WebSocket feed only populates during active invoice processing (not from seed data)

---

## License

MIT
