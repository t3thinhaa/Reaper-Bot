import os
import logging
import threading
import asyncio
import discord
from discord.ext import commands
from flask import Flask

# Import hàm khởi tạo database PostgreSQL
from database import init_db

# ==========================================
# 1. CẤU HÌNH LOGGING CHUẨN (ẨN LOG THỪA)
# ==========================================
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# Lấy TOKEN từ biến môi trường của Render (hoặc file config nếu có)
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    try:
        from config import TOKEN
    except ImportError:
        TOKEN = None

# ==========================================
# 2. KHỞI TẠO WEB SERVER (KEEP ALIVE FOR RENDER)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ==========================================
# 3. CLASS CHÍNH REAPER BOT
# ==========================================
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
        # --- BƯỚC 1: KHỞI TẠO BẢNG POSTGRESQL DATABASE ---
        print("🟢 Đang kết nối và khởi tạo bảng trong PostgreSQL...")
        try:
            init_db()
        except Exception as e:
            print(f"❌ Lỗi khởi tạo PostgreSQL Database: {e}")

        # --- BƯỚC 2: TỰ ĐỘNG NẠP TOÀN BỘ COGS ---
        if os.path.exists("./cogs"):
            for file in os.listdir("./cogs"):
                if file.endswith(".py") and file != "__init__.py":
                    try:
                        await self.load_extension(f"cogs.{file[:-3]}")
                        print(f"Loaded extension: {file}")
                    except Exception as e:
                        print(f"❌ Lỗi khi nạp file {file}: {e}")
        else:
            print("⚠️ Thư mục './cogs' không tồn tại, bỏ qua bước nạp Cogs.")

        # --- BƯỚC 3: ĐỒNG BỘ SLASH COMMANDS ---
        print("Synchronizing application commands...")
        try:
            synced = await self.tree.sync()
            print(f"Successfully synced {len(synced)} slash command(s).")
        except Exception as e:
            print(f"❌ Không thể đồng bộ lệnh lên Discord: {e}")

    async def on_ready(self):
        print("=" * 40)
        print(f"Logged in successfully as : {self.user}")
        print(f"Bot Application ID        : {self.user.id}")
        print(f"Discord.py Version        : {discord.__version__}")
        print("=" * 40)
        
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.playing, name="PUBG Multiverse")
        )

# ==========================================
# 4. KHỞI CHẠY HỆ THỐNG CÓ BẮT LỖI RATE LIMIT
# ==========================================
async def main():
    # 1. Chạy Flask Server ngầm duy nhất 1 lần
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    if not TOKEN:
        print("❌ LỖI NGHIÊM TRỌNG: Không tìm thấy DISCORD_TOKEN!")
        return

    # 2. Vòng lặp tự kết nối lại nếu dính Rate Limit
    retry_delay = 300  # 5 phút
    while True:
        bot = ReaperBot()
        try:
            await bot.start(TOKEN)
        except discord.errors.HTTPException as e:
            if e.status == 429:
                print(f"⚠️ CẢNH BÁO: Bị Discord/Cloudflare Rate Limit (429)! Tạm nghỉ {retry_delay // 60} phút rồi thử lại...")
                await asyncio.sleep(retry_delay)
            else:
                print(f"❌ Lỗi HTTP: {e}")
                await asyncio.sleep(30)
        except Exception as e:
            print(f"❌ Lỗi ngoài dự kiến khi khởi chạy Bot: {e}")
            await asyncio.sleep(30)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down bot gracefully...")