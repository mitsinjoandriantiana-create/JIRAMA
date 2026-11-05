"""enforce data integrity checks

Revision ID: 37e6889512f8
Revises: 0a576e1b4167
Create Date: 2026-11-05 21:56:00.205504

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '37e6889512f8'
down_revision: Union[str, Sequence[str], None] = '0a576e1b4167'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("invoices") as batch_op:
        batch_op.create_check_constraint(
            "ck_invoice_amount_positive", "amount > 0"
        )

    with op.batch_alter_table("payments") as batch_op:
        batch_op.create_check_constraint(
            "ck_payment_amount_positive", "amount_paid > 0"
        )

    with op.batch_alter_table("consumptions") as batch_op:
        batch_op.create_check_constraint(
            "ck_consumption_previous_index_nonnegative", "previous_index >= 0"
        )
        batch_op.create_check_constraint(
            "ck_consumption_indexes_ordered", "current_index >= previous_index"
        )
        batch_op.create_check_constraint(
            "ck_consumption_matches_indexes",
            "consumption = current_index - previous_index",
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("consumptions") as batch_op:
        batch_op.drop_constraint("ck_consumption_matches_indexes", type_="check")
        batch_op.drop_constraint("ck_consumption_indexes_ordered", type_="check")
        batch_op.drop_constraint(
            "ck_consumption_previous_index_nonnegative", type_="check"
        )

    with op.batch_alter_table("payments") as batch_op:
        batch_op.drop_constraint("ck_payment_amount_positive", type_="check")

    with op.batch_alter_table("invoices") as batch_op:
        batch_op.drop_constraint("ck_invoice_amount_positive", type_="check")
