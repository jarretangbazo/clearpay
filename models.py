# models.py
from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
from database import Base

class Merchant(Base):
    __tablename__ = "merchants"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    phone = Column(String, unique=True, index=True)
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
    phone = Column(String)
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



