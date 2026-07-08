from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Customer, User
from ..schemas import CustomerCreate, CustomerOut

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("", response_model=list[CustomerOut])
def list_customers(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(select(Customer).where(Customer.user_id == user.id).order_by(Customer.name)).all()


@router.post("", response_model=CustomerOut, status_code=201)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = Customer(user_id=user.id, **payload.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.delete("/{customer_id}", status_code=204)
def delete_customer(customer_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = db.get(Customer, customer_id)
    if not c or c.user_id != user.id:
        raise HTTPException(404, "Customer not found")
    db.delete(c)
    db.commit()
