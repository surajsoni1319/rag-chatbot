"""add knowledge_chunks pgvector table

Revision ID: c33fa1aa2a72
Revises: a17cf2170642
Create Date: 2026-02-03 17:55:08.166969
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision = 'c33fa1aa2a72'
down_revision = 'a17cf2170642'
branch_labels = None
depends_on = None


def upgrade():
    # ✅ CRITICAL: ensure pgvector is available in this migration session
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ### create knowledge_chunks table ###
    op.create_table(
        'knowledge_chunks',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),

        # pgvector embedding
        sa.Column('embedding', Vector(1536), nullable=False),

        sa.Column('document_name', sa.Text(), nullable=False),

        sa.Column(
            'source_type',
            postgresql.ENUM(
                'PRIMARY',
                'SECONDARY',
                name='knowledge_source',
                create_type=False
            ),
            nullable=False
        ),

        sa.Column('department', sa.String(length=50), nullable=False),

        sa.Column(
            'visibility',
            postgresql.ENUM(
                'EMPLOYEE',
                'MANAGER',
                'HOD',
                'CXO',
                name='visibility_level',
                create_type=False
            ),
            nullable=False
        ),

        sa.Column('uploaded_by', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('related_question', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),

        sa.ForeignKeyConstraint(['uploaded_by'], ['user.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Allow nullable session_id (legacy chats)
    with op.batch_alter_table('chat_history', schema=None) as batch_op:
        batch_op.alter_column(
            'session_id',
            existing_type=sa.INTEGER(),
            nullable=True
        )

    # Cleanup deprecated user columns
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('idx_user_access_level'))
        batch_op.drop_index(batch_op.f('idx_user_department'))
        batch_op.drop_index(batch_op.f('idx_user_role'))
        batch_op.drop_column('name')
        batch_op.drop_column('access_level')
        batch_op.drop_column('role')


def downgrade():
    # Restore user columns
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'role',
                sa.VARCHAR(length=20),
                server_default=sa.text("'user'::character varying"),
                nullable=True
            )
        )
        batch_op.add_column(
            sa.Column(
                'access_level',
                sa.VARCHAR(length=20),
                server_default=sa.text("'employee'::character varying"),
                nullable=True
            )
        )
        batch_op.add_column(
            sa.Column(
                'name',
                sa.VARCHAR(length=100),
                nullable=True
            )
        )
        batch_op.create_index(batch_op.f('idx_user_role'), ['role'], unique=False)
        batch_op.create_index(batch_op.f('idx_user_department'), ['department'], unique=False)
        batch_op.create_index(batch_op.f('idx_user_access_level'), ['access_level'], unique=False)

    with op.batch_alter_table('chat_history', schema=None) as batch_op:
        batch_op.alter_column(
            'session_id',
            existing_type=sa.INTEGER(),
            nullable=False
        )

    op.drop_table('knowledge_chunks')
