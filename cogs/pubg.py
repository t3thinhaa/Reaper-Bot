import os
import sys
import logging
import threading
import asyncio
import discord
from discord.ext import commands
from flask import Flask

# Import các biến cấu hình trung tâm
from config import TOKEN, GUILD_ID, PORT
from database import init_db

# Logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# Web Server Keep-Alive
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!", 200

def run_flask():
    try:
        app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
    except Exception as e:
        logging.error(f"❌ Lỗi khởi chạy Flask Web Server: {e}")

# Bot Class
class ReaperBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        intents.message_content = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        # 1. KHỞI TẠO DATABASE
        print("🟢 Đang kết nối và khởi tạo bảng trong Database...")
        try:
            await init_db()
        except Exception as e:
            print(f"❌ Lỗi khởi tạo Database: {e}")

        # 2. NẠP TOÀN BỘ COGS
        if os.path.exists("./cogs"):
            for file in os.listdir("./cogs"):
                if file.endswith(".py") and file != "__init__.py":
                    cog_name = f"cogs.{file[:-3]}"
                    try:
                        await self.load_extension(cog_name)
                        print(f"✅ Loaded extension: {file}")
                    except Exception as e:
                        print(f"❌ Lỗi khi nạp file {file}: {e}")
        else:
            print("⚠️ Thư mục './cogs' không tồn tại, bỏ qua bước nạp Cogs.")

        # 3. ĐỒNG BỘ SLASH COMMANDS (CHỐNG LẶP LỆNH TỐI ƯU)
        print("🔄 Đang đồng bộ Slash Commands...")
        try:
            if GUILD_ID:
                guild = discord.Object(id=GUILD_ID)
                # Chỉ copy lệnh sang Guild cụ thể nếu chạy môi trường Dev/Test
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                print(f"⚡ Đã đồng bộ {len(synced)} lệnh trực tiếp cho Guild ID: {GUILD_ID}")
            else:
                # Chế độ Production: Đồng bộ Global duy nhất
                synced = await self.tree.sync()
                print(f"🌐 Đã đồng bộ {len(synced)} lệnh Global toàn hệ thống.")
        except discord.errors.HTTPException as e:
            print(f"❌ Lỗi HTTP khi sync lệnh Discord (Có thể dính Rate Limit): {e}")
        except Exception as e:
            print(f"❌ Không thể đồng bộ lệnh Slash: {e}")

    async def on_ready(self):
        print("=" * 40)
        print(f"Logged in successfully as : {self.user}")
        print(f"Bot Application ID        : {self.user.id}")
        print(f"Discord.py Version        : {discord.__version__}")
        print("=" * 40)
        
        try:
            await self.change_presence(
                activity=discord.Activity(type=discord.ActivityType.playing, name="PUBG Multiverse")
            )
        except Exception as e:
            print(f"⚠️ Lỗi cập nhật trạng thái Bot: {e}")

async def main():
    if not TOKEN:
        print("❌ LỖI NGHIÊM TRỌNG: Không tìm thấy DISCORD_TOKEN!")
        sys.exit(1)

    # Khởi chạy Flask Thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    retry_delay = 300
    while True:
        bot = ReaperBot()
        try:
            await bot.start(TOKEN)
        except discord.errors.HTTPException as e:
            if e.status == 429:
                print(f"⚠️ Rate Limit (429)! Tạm nghỉ {retry_delay // 60} phút...")
                await asyncio.sleep(retry_delay)
            else:
                print(f"❌ Lỗi HTTP Discord: {e}")
                await asyncio.sleep(30)
        except discord.errors.LoginFailure:
            print("❌ Token Discord không hợp lệ! Vui lòng kiểm tra lại DISCORD_TOKEN.")
            break
        except Exception as e:
            print(f"❌ Lỗi ngoài dự kiến khi khởi chạy Bot: {e}")
            await asyncio.sleep(30)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTắt Bot an toàn (Graceful Shutdown)...")