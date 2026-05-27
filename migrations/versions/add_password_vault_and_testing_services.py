"""add password vault and testing services

Revision ID: add_vault_services
Revises: 
Create Date: 2026-02-02

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_vault_services'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Хранилище паролей
    op.create_table('password_vault',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('title', sa.String(length=255), nullable=False),
                    sa.Column('service_name', sa.String(
                        length=255), nullable=True),
                    sa.Column('url', sa.String(length=500), nullable=True),
                    sa.Column('username', sa.String(
                        length=255), nullable=True),
                    sa.Column('encrypted_password', sa.Text(), nullable=False),
                    sa.Column('notes', sa.Text(), nullable=True),
                    sa.Column('category', sa.String(
                        length=100), nullable=True),
                    sa.Column('owner_id', sa.Integer(), nullable=False),
                    sa.Column('is_shared', sa.Boolean(), nullable=True),
                    sa.Column('created_at', sa.DateTime(), nullable=True),
                    sa.Column('updated_at', sa.DateTime(), nullable=True),
                    sa.Column('last_accessed', sa.DateTime(), nullable=True),
                    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )

    # Права доступа к хранилищу
    op.create_table('password_vault_permissions',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('vault_id', sa.Integer(), nullable=False),
                    sa.Column('user_id', sa.Integer(), nullable=False),
                    sa.Column('can_read', sa.Boolean(), nullable=True),
                    sa.Column('can_edit', sa.Boolean(), nullable=True),
                    sa.Column('can_delete', sa.Boolean(), nullable=True),
                    sa.Column('can_share', sa.Boolean(), nullable=True),
                    sa.Column('granted_by_id', sa.Integer(), nullable=True),
                    sa.Column('granted_at', sa.DateTime(), nullable=True),
                    sa.ForeignKeyConstraint(['granted_by_id'], ['users.id'], ),
                    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
                    sa.ForeignKeyConstraint(
                        ['vault_id'], ['password_vault.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )

    # Логи доступа к хранилищу
    op.create_table('password_vault_logs',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('vault_id', sa.Integer(), nullable=False),
                    sa.Column('user_id', sa.Integer(), nullable=False),
                    sa.Column('action', sa.String(length=50), nullable=False),
                    sa.Column('ip_address', sa.String(
                        length=45), nullable=True),
                    sa.Column('user_agent', sa.String(
                        length=500), nullable=True),
                    sa.Column('timestamp', sa.DateTime(), nullable=True),
                    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
                    sa.ForeignKeyConstraint(
                        ['vault_id'], ['password_vault.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )

    # Сервисы тестирования
    op.create_table('testing_services',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('name', sa.String(length=255), nullable=False),
                    sa.Column('description', sa.Text(), nullable=True),
                    sa.Column('url', sa.String(length=500), nullable=True),
                    sa.Column('environment', sa.String(
                        length=50), nullable=True),
                    sa.Column('is_active', sa.Boolean(), nullable=True),
                    sa.Column('is_available', sa.Boolean(), nullable=True),
                    sa.Column('version', sa.String(length=50), nullable=True),
                    sa.Column('tech_stack', sa.String(
                        length=500), nullable=True),
                    sa.Column('documentation_url', sa.String(
                        length=500), nullable=True),
                    sa.Column('responsible_person', sa.String(
                        length=255), nullable=True),
                    sa.Column('contact_email', sa.String(
                        length=255), nullable=True),
                    sa.Column('created_by_id', sa.Integer(), nullable=True),
                    sa.Column('created_at', sa.DateTime(), nullable=True),
                    sa.Column('updated_at', sa.DateTime(), nullable=True),
                    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )

    # Логи использования сервисов
    op.create_table('testing_service_logs',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('service_id', sa.Integer(), nullable=False),
                    sa.Column('user_id', sa.Integer(), nullable=False),
                    sa.Column('action', sa.String(length=50), nullable=False),
                    sa.Column('details', sa.Text(), nullable=True),
                    sa.Column('ip_address', sa.String(
                        length=45), nullable=True),
                    sa.Column('timestamp', sa.DateTime(), nullable=True),
                    sa.ForeignKeyConstraint(
                        ['service_id'], ['testing_services.id'], ),
                    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )


def downgrade():
    op.drop_table('testing_service_logs')
    op.drop_table('testing_services')
    op.drop_table('password_vault_logs')
    op.drop_table('password_vault_permissions')
    op.drop_table('password_vault')
