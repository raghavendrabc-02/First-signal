"""add article delivery tracking

Revision ID: a7c3e91f2b04
Revises: 5898c9a2922a
Create Date: 2026-10-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c3e91f2b04'
down_revision: Union[str, Sequence[str], None] = '5898c9a2922a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Nullable columns only: existing rows are kept as "not delivered".
    op.add_column('articles', sa.Column('delivered_at', sa.DateTime(), nullable=True))
    op.add_column('articles', sa.Column('telegram_message_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('articles', 'telegram_message_id')
    op.drop_column('articles', 'delivered_at')
