from datetime import datetime, time
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config_reader import ADMIN_IDS
from db.models import Booking as BookingModel, Waypoint, User, UserRole, SharedTripParticipant
from states.booking_states import Booking
from keyboards.inline import (
    get_calendar_kb, get_add_point_kb, get_confirm_booking_kb,
    get_back_to_main_menu_kb, get_joinable_trips_kb
)
from sqlalchemy.orm import selectinload

router = Router()


async def is_employee_filter(message: types.Message | types.CallbackQuery, user: User | None) -> bool:
    return user and user.role.value == "employee"


router.message.filter(is_employee_filter)
router.callback_query.filter(is_employee_filter)


# Выбор даты
@router.callback_query(F.data == "new_timed_booking")
async def start_booking(callback: types.CallbackQuery, state: FSMContext, user: User | None):
    if not user or user.role != UserRole.EMPLOYEE:
        await callback.answer("Эта функция доступна только сотрудникам.", show_alert=True)
        return
    await state.set_state(Booking.choosing_date)
    await callback.message.edit_text("Выберите дату поездки:", reply_markup=get_calendar_kb())
    await callback.answer()


# Ввод маршрута

@router.message(Booking.entering_start_point)
async def process_start_point(message: types.Message, state: FSMContext, user: User | None):
    if not user or user.role != UserRole.EMPLOYEE: return
    await state.update_data(start_point_address=message.text)
    await state.set_state(Booking.entering_start_time)
    await message.answer("Отлично. Теперь введите <b>время отправления</b> в формате <b>ЧЧ:ММ</b> (например, 10:15)")


@router.message(Booking.entering_start_time)
async def process_start_time(message: types.Message, state: FSMContext, user: User | None):
    if not user or user.role != UserRole.EMPLOYEE: return
    try:
        datetime.strptime(message.text, '%H:%M')
        await state.update_data(start_time_raw=message.text, intermediate_points=[])
        await state.set_state(Booking.choosing_next_point)
        await message.answer("Начальная точка добавлена. Хотите добавить промежуточную или сразу конечную?",
                             reply_markup=get_add_point_kb())
    except ValueError:
        await message.answer(
            "❗️ Неверный формат времени. Пожалуйста, введите время в формате <b>ЧЧ:ММ</b> (например, 09:30 или 18:00).")


@router.callback_query(F.data == "add_intermediate_point", Booking.choosing_next_point)
async def request_intermediate_point(callback: types.CallbackQuery, state: FSMContext, user: User | None):
    if not user or user.role != UserRole.EMPLOYEE: return
    await state.set_state(Booking.entering_intermediate_address)
    await callback.message.edit_text("Введите <b>адрес промежуточной точки</b>:")
    await callback.answer()


@router.callback_query(F.data == "add_end_point", Booking.choosing_next_point)
async def request_end_point(callback: types.CallbackQuery, state: FSMContext, user: User | None):
    if not user or user.role != UserRole.EMPLOYEE: return
    await state.set_state(Booking.entering_end_address)
    await callback.message.edit_text("Введите <b>адрес конечной точки</b>:")
    await callback.answer()


@router.message(Booking.entering_intermediate_address)
async def process_intermediate_address(message: types.Message, state: FSMContext, user: User | None):
    if not user or user.role != UserRole.EMPLOYEE: return
    await state.update_data(current_intermediate_address=message.text)
    await state.set_state(Booking.entering_intermediate_time)
    await message.answer("Отлично. Теперь введите <b>время прибытия</b> на эту точку (формат ЧЧ:ММ):")


@router.message(Booking.entering_intermediate_time)
async def process_intermediate_time(message: types.Message, state: FSMContext, user: User | None):
    if not user or user.role != UserRole.EMPLOYEE: return
    try:
        datetime.strptime(message.text, '%H:%M')
        await state.update_data(current_intermediate_time=message.text)
        await state.set_state(Booking.entering_intermediate_wait)
        await message.answer("Принято. Теперь введите <b>время ожидания</b> на этой точке (в минутах, просто число):")
    except ValueError:
        await message.answer("❗️ Неверный формат времени. Пожалуйста, введите время в формате <b>ЧЧ:ММ</b>.")


@router.message(Booking.entering_intermediate_wait)
async def process_intermediate_wait(message: types.Message, state: FSMContext, user: User | None):
    if not user or user.role != UserRole.EMPLOYEE: return
    try:
        wait_minutes = int(message.text)
        user_data = await state.get_data()
        new_point = {"address": user_data.get("current_intermediate_address"),
                     "time": user_data.get("current_intermediate_time"), "wait": wait_minutes}
        intermediate_points = user_data.get('intermediate_points', [])
        intermediate_points.append(new_point)
        await state.update_data(intermediate_points=intermediate_points, current_intermediate_address=None,
                                current_intermediate_time=None)
        await state.set_state(Booking.choosing_next_point)
        await message.answer(
            f"Промежуточная точка <b>\"{new_point['address']}\"</b> добавлена.\n\nДобавляем следующую?",
            reply_markup=get_add_point_kb())
    except ValueError:
        await message.answer("❗️ Неверный формат. Пожалуйста, введите время ожидания просто числом (например, 15).")


@router.message(Booking.entering_end_address)
async def process_end_address(message: types.Message, state: FSMContext, user: User | None):
    if not user or user.role != UserRole.EMPLOYEE: return
    await state.update_data(end_point_address=message.text)
    await state.set_state(Booking.entering_end_time)
    await message.answer("Принято. Теперь введите примерное <b>время прибытия</b> на конечную точку (формат ЧЧ:ММ):")


# Проверка пересечений по времени
@router.message(Booking.entering_end_time)
async def process_end_time_and_check_conflicts(message: types.Message, state: FSMContext, session: AsyncSession,
                                               user: User | None):
    if not user or user.role != UserRole.EMPLOYEE: return
    try:
        end_time = datetime.strptime(message.text, '%H:%M').time()
        await state.update_data(end_point_time=message.text)

        user_data = await state.get_data()
        booking_date = user_data['booking_date']
        start_time_str = user_data['start_time_raw']
        start_time = datetime.strptime(start_time_str, '%H:%M').time()

        conflicting_bookings = await find_conflicting_bookings(session, booking_date, start_time, end_time,
                                                               user.telegram_id)

        if conflicting_bookings:
            await state.set_state(Booking.choosing_next_point)
            await message.answer(
                "❗️ На выбранное вами время уже есть поездки, к которым можно присоединиться. Выберите одну из них или создайте свою заявку.",
                reply_markup=get_joinable_trips_kb(conflicting_bookings)
            )
            return

        await show_booking_summary(message, state)
    except ValueError:
        await message.answer("❗️ Неверный формат времени. Введите время как <b>ЧЧ:ММ</b>.")


# Присоединиться или создать свою

@router.callback_query(F.data == "create_anyway", Booking.choosing_next_point)
async def create_booking_anyway(callback: types.CallbackQuery, state: FSMContext, user: User | None):
    if not user or user.role != UserRole.EMPLOYEE: return
    await callback.message.delete()
    await show_booking_summary(callback, state)
    await callback.answer()


@router.callback_query(F.data.startswith("join_trip:"), Booking.choosing_next_point)
async def join_existing_trip(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession, user: User | None):
    if not user or user.role != UserRole.EMPLOYEE: return

    booking_id = int(callback.data.split(":")[1])
    booking = await session.get(BookingModel, booking_id)

    if not booking:
        await callback.answer("Поездка больше не доступна.", show_alert=True)
        return

    new_participant = SharedTripParticipant(booking_id=booking_id, user_id=user.telegram_id, status='approved')
    session.add(new_participant)
    await session.commit()
    await state.clear()

    try:
        await callback.bot.send_message(
            chat_id=int(booking.user_id),
            text=f"👤 К вашей поездке #{booking.id} присоединился {user.full_name}."
        )

        if booking.driver_id:
            await callback.bot.send_message(
                chat_id=int(booking.driver_id),
                text=f"👤 К вашей поездке #{booking.id} присоединился новый пассажир: {user.full_name}."
            )

    except Exception as e:
        print(f"Ошибка уведомления о присоединении к поездке {booking_id}: {e}")

    await callback.message.edit_text(f"✅ Вы успешно присоединились к поездке #{booking_id}!",
                                     reply_markup=get_back_to_main_menu_kb())
    await callback.answer()


# Подтверждение и сохранение заявки

@router.callback_query(F.data.startswith("confirm_booking:"), Booking.confirming_booking)
async def process_booking_confirmation(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession,
                                       user: User | None):
    if not user or user.role != UserRole.EMPLOYEE: return

    share_type = callback.data.split(":")[1]
    allow_sharing = True if share_type == "shared" else False

    booking_id = await save_booking_to_db(state, user, session, allow_sharing)
    if booking_id:
        for admin_id in ADMIN_IDS:
            try:
                await callback.bot.send_message(admin_id,
                                                f"🔔 Новая заявка #{booking_id} от сотрудника {user.full_name}. Требуется назначить водителя.")
            except Exception as e:
                print(f"Ошибка отправки уведомления админу {admin_id}: {e}")
        await callback.message.edit_text("✅ Ваша заявка успешно создана и отправлена на обработку!",
                                         reply_markup=get_back_to_main_menu_kb())
    else:
        await callback.message.edit_text("Произошла ошибка при сохранении. Попробуйте снова.",
                                         reply_markup=get_back_to_main_menu_kb())
    await callback.answer()


# Вспомогательные функции

async def show_booking_summary(message_or_callback: types.Message | types.CallbackQuery, state: FSMContext):
    await state.set_state(Booking.confirming_booking)
    user_data = await state.get_data()

    date_str = user_data['booking_date'].strftime('%d.%m.%Y')
    start_address = user_data['start_point_address']
    start_time = user_data['start_time_raw']
    intermediate_points = user_data.get('intermediate_points', [])
    end_address = user_data['end_point_address']
    end_time = user_data['end_point_time']

    response_text = "<b>Проверьте детали бронирования:</b>\n\n"
    response_text += f"<b>Дата:</b> {date_str}\n"
    response_text += f"<b>Начало:</b> {start_address} в {start_time}\n"
    if intermediate_points:
        response_text += "<b>Промежуточные точки:</b>\n"
        for i, point in enumerate(intermediate_points, 1):
            response_text += f"  {i}. {point['address']} (прибытие: {point['time']}, ожидание: {point['wait']} мин)\n"
    response_text += f"<b>Конец:</b> {end_address} в {end_time}\n\n"
    response_text += "Все верно?"

    target_message = message_or_callback if isinstance(message_or_callback,
                                                       types.Message) else message_or_callback.message
    await target_message.answer(response_text, reply_markup=get_confirm_booking_kb())


async def save_booking_to_db(state: FSMContext, user: User, session: AsyncSession, allow_sharing: bool) -> int | None:
    try:
        data = await state.get_data()
        new_booking = BookingModel(
            user_id=user.telegram_id,
            passenger_name=user.full_name,
            booking_date=data['booking_date'],
            allow_sharing=allow_sharing
        )
        session.add(new_booking)
        await session.flush()

        waypoints_to_add = []
        waypoints_to_add.append(
            Waypoint(booking_id=new_booking.id, point_type='start', address=data['start_point_address'],
                     departure_time=datetime.strptime(data['start_time_raw'], '%H:%M').time(), order_num=1))
        for i, p in enumerate(data.get('intermediate_points', []), 2):
            waypoints_to_add.append(Waypoint(booking_id=new_booking.id, point_type='intermediate', address=p['address'],
                                             arrival_time=datetime.strptime(p['time'], '%H:%M').time(),
                                             wait_minutes=int(p['wait']), order_num=i + 1))
        waypoints_to_add.append(Waypoint(booking_id=new_booking.id, point_type='end', address=data['end_point_address'],
                                         arrival_time=datetime.strptime(data['end_point_time'], '%H:%M').time(),
                                         order_num=len(waypoints_to_add) + 1))

        session.add_all(waypoints_to_add)
        await session.commit()
        return new_booking.id
    except Exception as e:
        print(f"Ошибка при сохранении в БД: {e}")
        await session.rollback()
        return None


async def find_conflicting_bookings(session: AsyncSession, date, start_time: time, end_time: time,
                                    current_user_id: int) -> list[BookingModel]:

    print("\n--- [DEBUG] Запуск find_conflicting_bookings ---")
    print(f"[DEBUG] Ищу конфликты для даты: {date}, время: {start_time} - {end_time}, user_id: {current_user_id}")

    result = await session.execute(
        select(BookingModel)
        .options(selectinload(BookingModel.waypoints), selectinload(BookingModel.creator))
        .where(
            BookingModel.booking_date == date,
            BookingModel.allow_sharing == True,
            BookingModel.status.in_(['confirmed', 'pending_driver']),
            BookingModel.user_id != current_user_id
        )
    )
    potential_bookings = result.scalars().unique().all()

    print(f"[DEBUG] Найдено потенциальных поездок для проверки: {len(potential_bookings)}")

    conflicts = []
    for booking in potential_bookings:
        print(f"\n[DEBUG] Проверяю поездку #{booking.id}, создатель: {booking.creator.full_name}")

        times = []
        for w in booking.waypoints:
            print(f"  -> Точка: '{w.address}', Отправление: {w.departure_time}, Прибытие: {w.arrival_time}")
            if w.departure_time:
                times.append(w.departure_time)
            if w.arrival_time:
                times.append(w.arrival_time)

        if not times:
            print("[DEBUG] У поездки нет временных меток. Пропускаю.")
            continue

        existing_start = min(times)
        existing_end = max(times)
        print(f"[DEBUG] Временные рамки поездки: {existing_start} - {existing_end}")

        is_conflicting = start_time < existing_end and end_time > existing_start
        print(
            f"[DEBUG] Проверка пересечения ({start_time} < {existing_end} and {end_time} > {existing_start}) -> {is_conflicting}")

        if is_conflicting:
            print(f"[DEBUG] НАЙДЕН КОНФЛИКТ! Добавляю поездку #{booking.id} в список.")
            conflicts.append(booking)

    print(f"--- [DEBUG] Завершение find_conflicting_bookings. Найдено конфликтов: {len(conflicts)} ---\n")
    return conflicts
