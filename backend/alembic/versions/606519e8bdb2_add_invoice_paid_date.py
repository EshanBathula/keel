"""add invoice paid_date

Revision ID: 606519e8bdb2
Revises: f1dde5ad45e1
Create Date: 2026-07-07 14:08:27.627547

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '606519e8bdb2'
down_revision: Union[str, Sequence[str], None] = 'f1dde5ad45e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Left NULL for existing paid invoices — we have no record of when they
    # were actually marked paid, and backfilling with due_date would fabricate
    # an "on time" assumption. Excluded from on-time-rate calculations instead.
    with op.batch_alter_table("invoices") as batch_op:
        batch_op.add_column(sa.Column("paid_date", sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("invoices") as batch_op:
        batch_op.drop_column("paid_date")
