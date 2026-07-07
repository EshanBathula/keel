"""Seed a demo account with 12 months of realistic data.

Run (after `alembic upgrade head`):  python -m app.seed
Login: demo@keel.app / demopassword
"""
import random
from datetime import date, timedelta

from .auth import hash_password
from .database import SessionLocal
from .models import Customer, Invoice, InvoiceStatus, Transaction, TxType, User

random.seed(7)

CUSTOMERS = ["Harbor Coffee Co.", "Northline Studio", "Brightpath Dental", "Cedar & Main",
             "Vela Fitness", "Kite Analytics"]
EXPENSE_CATS = {"Payroll": 5200, "Rent": 1800, "Software": 420, "Marketing": 900,
                "Supplies": 350, "Utilities": 260, "Insurance": 310}


def run():
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == "demo@keel.app").first()
        if existing:
            print("Demo account already exists — skipping.")
            return
        user = User(email="demo@keel.app", password_hash=hash_password("demopassword"),
                    business_name="Keel Demo Co.")
        db.add(user)
        db.flush()

        customers = [Customer(user_id=user.id, name=n, email=f"billing@{n.split()[0].lower()}.com")
                     for n in CUSTOMERS]
        db.add_all(customers)
        db.flush()

        today = date.today()
        # 12 months of income with mild growth + seasonality, weighted toward top customers.
        weights = [0.34, 0.22, 0.16, 0.12, 0.09, 0.07]
        for m_back in range(11, -1, -1):
            anchor = (today.replace(day=15) - timedelta(days=30 * m_back))
            growth = 1 + (11 - m_back) * 0.035
            season = 1 + 0.12 * ((anchor.month % 6) - 3) / 3
            base_month_rev = 14000 * growth * season
            for cust, w in zip(customers, weights):
                n_payments = random.randint(1, 3)
                for _ in range(n_payments):
                    amt = round(base_month_rev * w / n_payments * random.uniform(0.85, 1.15), 2)
                    day = min(random.randint(2, 27), 28)
                    db.add(Transaction(
                        user_id=user.id, customer_id=cust.id, type=TxType.income,
                        amount=amt, category="Services",
                        description=f"Monthly services — {cust.name}",
                        date=anchor.replace(day=day)))
            for cat, base in EXPENSE_CATS.items():
                amt = round(base * random.uniform(0.9, 1.12), 2)
                if cat == "Marketing" and m_back == 0:
                    amt = round(amt * 2.1, 2)  # spike for the insight engine to catch
                db.add(Transaction(
                    user_id=user.id, type=TxType.expense, amount=amt, category=cat,
                    description=f"{cat} — monthly", date=anchor.replace(day=min(5, 28))))

        # Invoices: a mix of paid, sent, and overdue. Paid ones get a
        # paid_date (some on time, some late) so the cash-aware forecast and
        # payment-behavior insights have real history to learn from.
        statuses = [InvoiceStatus.paid, InvoiceStatus.paid, InvoiceStatus.sent,
                    InvoiceStatus.sent, InvoiceStatus.overdue]
        for i, st in enumerate(statuses, start=1):
            cust = random.choice(customers)
            issue = today - timedelta(days=random.randint(10, 60))
            due = issue + timedelta(days=30)
            paid = None
            if st == InvoiceStatus.paid:
                # First paid invoice on time, second one ~a week late — but
                # never a paid_date in the future.
                paid = min(due - timedelta(days=3) if i == 1 else due + timedelta(days=8), today)
            db.add(Invoice(
                user_id=user.id, customer_id=cust.id, number=f"INV-{1000 + i}",
                amount=round(random.uniform(900, 4200), 2), status=st,
                issue_date=issue, due_date=due, paid_date=paid))

        db.commit()
        print("Seeded demo account: demo@keel.app / demopassword")
    finally:
        db.close()


if __name__ == "__main__":
    run()
