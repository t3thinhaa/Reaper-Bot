import os
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
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)

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
        print("🟢 Đang kết nối và khởi tạo bảng trong Database...")
        try:
            await init_db()
        except Exception as e:
            print(f"❌ Lỗi khởi tạo Database: {e}")

        if os.path.exists("./cogs"):
            for file in os.listdir("./cogs"):
                if file.endswith(".py") and file != "__init__.py":
                    try:
                        await self.load_extension(f"cogs.{file[:-3]}")
                        print(f"Loaded extension: {file}")
                    except Exception as e:
                        print(f"❌ Lỗi khi nạp file {file}: {e}")

        # --- BƯỚC 3: ĐỒNG BỘ SLASH COMMANDS GLOBAL ---
        print("Synchronizing application commands...")
        try:
            # Xóa toàn bộ lệnh thừa ở cấp Guild nếu từng copy
            if GUILD_ID:
                guild = discord.Object(id=GUILD_ID)
                self.tree.clear_commands(guild=guild)
                await self.tree.sync(guild=guild)
                
            # Chỉ sync Global
            synced = await self.tree.sync()
            print(f"Successfully synced {len(synced)} global slash command(s).")
        except Exception as e:
            print(f"❌ Không thể đồng bộ lệnh: {e}")

    async def on_ready(self):
        print("=" * 40)
        print(f"Logged in successfully as : {self.user}")
        print(f"Bot Application ID        : {self.user.id}")
        print(f"Discord.py Version        : {discord.__version__}")
        print("=" * 40)
        
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.playing, name="PUBG Multiverse")
        )

async def main():
    if not TOKEN:
        print("❌ LỖI NGHIÊM TRỌNG: Không tìm thấy DISCORD_TOKEN!")
        return

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
                print(f"❌ Lỗi HTTP: {e}")
                await asyncio.sleep(30)
        except Exception as e:
            print(f"❌ Lỗi khi khởi chạy Bot: {e}")
            await asyncio.sleep(30)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down bot gracefully...")