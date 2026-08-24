import logging
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, BigInteger, Text

# Import chuỗi URL đã được chuẩn hoá từ config.py
from config import DATABASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Database")

# Cấu hình Engine & Connection Pool
engine_args = {"echo": False}

if "sqlite" not in DATABASE_URL:
    engine_args.update({
        "pool_size": 5,          # Tối đa 5 kết nối thường trực
        "max_overflow": 10,      # Tối đa 10 kết nối tạm thời khi tải cao
        "pool_recycle": 300,     # Reset kết nối sau 5 phút tránh bị rớt mạng ngầm
        "pool_pre_ping": True    # Ping DB kiểm tra kết nối còn sống trước khi query
    })

engine = create_async_engine(DATABASE_URL, **engine_args)
AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# ORM Models (Giữ nguyên cấu trúc cũ)
class Base(DeclarativeBase):
    pass

class UserPoint(Base):
    __tablename__ = "users_points"

    user_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    guild_id: Mapped[str] = mapped_column(String(50), primary_key=True, default="0")
    user_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    soul_points: Mapped[int] = mapped_column(Integer, default=0)
    current_challenge: Mapped[str | None] = mapped_column(Text, default="None")
    challenge_reward: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str | None] = mapped_column(String(20), default="IDLE")
    bao_day: Mapped[int] = mapped_column(Integer, default=0)
    bao_week: Mapped[int] = mapped_column(Integer, default=0)
    bao_month: Mapped[int] = mapped_column(Integer, default=0)
    is_sieu_cap: Mapped[int] = mapped_column(Integer, default=0)
    time_archive: Mapped[str | None] = mapped_column(Text, nullable=True)

class GuildRole(Base):
    __tablename__ = "guild_roles"

    guild_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    role_day: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    role_week: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    role_month: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    role_sieu_cap: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    role_ba_chu: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

async def init_db():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Khởi tạo và kết nối Database thành công!")
    except Exception as e:
        logger.error(f"❌ Lỗi khởi tạo Database: {e}", exc_info=True)

@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    session = AsyncSessionFactory()
    try:
        yield session
    except Exception as e:
        await session.rollback()
        logger.error(f"❌ Lỗi trong phiên làm việc DB: {e}", exc_info=True)
        raise
    finally:
        await session.close()