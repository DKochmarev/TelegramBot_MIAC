from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.simple_calendar import SimpleRussianCalendar
from db.models import User, Booking

# Универсальные кнопки
cancel_fsm_button = InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_fsm")
back_to_main_menu_button = InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_main_menu")


def get_back_to_main_menu_kb():
    return InlineKeyboardBuilder().row(back_to_main_menu_button).as_markup()


# Главные меню для ролей
def get_employee_menu_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🗓 Мои заявки", callback_data="view_my_bookings"))
    builder.row(InlineKeyboardButton(text="➕ Новая заявка (со временем)", callback_data="new_timed_booking"))
    builder.row(InlineKeyboardButton(text="📅 Новая заявка (на весь день)", callback_data="new_allday_booking"))
    builder.row(InlineKeyboardButton(text="❌ Отменить заявку", callback_data="cancel_booking"))
    return builder.as_markup()


def get_driver_menu_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🗓 Мое расписание", callback_data="view_driver_schedule"))
    return builder.as_markup()


def get_admin_menu_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👤 Утверждение пользователей", callback_data="admin_approve_users"))
    builder.row(InlineKeyboardButton(text="🚗 Назначение водителей", callback_data="admin_assign_drivers"))
    return builder.as_markup()


# FSM Клавиатуры
def get_calendar_kb(year: int = None, month: int = None, for_viewing: bool = False):
    return SimpleRussianCalendar.create_calendar(year, month, for_viewing)


def get_add_point_kb():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Промежуточная", callback_data="add_intermediate_point"),
        InlineKeyboardButton(text="🏁 Конечная", callback_data="add_end_point")
    )
    builder.row(cancel_fsm_button)
    return builder.as_markup()


def get_confirm_booking_kb():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить как личную", callback_data="confirm_booking:private")
    )
    builder.row(
        InlineKeyboardButton(text="🤝 Разрешить присоединиться другим", callback_data="confirm_booking:shared")
    )
    builder.row(cancel_fsm_button)
    return builder.as_markup()


def get_joinable_trips_kb(bookings: list[Booking]):
    builder = InlineKeyboardBuilder()
    for booking in bookings:
        start_point = next((w for w in booking.waypoints if w.point_type == 'start'), None)
        if not start_point: continue

        time_str = start_point.departure_time.strftime('%H:%M')
        creator_name = booking.creator.full_name

        text = f"{time_str} с {creator_name} (Маршрут: {start_point.address} ...)"
        builder.row(
            InlineKeyboardButton(text=text, callback_data=f"join_trip:{booking.id}")
        )
    builder.row(
        InlineKeyboardButton(text="✍️ Все равно создать свою заявку", callback_data="create_anyway")
    )
    builder.row(cancel_fsm_button)
    return builder.as_markup()


# Админ-панель
def get_pending_users_kb(users: list[User]):
    builder = InlineKeyboardBuilder()
    for user in users:
        builder.row(InlineKeyboardButton(
            text=f"{user.full_name} (@{user.username or 'N/A'})",
            callback_data=f"admin_user_details:{user.telegram_id}"
        ))
    builder.row(back_to_main_menu_button)
    return builder.as_markup()


def get_user_approval_kb(user_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Одобрить (Сотрудник)", callback_data=f"admin_approve:{user_id}:EMPLOYEE"),
        InlineKeyboardButton(text="✅ Одобрить (Водитель)", callback_data=f"admin_approve:{user_id}:DRIVER")
    )
    builder.row(InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject_user:{user_id}"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="admin_approve_users"))
    return builder.as_markup()


def get_unassigned_bookings_kb(bookings: list[Booking]):
    builder = InlineKeyboardBuilder()
    for booking in bookings:
        date_str = booking.booking_date.strftime('%d.%m')
        creator_name = booking.creator.full_name if booking.creator else "Неизвестно"
        text = f"Заявка #{booking.id} ({date_str}) от {creator_name}"
        builder.row(InlineKeyboardButton(text=text, callback_data=f"admin_assign_booking:{booking.id}"))
    builder.row(back_to_main_menu_button)
    return builder.as_markup()


def get_driver_selection_kb(booking_id: int, drivers: list[User]):
    builder = InlineKeyboardBuilder()
    for driver in drivers:
        builder.row(InlineKeyboardButton(
            text=driver.full_name,
            callback_data=f"admin_select_driver:{booking_id}:{driver.telegram_id}"
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад к заявкам", callback_data="admin_assign_drivers"))
    return builder.as_markup()


# Отмена брони
def get_bookings_for_cancellation_kb(bookings):
    builder = InlineKeyboardBuilder()
    for booking in bookings:
        if booking.booking_type == 'allday':
            route_text = f"Весь день ({booking.comment or 'без комментария'})"
            time_text = ""
        else:
            start_point = next((w for w in booking.waypoints if w.point_type == 'start'), None)
            end_point = next((w for w in booking.waypoints if w.point_type == 'end'), None)
            route_text = f"{start_point.address} ➡️ {end_point.address}" if start_point and end_point else "Маршрут не указан"
            time_text = f"({start_point.departure_time.strftime('%H:%M')})" if start_point and start_point.departure_time else ""

        date_text = booking.booking_date.strftime('%d.%m')
        button_text = f"❌ {date_text} {time_text} {route_text}"
        builder.row(InlineKeyboardButton(text=button_text, callback_data=f"cancel_booking_id:{booking.id}"))

    builder.row(back_to_main_menu_button)
    return builder.as_markup()


def get_confirm_cancellation_kb(booking_id):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, отменить", callback_data=f"confirm_cancel:{booking_id}"),
        InlineKeyboardButton(text="⬅️ Нет, назад", callback_data="back_to_main_menu")
    )
    return builder.as_markup()


def get_driver_booking_confirmation_kb(booking_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Принять", callback_data=f"driver_approve:{booking_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"driver_reject:{booking_id}")
    )
    return builder.as_markup()
