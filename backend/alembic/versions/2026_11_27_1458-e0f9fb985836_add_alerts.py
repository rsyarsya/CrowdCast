"""add alerts

Revision ID: e0f9fb985836
Revises: 2b7dca11fe11
Create Date: 2026-11-27 14:58:12.089896

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e0f9fb985836'
down_revision: Union[str, Sequence[str], None] = '2b7dca11fe11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('alerts',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('camera_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.Enum('crowded', 'forecast_crowded', name='alert_kind', native_enum=False, create_constraint=True, length=20), nullable=False),
    sa.Column('horizon_minutes', sa.Integer(), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('peak_count', sa.Integer(), nullable=False),
    sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('acknowledged_by_id', sa.Integer(), nullable=True),
    sa.CheckConstraint("(kind = 'crowded') = (horizon_minutes IS NULL)", name=op.f('ck_alerts_horizon_matches_kind')),
    sa.CheckConstraint('peak_count >= 0', name=op.f('ck_alerts_peak_count_nonnegative')),
    sa.ForeignKeyConstraint(['acknowledged_by_id'], ['users.id'], name=op.f('fk_alerts_acknowledged_by_id_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['camera_id'], ['cameras.id'], name=op.f('fk_alerts_camera_id_cameras'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_alerts'))
    )
    op.create_index('ix_alerts_started_at', 'alerts', ['started_at'], unique=False)
    op.create_index('uq_alerts_open', 'alerts', ['camera_id', 'kind', 'horizon_minutes'], unique=True, postgresql_where=sa.text('ended_at IS NULL'), postgresql_nulls_not_distinct=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_alerts_open', table_name='alerts', postgresql_where=sa.text('ended_at IS NULL'), postgresql_nulls_not_distinct=True)
    op.drop_index('ix_alerts_started_at', table_name='alerts')
    op.drop_table('alerts')
