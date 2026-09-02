from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
raw_admin_ids = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(admin_id) for admin_id in raw_admin_ids.split(',') if admin_id.strip().isdigit()]

if not ADMIN_IDS:
    print("ВНИМАНИЕ: ADMIN_IDS в .env не заданы. Никто не сможет администрировать бота.")

db_user = os.getenv("POSTGRES_USER")
db_pass = os.getenv("POSTGRES_PASSWORD")
db_name = os.getenv("POSTGRES_DB")
db_host = os.getenv("DB_HOST", "localhost")

DATABASE_URL = f"postgresql+asyncpg://{db_user}:{db_pass}@{db_host}/{db_name}"

if not BOT_TOKEN or not DATABASE_URL:
    print("КРИТИЧЕСКАЯ ОШИБКА: не найдены переменные окружения BOT_TOKEN или DATABASE_URL.")
    exit()
