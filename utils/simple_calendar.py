from datetime import datetime, date
from calendar import monthrange
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


class SimpleRussianCalendar:
    MONTHS = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ]
    DAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

    @staticmethod
    def create_calendar(year: int = None, month: int = None, for_viewing: bool = False) -> InlineKeyboardMarkup:
        now = datetime.now()
        year = year or now.year
        month = month or now.month

        builder = InlineKeyboardBuilder()

        builder.row(
            InlineKeyboardButton(text="◀️", callback_data=f"calendar:prev:{year}:{month}"),
            InlineKeyboardButton(
                text=f"{SimpleRussianCalendar.MONTHS[month - 1]} {year}",
                callback_data="calendar:ignore"
            ),
            InlineKeyboardButton(text="▶️", callback_data=f"calendar:next:{year}:{month}")
        )

        builder.row(*[
            InlineKeyboardButton(text=day, callback_data="calendar:ignore")
            for day in SimpleRussianCalendar.DAYS
        ])

        first_day = date(year, month, 1).weekday()
        days_in_month = monthrange(year, month)[1]

        buttons = []
        for _ in range(first_day):
            buttons.append(InlineKeyboardButton(text=" ", callback_data="calendar:ignore"))

        today = date.today()
        for day in range(1, days_in_month + 1):
            current_date = date(year, month, day)
            if current_date < today:
                text = f"·{day}·"
            else:
                text = str(day)

            buttons.append(
                InlineKeyboardButton(
                    text=text,
                    callback_data=f"calendar:day:{year}:{month}:{day}"
                )
            )

        while len(buttons) % 7 != 0:
            buttons.append(InlineKeyboardButton(text=" ", callback_data="calendar:ignore"))

        for i in range(0, len(buttons), 7):
            builder.row(*buttons[i:i + 7])

        builder.row(InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_fsm"))

        return builder.as_markup()
