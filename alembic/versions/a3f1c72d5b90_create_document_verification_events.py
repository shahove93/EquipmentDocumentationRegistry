"""create document_verification_events

Revision ID: a3f1c72d5b90
Revises: 9e6a954d41be
Create Date: 2026-10-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f1c72d5b90'
down_revision: Union[str, Sequence[str], None] = '9e6a954d41be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # documents.verification_status holds only the current value, so a decision
    # cannot be explained after the fact. This table records the transition, and
    # the CHECK constraints make an unusable row impossible rather than
    # merely unlikely:
    #   - from_status / to_status / event_type are drawn from closed sets;
    #   - a transition must actually change something;
    #   - event_type must agree with the status it leads to;
    #   - a rejection must state why. btrim is given an explicit whitespace set
    #     because its default trims spaces only, which would let a reason made
    #     of tabs or newlines pass as if it were a reason;
    #   - a reopening only follows a decided state.
    op.create_table('document_verification_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('document_id', sa.Integer(), nullable=False),
    sa.Column('from_status', sa.String(length=20), nullable=False),
    sa.Column('to_status', sa.String(length=20), nullable=False),
    sa.Column('event_type', sa.String(length=30), nullable=False),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("from_status IN ('pending', 'verified', 'rejected')", name='ck_document_verification_events_from_status'),
    sa.CheckConstraint("to_status IN ('pending', 'verified', 'rejected')", name='ck_document_verification_events_to_status'),
    sa.CheckConstraint("event_type IN ('verified', 'rejected', 'reopened')", name='ck_document_verification_events_event_type'),
    sa.CheckConstraint('from_status <> to_status', name='ck_document_verification_events_status_changed'),
    sa.CheckConstraint("(event_type = 'verified' AND to_status = 'verified') OR (event_type = 'rejected' AND to_status = 'rejected') OR (event_type = 'reopened' AND to_status = 'pending')", name='ck_document_verification_events_type_matches_target'),
    sa.CheckConstraint("event_type <> 'rejected' OR (reason IS NOT NULL AND btrim(reason, E' \\t\\n\\r\\f\\v') <> '')", name='ck_document_verification_events_rejected_reason'),
    sa.CheckConstraint("event_type <> 'reopened' OR from_status IN ('verified', 'rejected')", name='ck_document_verification_events_reopened_origin'),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    # Serves the only query this table needs: one document's history in
    # chronological order. `id` breaks ties inside a single transaction, where
    # now() returns the same timestamp for every row.
    op.create_index('ix_document_verification_events_document_id_created_at_id', 'document_verification_events', ['document_id', 'created_at', 'id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Dropping the table removes its index and every CHECK constraint with it.
    op.drop_table('document_verification_events')