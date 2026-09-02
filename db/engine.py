from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from config_reader import DATABASE_URL

# Создаем асинхронный "движок" для подключения к БД
engine = create_async_engine(DATABASE_URL, echo=False) # echo=True покажет все SQL запросы

# Создаем "фабрику сессий", через которую мы будем отправлять запросы
session_maker = async_sessionmaker(engine, expire_on_commit=False)

# Функция, которую мы будем вызывать, чтобы получить сессию
async def get_session():
    async with session_maker() as session:
        yield session