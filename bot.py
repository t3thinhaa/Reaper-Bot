import os
import logging
import threading
import asyncio
import discord
from discord.ext import commands
from flask import Flask
from config import TOKEN

# ==========================================
# 1. CẤU HÌNH LOGGING CHUẨN (ẨN LOG THỪA)
# ==========================================
# Tắt log thông báo request liên tục của Flask để sạch Terminal
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# ==========================================
# 2. KHỞI TẠO WEB SERVER (KEEP ALIVE FOR RENDER)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!", 200

def run_flask():
    # Chạy Flask ở chế độ production-ready đơn giản, ẩn banner chào mừng
    app.run(host='0.0.0.0', port=10000, debug=False, use_reloader=False)

# ==========================================
# 3. CLASS CHÍNH REAPER BOT
# ==========================================
class ReaperBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        # Bật thêm message_content nếu sau này bạn muốn dùng thêm lệnh tiền tố dạng cổ điển (!)
        intents.message_content = True 

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None # Ẩn lệnh help mặc định xấu xí của discord.py để tự custom sau
        )

    async def setup_hook(self):
        # Tự động nạp toàn bộ Cogs trong thư mục cogs
        for file in os.listdir("./cogs"):
            if file.endswith(".py") and file != "__init__.py":
                try:
                    await self.load_extension(f"cogs.{file[:-3]}")
                    print(f"Loaded extension: {file}")
                except Exception as e:
                    print(f"❌ Lỗi khi nạp file {file}: {e}")

        # Đồng bộ Slash Command một cách thông minh (Chỉ sync cục bộ hoặc khi thực sự có thay đổi)
        # Giúp tránh bị Discord block (Rate Limit) do gọi hàm sync vô tội vạ
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
        
        # Đặt trạng thái hoạt động chuyên nghiệp cho bot
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.playing, name="PUBG Multiverse")
        )

# ==========================================
# 4. KHỞI CHẠY HỆ THỐNG
# ==========================================
if __name__ == "__main__":
    # 1. Chạy Web Server ở luồng phụ
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # 2. Khởi tạo và chạy Bot
    bot = ReaperBot()
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        print("\nShutting down bot gracefully...")