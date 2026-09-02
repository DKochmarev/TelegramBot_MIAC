from aiogram import Router, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from db.models import User, UserRole
from keyboards.inline import get_employee_menu_kb, get_driver_menu_kb, get_admin_menu_kb, get_user_approval_kb
from config_reader import ADMIN_IDS
from aiogram.fsm.state import any_state

router = Router()


async def send_main_menu(message_or_callback: types.Message | types.CallbackQuery, state: FSMContext, user: User):
    await state.clear()

    text, markup = "", None
    if user.role == UserRole.ADMIN:
        text, markup = f"Здравствуйте, {user.full_name}!\nДобро пожаловать в панель администратора.", get_admin_menu_kb()
    elif user.role == UserRole.EMPLOYEE:
        text, markup = f"Здравствуйте, {user.full_name}!\nВы можете создавать и управлять заявками.", get_employee_menu_kb()
    elif user.role == UserRole.DRIVER:
        text, markup = f"Здравствуйте, {user.full_name}!\nВам доступны назначенные поездки.", get_driver_menu_kb()

    if isinstance(message_or_callback, types.Message):
        await message_or_callback.answer(text, reply_markup=markup)
    else:
        try:
            await message_or_callback.message.edit_text(text, reply_markup=markup)
        except:
            await message_or_callback.message.delete()
            await message_or_callback.message.answer(text, reply_markup=markup)


@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext, user: User):
    if not user:
        await message.answer("Не удалось идентифицировать вас. Попробуйте еще раз.")
        return

    if user.role == UserRole.PENDING:
        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_message(
                    admin_id,
                    f"🔔 Новый пользователь запрашивает доступ:\n"
                    f"<b>Имя:</b> {user.full_name}\n"
                    f"<b>Username:</b> @{user.username or 'нет'}\n"
                    f"<b>ID:</b> <code>{user.telegram_id}</code>",
                    reply_markup=get_user_approval_kb(user.telegram_id)
                )
            except Exception as e:
                print(f"Не удалось отправить уведомление админу {admin_id}: {e}")
        await message.answer("Спасибо за регистрацию! Ваша заявка отправлена администратору на рассмотрение.")
        return

    await send_main_menu(message, state, user)


@router.callback_query(F.data == "back_to_main_menu")
async def back_to_main_menu_handler(callback: types.CallbackQuery, state: FSMContext, user: User):
    await send_main_menu(callback, state, user)
    await callback.answer()


@router.callback_query(F.data == "cancel_fsm", any_state)
async def cancel_fsm_handler(callback: types.CallbackQuery, state: FSMContext, user: User):
    await send_main_menu(callback, state, user)
    await callback.answer()