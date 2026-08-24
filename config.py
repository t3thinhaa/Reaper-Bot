import os
import logging
from dotenv import load_dotenv

# Load file .env nếu chạy ở môi trường Local
load_dotenv()

logger = logging.getLogger("Config")

# 1. Discord Bot Tokens & IDs
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    logger.warning("⚠️ DISCORD_TOKEN chưa được cài đặt trong môi trường!")

guild_id_env = os.getenv("GUILD_ID")
GUILD_ID = int(guild_id_env) if guild_id_env and guild_id_env.isdigit() else None

# 2. Database Configuration
RAW_DATABASE_URL = os.getenv("DATABASE_URL")

if not RAW_DATABASE_URL:
    logger.warning("⚠️ DATABASE_URL chưa được thiết lập! Đang dùng SQLite local fallback.")
    DATABASE_URL = "sqlite+aiosqlite:///bot.db"
else:
    # Tự động chuẩn hoá Prefix phù hợp cho driver asyncpg của SQLAlchemy
    if RAW_DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = RAW_DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
    elif RAW_DATABASE_URL.startswith("postgresql://") and not RAW_DATABASE_URL.startswith("postgresql+asyncpg://"):
        DATABASE_URL = RAW_DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    else:
        DATABASE_URL = RAW_DATABASE_URL

# 3. Server Config
PORT = int(os.getenv("PORT", 10000))