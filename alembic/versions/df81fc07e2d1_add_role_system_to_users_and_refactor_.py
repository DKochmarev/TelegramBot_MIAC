"""Add role system to users and refactor bookings

Revision ID: df81fc07e2d1
Revises: d426d69557ac
Create Date: 2025-07-22 15:19:05.068938

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'df81fc07e2d1'
down_revision: Union[str, Sequence[str], None] = 'd426d69557ac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Определяем наш Enum один раз, чтобы использовать его в upgrade и downgrade
user_role_enum = sa.Enum('PENDING', 'EMPLOYEE', 'DRIVER', 'ADMIN', name='userrole')


def upgrade() -> None:
    """Upgrade schema."""
    # --- Шаг 1: Создание типа Enum в PostgreSQL ---
    # Эта команда должна идти первой, до использования типа 'userrole'.
    user_role_enum.create(op.get_bind(), checkfirst=True)

    # --- Шаг 2: Добавление колонки 'role' в таблицу 'users' ---
    # Сначала добавляем как nullable=True, чтобы не было конфликтов с существующими данными.
    op.add_column('users', sa.Column('role', user_role_enum, nullable=True))

    # --- Шаг 3: Заполнение значения по умолчанию для существующих пользователей ---
    # Все существующие пользователи получат роль PENDING.
    # Это нужно, чтобы на следующем шаге сделать колонку non-nullable.
    op.execute("UPDATE users SET role = 'PENDING' WHERE role IS NULL")

    # --- Шаг 4: Установка ограничения NOT NULL на колонку 'role' ---
    op.alter_column('users', 'role', nullable=False)

    # --- Шаг 5: Добавление остальных колонок и внешних ключей (из вашей автогенерации) ---
    op.add_column('bookings', sa.Column('driver_id', sa.BigInteger(), nullable=True))
    op.add_column('bookings', sa.Column('comment', sa.String(length=255), nullable=True))

    # Создаем внешний ключ для driver_id.
    # Рекомендуется дать ключу осмысленное имя (constraint name).
    op.create_foreign_key(
        'fk_bookings_driver_id_users',  # Имя ограничения
        'bookings',                     # Исходная таблица
        'users',                        # Целевая таблица
        ['driver_id'],                  # Колонки в исходной таблице
        ['telegram_id']                 # Колонки в целевой таблице
    )


def downgrade() -> None:
    """Downgrade schema."""
    # --- Выполняем действия в обратном порядке ---

    # --- Шаг 1: Удаляем внешний ключ ---
    op.drop_constraint('fk_bookings_driver_id_users', 'bookings', type_='foreignkey')

    # --- Шаг 2: Удаляем колонки из 'bookings' ---
    op.drop_column('bookings', 'comment')
    op.drop_column('bookings', 'driver_id')

    # --- Шаг 3: Удаляем колонку 'role' из 'users' ---
    op.drop_column('users', 'role')

    # --- Шаг 4: Удаляем сам тип Enum из базы данных ---
    user_role_enum.drop(op.get_bind())