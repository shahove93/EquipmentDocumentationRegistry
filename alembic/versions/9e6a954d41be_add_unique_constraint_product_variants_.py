"""add unique constraint product_variants product_id size_text

Revision ID: 9e6a954d41be
Revises: 4a43cb5a19ea
Create Date: 2026-10-12 19:43:35.341965

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9e6a954d41be'
down_revision: Union[str, Sequence[str], None] = '4a43cb5a19ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ADR-006: a product variant is unique per (product_id, size_text), so one
    # document can be attached to an unambiguous set of sizes.
    op.create_unique_constraint(
        "uq_product_variants_product_id_size_text",
        "product_variants",
        ["product_id", "size_text"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_product_variants_product_id_size_text",
        "product_variants",
        type_="unique",
    )
