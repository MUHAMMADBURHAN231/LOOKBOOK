"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-09-27 21:33:43.712766

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector.sqlalchemy

from app.core.config import get_settings

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Extensions need elevated rights; docker/postgres-init.sql pre-creates them in managed setups.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table('garments',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('slug', sa.String(length=96), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('category', sa.String(length=64), nullable=False),
    sa.Column('brand', sa.String(length=128), nullable=True),
    sa.Column('color', sa.String(length=64), nullable=True),
    sa.Column('season', sa.String(length=32), nullable=True),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('price_cents', sa.Integer(), nullable=True),
    sa.Column('image_key', sa.String(length=512), nullable=False),
    sa.Column('flatlay_mask_key', sa.String(length=512), nullable=True),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=768), nullable=False),
    sa.Column('embedding_model', sa.String(length=64), nullable=False),
    sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )
    op.create_index('idx_garments_embedding', 'garments', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.create_index(op.f('ix_garments_category'), 'garments', ['category'], unique=False)
    op.create_table('merchants',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('publishable_key', sa.String(length=64), nullable=False),
    sa.Column('allowed_origins', sa.ARRAY(sa.String(length=255)), nullable=False),
    sa.Column('daily_session_limit', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('publishable_key')
    )
    op.create_table('users',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('hashed_password', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=128), nullable=True),
    sa.Column('biometric_consent_granted', sa.Boolean(), nullable=False),
    sa.Column('biometric_consent_timestamp', sa.DateTime(timezone=True), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('uq_users_email_lower', 'users', [sa.literal_column('lower(email)')], unique=True)
    op.create_table('auth_sessions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('idle_expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('absolute_expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('user_agent', sa.String(length=256), nullable=True),
    sa.Column('ip_prefix', sa.String(length=64), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index(op.f('ix_auth_sessions_user_id'), 'auth_sessions', ['user_id'], unique=False)
    op.create_table('password_reset_tokens',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index(op.f('ix_password_reset_tokens_user_id'), 'password_reset_tokens', ['user_id'], unique=False)
    op.create_table('stylist_sessions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=128), nullable=False),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('context_memory', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_stylist_sessions_user_id'), 'stylist_sessions', ['user_id'], unique=False)
    op.create_table('user_photos',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('storage_key', sa.String(length=512), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('mime_type', sa.String(length=32), nullable=False),
    sa.Column('width', sa.Integer(), nullable=True),
    sa.Column('height', sa.Integer(), nullable=True),
    sa.Column('aspect_ratio', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('pose_keypoints', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('is_primary', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_photos_user_id'), 'user_photos', ['user_id'], unique=False)
    op.create_table('stylist_messages',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('session_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('garment_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('tool_trace', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['session_id'], ['stylist_sessions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_stylist_messages_session_id'), 'stylist_messages', ['session_id'], unique=False)
    op.create_table('tryon_tasks',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('user_photo_id', sa.UUID(), nullable=True),
    sa.Column('garment_id', sa.UUID(), nullable=True),
    sa.Column('custom_prompt', sa.Text(), nullable=True),
    sa.Column('category', sa.String(length=32), nullable=False),
    sa.Column('enhance_face', sa.Boolean(), nullable=False),
    sa.Column('pipeline', sa.String(length=16), nullable=False),
    sa.Column('adapter', sa.String(length=32), nullable=True),
    sa.Column('outfit_spec', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('stage', sa.String(length=64), nullable=False),
    sa.Column('progress_percentage', sa.Integer(), nullable=False),
    sa.Column('result_storage_key', sa.String(length=512), nullable=True),
    sa.Column('execution_time_ms', sa.Integer(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['garment_id'], ['garments.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_photo_id'], ['user_photos.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tryon_tasks_status'), 'tryon_tasks', ['status'], unique=False)
    op.create_index(op.f('ix_tryon_tasks_user_id'), 'tryon_tasks', ['user_id'], unique=False)
    op.create_table('looks',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('tryon_task_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=160), nullable=False),
    sa.Column('collection', sa.String(length=60), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['tryon_task_id'], ['tryon_tasks.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_looks_user_id'), 'looks', ['user_id'], unique=False)
    _grant_app_role()
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_looks_user_id'), table_name='looks')
    op.drop_table('looks')
    op.drop_index(op.f('ix_tryon_tasks_user_id'), table_name='tryon_tasks')
    op.drop_index(op.f('ix_tryon_tasks_status'), table_name='tryon_tasks')
    op.drop_table('tryon_tasks')
    op.drop_index(op.f('ix_stylist_messages_session_id'), table_name='stylist_messages')
    op.drop_table('stylist_messages')
    op.drop_index(op.f('ix_user_photos_user_id'), table_name='user_photos')
    op.drop_table('user_photos')
    op.drop_index(op.f('ix_stylist_sessions_user_id'), table_name='stylist_sessions')
    op.drop_table('stylist_sessions')
    op.drop_index(op.f('ix_password_reset_tokens_user_id'), table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')
    op.drop_index(op.f('ix_auth_sessions_user_id'), table_name='auth_sessions')
    op.drop_table('auth_sessions')
    op.drop_index('uq_users_email_lower', table_name='users')
    op.drop_table('users')
    op.drop_table('merchants')
    op.drop_index(op.f('ix_garments_category'), table_name='garments')
    op.drop_index('idx_garments_embedding', table_name='garments', postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.drop_table('garments')
    # ### end Alembic commands ###


def _grant_app_role() -> None:
    """The running API/workers use a DML-only role: no DDL, no TRUNCATE, no ownership."""
    role = get_settings().app_db_role
    op.execute(f'GRANT USAGE ON SCHEMA public TO "{role}"')
    op.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{role}"')
    op.execute(f'REVOKE ALL ON alembic_version FROM "{role}"')
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "{role}"'
    )
