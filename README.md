# Form 26AS & AIS Automation Framework

[![CI](https://github.com/jilsnshah/Income-Tax-Automation/actions/workflows/ci.yml/badge.svg)](https://github.com/jilsnshah/Income-Tax-Automation/actions/workflows/ci.yml)

> **End-to-end Playwright automation framework for downloading, decrypting, and batch-processing Indian Income Tax documents (Form 26AS, AIS, TIS) — built with a FastAPI backend, React frontend, and a full pytest test suite.**

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     React Frontend                       │
│   Upload XLSX → Configure mapping → Monitor queue       │
└──────────────────────┬──────────────────────────────────┘
                       │ REST (FastAPI)
┌──────────────────────▼──────────────────────────────────┐
│                   FastAPI Server (server.py)             │
│  /api/start_batch   /api/status   /api/logs             │
│  Background task queue (per-client processing)          │
└──────────────────────┬──────────────────────────────────┘
                       │ calls
┌──────────────────────▼──────────────────────────────────┐
│               Playwright Scraper (scraper.py)            │
│  Chromium + playwright-stealth (anti-bot bypass)        │
│  Multi-tab orchestration: IT Portal → TRACES → AIS      │
│  Async file polling + error-screenshot capture          │
└──────────────────────┬──────────────────────────────────┘
                       │ decrypts
┌──────────────────────▼──────────────────────────────────┐
│               Crypto Utils (crypto_utils.py)             │
│  PAN+DOB keyed PDF decryption / ZIP extraction          │
│  Strict output directory cleanup after processing       │
└─────────────────────────────────────────────────────────┘
```

---

## Key Engineering Decisions

### 1. Stealth browser fingerprinting bypass
The Income Tax portal detects headless Chromium via `navigator.webdriver`. The scraper applies [`playwright-stealth`](https://github.com/AtuboDad/playwright-stealth) to patch JS properties that betray automation, enabling reliable headless execution.

### 2. Multi-tab orchestration
Navigating to Form 26AS opens a new TRACES tab; navigating to AIS opens another. The scraper tracks all three page handles (`page`, `traces_page`, `ais_page`) with independent timeouts and state, handling each tab's lifecycle correctly.

### 3. Async file generation with polling
For large AIS files, the portal generates documents asynchronously — the "Download" button changes to "Go to Activity History" when the file isn't ready. The scraper detects this, polls the Activity History tab in a loop, and retries the click sequence automatically.

### 4. Stage-based error recovery + observability
Every major action is labelled with a `current_stage` string. On any exception, the scraper captures screenshots from all open tabs before propagating the error, giving a precise trace of exactly what the portal was showing at the moment of failure.

### 5. Credential security
All credentials are loaded from **environment variables** — never hardcoded. See `.env.example` for the required variables. The `.gitignore` additionally blocks output directories (which contain real tax documents) and any `.env` file.

---

## Test Coverage

The project includes a three-layer test suite matching the unit → integration → E2E pyramid:

| File | Layer | What it tests | Credentials needed? |
|---|---|---|---|
| `tests/test_crypto_utils.py` | Unit | `decrypt_pdf` happy/negative/boundary, `process_client_files` cleanup | ❌ No |
| `tests/test_api.py` | Integration | FastAPI contract: schema, 422 validation, state | ❌ No |
| `tests/test_login.py` | E2E (Playwright) | Login happy path, dual-login bypass, invalid PAN boundary | ✅ Yes |

**Test design techniques used:**
- **Equivalence partitioning**: valid/invalid PAN, correct/incorrect PDF password
- **Boundary analysis**: unencrypted PDF (boundary of decrypt logic), empty clients list
- **Negative testing**: wrong password, non-existent file, missing required fields

---

## CI/CD Pipeline

The GitHub Actions workflow (`.github/workflows/ci.yml`) runs on every push and pull request:

```
Push / PR
    │
    ▼
[lint] ruff check
    │
    ▼
[unit-tests] pytest test_crypto_utils.py test_api.py
    │  (no browser, no credentials — safe for fork PRs)
    ▼
[e2e-tests] pytest test_login.py   ← secrets-gated, Playwright
    │
    ▼
Upload failure screenshots as artifacts
```

---

## Setup

### Prerequisites
- Python 3.9+
- Node.js 18+ (for frontend only)

### Installation

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install all dependencies (including test tools)
pip install -r requirements.txt

# 3. Install Playwright browser binaries
playwright install chromium

# 4. Configure credentials
cp .env.example .env
# Edit .env with your IT portal PAN, password, and DOB
```

### Running the Application

```bash
# Start the FastAPI backend
python server.py

# In a separate terminal, start the React frontend
cd frontend && npm install && npm run dev
```

The frontend will be available at `http://localhost:5173`.

### Running Tests

```bash
# Unit + API tests (no credentials required)
pytest tests/test_crypto_utils.py tests/test_api.py -v

# E2E tests (requires IT portal credentials in environment)
export IT_PAN=YOURPAN
export IT_PASSWORD=yourpassword
export IT_DOB=ddmmyyyy
pytest tests/test_login.py -v

# Full suite with coverage
pytest tests/ -v --cov=. --cov-report=term-missing
```

---

## Project Structure

```
.
├── scraper.py           # Core Playwright automation (login → TRACES → AIS)
├── server.py            # FastAPI REST API + background batch queue
├── crypto_utils.py      # PDF/ZIP decryption with PAN+DOB keys
├── config.py            # Portal URLs, timeouts, assessment year
├── utils.py             # Logging setup, directory helpers
├── main.py              # CLI entry point for single-run mode
├── tests/
│   ├── conftest.py      # Shared pytest fixtures (browser context, credentials)
│   ├── test_login.py    # E2E login flow tests (Playwright)
│   ├── test_api.py      # API contract tests (FastAPI TestClient)
│   └── test_crypto_utils.py  # Unit tests for decryption logic
├── frontend/            # React + Vite UI (upload → configure → process)
├── .github/
│   └── workflows/
│       └── ci.yml       # 3-stage CI: lint → unit → E2E
├── .env.example         # Credential template (no real values)
├── requirements.txt     # Python dependencies
└── .gitignore
```

---

## Output

For each client processed, the following files are saved to `output/<fileNo>/`:

| File | Content |
|---|---|
| `<PAN>_html.pdf` | Form 26AS — HTML export as PDF |
| `<PAN>_text.txt` | Form 26AS — raw text |
| `<PAN>_ais.pdf` | Annual Information Statement (decrypted) |
| `<PAN>_tis.pdf` | Taxpayer Information Summary (decrypted) |

Error screenshots (e.g. `<PAN>_error_page.png`) are saved automatically when any stage fails.

Structured logs are written to `run.log` and streamed live via `/api/logs`.
