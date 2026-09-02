from aiogram import Router, F, types
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from db.models import User, UserRole, Booking
from keyboards.inline import (
    get_pending_users_kb, get_back_to_main_menu_kb, get_user_approval_kb,
    get_unassigned_bookings_kb, get_driver_selection_kb, get_driver_booking_confirmation_kb
)

router = Router()


# Управление пользователями
@router.callback_query(F.data == "admin_approve_users")
async def show_pending_users(callback: types.CallbackQuery, session: AsyncSession, user: User | None):
    if not user or user.role.value != "admin":
        await callback.answer("Эта функция доступна только администраторам.", show_alert=True)
        return

    res = await session.execute(select(User).where(User.role == UserRole.PENDING))
    pending_users = list(res.scalars().all())

    if not pending_users:
        await callback.message.edit_text("Нет новых заявок на регистрацию.", reply_markup=get_back_to_main_menu_kb())
    else:
        await callback.message.edit_text("Выберите пользователя для утверждения:",
                                         reply_markup=get_pending_users_kb(pending_users))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_user_details:"))
async def show_user_details(callback: types.CallbackQuery, user: User | None):
    if not user or user.role.value != "admin":
        await callback.answer("Эта функция доступна только администраторам.", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(f"Выберите роль для пользователя #{user_id}:",
                                     reply_markup=get_user_approval_kb(user_id))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_approve:"))
async def approve_user(callback: types.CallbackQuery, session: AsyncSession, user: User | None):
    if not user or user.role.value != "admin":
        await callback.answer("Эта функция доступна только администраторам.", show_alert=True)
        return

    _, user_id_str, role_str = callback.data.split(":")
    user_to_approve = await session.get(User, int(user_id_str))

    if user_to_approve and user_to_approve.role == UserRole.PENDING:
        role_to_assign = UserRole[role_str]
        user_to_approve.role = role_to_assign
        await session.commit()
        await callback.message.edit_text(f"✅ Пользователь {user_to_approve.full_name} одобрен с ролью '{role_to_assign.value}'.", reply_markup=get_back_to_main_menu_kb())
        try:
            await callback.bot.send_message(user_to_approve.telegram_id, "Ваша учетная запись одобрена! Нажмите /start, чтобы начать работу.")
        except Exception as e:
            print(f"Failed to notify user {user_to_approve.telegram_id}: {e}")
    else:
        await callback.message.edit_text("Пользователь не найден или уже одобрен.", reply_markup=get_back_to_main_menu_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("admin_reject_user:"))
async def reject_user(callback: types.CallbackQuery, session: AsyncSession, user: User | None):
    if not user or user.role.value != "admin":
        await callback.answer("Эта функция доступна только администраторам.", show_alert=True)
        return
    user_id = int(callback.data.split(":")[1])
    user_to_reject = await session.get(User, user_id)

    if user_to_reject and user_to_reject.role == UserRole.PENDING:
        await session.delete(user_to_reject)
        await session.commit()
        await callback.message.edit_text(f"❌ Заявка пользователя {user_to_reject.full_name} отклонена. Пользователь удален.", reply_markup=get_back_to_main_menu_kb())
        try:
            await callback.bot.send_message(user_id, "К сожалению, ваша заявка на регистрацию в боте была отклонена.")
        except Exception as e:
            print(f"Failed to notify user {user_id}: {e}")
    else:
        await callback.message.edit_text("Пользователь не найден или уже одобрен.", reply_markup=get_back_to_main_menu_kb())
    await callback.answer()


# Назначение водителей
@router.callback_query(F.data == "admin_assign_drivers")
async def show_unassigned_bookings(callback: types.CallbackQuery, session: AsyncSession, user: User | None):
    if not user or user.role.value != "admin":
        await callback.answer("Эта функция доступна только администраторам.", show_alert=True)
        return

    res = await session.execute(
        select(Booking).options(selectinload(Booking.creator)).where(Booking.status == 'pending_driver').order_by(
            Booking.booking_date))
    bookings = list(res.scalars().unique().all())
    if not bookings:
        await callback.message.edit_text("Нет заявок, ожидающих назначения водителя.",
                                         reply_markup=get_back_to_main_menu_kb())
    else:
        await callback.message.edit_text("Выберите заявку для назначения водителя:",
                                         reply_markup=get_unassigned_bookings_kb(bookings))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_assign_booking:"))
async def assign_booking_prompt(callback: types.CallbackQuery, session: AsyncSession, user: User | None):
    if not user or user.role.value != "admin":
        await callback.answer("Эта функция доступна только администраторам.", show_alert=True)
        return

    booking_id = int(callback.data.split(":")[1])
    res = await session.execute(select(User).where(User.role == UserRole.DRIVER))
    drivers = list(res.scalars().all())

    if not drivers:
        await callback.answer("В системе нет одобренных водителей для назначения!", show_alert=True)
        return

    await callback.message.edit_text(f"Выберите водителя для заявки #{booking_id}:",
                                     reply_markup=get_driver_selection_kb(booking_id, drivers))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_select_driver:"))
async def select_driver_for_booking(callback: types.CallbackQuery, session: AsyncSession, user: User | None):
    if not user or user.role.value != "admin":
        await callback.answer("Эта функция доступна только администраторам.", show_alert=True)
        return
    _, booking_id_str, driver_id_str = callback.data.split(":")
    booking = await session.get(Booking, int(booking_id_str), options=[selectinload(Booking.creator)])
    driver = await session.get(User, int(driver_id_str))

    if booking and driver:
        booking.driver_id = driver.telegram_id
        booking.status = 'pending_confirmation'
        await session.commit()
        await callback.message.edit_text(
            f"✅ Заявка #{booking.id} отправлена на подтверждение водителю {driver.full_name}.",
            reply_markup=get_back_to_main_menu_kb())

        try:
            notification_text = (
                f"🔔 Вам предложена новая поездка #{booking.id} от {booking.creator.full_name}.\n"
                f"Дата: {booking.booking_date.strftime('%d.%m.%Y')}.\n"
                f"Пожалуйста, подтвердите или отклоните ее."
            )
            await callback.bot.send_message(
                driver.telegram_id,
                notification_text,
                reply_markup=get_driver_booking_confirmation_kb(booking.id)
            )
        except Exception as e:
            print(f"Error sending notifications for booking {booking.id}: {e}")
    else:
        await callback.message.edit_text("Ошибка: заявка или водитель не найдены.", reply_markup=get_back_to_main_menu_kb())
    await callback.answer()