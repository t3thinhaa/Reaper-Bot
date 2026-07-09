import os
import logging
import threading
import asyncio
import discord
from discord.ext import commands
from flask import Flask
from motor.motor_asyncio import AsyncIOMotorClient # Thư viện kết nối MongoDB bất đồng bộ chuẩn bài cho discord.py
from config import TOKEN

# ==========================================
# 1. CẤU HÌNH LOGGING CHUẨN (ẨN LOG THỪA)
# ==========================================
# Mình tắt bớt mấy cái log thông báo request 200/404 liên tục của Flask 
# để màn hình Terminal sạch sẽ, chỉ hiện log của Bot thôi.
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# ==========================================
# 2. KHỞI TẠO WEB SERVER (KEEP ALIVE FOR RENDER)
# ==========================================
# Tạo một web server mini bằng Flask để giữ cho bot luôn sống trên Render.
# Render thấy có cổng web mở liên tục thì nó sẽ không đưa bot về trạng thái ngủ (Sleep).
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!", 200

def run_flask():
    # Chạy Flask ở luồng phụ, ẩn cái banner chào mừng của Flask đi cho gọn.
    app.run(host='0.0.0.0', port=10000, debug=False, use_reloader=False)

# ==========================================
# 3. CLASS CHÍNH REAPER BOT
# ==========================================
class ReaperBot(commands.Bot):
    def __init__(self):
        # Bật các quyền (Intents) cần thiết để Bot hoạt động.
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        intents.message_content = True # Bật cái này để sau này thích viết lệnh tiền tố bằng dấu (!) cũng được.

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None # Ẩn lệnh help mặc định đi, sau này mình tự viết menu help xịn hơn.
        )
        
        # Khai báo biến db sẵn ở đây để các file Cogs khác có thể gọi qua self.bot.db hoặc interaction.client.db
        self.db = None
        self.db_client = None

    async def setup_hook(self):
        # --- BƯỚC 1: KẾT NỐI MONGODB ĐÁM MÂY ---
        # Mình sẽ lấy chuỗi kết nối URI từ file .env (hoặc từ cài đặt môi trường trên Render).
        mongo_uri = os.getenv("MONGODB_URI")
        if mongo_uri:
            try:
                # Sử dụng AsyncIOMotorClient để khi bot truy vấn data, nó không làm đơ (block) luồng xử lý của Bot.
                self.db_client = AsyncIOMotorClient(mongo_uri)
                # Đặt tên database là 'reaper_db'. MongoDB sẽ tự tạo db này nếu nó chưa tồn tại.
                self.db = self.db_client['reaper_db']
                print("🗄️ Đã khởi tạo cấu hình kết nối MongoDB đám mây!")
            except Exception as e:
                print(f"❌ Lỗi kết nối MongoDB: {e}")
                self.db = None
        else:
            print("⚠️ WARNING: Chưa cấu hình MONGODB_URI! Bot sẽ chạy mà không có Database.")

        # --- BƯỚC 2: TỰ ĐỘNG NẠP TOÀN BỘ COGS ---
        # Quét thư mục cogs, cứ file nào đuôi .py thì nạp vào hệ thống để chia nhỏ code cho dễ quản lý.
        for file in os.listdir("./cogs"):
            if file.endswith(".py") and file != "__init__.py":
                try:
                    await self.load_extension(f"cogs.{file[:-3]}")
                    print(f"Loaded extension: {file}")
                except Exception as e:
                    print(f"❌ Lỗi khi nạp file {file}: {e}")

        # --- BƯỚC 3: ĐỒNG BỘ SLASH COMMANDS ---
        # Gửi danh sách các lệnh gạch chéo (/) lên hệ thống Discord để người dùng gõ thấy lệnh.
        print("Synchronizing application commands...")
        try:
            synced = await self.tree.sync()
            print(f"Successfully synced {len(synced)} slash command(s).")
        except Exception as e:
            print(f"❌ Không thể đồng bộ lệnh lên Discord: {e}")

    async def on_ready(self):
        # Màn hình chào mừng cực kỳ chuyên nghiệp khi bot khởi chạy thành công.
        print("=" * 40)
        print(f"Logged in successfully as : {self.user}")
        print(f"Bot Application ID        : {self.user.id}")
        print(f"Discord.py Version        : {discord.__version__}")
        print("=" * 40)
        
        # Đặt trạng thái hiển thị "Đang chơi PUBG Multiverse" cho oai.
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.playing, name="PUBG Multiverse")
        )

# ==========================================
# 4. KHỔI CHẠY HỆ THỐNG
# ==========================================
if __name__ == "__main__":
    # 1. Bật Web Server Flask chạy ngầm ở một luồng (thread) riêng 
    # để nó không tranh chấp tài nguyên với vòng lặp chính (event loop) của Bot.
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # 2. Khởi tạo thực thể bot và ra lệnh chạy bằng Token bí mật.
    bot = ReaperBot()
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        print("\nShutting down bot gracefully...")