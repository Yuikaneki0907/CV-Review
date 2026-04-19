"""Harden upload versioning constraints

Revision ID: 8d4a5d9e6f11
Revises: c0e8d0c2d1b3
Create Date: 2026-04-24 12:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8d4a5d9e6f11"
down_revision: Union[str, None] = "c0e8d0c2d1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY user_id, original_filename
                    ORDER BY COALESCE(version, 0), created_at, id
                ) AS new_version
            FROM cv_files
            WHERE deleted_at IS NULL
        )
        UPDATE cv_files AS current
        SET version = ranked.new_version
        FROM ranked
        WHERE current.id = ranked.id
          AND current.version IS DISTINCT FROM ranked.new_version
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY user_id, conversation_id
                    ORDER BY COALESCE(version, 0), created_at, id
                ) AS new_version
            FROM generated_cvs
            WHERE deleted_at IS NULL
        )
        UPDATE generated_cvs AS current
        SET version = ranked.new_version
        FROM ranked
        WHERE current.id = ranked.id
          AND current.version IS DISTINCT FROM ranked.new_version
        """
    )

    op.alter_column(
        "cv_files",
        "file_size",
        existing_type=sa.Float(),
        type_=sa.Integer(),
        postgresql_using="file_size::integer",
        existing_nullable=True,
    )
    op.alter_column(
        "cv_files",
        "version",
        existing_type=sa.Float(),
        type_=sa.Integer(),
        postgresql_using="version::integer",
        existing_nullable=True,
    )

    op.create_index(
        "ux_cv_files_user_filename_version_active",
        "cv_files",
        ["user_id", "original_filename", "version"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ux_generated_cvs_user_conversation_version_active",
        "generated_cvs",
        ["user_id", "conversation_id", "version"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ux_generated_cvs_user_conversation_version_active", table_name="generated_cvs")
    op.drop_index("ux_cv_files_user_filename_version_active", table_name="cv_files")

    op.alter_column(
        "cv_files",
        "version",
        existing_type=sa.Integer(),
        type_=sa.Float(),
        postgresql_using="version::double precision",
        existing_nullable=True,
    )
    op.alter_column(
        "cv_files",
        "file_size",
        existing_type=sa.Integer(),
        type_=sa.Float(),
        postgresql_using="file_size::double precision",
        existing_nullable=True,
    )
