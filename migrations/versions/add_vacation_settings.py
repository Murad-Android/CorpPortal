"""Add vacation settings and balance tables

Revision ID: vacation_settings_001
Revises: 41e3f59e6272
Create Date: 2026-02-02

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = 'vacation_settings_001'
down_revision = '41e3f59e6272'
branch_labels = None
depends_on = None


def upgrade():
    # Создаем таблицу настроек отпусков
    op.create_table('vacation_settings',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('annual_days_default', sa.Integer(),
                              nullable=True, default=28),
                    sa.Column('dayoff_enabled', sa.Boolean(),
                              nullable=True, default=False),
                    sa.Column('dayoff_days_limit', sa.Integer(),
                              nullable=True, default=0),
                    sa.Column('updated_at', sa.DateTime(),
                              nullable=True, default=datetime.utcnow),
                    sa.PrimaryKeyConstraint('id')
                    )

    # Создаем таблицу баланса отпусков пользователей
    op.create_table('user_vacation_balance',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('user_id', sa.Integer(), nullable=False),
                    sa.Column('year', sa.Integer(), nullable=False),
                    sa.Column('annual_days_total', sa.Integer(),
                              nullable=True, default=28),
                    sa.Column('annual_days_used', sa.Integer(),
                              nullable=True, default=0),
                    sa.Column('dayoff_days_total', sa.Integer(),
                              nullable=True, default=0),
                    sa.Column('dayoff_days_used', sa.Integer(),
                              nullable=True, default=0),
                    sa.Column('updated_at', sa.DateTime(),
                              nullable=True, default=datetime.utcnow),
                    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('user_id', 'year', name='uq_user_year')
                    )

    # Добавляем индексы
    op.create_index('ix_user_vacation_balance_user_id',
                    'user_vacation_balance', ['user_id'])
    op.create_index('ix_user_vacation_balance_year',
                    'user_vacation_balance', ['year'])

    # Инициализируем настройки по умолчанию
    op.execute("""
        INSERT INTO vacation_settings (annual_days_default, dayoff_enabled, dayoff_days_limit, updated_at)
        VALUES (28, 0, 0, datetime('now'))
    """)


def downgrade():
    op.drop_index('ix_user_vacation_balance_year',
                  table_name='user_vacation_balance')
    op.drop_index('ix_user_vacation_balance_user_id',
                  table_name='user_vacation_balance')
    op.drop_table('user_vacation_balance')
    op.drop_table('vacation_settings')
