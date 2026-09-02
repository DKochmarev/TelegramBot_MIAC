from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from config_reader import ADMIN_IDS
from db.models import Booking as BookingModel, User
from states.booking_states import AllDayBooking
from keyboards.inline import get_calendar_kb, get_back_to_main_menu_kb

router = Router()


@router.callback_query(F.data == "new_allday_booking")
async def start_allday_booking(callback: types.CallbackQuery, state: FSMContext, user: User | None):
    if not user or user.role.value != "employee":
        await callback.answer("Эта функция доступна только сотрудникам.", show_alert=True)
        return
    await state.set_state(AllDayBooking.choosing_date)
    await callback.message.edit_text("Выберите дату для заявки на весь день:", reply_markup=get_calendar_kb())
    await callback.answer()


@router.message(AllDayBooking.entering_comment)
async def process_comment_and_save(message: types.Message, state: FSMContext, session: AsyncSession, user: User | None):
    if not user or user.role.value != "employee":
        return

    user_data = await state.get_data()
    new_booking = BookingModel(
        user_id=user.telegram_id,
        passenger_name=user.full_name,
        comment=message.text,
        booking_date=user_data['booking_date'],
        booking_type='allday',
        status='pending_driver'
    )
    session.add(new_booking)
    await session.commit()
    await state.clear()

    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(admin_id, f"🔔 Новая заявка на весь день #{new_booking.id} от {user.full_name}.\nКомментарий: {message.text}")
        except Exception as e:
            print(f"Ошибка отправки уведомления админу {admin_id}: {e}")

    await message.answer("✅ Заявка на весь день успешно создана и отправлена!", reply_markup=get_back_to_main_menu_kb())
