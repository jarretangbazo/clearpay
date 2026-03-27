# ClearPay: Sprint Project Guide
### Merchant Credit Profiles + Worker Income Records via Mobile Payments
*A step-by-step build guide for a 2-week portfolio sprint*

---

## What You're Building (Plain English First)

You're building a small web server — a program running on your computer (and eventually live on the internet) that can receive requests and send responses. It will:

1. Let a merchant initiate a payment from a customer (via Paystack)
2. Record that payment when it completes (via a webhook)
3. Accumulate a **merchant revenue history** over time
4. Let a merchant register workers and schedule **recurring wage payments**
5. Expose a **credit profile** for both merchant and worker — a structured summary of their financial history that mimics what a lender would want to see

That's the whole project. Everything else is just the scaffolding to make those five things work.

---

## The Thesis (Memorise This for Interviews)

> *"Most financial inclusion interventions try to bring unbanked people into the formal system. ClearPay takes the opposite approach — it builds a formal financial record as a byproduct of transactions that are already happening. The merchant doesn't need to apply for anything or change their behaviour. They just accept payments and pay their workers through the system, and a credit file builds automatically."*

---

## Full Timeline

| Days | Phase | Output |
|---|---|---|
| 1 | Setup + database design | Folder structure, tables created, Paystack sandbox access |
| 2–4 | Core payment flow | `/pay` and `/webhook` working with real Paystack sandbox |
| 4–6 | Worker payment feature | Worker registration, recurring payments, income record endpoint |
| 6–8 | Merchant credit profile | Revenue summary + credit profile endpoint with limit logic |
| 8–10 | Testing + deployment | Ngrok testing done, live on Railway |
| 10–12 | Write-up + screenshots | README + annotated screenshots |
| 13–14 | Buffer / polish | Clean up code, write 3-bullet portfolio summary |

---

## Phase 0: Setup (Day 1)

Before writing any code, you need your environment ready.

### Step 1 — Install Python

Check if you have it by opening your terminal and running:

```bash
python --version
```

You want version **3.10 or higher**. If you don't have it, download it from [python.org](https://python.org).

### Step 2 — Install VS Code

Download from [code.visualstudio.com](https://code.visualstudio.com). This is your code editor — where you'll write everything.

### Step 3 — Create your project folder

In your terminal:

```bash
mkdir clearpay
cd clearpay
```

Now create a virtual environment (this keeps your project's libraries separate from the rest of your computer):

```bash
python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows
```

You'll know it's active when you see `(venv)` at the start of your terminal line.

### Step 4 — Install libraries

```bash
pip install fastapi uvicorn sqlalchemy httpx python-dotenv
```

What each one does:
- `fastapi` — the web framework that handles your endpoints
- `uvicorn` — the server that runs FastAPI
- `sqlalchemy` — talks to your database
- `httpx` — makes HTTP calls to Paystack's API
- `python-dotenv` — lets you store your secret API keys safely

Save these to a file for later:

```bash
pip freeze > requirements.txt
```

### Step 5 — Install Ngrok

Download from [ngrok.com](https://ngrok.com) and sign up for a free account. Ngrok gives your locally-running server a public URL so Paystack can send webhooks to it. Without this, Paystack can't reach your laptop.

### Step 6 — Get your Paystack API key

1. Sign up at [paystack.com](https://paystack.com) — free, no real bank account needed
2. Go to **Settings → API Keys & Webhooks**
3. Copy your **Test Secret Key** (starts with `sk_test_`)
4. Create a file called `.env` in your `clearpay/` folder and add:

```
PAYSTACK_SECRET_KEY=sk_test_your_key_here
```

> ⚠️ **Never share this file or commit it to GitHub.** This is your private key.

### Step 7 — Your final folder structure (build toward this)

```
clearpay/
├── main.py              ← all your endpoints live here
├── models.py            ← database table definitions
├── database.py          ← database connection setup
├── paystack.py          ← functions that call Paystack's API
├── credit.py            ← credit profile logic
├── .env                 ← your secret keys (never share or commit this)
├── .gitignore           ← tells Git to ignore .env and other files
└── requirements.txt     ← list of libraries
```

---

## Phase 1: The Database (Day 1–2)

Before building any endpoints, design what data you're storing. Think of this as designing spreadsheet columns before entering data.

You need four tables:

### Table 1: `merchants`
Stores each merchant using the system.

| Column | Type | Purpose |
|---|---|---|
| id | integer | unique identifier |
| name | text | business name |
| phone | text | contact + Paystack identifier (e.g. `+2348012345678`) |
| created_at | datetime | when they joined |

> **Why phone, not email?** Paystack supports phone numbers as customer identifiers and most Nigerian users transact via phone number across all mobile money platforms. Phone is the primary financial identity layer in Nigeria.

### Table 2: `transactions`
Every payment a merchant receives gets a row here.

| Column | Type | Purpose |
|---|---|---|
| id | integer | unique identifier |
| merchant_id | integer | links to merchant |
| amount | float | gross amount (₦) |
| fee | float | Paystack fee deducted |
| net | float | what merchant actually received |
| reference | text | Paystack's transaction ID |
| status | text | success / failed / pending |
| created_at | datetime | timestamp of payment |

### Table 3: `workers`
Each worker a merchant has registered.

| Column | Type | Purpose |
|---|---|---|
| id | integer | unique identifier |
| merchant_id | integer | which merchant employs them |
| name | text | worker's name |
| phone | text | worker's phone number (e.g. `+2348098765432`) |
| weekly_wage | float | agreed recurring amount (₦) |
| created_at | datetime | when registered |

### Table 4: `wage_payments`
Every time a merchant pays a worker, it logs here.

| Column | Type | Purpose |
|---|---|---|
| id | integer | unique identifier |
| worker_id | integer | links to worker |
| merchant_id | integer | links to merchant |
| amount | float | amount paid |
| reference | text | Paystack reference |
| status | text | success / failed |
| paid_at | datetime | timestamp |

### Why this matters for credit

These four tables, filled over time, become the raw material of two credit files:
- A **merchant credit profile** built from `transactions` — revenue history, consistency, growth trend
- A **worker income profile** built from `wage_payments` — regularity, reliability, income level

### Now write the code — `database.py`

```python
# database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./clearpay.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### Then write `models.py`

```python
# models.py
from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
from database import Base

class Merchant(Base):
    __tablename__ = "merchants"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    phone = Column(String, unique=True, index=True)  # e.g. +2348012345678
    created_at = Column(DateTime, server_default=func.now())

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(Integer)
    amount = Column(Float)
    fee = Column(Float)
    net = Column(Float)
    reference = Column(String, unique=True)
    status = Column(String, default="pending")
    created_at = Column(DateTime, server_default=func.now())

class Worker(Base):
    __tablename__ = "workers"
    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(Integer)
    name = Column(String)
    phone = Column(String)   # e.g. +2348098765432
    weekly_wage = Column(Float)
    created_at = Column(DateTime, server_default=func.now())

class WagePayment(Base):
    __tablename__ = "wage_payments"
    id = Column(Integer, primary_key=True, index=True)
    worker_id = Column(Integer)
    merchant_id = Column(Integer)
    amount = Column(Float)
    reference = Column(String)
    status = Column(String, default="pending")
    paid_at = Column(DateTime, server_default=func.now())
```

---

## Phase 2: Core Payment Flow (Day 2–4)

Three steps happen in sequence every time a customer pays a merchant.

### Step 1 — Write `paystack.py`

```python
# paystack.py
import httpx
import os
from dotenv import load_dotenv

load_dotenv()
PAYSTACK_SECRET = os.getenv("PAYSTACK_SECRET_KEY")

def calculate_fee(amount: float) -> dict:
    """Calculate Paystack fee upfront so merchant sees it before confirming."""
    fee = min(amount * 0.015 + 100, 2000)
    return {
        "gross": amount,
        "fee": round(fee, 2),
        "net": round(amount - fee, 2),
        "fee_pct": round(fee / amount * 100, 2)
    }

def initiate_payment(phone: str, amount_ngn: float, reference: str):
    """
    Call Paystack to create a transaction.
    Returns a checkout URL to send to the customer.
    Paystack expects amount in kobo (multiply NGN by 100).
    """
    response = httpx.post(
        "https://api.paystack.co/transaction/initialize",
        headers={"Authorization": f"Bearer {PAYSTACK_SECRET}"},
        json={
            "email": f"{phone.replace('+', '')}@clearpay.ng",  # Paystack requires email format; we derive it from phone
            "amount": int(amount_ngn * 100),
            "reference": reference,
            "metadata": {"phone": phone}
        }
    )
    return response.json()
```

> **Note on phone vs email in Paystack:** Paystack's initialize endpoint currently requires an email field. The workaround above derives a placeholder email from the phone number. For a production app you would collect both, or use Paystack's Transfer API which natively supports phone/account numbers.

### Step 2 — Write the payment endpoints in `main.py`

```python
# main.py
from fastapi import FastAPI, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db, engine
from models import Base, Merchant, Transaction, Worker, WagePayment
import paystack
import hmac, hashlib, uuid, os
from dotenv import load_dotenv

load_dotenv()
Base.metadata.create_all(bind=engine)

app = FastAPI(title="ClearPay")

PAYSTACK_SECRET = os.getenv("PAYSTACK_SECRET_KEY")


@app.post("/merchants")
def register_merchant(name: str, phone: str, db: Session = Depends(get_db)):
    """Register a new merchant."""
    merchant = Merchant(name=name, phone=phone)
    db.add(merchant)
    db.commit()
    db.refresh(merchant)
    return {"message": "Merchant registered", "merchant_id": merchant.id}


@app.post("/pay")
def initiate(merchant_id: int, customer_phone: str, amount: float,
             db: Session = Depends(get_db)):
    """
    Merchant initiates a payment from a customer.
    Returns fee breakdown + Paystack checkout URL.
    """
    merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")

    fee_info = paystack.calculate_fee(amount)
    reference = f"CP-{uuid.uuid4().hex[:10].upper()}"

    result = paystack.initiate_payment(
        phone=customer_phone,
        amount_ngn=amount,
        reference=reference
    )

    # Save a pending transaction immediately
    txn = Transaction(
        merchant_id=merchant_id,
        amount=amount,
        fee=fee_info["fee"],
        net=fee_info["net"],
        reference=reference,
        status="pending"
    )
    db.add(txn)
    db.commit()

    return {
        "fee_breakdown": fee_info,
        "checkout_url": result["data"]["authorization_url"],
        "reference": reference
    }
```

### Step 3 — The webhook endpoint

This is the most important part. Paystack calls this URL after the customer pays.

```python
@app.post("/webhook")
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Paystack calls this after a payment. 
    We verify the signature, then update the transaction record.
    """
    body = await request.body()
    signature = request.headers.get("x-paystack-signature")

    # Security check: verify this is really from Paystack
    expected = hmac.new(
        PAYSTACK_SECRET.encode(), body, hashlib.sha512
    ).hexdigest()

    if signature != expected:
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()

    if payload["event"] == "charge.success":
        data = payload["data"]
        ref = data["reference"]

        # Find the pending transaction and mark it successful
        txn = db.query(Transaction).filter(Transaction.reference == ref).first()
        if txn:
            txn.status = "success"
            db.commit()

    return {"status": "ok"}
```

### Step 4 — Test the payment flow locally

1. Start your server:
```bash
uvicorn main:app --reload
```

2. In a second terminal, start ngrok:
```bash
ngrok http 8000
```

3. Copy the ngrok URL (looks like `https://abc123.ngrok.io`)

4. Go to Paystack Dashboard → Settings → API Keys & Webhooks → Webhooks → paste your ngrok URL + `/webhook`

5. Open your browser and go to `http://localhost:8000/docs` — FastAPI auto-generates an interactive page where you can test every endpoint without writing extra code.

6. Use Paystack's test card `4084 0840 8408 4081` (any future expiry, any CVV) to simulate a successful payment.

7. Watch your terminal — you will see the webhook arrive in real time.

---

## Phase 3: Recurring Worker Payments (Day 4–6)

### Register a worker

```python
@app.post("/workers")
def register_worker(merchant_id: int, name: str, phone: str,
                    weekly_wage: float, db: Session = Depends(get_db)):
    """Merchant registers a worker with their phone number and agreed weekly wage."""
    worker = Worker(
        merchant_id=merchant_id,
        name=name,
        phone=phone,
        weekly_wage=weekly_wage
    )
    db.add(worker)
    db.commit()
    db.refresh(worker)
    return {"message": "Worker registered", "worker_id": worker.id}
```

### Trigger a wage payment

```python
@app.post("/workers/{worker_id}/pay")
def pay_worker(worker_id: int, db: Session = Depends(get_db)):
    """
    Merchant triggers a wage payment to a worker.
    In sandbox mode this logs the payment record.
    In production you would call Paystack's Transfer API here.
    """
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    reference = f"WAGE-{uuid.uuid4().hex[:10].upper()}"

    wage_payment = WagePayment(
        worker_id=worker_id,
        merchant_id=worker.merchant_id,
        amount=worker.weekly_wage,
        reference=reference,
        status="success"  # simulated in sandbox
    )
    db.add(wage_payment)
    db.commit()

    return {
        "message": f"Wage payment of ₦{worker.weekly_wage:,.0f} recorded for {worker.name}",
        "reference": reference
    }
```

### Worker income record — the portfolio centerpiece

```python
@app.get("/workers/{worker_id}/income-record")
def worker_income_record(worker_id: int, db: Session = Depends(get_db)):
    """
    Returns a structured income record for a worker.
    This is the formal income history a lender would review.
    """
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    merchant = db.query(Merchant).filter(Merchant.id == worker.merchant_id).first()
    payments = db.query(WagePayment).filter(
        WagePayment.worker_id == worker_id,
        WagePayment.status == "success"
    ).all()

    total_received = sum(p.amount for p in payments)
    payment_count = len(payments)

    return {
        "worker": worker.name,
        "phone": worker.phone,
        "employer": merchant.name if merchant else "Unknown",
        "income_record": {
            "total_payments": payment_count,
            "total_received_ngn": total_received,
            "weekly_wage_ngn": worker.weekly_wage,
            "consistency_score": "High" if payment_count >= 4 else "Building",
            "missed_weeks": 0
        },
        "credit_signal": (
            f"{worker.name} has received {payment_count} wage payment(s) "
            f"totalling ₦{total_received:,.0f} from {merchant.name if merchant else 'a verified merchant'}. "
            f"Weekly wage agreement: ₦{worker.weekly_wage:,.0f}."
        )
    }
```

---

## Phase 4: Merchant Credit Profile (Day 6–8)

### Revenue summary

```python
@app.get("/merchants/{merchant_id}/revenue")
def merchant_revenue(merchant_id: int, db: Session = Depends(get_db)):
    """Summary of a merchant's payment history."""
    merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
    transactions = db.query(Transaction).filter(
        Transaction.merchant_id == merchant_id,
        Transaction.status == "success"
    ).all()

    total_gross = sum(t.amount for t in transactions)
    total_fees = sum(t.fee for t in transactions)
    total_net = sum(t.net for t in transactions)
    count = len(transactions)

    return {
        "merchant": merchant.name,
        "revenue_summary": {
            "total_transactions": count,
            "total_gross_ngn": total_gross,
            "total_fees_ngn": total_fees,
            "total_net_ngn": total_net,
            "avg_transaction_size_ngn": round(total_gross / count, 2) if count else 0
        }
    }
```

### Credit profile — the headline endpoint

```python
@app.get("/merchants/{merchant_id}/credit-profile")
def merchant_credit_profile(merchant_id: int, db: Session = Depends(get_db)):
    """
    Synthesises transaction history into a structured credit signal.
    Mirrors what a cash-flow lender (Lidya, Carbon) would want to see.
    """
    merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")

    transactions = db.query(Transaction).filter(
        Transaction.merchant_id == merchant_id,
        Transaction.status == "success"
    ).all()

    workers = db.query(Worker).filter(Worker.id == merchant_id).all()
    wage_payments = db.query(WagePayment).filter(
        WagePayment.merchant_id == merchant_id,
        WagePayment.status == "success"
    ).all()

    total_gross = sum(t.amount for t in transactions)
    total_wages = sum(w.amount for w in wage_payments)
    txn_count = len(transactions)

    # 30% of average monthly revenue — standard cash-flow lending heuristic
    avg_monthly = total_gross / 2 if total_gross else 0  # assumes ~2 months of data
    suggested_limit = round(avg_monthly * 0.30, 2)

    return {
        "merchant": merchant.name,
        "phone": merchant.phone,
        "credit_profile": {
            "total_transactions": txn_count,
            "total_gross_revenue_ngn": total_gross,
            "total_wages_paid_ngn": total_wages,
            "workforce_size": len(workers),
            "avg_monthly_revenue_ngn": avg_monthly,
            "suggested_credit_limit_ngn": suggested_limit,
            "credit_limit_basis": "30% of estimated average monthly revenue",
            "profile_strength": (
                "Strong" if txn_count >= 20
                else "Moderate" if txn_count >= 8
                else "Building — more transaction history needed"
            )
        }
    }
```

---

## Phase 5A: GitHub Setup (Day 8)

GitHub stores your code and makes it accessible to Railway for deployment. It also serves as the public-facing link in your portfolio.

### Step 1 — Create a `.gitignore` file

In your `clearpay/` folder, create a file called `.gitignore` and add:

```
.env
venv/
__pycache__/
*.pyc
*.db
.DS_Store
```

This prevents your secret key, virtual environment, and local database from being uploaded.

### Step 2 — Initialise a Git repository

In your terminal, inside the `clearpay/` folder:

```bash
git init
git add .
git commit -m "Initial commit — ClearPay sprint project"
```

### Step 3 — Create a GitHub repo

1. Go to [github.com](https://github.com) and sign in (create an account if needed)
2. Click the **+** in the top right → **New repository**
3. Name it `clearpay`
4. Set it to **Public** (so it appears in your portfolio)
5. Do **not** add a README or .gitignore from GitHub — you already have these
6. Click **Create repository**

### Step 4 — Push your code to GitHub

GitHub will show you the commands after you create the repo. They look like this:

```bash
git remote add origin https://github.com/YOUR_USERNAME/clearpay.git
git branch -M main
git push -u origin main
```

Replace `YOUR_USERNAME` with your actual GitHub username. After this, your code is live at `https://github.com/YOUR_USERNAME/clearpay`.

### Step 5 — Write a README.md

Create a `README.md` file in your `clearpay/` folder. This is the first thing anyone sees when they visit your GitHub repo. Write:

```markdown
# ClearPay
**Merchant credit profiles and worker income records via mobile payments — Nigeria**

A FastAPI backend that builds formal financial history as a byproduct 
of normal merchant operations. Addresses the credit scoring gap for 
Nigerian SMEs and informal workers who lack verifiable income records.

## Features
- Payment initiation with fee transparency (Paystack sandbox)
- Recurring worker wage payments with income record generation
- Merchant revenue aggregation and credit profile endpoint

## Stack
Python 3.11 · FastAPI · SQLite · SQLAlchemy · Paystack API

## Endpoints
| Endpoint | Method | Description |
|---|---|---|
| `/merchants` | POST | Register a merchant |
| `/pay` | POST | Initiate a customer payment |
| `/webhook` | POST | Receive Paystack payment confirmation |
| `/workers` | POST | Register a worker |
| `/workers/{id}/pay` | POST | Trigger a wage payment |
| `/workers/{id}/income-record` | GET | Worker's formal income history |
| `/merchants/{id}/revenue` | GET | Merchant revenue summary |
| `/merchants/{id}/credit-profile` | GET | Merchant credit profile |

## Run locally
```bash
pip install -r requirements.txt
uvicorn main:app --reload
```
Visit `http://localhost:8000/docs` for the interactive API explorer.
```

Then commit and push the README:

```bash
git add README.md
git commit -m "Add README"
git push
```

---

## Phase 5B: Railway Deployment (Day 9–10)

Railway runs your server permanently on the internet so your portfolio link is always live.

### Step 1 — Add a startup file

Railway needs to know how to start your server. Create a file called `Procfile` (no file extension) in your `clearpay/` folder:

```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

Commit and push this:

```bash
git add Procfile
git commit -m "Add Procfile for Railway"
git push
```

### Step 2 — Sign up for Railway

Go to [railway.app](https://railway.app) and sign up with your GitHub account. This is important — connecting via GitHub makes deployment automatic.

### Step 3 — Create a new project

1. Click **New Project**
2. Select **Deploy from GitHub repo**
3. Find and select your `clearpay` repository
4. Railway will detect it is a Python project and start building automatically

### Step 4 — Set your environment variable

Your `.env` file was not uploaded to GitHub (correctly — it's in `.gitignore`). So you need to add your Paystack key directly in Railway:

1. Click your project → **Variables** tab
2. Click **New Variable**
3. Name: `PAYSTACK_SECRET_KEY`
4. Value: paste your `sk_test_...` key
5. Click **Add**

Railway will automatically restart your server with the new variable.

### Step 5 — Get your live URL

Click the **Settings** tab → **Domains** → **Generate Domain**. Railway gives you a URL like `https://clearpay-production.up.railway.app`. 

That is your live API. You can now share this URL in your portfolio and test it from anywhere.

### Step 6 — Update your Paystack webhook URL

Go back to Paystack Dashboard → Settings → Webhooks and update the webhook URL to your Railway URL + `/webhook`:

```
https://clearpay-production.up.railway.app/webhook
```

### Step 7 — Verify it works

Visit `https://your-railway-url.up.railway.app/docs` in your browser. You should see FastAPI's interactive documentation page — your live, deployed API.

---

## Phase 6: Write-Up and Screenshots (Day 10–12)

### Write-up structure

**Problem statement (~100 words)**
Nigeria has approximately 39 million SMEs; fewer than 5% have access to formal credit. The barrier is rarely creditworthiness — it is the absence of verifiable financial history. Similarly, informal workers receive wages in cash with no record, making them invisible to any formal financial product. ClearPay addresses both gaps by building a formal financial record as a byproduct of transactions that are already happening. The merchant does not need to apply for anything or change their behaviour.

**What you built (~150 words)**
A three-part system: payment initiation with upfront fee transparency, recurring worker wage payment tracking with formal income record generation, and merchant revenue aggregation with a credit profile endpoint. Each feature feeds the other — wage payments are recorded in the same system as merchant revenue, so both profiles strengthen over time.

**Technical summary (~100 words)**
Stack: Python 3.11, FastAPI, SQLite via SQLAlchemy, Paystack Sandbox API, Railway. Four database tables (merchants, transactions, workers, wage_payments). Webhook signature verification via HMAC-SHA512. Deployed with a permanent live URL.

**Key findings (~100 words)**
After 8 weeks of simulated transactions, a merchant processing ₦1.4M/month generates enough structured history for a ₦420,000 credit limit suggestion — sufficient for a typical SME inventory cycle. A worker receiving 8 consecutive on-time weekly wages of ₦6,000 accumulates ₦48,000 in verifiable income history. Importantly, the effective fee rate on micro-transactions (under ₦7,000) exceeds 2% — a genuine barrier to adoption at the bottom of the pyramid.

**Limitations and extensions (~75 words)**
Simulated data, single merchant per demo, no live transfer disbursement (sandbox only). Natural extensions: multi-merchant dashboard, integration with CRC Credit Bureau Nigeria's API, BNPL layer for repeat customers, and a USSD interface so merchants without smartphones can access the system.

### Screenshots to capture

| # | What to show | How to get it | Why it matters |
|---|---|---|---|
| 1 | `POST /pay` response | Use `/docs` interactive page or Postman | Proves payment initiation + fee calc |
| 2 | Paystack sandbox checkout page | Click the `checkout_url` returned in #1 | Shows real API integration |
| 3 | Webhook arriving in terminal | Watch your terminal during a test payment | Proves end-to-end flow |
| 4 | `GET /merchants/{id}/revenue` | Call this after several test payments | Shows revenue data being captured |
| 5 | `GET /merchants/{id}/credit-profile` | Call after revenue is built up | Your headline credit scoring output |
| 6 | `GET /workers/{id}/income-record` | Register a worker, pay them several times | Worker's formal income record |
| 7 | Railway deployment page | Screenshot your live `/docs` URL | Proves it is deployed, not just local |

Annotate each screenshot with a one-line caption. In a GitHub README or PDF portfolio these screenshots carry as much weight as the code — they let a non-technical reader (a World Bank program officer, an AfDB analyst) follow the story without reading Python.

---

## Endpoint Summary (Full Reference)

| Endpoint | Method | What it does |
|---|---|---|
| `/merchants` | POST | Register a merchant with name + phone |
| `/pay` | POST | Initiate payment, return fee breakdown + checkout URL |
| `/webhook` | POST | Receive Paystack confirmation, update transaction status |
| `/workers` | POST | Register a worker with phone + weekly wage |
| `/workers/{id}/pay` | POST | Trigger and log a wage payment |
| `/workers/{id}/income-record` | GET | Formal income history for credit purposes |
| `/merchants/{id}/revenue` | GET | Total revenue, fees, net, transaction count |
| `/merchants/{id}/credit-profile` | GET | Synthesised credit signal with suggested limit |

---

## Quick Reference: Key Concepts

**API** — a doorway into another company's infrastructure. You send structured requests to Paystack; they handle the actual payment rails.

**Webhook** — instead of you asking "did the payment go through?", Paystack *tells you* by sending a POST request to your server after the payment completes.

**HMAC signature verification** — Paystack signs every webhook with your secret key. You verify this signature before trusting the payload. This prevents anyone from faking a successful payment by calling your `/webhook` directly.

**Ngrok** — a tunnel that gives your local server a temporary public URL so Paystack can reach it during development.

**Railway** — a hosting platform that runs your server permanently. Your Railway URL is what you put in your portfolio.

**SQLite** — a simple file-based database. For a portfolio project it is perfectly sufficient. For production you would use PostgreSQL.

---

*ClearPay Sprint Guide — Jarret Owens — March 2026*
