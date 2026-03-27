# ClearPay
**Merchant credit profiles and worker income records via mobile payments**

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