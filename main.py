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
    """Register a new merchant"""
    merchant = Merchant(name = name, phone = phone)
    db.add(merchant)
    db.commit()
    db.refresh(merchant)
    return {"message": "Merchant registered", "merchant_id": merchant.id}

@app.post("/pay")
def initiate(merchant_id: int, customer_phone: str, amount: float,
             db: Session = Depends(get_db)):
    """
    Merchant initiates a payment from a customer.
    Returns fee breakdown + PayStack checkout URL
    """
    merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
    if not merchant:
        raise HTTPException(status_code = 404, detail = "Merchant not found")
    
    fee_info = paystack.calculate_fee(amount)
    reference = f"CP-{uuid.uuid4().hex[:10].upper()}"

    result = paystack.initiate_payment(
        phone = customer_phone,
        amount_ngn = amount,
        reference = reference
    )

    # Save a pending transaction immediately
    txn = Transaction(
        merchant_id = merchant_id,
        amount = amount,
        fee = fee_info["fee"],
        net = fee_info["net"],
        reference = reference,
        status = "pending"
    )
    db.add(txn)
    db.commit()

    return{
        "fee_breakdown": fee_info,
        "checkout_url": result["data"]["authorization_url"],
        "reference": reference
    }

@app.post("/webhook")
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    """
    PayStack calls this after a payment.
    We verify the signature, then update the transaction record.
    """
    body = await request.body()
    signature = request.headers.get("x-paystack-signature")

    # Security check: verify this is really from PayStack
    expected = hmac.new(
        PAYSTACK_SECRET.encode(), body, hashlib.sha512
    ).hexdigest()

    if signature != expected:
        raise HTTPException(status_code = 401, detail = "Invalid sigature")
    
    payload = await request.json()

    if payload["event"] == "charge.success":
        data = payload["data"]
        ref = data["reference"]

        # Find the pending transaction and mark it succesful
        txn = db.query(Transaction).filter(Transaction.reference == ref).first()
        if txn:
            txn.status = "success"
            db.commit()

    return {"status": "ok"}


# Recurring Worker Wage Payments
## Register a Worker
@app.post("/workers")
def register_worker(merchant_id: str, name: str, phone: str,
                    weekly_wage: float, db: Session = Depends(get_db)):
    """Merchant registers a worker with their phone number and agreed weekly wage"""
    worker = Worker(
        merchant_id = merchant_id,
        name = name,
        phone = phone,
        weekly_wage = weekly_wage
    )
    db.add(worker)
    db.commit()
    db.refresh(worker)
    return {"message": "Worker registered", "worker_id": worker.id}

# Trigger a wage payment to a worker (simulated in sandbox)
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

# Worker Income Record - the portfolio centerpiece for worker credit signals
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

# Merchant credit profile - the portfolio centerpiece for merchant credit signals
## Revenue summary for a merchant
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

# Credit profile - the headline endpoint
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