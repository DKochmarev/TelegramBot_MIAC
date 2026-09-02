from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery, User as TelegramUser, Update
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import User, UserRole
from config_reader import ADMIN_IDS


class AuthMiddleware(BaseMiddleware):
    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any],
    ) -> Any:

        telegram_user: TelegramUser | None = None

        if isinstance(event, Update):
            if event.message:
                telegram_user = event.message.from_user
            elif event.callback_query:
                telegram_user = event.callback_query.from_user
        elif isinstance(event, Message):
            telegram_user = event.from_user
        elif isinstance(event, CallbackQuery):
            telegram_user = event.from_user

        if not telegram_user:
            data["user"] = None
            return await handler(event, data)

        session: AsyncSession = data["session"]
        user = await session.get(User, telegram_user.id)

        if telegram_user.id in ADMIN_IDS:
            if not user or user.role != UserRole.ADMIN:
                if not user:
                    user = User(telegram_id=telegram_user.id, full_name=telegram_user.full_name,
                                username=telegram_user.username, role=UserRole.ADMIN)
                    session.add(user)
                else:
                    user.role = UserRole.ADMIN
                await session.commit()

        elif not user:
            user = User(telegram_id=telegram_user.id, full_name=telegram_user.full_name,
                        username=telegram_user.username, role=UserRole.PENDING)
            session.add(user)
            await session.commit()

        data["user"] = user

        return await handler(event, data)
