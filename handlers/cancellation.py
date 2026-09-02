from datetime import date
from aiogram import Router, F, types
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from db.models import Booking, User, UserRole
from keyboards.inline import get_bookings_for_cancellation_kb, get_confirm_cancellation_kb, get_back_to_main_menu_kb

router = Router()


# "Отменить заявку"
@router.callback_query(F.data == "cancel_booking")
async def list_bookings_for_cancellation(callback: types.CallbackQuery, session: AsyncSession, user: User | None):
    if not user or user.role != UserRole.EMPLOYEE:
        await callback.answer("Эта функция доступна только сотрудникам.", show_alert=True)
        return

    today = date.today()
    result = await session.execute(
        select(Booking)
        .options(selectinload(Booking.waypoints))
        .where(
            Booking.user_id == user.telegram_id,
            Booking.status.in_(['confirmed', 'pending_driver']),
            Booking.booking_date >= today
        ).order_by(Booking.booking_date)
    )
    user_bookings = list(result.scalars().unique().all())

    if not user_bookings:
        await callback.message.edit_text(
            "У вас нет активных заявок для отмены.",
            reply_markup=get_back_to_main_menu_kb()
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "Какую заявку вы хотите отменить?",
        reply_markup=get_bookings_for_cancellation_kb(user_bookings)
    )
    await callback.answer()


# Пользователь выбрал конкретную заявку для отмены
@router.callback_query(F.data.startswith("cancel_booking_id:"))
async def confirm_cancellation(callback: types.CallbackQuery, user: User | None):
    if not user or user.role != UserRole.EMPLOYEE:
        await callback.answer("Эта функция доступна только сотрудникам.", show_alert=True)
        return

    booking_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        f"Вы уверены, что хотите отменить заявку #{booking_id}?",
        reply_markup=get_confirm_cancellation_kb(booking_id)
    )
    await callback.answer()


# Пользователь подтвердил отмену
@router.callback_query(F.data.startswith("confirm_cancel:"))
async def process_cancellation(callback: types.CallbackQuery, session: AsyncSession, user: User | None):
    if not user or user.role != UserRole.EMPLOYEE:
        await callback.answer("Эта функция доступна только сотрудникам.", show_alert=True)
        return

    booking_id = int(callback.data.split(":")[1])
    booking_to_cancel = await session.get(Booking, booking_id)
    if booking_to_cancel and booking_to_cancel.user_id == user.telegram_id:
        booking_to_cancel.status = 'cancelled'
        await session.commit()
        await callback.message.edit_text(
            f"✅ Заявка #{booking_id} успешно отменена.",
            reply_markup=get_back_to_main_menu_kb()
        )
    else:
        await callback.message.edit_text(
            "Не удалось найти эту заявку или у вас нет прав на ее отмену.",
            reply_markup=get_back_to_main_menu_kb()
        )
    await callback.answer()