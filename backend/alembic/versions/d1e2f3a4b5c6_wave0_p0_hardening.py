"""Wave 0 P0 hardening: prices, re-auth lockout, reconciliation persistence, idempotency hash

Revision ID: d1e2f3a4b5c6
Revises: c8c8a8abb21c
Create Date: 2026-11-16 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, Sequence[str], None] = 'c8c8a8abb21c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'fuel_prices',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('station_id', sa.Uuid(), nullable=False),
        sa.Column('product_id', sa.Uuid(), nullable=False),
        sa.Column('unit_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('effective_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('unit_price > 0', name='ck_fuel_price_positive'),
        sa.ForeignKeyConstraint(['created_by'], ['employees.id'], ),
        sa.ForeignKeyConstraint(['product_id'], ['fuel_products.id'], ),
        sa.ForeignKeyConstraint(['station_id'], ['stations.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_fuel_prices_station_product_effective',
        'fuel_prices',
        ['station_id', 'product_id', 'effective_from'],
        unique=False,
    )
    op.create_index(op.f('ix_fuel_prices_station_id'), 'fuel_prices', ['station_id'], unique=False)

    op.create_table(
        'reauth_attempts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('station_id', sa.Uuid(), nullable=False),
        sa.Column('employee_id', sa.Uuid(), nullable=False),
        sa.Column('failures', sa.Integer(), nullable=False),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ),
        sa.ForeignKeyConstraint(['station_id'], ['stations.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('employee_id', name='uq_reauth_attempt_employee'),
    )

    with op.batch_alter_table('shifts') as batch:
        batch.add_column(sa.Column('collections', sa.JSON(), nullable=True))
        batch.add_column(sa.Column('variance_amount', sa.Numeric(precision=12, scale=2), nullable=True))
        batch.add_column(sa.Column('variance_reason', sa.String(length=300), nullable=True))
        batch.add_column(sa.Column('rollover_values', sa.JSON(), nullable=True))

    with op.batch_alter_table('idempotency_keys') as batch:
        batch.add_column(sa.Column('request_hash', sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('idempotency_keys') as batch:
        batch.drop_column('request_hash')

    with op.batch_alter_table('shifts') as batch:
        batch.drop_column('rollover_values')
        batch.drop_column('variance_reason')
        batch.drop_column('variance_amount')
        batch.drop_column('collections')

    op.drop_table('reauth_attempts')
    op.drop_index(op.f('ix_fuel_prices_station_id'), table_name='fuel_prices')
    op.drop_index('ix_fuel_prices_station_product_effective', table_name='fuel_prices')
    op.drop_table('fuel_prices')
