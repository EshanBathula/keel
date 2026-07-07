"""add user timezone

Revision ID: f1dde5ad45e1
Revises: 18851eed2a8a
Create Date: 2026-07-06 23:00:50.010462

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1dde5ad45e1'
down_revision: Union[str, Sequence[str], None] = '18851eed2a8a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("timezone", sa.String(64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("timezone")
