"""baseline schema

Reflects the schema as shipped in Keel v1.0 (commit 8f69432), before the
integer-cents migration. This exists so `alembic upgrade head` has a real
starting point for anyone with a v1.0 database; a fresh clone runs this and
the following migration back-to-back.

Revision ID: d3fc1e4ef268
Revises:
Create Date: 2026-07-06 15:31:05.786718

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3fc1e4ef268'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("business_name", sa.String(255), nullable=False, server_default="My Business"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, server_default=""),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_customers_user_id", "customers", ["user_id"])

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("type", sa.Enum("income", "expense", name="txtype"), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("category", sa.String(100), nullable=False, server_default="Uncategorized"),
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_transactions_user_id", "transactions", ["user_id"])
    op.create_index("ix_transactions_type", "transactions", ["type"])
    op.create_index("ix_transactions_category", "transactions", ["category"])
    op.create_index("ix_transactions_date", "transactions", ["date"])

    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("number", sa.String(50), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("status", sa.Enum("draft", "sent", "paid", "overdue", name="invoicestatus"),
                  nullable=False, server_default="draft"),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_invoices_user_id", "invoices", ["user_id"])
    op.create_index("ix_invoices_status", "invoices", ["status"])


def downgrade() -> None:
    op.drop_table("invoices")
    op.drop_table("transactions")
    op.drop_table("customers")
    op.drop_table("users")
