from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List
from uuid import uuid4, UUID
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Float, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import random
import smtplib
import logging

# --- Config ---
DATABASE_URL = "sqlite:///./transactions.db"  # Replace with PostgreSQL URL in production
EMAIL_ALERTS_ENABLED = False  # Set True to enable email alerts
ALERT_EMAIL = "alert@example.com"

# --- Logger ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- FastAPI App ---
app = FastAPI()

# --- SQLAlchemy Setup ---
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Database Model ---
class TransactionDB(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String)
    amount = Column(Float)
    currency = Column(String)
    timestamp = Column(DateTime)
    merchant = Column(String)
    location = Column(String)
    category = Column(String)
    is_fraud = Column(Boolean, default=False)

Base.metadata.create_all(bind=engine)

# --- Pydantic Schema ---
class Transaction(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: str
    amount: float
    currency: str
    timestamp: datetime
    merchant: str
    location: str
    category: str
    is_fraud: bool = False

# --- Fraud Detection ---
def detect_fraud(transaction: Transaction) -> bool:
    if transaction.amount > 10000:
        return True
    if transaction.location not in ["Cape Town", "Johannesburg", "Durban"]:
        return True
    return False

# --- Email Notification ---
def send_email_alert(transaction: Transaction):
    if not EMAIL_ALERTS_ENABLED:
        return
    try:
        with smtplib.SMTP('localhost') as smtp:
            message = f"Subject: Fraud Alert\n\nTransaction flagged as fraud:\n{transaction}"
            smtp.sendmail("from@example.com", ALERT_EMAIL, message)
    except Exception as e:
        logger.error(f"Failed to send email: {e}")

# --- API Routes ---
@app.post("/transactions", response_model=Transaction)
def submit_transaction(tx: Transaction, background_tasks: BackgroundTasks):
    tx.is_fraud = detect_fraud(tx)
    db = SessionLocal()
    db_tx = TransactionDB(
        id=str(tx.id), user_id=tx.user_id, amount=tx.amount, currency=tx.currency,
        timestamp=tx.timestamp, merchant=tx.merchant, location=tx.location,
        category=tx.category, is_fraud=tx.is_fraud
    )
    db.add(db_tx)
    db.commit()
    db.close()
    if tx.is_fraud:
        background_tasks.add_task(send_email_alert, tx)
    return tx

@app.get("/transactions", response_model=List[Transaction])
def get_transactions():
    db = SessionLocal()
    db_tx = db.query(TransactionDB).all()
    db.close()
    return [Transaction(**t.__dict__) for t in db_tx]

@app.get("/transactions/{tx_id}", response_model=Transaction)
def get_transaction(tx_id: UUID):
    db = SessionLocal()
    tx = db.query(TransactionDB).filter(TransactionDB.id == str(tx_id)).first()
    db.close()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return Transaction(**tx.__dict__)

# --- Simulate Transactions ---
@app.post("/simulate")
def simulate_transactions(n: int = 5):
    merchants = ["Uber", "Checkers", "Takealot", "Netflix", "Woolworths"]
    locations = ["Cape Town", "Johannesburg", "London"]
    categories = ["Transport", "Groceries", "Entertainment", "Shopping"]
    db = SessionLocal()
    for _ in range(n):
        tx = Transaction(
            user_id=str(random.randint(100, 999)),
            amount=round(random.uniform(10, 20000), 2),
            currency="ZAR",
            timestamp=datetime.utcnow(),
            merchant=random.choice(merchants),
            location=random.choice(locations),
            category=random.choice(categories)
        )
        tx.is_fraud = detect_fraud(tx)
        db_tx = TransactionDB(**tx.dict())
        db.add(db_tx)
    db.commit()
    db.close()
    return {"message": f"{n} transactions simulated."}

# --- Smart Finance Insights ---
@app.get("/insights/{user_id}")
def user_insights(user_id: str):
    db = SessionLocal()
    txs = db.query(TransactionDB).filter(TransactionDB.user_id == user_id).all()
    db.close()

    total_spent = sum(t.amount for t in txs)
    by_category = {}
    recurring = {}

    for t in txs:
        by_category[t.category] = by_category.get(t.category, 0) + t.amount
        recurring[t.merchant] = recurring.get(t.merchant, 0) + 1

    common_merchants = [m for m, count in recurring.items() if count > 2]

    return {
        "user_id": user_id,
        "total_spent": total_spent,
        "by_category": by_category,
        "recurring_merchants": common_merchants,
        "advice": "Consider budgeting for high-spend categories like " + max(by_category, key=by_category.get)
    }
