"""Add generated CV conversation versioning

Revision ID: 6f1f7a2d0f5b
Revises: 3506ba79a9d1
Create Date: 2026-04-23 17:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6f1f7a2d0f5b"
down_revision: Union[str, None] = "3506ba79a9d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("generated_cvs", sa.Column("conversation_id", sa.UUID(), nullable=True))
    op.add_column("generated_cvs", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("generated_cvs", sa.Column("parent_version_id", sa.UUID(), nullable=True))

    op.execute("UPDATE generated_cvs SET conversation_id = id WHERE conversation_id IS NULL")
    op.alter_column("generated_cvs", "conversation_id", nullable=False)

    op.create_index("ix_generated_cvs_conversation_id", "generated_cvs", ["conversation_id"], unique=False)
    op.create_foreign_key(
        "fk_generated_cvs_parent_version_id",
        "generated_cvs",
        "generated_cvs",
        ["parent_version_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_generated_cvs_parent_version_id", "generated_cvs", type_="foreignkey")
    op.drop_index("ix_generated_cvs_conversation_id", table_name="generated_cvs")
    op.drop_column("generated_cvs", "parent_version_id")
    op.drop_column("generated_cvs", "version")
    op.drop_column("generated_cvs", "conversation_id")
