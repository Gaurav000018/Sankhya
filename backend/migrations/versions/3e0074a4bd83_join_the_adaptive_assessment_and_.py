"""join the adaptive assessment and interview analytics branches

Two migrations branched from the same parent: the IRT item parameters added for
the adaptive assessment, and the mistakes/gesture columns added for interview
analytics. They touch disjoint tables — `generated_questions`, `quiz_attempts`
and `item_responses` on one side, `answer_scores` and `attention_metrics` on the
other — so this is a graph join with nothing to reconcile. Without it
`alembic upgrade head` refuses to run at all, with "Multiple head revisions".

Revision ID: 3e0074a4bd83
Revises: 5a74dbf2113a, bf8d038fa416
Create Date: 2026-09-15 20:01:52.772807

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3e0074a4bd83'
down_revision: Union[str, Sequence[str], None] = ('5a74dbf2113a', 'bf8d038fa416')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
