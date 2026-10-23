"""add ix_files_document_id_id

Revision ID: e4b8c2d16a70
Revises: a3f1c72d5b90
Create Date: 2026-10-23

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e4b8c2d16a70'
down_revision: Union[str, Sequence[str], None] = 'a3f1c72d5b90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    `(document_id, id)` serves both the foreign-key/cascade lookup and the
    list query's `ORDER BY id`, so one non-unique btree covers both. It is
    deliberately not declared `CONCURRENTLY`: migrations run inside Alembic's
    transaction, and this table is small in the MVP.
    """
    op.create_index(
        'ix_files_document_id_id',
        'files',
        ['document_id', 'id'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_files_document_id_id', table_name='files')
