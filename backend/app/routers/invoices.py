from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Invoice, InvoiceStatus, Transaction, TxType, User
from ..schemas import InvoiceCreate, InvoiceOut, InvoiceUpdate

router = APIRouter(prefix="/api/invoices", tags=["invoices"])


@router.get("", response_model=list[InvoiceOut])
def list_invoices(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    invoices = db.scalars(select(Invoice).where(Invoice.user_id == user.id)
                          .order_by(Invoice.due_date.desc())).all()
    # Auto-flag overdue on read so status is always current.
    today = date.today()
    changed = False
    for inv in invoices:
        if inv.status == InvoiceStatus.sent and inv.due_date < today:
            inv.status = InvoiceStatus.overdue
            changed = True
    if changed:
        db.commit()
    return invoices


@router.post("", response_model=InvoiceOut, status_code=201)
def create_invoice(payload: InvoiceCreate, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    inv = Invoice(user_id=user.id, **payload.model_dump())
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


@router.patch("/{invoice_id}", response_model=InvoiceOut)
def update_invoice(invoice_id: int, payload: InvoiceUpdate, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    inv = db.get(Invoice, invoice_id)
    if not inv or inv.user_id != user.id:
        raise HTTPException(404, "Invoice not found")
    previously_paid = inv.status == InvoiceStatus.paid
    inv.status = payload.status
    # Marking paid records the revenue automatically.
    if payload.status == InvoiceStatus.paid and not previously_paid:
        db.add(Transaction(
            user_id=user.id, customer_id=inv.customer_id, type=TxType.income,
            amount=inv.amount, category="Invoice payment",
            description=f"Invoice {inv.number} paid", date=date.today(),
        ))
    db.commit()
    db.refresh(inv)
    return inv
