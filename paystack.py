# paystack.py
# Note: PayStack's initialize endpoint currently requires an email field. The workaround below derives a placeholder email from
# the phone number. For a production app, we would collect both or use PayStack's Transfer API which natively supports phone/account 
# numbers 
import httpx
import os
from dotenv import load_dotenv

load_dotenv()
PAYSTACK_SECRET = os.getenv("PAYSTACK_SECRET_KEY")

def calculate_fee(amount: float) -> dict:
    """Calculate PayStack fee upfront so merchant sees it before confirming."""
    fee = min(amount * 0.015 + 100, 2000)
    return {
        "gross": amount,
        "fee": round(fee, 2),
        "net": round(amount - fee, 2),
        "fee_pct": round(fee / amount * 100, 2)
    }


def initiate_payment(phone: str, amount_ngn: float, reference: str):
    """
    Call PayStack to create a transaction.
    Returns a checkout URL to send to the customer.
    PayStack expects an amount in kobo (multiply NGN by 100).
    """
    response = httpx.post(
        "https://api.paystack.co/transaction/initialize",
        headers = {"Authorization": f"Bearer {PAYSTACK_SECRET}"},
        json = {
            "email": f"{phone.replace('+', '')}@clearpay.ng",           
            "amount": int(amount_ngn * 100),
            "reference": reference,
            "metadata": {"phone": phone}
        }
    )
    return response.json()

