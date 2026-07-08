"""Small validation helpers shared across routers."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Customer


def ensure_customer_owned(db: Session, user_id: int, customer_id: int | None) -> None:
    """Raise 400 if customer_id is set but doesn't belong to user_id.

    Without this, a transaction/invoice could be linked to another tenant's
    customer row — the FK would resolve, and `top_customers`/analytics would
    leak that customer's name to the wrong owner (a multi-tenant isolation
    bug, not just a data-integrity one).
    """
    if customer_id is None:
        return
    customer = db.get(Customer, customer_id)
    if not customer or customer.user_id != user_id:
        raise HTTPException(400, "Customer not found")
