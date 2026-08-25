from __future__ import annotations

import asyncio
import logging
import os
import threading
from typing import Optional

import discord
from discord.ext import commands
from flask import Flask

from config import TOKEN, GUILD_ID, PORT
from database import init_db

# ============================================================
# LOGGING & FLASK KEEP-ALIVE
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("ReaperBot")
logging.getLogger("werkzeug").setLevel(logging.ERROR)

app = Flask("ReaperBot")

@app.route("/")
def home():
    return "Reaper Bot is alive!", 200

def run_flask() -> None:
    """Chạy Flask server ở background thread để keep-alive bot."""
    try:
        logger.info("🌐 Keep-Alive server starting on port %s...", PORT)
        app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
    except Exception:
        logger.exception("❌ Keep-Alive server crashed!")

# ============================================================
# BOT CLASS
# ============================================================

class ReaperBot(commands.Bot):

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        intents.message_content = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
        )

        self.loaded_cogs: list[str] = []
        self.failed_cogs: list[str] = []

    # --------------------------------------------------------
    # INITIALIZATION & COG LOADING
    # --------------------------------------------------------

    async def initialize_database(self) -> bool:
        """Khởi tạo kết nối CSDL."""
        logger.info("🗄️ Initializing database...")
        try:
            await init_db()
            logger.info("✅ Database initialized successfully.")
            return True
        except Exception:
            logger.exception("❌ Database initialization failed!")
            return False

    async def load_cogs(self) -> None:
        """Tự động load toàn bộ file .py trong thư mục ./cogs."""
        cog_dir = "./cogs"
        if not os.path.isdir(cog_dir):
            logger.error("❌ Cog directory '%s' does not exist!", cog_dir)
            return

        cog_files = sorted(
            f for f in os.listdir(cog_dir) if f.endswith(".py") and f != "__init__.py"
        )
        if not cog_files:
            logger.warning("⚠️ No Cog files found!")
            return

        for filename in cog_files:
            ext = f"cogs.{filename[:-3]}"
            try:
                await self.load_extension(ext)
                self.loaded_cogs.append(filename)
                logger.info("✅ Loaded: %s", ext)
            except Exception:
                self.failed_cogs.append(filename)
                logger.exception("❌ Failed to load: %s", ext)

        logger.info("📦 Cog status: %d loaded / %d failed", len(self.loaded_cogs), len(self.failed_cogs))

    # --------------------------------------------------------
    # SLASH COMMAND SYNC
    # --------------------------------------------------------

    async def sync_commands(self) -> None:
        """Xử lý đồng bộ lệnh Slash (Guild fast-sync & Global sync)."""
        cmds = self.tree.get_commands()
        logger.info("🔍 Local CommandTree has %d global commands registered.", len(cmds))

        if not cmds:
            logger.error("❌ Không có command nào trong tree để sync!")
            return

        # 1. Guild Sync (Cho phép thử nghiệm lệnh ngay lập tức)
        if GUILD_ID:
            try:
                guild = discord.Object(id=int(GUILD_ID))
                self.tree.copy_global_to(guild=guild)
                synced_guild = await self.tree.sync(guild=guild)
                logger.info("⚡ Guild Sync [%s]: %d lệnh sẵn sàng ngay lập tức.", GUILD_ID, len(synced_guild))
            except Exception:
                logger.exception("❌ Guild sync thất bại!")

        # 2. Global Sync (Phủ sóng toàn bộ server, mất 15-60p để Discord cập nhật)
        try:
            synced_global = await self.tree.sync()
            logger.info("🌐 Global Sync: %d lệnh đã gửi lên Discord.", len(synced_global))
        except Exception:
            logger.exception("❌ Global sync thất bại!")

    # --------------------------------------------------------
    # DISCORD EVENTS
    # --------------------------------------------------------

    async def setup_hook(self) -> None:
        """Vòng đời khởi chạy chuẩn của Discord.py trước khi Bot READY."""
        logger.info("🚀 Starting Bot Initialization...")
        await self.initialize_database()
        await self.load_cogs()
        await self.sync_commands()
        logger.info("✅ Initialization completed.")

    async def on_ready(self) -> None:
        logger.info("🤖 Connected as %s (ID: %s)", self.user, getattr(self.user, "id", None))
        logger.info("🏠 Connected Guilds: %d | Cogs: %d | Commands: %d", 
                    len(self.guilds), len(self.loaded_cogs), len(self.tree.get_commands()))
        
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.playing,
                name="PUBG Multiverse",
            )
        )

    async def on_error(self, event_method: str, *args, **kwargs) -> None:
        logger.exception("❌ Unhandled Discord event error in '%s'", event_method)

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.CommandNotFound):
            return
        logger.exception("❌ Prefix command error: %s", error)

# ============================================================
# MAIN EXECUTION
# ============================================================

async def main() -> None:
    if not TOKEN:
        logger.critical("❌ DISCORD_TOKEN chưa được cấu hình!")
        return

    # Chạy Web Server ở Thread riêng
    threading.Thread(target=run_flask, name="FlaskKeepAlive", daemon=True).start()

    retry_delay = 30
    while True:
        bot: Optional[ReaperBot] = None
        try:
            bot = ReaperBot()
            await bot.start(TOKEN)
            logger.warning("⚠️ Kết nối Bot kết thúc bình thường.")
            break

        except discord.LoginFailure:
            logger.critical("❌ Token không hợp lệ! Hãy kiểm tra DISCORD_TOKEN.")
            break

        except discord.HTTPException as e:
            if e.status == 429:
                logger.warning("⚠️ Rate Limit (429). Thử lại sau %ds...", retry_delay)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 300)
                continue
            logger.exception("❌ Discord HTTP Error: %s", e)

        except (discord.ConnectionClosed, Exception) as e:
            logger.exception("❌ Bắt được lỗi hệ thống/kết nối: %s", e)

        finally:
            if bot and not bot.is_closed():
                await bot.close()

        logger.info("🔄 Kết nối lại sau %d giây...", retry_delay)
        await asyncio.sleep(retry_delay)
        retry_delay = min(retry_delay * 2, 300)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot đã dừng bởi người dùng.")