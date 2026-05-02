"""Add chat_sessions table

Revision ID: 4a65d14c1870
Revises: 8d4a5d9e6f11
Create Date: 2026-05-01 15:36:20.924363

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4a65d14c1870'
down_revision: Union[str, None] = '8d4a5d9e6f11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create table
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('conversation_id', sa.UUID(), nullable=False),
        sa.Column('messages', sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_sessions_conversation_id'), 'chat_sessions', ['conversation_id'], unique=True)
    op.create_index(op.f('ix_chat_sessions_user_id'), 'chat_sessions', ['user_id'], unique=False)

    # 2. Migrate existing chat histories to chat_sessions
    op.execute("""
        INSERT INTO chat_sessions (id, user_id, conversation_id, messages, created_at, updated_at)
        SELECT 
            gen_random_uuid(),
            g.user_id,
            g.conversation_id,
            COALESCE(g.generated_content->'chat_history', '[]'::jsonb),
            NOW(),
            NOW()
        FROM (
            SELECT DISTINCT ON (conversation_id) *
            FROM generated_cvs
            ORDER BY conversation_id, version DESC
        ) g
        WHERE g.generated_content ? 'chat_history'
        ON CONFLICT (conversation_id) DO NOTHING;
    """)

    # 3. Clean up the chat_history from the generated_content payload in generated_cvs
    op.execute("""
        UPDATE generated_cvs
        SET generated_content = generated_content - 'chat_history'
        WHERE generated_content ? 'chat_history';
    """)


def downgrade() -> None:
    op.drop_index(op.f('ix_chat_sessions_user_id'), table_name='chat_sessions')
    op.drop_index(op.f('ix_chat_sessions_conversation_id'), table_name='chat_sessions')
    op.drop_table('chat_sessions')
