"""money as integer cents

Replaces the float `amount` column on transactions/invoices with an integer
`amount_cents` column, converting existing data with the same Decimal-based,
round-half-up logic used by the app (app.money.to_cents) so the migration and
the running application never disagree on a conversion.

Revision ID: 18851eed2a8a
Revises: d3fc1e4ef268
Create Date: 2026-07-06 15:31:11.930567

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.money import to_cents, to_dollars


# revision identifiers, used by Alembic.
revision: str = '18851eed2a8a'
down_revision: Union[str, Sequence[str], None] = 'd3fc1e4ef268'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _convert(table: str, old_col: str, new_col: str, convert) -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text(f"SELECT id, {old_col} FROM {table}")).fetchall()
    for row in rows:
        conn.execute(
            sa.text(f"UPDATE {table} SET {new_col} = :v WHERE id = :id"),
            {"v": convert(getattr(row, old_col)), "id": row.id},
        )


def upgrade() -> None:
    for table in ("transactions", "invoices"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column("amount_cents", sa.Integer(), nullable=True))
        _convert(table, "amount", "amount_cents", to_cents)
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column("amount_cents", nullable=False)
            batch_op.drop_column("amount")


def downgrade() -> None:
    for table in ("transactions", "invoices"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column("amount", sa.Float(), nullable=True))
        _convert(table, "amount_cents", "amount", to_dollars)
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column("amount", nullable=False)
            batch_op.drop_column("amount_cents")
