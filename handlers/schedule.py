from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from datetime import date
from db.models import Booking, User, UserRole, SharedTripParticipant
from keyboards.inline import get_calendar_kb, get_back_to_main_menu_kb
from states.booking_states import ViewSchedule
from config_reader import ADMIN_IDS

router = Router()


@router.callback_query(F.data == "view_my_bookings")
async def request_employee_schedule(callback: types.CallbackQuery, state: FSMContext, user: User | None):
    if not user or user.role != UserRole.EMPLOYEE:
        await callback.answer("Эта функция доступна только сотрудникам.", show_alert=True)
        return
    await state.set_state(ViewSchedule.choosing_date)
    await state.update_data(schedule_type=callback.data)
    await callback.message.edit_text("Выберите дату для просмотра ваших заявок:", reply_markup=get_calendar_kb(for_viewing=True))
    await callback.answer()


@router.callback_query(F.data == "view_driver_schedule")
async def request_driver_schedule(callback: types.CallbackQuery, state: FSMContext, user: User | None):
    if not user or user.role != UserRole.DRIVER:
        await callback.answer("Эта функция доступна только водителям.", show_alert=True)
        return
    await state.set_state(ViewSchedule.choosing_date)
    await state.update_data(schedule_type=callback.data)
    await callback.message.edit_text("Выберите дату для просмотра вашего расписания:", reply_markup=get_calendar_kb(for_viewing=True))
    await callback.answer()


@router.callback_query(F.data.startswith("calendar:day:"), ViewSchedule.choosing_date)
async def process_schedule_date(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession,
                                user: User | None):
    if not user:
        await callback.message.edit_text("Не удалось определить пользователя.", reply_markup=get_back_to_main_menu_kb())
        return

    parts = callback.data.split(":")
    year, month, day = map(int, parts[2:])
    selected_date = date(year, month, day)

    fsm_data = await state.get_data()
    schedule_type = fsm_data.get('schedule_type')
    await state.set_state(None)

    query = select(Booking).options(
        selectinload(Booking.waypoints),
        selectinload(Booking.driver),
        selectinload(Booking.creator),
        selectinload(Booking.participants).selectinload(SharedTripParticipant.user)
    ).where(
        Booking.booking_date == selected_date,
        Booking.status.in_(['confirmed', 'pending_driver'])
    ).order_by(Booking.id)

    title = ""

    if schedule_type == 'view_my_bookings' and user.role.value == "employee":
        query = query.where(Booking.user_id == user.telegram_id)
        title = "Ваши заявки"
    elif schedule_type == 'view_driver_schedule' and user.role.value == "driver":
        query = query.where(Booking.driver_id == user.telegram_id)
        title = "Ваше расписание"
    else:
        await callback.message.edit_text("Ошибка доступа.", reply_markup=get_back_to_main_menu_kb())
        return

    bookings = list((await session.execute(query)).scalars().unique().all())

    if not bookings:
        response_text = f"На {selected_date.strftime('%d.%m.%Y')} у вас нет записей."
    else:
        response_text = f"<b>{title} на {selected_date.strftime('%d.%m.%Y')}:</b>\n"
        for b in bookings:
            driver_info = f"Водитель: {b.driver.full_name}" if b.driver else "Водитель не назначен"
            status_text = {
                'pending_driver': '🟡 Ожидает водителя',
                'confirmed': '✅ Подтверждено',
                'cancelled': '❌ Отменено'
            }.get(b.status, b.status)

            response_text += f"\n" + ("-" * 20) + f"\n<b>Заявка #{b.id}</b> ({status_text})\n"

            response_text += f"👤 <b>Пассажир (организатор):</b> {b.creator.full_name}\n"

            if b.participants:
                response_text += "👥 <b>Присоединились:</b>\n"
                for p in b.participants:
                    if p.user:
                        response_text += f"  - {p.user.full_name}\n"

            response_text += f"🚗 {driver_info}\n"

            if b.booking_type == 'allday':
                response_text += f"📍 <b>Маршрут:</b> На весь день ({b.passenger_name or 'без цели'})\n"
                if b.comment:
                    response_text += f"📝 <b>Комментарий:</b> {b.comment}\n"
            else:
                response_text += f"📍 <b>Маршрут:</b>\n"
                sorted_waypoints = sorted(b.waypoints, key=lambda w: w.order_num)
                for p in sorted_waypoints:
                    time_info = ""
                    if p.point_type == 'start' and p.departure_time: time_info = f" (отпр. {p.departure_time.strftime('%H:%M')})"
                    if p.point_type != 'start' and p.arrival_time: time_info = f" (приб. {p.arrival_time.strftime('%H:%M')})"
                    response_text += f"  - {p.address}{time_info}\n"

    await callback.message.edit_text(response_text, reply_markup=get_back_to_main_menu_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("driver_approve:"))
async def approve_booking_by_driver(callback: types.CallbackQuery, session: AsyncSession, user: User | None):
    if not user or user.role != UserRole.DRIVER:
        await callback.answer("Эта функция доступна только водителям.", show_alert=True)
        return

    booking_id = int(callback.data.split(":")[1])
    booking = await session.get(Booking, booking_id, options=[selectinload(Booking.creator)])

    if not booking or booking.driver_id != user.telegram_id or booking.status != 'pending_confirmation':
        await callback.message.edit_text("Эта заявка больше не актуальна.")
        await callback.answer()
        return

    booking.status = 'confirmed'
    await session.commit()

    await callback.message.edit_text(f"✅ Вы подтвердили поездку #{booking.id}.")

    try:
        await callback.bot.send_message(
            booking.user_id,
            f"✅ Ваша заявка #{booking.id} подтверждена водителем {user.full_name}!"
        )
    except Exception as e:
        print(f"Не удалось уведомить сотрудника {booking.user_id}: {e}")

    await callback.answer()


@router.callback_query(F.data.startswith("driver_reject:"))
async def reject_booking_by_driver(callback: types.CallbackQuery, session: AsyncSession, user: User | None):
    if not user or user.role != UserRole.DRIVER:
        await callback.answer("Эта функция доступна только водителям.", show_alert=True)
        return

    booking_id = int(callback.data.split(":")[1])
    booking = await session.get(Booking, booking_id, options=[selectinload(Booking.creator)])

    if not booking or booking.driver_id != user.telegram_id or booking.status != 'pending_confirmation':
        await callback.message.edit_text("Эта заявка больше не актуальна.")
        await callback.answer()
        return

    booking.status = 'pending_driver'
    booking.driver_id = None
    await session.commit()

    await callback.message.edit_text(f"❌ Вы отклонили поездку #{booking.id}.")

    notification_text = (
        f"❗️ Водитель {user.full_name} отклонил заявку #{booking.id} "
        f"от сотрудника {booking.creator.full_name}.\n"
        f"Требуется назначить другого водителя."
    )
    for admin_id in ADMIN_IDS:
        try:
            await callback.bot.send_message(admin_id, notification_text)
        except Exception as e:
            print(f"Не удалось уведомить админа {admin_id}: {e}")

    await callback.answer()
