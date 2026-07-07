import csv
import io
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Transaction, TxType, User
from ..schemas import TransactionCreate, TransactionOut, TransactionPage, TransactionUpdate
from ._util import ensure_customer_owned

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("", response_model=TransactionPage)
def list_transactions(
    type: TxType | None = None,
    category: str | None = None,
    q: str | None = Query(None, description="Case-insensitive search across category and description"),
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(Transaction).where(Transaction.user_id == user.id)
    if type:
        stmt = stmt.where(Transaction.type == type)
    if category:
        stmt = stmt.where(Transaction.category == category)
    if date_from:
        stmt = stmt.where(Transaction.date >= date_from)
    if date_to:
        stmt = stmt.where(Transaction.date <= date_to)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Transaction.description.ilike(like), Transaction.category.ilike(like)))

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = db.scalars(
        stmt.order_by(Transaction.date.desc(), Transaction.id.desc()).limit(limit).offset(offset)
    ).all()
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("", response_model=TransactionOut, status_code=201)
def create_transaction(payload: TransactionCreate, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    ensure_customer_owned(db, user.id, payload.customer_id)
    tx = Transaction(user_id=user.id, **payload.model_dump())
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


@router.patch("/{tx_id}", response_model=TransactionOut)
def update_transaction(tx_id: int, payload: TransactionUpdate, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    tx = db.get(Transaction, tx_id)
    if not tx or tx.user_id != user.id:
        raise HTTPException(404, "Transaction not found")
    changes = payload.model_dump(exclude_unset=True)
    if "customer_id" in changes:
        ensure_customer_owned(db, user.id, changes["customer_id"])
    for field, value in changes.items():
        setattr(tx, field, value)
    db.commit()
    db.refresh(tx)
    return tx


@router.delete("/{tx_id}", status_code=204)
def delete_transaction(tx_id: int, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    tx = db.get(Transaction, tx_id)
    if not tx or tx.user_id != user.id:
        raise HTTPException(404, "Transaction not found")
    db.delete(tx)
    db.commit()


@router.post("/import", status_code=201)
async def import_csv(file: UploadFile = File(...), db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    """Import transactions from CSV with columns: date,type,amount,category,description.

    Dates accept YYYY-MM-DD or MM/DD/YYYY. Type must be `income` or `expense`.
    """
    raw = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    created, errors = 0, []
    for i, row in enumerate(reader, start=2):  # header is line 1
        try:
            raw_date = (row.get("date") or "").strip()
            for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
                try:
                    tx_date = datetime.strptime(raw_date, fmt).date()
                    break
                except ValueError:
                    tx_date = None
            if tx_date is None:
                raise ValueError(f"unrecognized date '{raw_date}'")
            tx_type = TxType((row.get("type") or "").strip().lower())
            amount = abs(float(row.get("amount") or 0))
            if amount <= 0:
                raise ValueError("amount must be non-zero")
            db.add(Transaction(
                user_id=user.id, type=tx_type, amount=amount, date=tx_date,
                category=(row.get("category") or "Uncategorized").strip() or "Uncategorized",
                description=(row.get("description") or "").strip(),
            ))
            created += 1
        except (ValueError, KeyError) as e:
            errors.append(f"line {i}: {e}")
    db.commit()
    return {"created": created, "errors": errors}
