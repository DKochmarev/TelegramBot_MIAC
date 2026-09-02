# from datetime import date
# from aiogram import Router, F, types
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy.future import select
# from sqlalchemy.orm import selectinload
# from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
#
# from db.models import Booking, SharedTripParticipant
# from keyboards.inline import get_shared_trips_kb, get_main_menu_kb, get_manage_trip_request_kb
#
# router = Router()
#
#
# # Пользователь нажимает "Совместные поездки"
# @router.callback_query(F.data == "shared_trips")
# async def list_shared_trips(callback: types.CallbackQuery, session: AsyncSession):
#     today = date.today()
#
#     result = await session.execute(
#         select(Booking)
#         .options(
#             selectinload(Booking.user),
#             selectinload(Booking.waypoints)
#         )
#         .where(
#             Booking.is_shared == True,
#             Booking.status == 'confirmed',
#             Booking.booking_date == today,
#             #Booking.user_id != callback.from_user.id --- строка, которая запрещает пользователю видеть свои же собственные совместные поездки в общем списке
#         )
#     )
#     shared_bookings = result.scalars().unique().all()
#
#     if not shared_bookings:
#         back_kb = InlineKeyboardMarkup(inline_keyboard=[
#             [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_main_menu")]
#         ])
#         await callback.message.edit_text(
#             "На сегодня нет доступных совместных поездок.",
#             reply_markup=back_kb
#         )
#         await callback.answer()
#         return
#
#     await callback.message.edit_text(
#         "Выберите поездку, к которой хотите присоединиться:",
#         reply_markup=get_shared_trips_kb(shared_bookings)
#     )
#     await callback.answer()
#
#
# @router.callback_query(F.data.startswith("join_trip_id:"))
# async def join_trip_request(callback: types.CallbackQuery, session: AsyncSession):
#     booking_id = int(callback.data.split(":")[1])
#
#     existing_request = await session.execute(
#         select(SharedTripParticipant).where(
#             SharedTripParticipant.booking_id == booking_id,
#             SharedTripParticipant.user_id == callback.from_user.id
#         )
#     )
#     if existing_request.scalar_one_or_none():
#         await callback.answer("Вы уже подали заявку на участие в этой поездке.", show_alert=True)
#         return
#
#     new_participant = SharedTripParticipant(
#         booking_id=booking_id,
#         user_id=callback.from_user.id,
#         status='pending'
#     )
#     session.add(new_participant)
#
#     await session.flush()
#
#     booking = await session.get(Booking, booking_id)
#     if booking:
#         try:
#             await callback.bot.send_message(
#                 chat_id=booking.user_id,
#                 text=f"🔔 Новый запрос...",
#                 reply_markup=get_manage_trip_request_kb(new_participant.id)
#             )
#         except Exception as e:
#             print(f"Не удалось отправить уведомление водителю {booking.user_id}: {e}")
#
#     await session.commit()
#
#     await callback.answer("Ваша заявка отправлена водителю на рассмотрение!", show_alert=True)
#     await callback.message.edit_text("Вы вернулись в главное меню.", reply_markup=get_main_menu_kb())
#
#
# # Хендлер для кнопки "Назад", чтобы вернуться в главное меню
# @router.callback_query(F.data == "back_to_main_menu")
# async def back_to_main_menu(callback: types.CallbackQuery):
#     await callback.message.edit_text(
#         "Вы вернулись в главное меню. Выберите действие:",
#         reply_markup=get_main_menu_kb()
#     )
#     await callback.answer()
#
#
# # Водитель нажимает "Принять"
# @router.callback_query(F.data.startswith("approve_trip:"))
# async def approve_trip_request(callback: types.CallbackQuery, session: AsyncSession):
#     participant_id = int(callback.data.split(":")[1])
#
#     participant_req = await session.get(SharedTripParticipant, participant_id,
#                                         options=[selectinload(SharedTripParticipant.user)])
#
#     if not participant_req:
#         await callback.message.edit_text("Заявка не найдена или устарела.")
#         await callback.answer()
#         return
#
#     participant_req.status = 'approved'
#     await session.commit()
#
#     await callback.message.edit_text(
#         f"✅ Вы приняли заявку от пользователя {participant_req.user.full_name}."
#     )
#
#     try:
#         await callback.bot.send_message(
#             chat_id=participant_req.user_id,
#             text=f"Отличные новости! Ваша заявка на участие в поездке #{participant_req.booking_id} была принята."
#         )
#     except Exception as e:
#         print(f"Не удалось отправить уведомление пассажиру {participant_req.user_id}: {e}")
#
#     await callback.answer()
#
#
# # Водитель нажимает "Отклонить"
# @router.callback_query(F.data.startswith("reject_trip:"))
# async def reject_trip_request(callback: types.CallbackQuery, session: AsyncSession):
#     participant_id = int(callback.data.split(":")[1])
#
#     participant_req = await session.get(SharedTripParticipant, participant_id,
#                                         options=[selectinload(SharedTripParticipant.user)])
#
#     if not participant_req:
#         await callback.message.edit_text("Заявка не найдена или устарела.")
#         await callback.answer()
#         return
#
#     participant_req.status = 'rejected'
#     await session.commit()
#
#     await callback.message.edit_text(
#         f"❌ Вы отклонили заявку от пользователя {participant_req.user.full_name}."
#     )
#
#     try:
#         await callback.bot.send_message(
#             chat_id=participant_req.user_id,
#             text=f"К сожалению, ваша заявка на участие в поездке #{participant_req.booking_id} была отклонена."
#         )
#     except Exception as e:
#         print(f"Не удалось отправить уведомление пассажиру {participant_req.user_id}: {e}")
#
#     await callback.answer()