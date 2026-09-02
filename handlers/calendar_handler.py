from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession

from utils.simple_calendar import SimpleRussianCalendar
from states.booking_states import Booking, AllDayBooking

router = Router()


@router.callback_query(F.data.startswith("calendar:"))
async def process_calendar_selection(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    action, *params = callback.data.split(":")[1:]

    if action == "ignore":
        await callback.answer()
        return

    current_state = await state.get_state()

    if current_state not in [Booking.choosing_date, AllDayBooking.choosing_date]:
        await callback.answer("Календарь неактивен для этого действия.", show_alert=True)
        return

    if action in ("prev", "next"):
        year, month = map(int, params)
        if action == "prev":
            month -= 1
            if month < 1:
                month = 12
                year -= 1
        else:
            month += 1
            if month > 12:
                month = 1
                year += 1

        await callback.message.edit_reply_markup(
            reply_markup=SimpleRussianCalendar.create_calendar(year, month)
        )
        await callback.answer()
        return

    if action == "day":
        year, month, day = map(int, params)
        selected_date = date(year, month, day)

        if selected_date < date.today():
            await callback.answer("❌ Нельзя выбрать прошедшую дату!", show_alert=True)
            return

        if current_state == Booking.choosing_date:
            await state.update_data(booking_date=selected_date)
            await state.set_state(Booking.entering_start_point)
            await callback.message.edit_text(
                f"Вы выбрали дату: {selected_date.strftime('%d.%m.%Y')}\n\n"
                "Теперь введите <b>адрес начальной точки</b> (например, Проспект Победы, 1):"
            )

        elif current_state == AllDayBooking.choosing_date:
            await state.update_data(booking_date=selected_date)
            await state.set_state(AllDayBooking.entering_comment)
            await callback.message.edit_text(
                f"Вы выбрали дату: {selected_date.strftime('%d.%m.%Y')}\n\n"
                "Теперь введите цель поездки или комментарий (например, 'Развозка документов по городу')."
            )

        await callback.answer()
