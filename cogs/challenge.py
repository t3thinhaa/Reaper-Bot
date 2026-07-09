import discord
from discord.ext import commands
from discord import app_commands
import random
import json
import os

# Đường dẫn đến file JSON mới của bạn
CHALLENGES_FILE = "./data/challenges.json"

def load_challenges_from_file():
    if not os.path.exists(CHALLENGES_FILE):
        return []
    try:
        with open(CHALLENGES_FILE, "r", encoding="utf-8") as f:
            # Đọc JSON siêu gọn, tự động chuyển thành danh sách Python Dictionary
            return json.load(f)
    except Exception as e:
        print(f"❌ Lỗi cấu trúc file JSON hoặc không đọc được file: {e}")
        return []

# ==========================================
# BẢNG ĐIỀU KHIỂN TRUNG TÂM VĨNH CỬU TỐI GIẢN
# ==========================================
class ChallengeControlView(discord.ui.View):
    def __init__(self, current_challenge_idx=0):
        super().__init__(timeout=None) # Giúp nút bấm sống mãi mãi qua các lần restart bot
        self.challenges = load_challenges_from_file()
        self.idx = current_challenge_idx if self.challenges else 0

    def get_current_embed(self):
        if not self.challenges:
            embed = discord.Embed(
                title="❌ Hệ Thống Trống", 
                description="Kho dữ liệu hiện đang trống hoặc file `challenges.json` bị lỗi định dạng dấu ngoặc. Hãy kiểm tra lại!", 
                color=discord.Color.red()
            )
            return embed
        
        c = self.challenges[self.idx % len(self.challenges)]
        embed = discord.Embed(
            title=f"⚔️ THỬ THÁCH SINH TỒN: {c.get('title', 'Nhiệm vụ vô danh')}", 
            description=c.get('description', 'Không có mô tả.'), 
            color=discord.Color.purple()
        )
        embed.add_field(name="Độ khó", value=f"🟡 {c.get('difficulty', 'Chưa rõ')}", inline=True)
        embed.add_field(name="🎁 Phần thưởng", value=f"`{c.get('reward', 0)}` Điểm Linh Hồn", inline=True)
        embed.set_footer(text=f"Kho dữ liệu vĩnh cửu: {len(self.challenges)} thử thách độc lạ!")
        
        if os.path.exists("./data/images/ReaperChallenge.png"):
            embed.set_image(url="attachment://ReaperChallenge.png")
        return embed

    # --- NÚT 1: ĐỔI THỬ THÁCH ---
    @discord.ui.button(label="🎲 Đổi Thử Thách", style=discord.ButtonStyle.secondary, custom_id="btn_next_challenge")
    async def next_challenge(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Đề phòng trường hợp bạn vừa cập nhật file json khi bot đang chạy, nó sẽ tự nạp lại dữ liệu mới
        self.challenges = load_challenges_from_file()
        if not self.challenges:
            return await interaction.response.send_message("❌ File JSON trống hoặc lỗi cấu trúc, không thể đổi!", ephemeral=True)
            
        self.idx += 1
        embed = self.get_current_embed()
        
        if os.path.exists("./data/images/ReaperChallenge.png"):
            file = discord.File("./data/images/ReaperChallenge.png", filename="ReaperChallenge.png")
            await interaction.message.edit(embed=embed, attachments=[file])
        else:
            await interaction.message.edit(embed=embed, attachments=[])
            
        await interaction.response.defer()

    # --- NÚT 2: NHẬN KÈO (TỰ ĐỘNG ĐÈ KÈO CŨ) ---
    @discord.ui.button(label="✅ Nhận Kèo", style=discord.ButtonStyle.success, custom_id="btn_accept_challenge")
    async def accept_challenge(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = interaction.client.db
        if db is None: 
            return await interaction.response.send_message("❌ Lỗi kết nối Database đám mây!", ephemeral=True)
        
        if not self.challenges:
            return await interaction.response.send_message("❌ Không có thử thách khả dụng!", ephemeral=True)

        user_id = str(interaction.user.id)
        c = self.challenges[self.idx % len(self.challenges)]
        
        # Ghi đè trạng thái thẳng lên MongoDB để đổi kèo tự do không lo kẹt trạng thái cũ
        await db.users_points.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "user_name": interaction.user.name,
                    "current_challenge": c.get('title'),
                    "challenge_reward": c.get('reward', 0),
                    "status": "DOING"
                }
            },
            upsert=True
        )
        await interaction.response.send_message(f"⚔️ Bạn đã nhận thử thách: **{c.get('title')}**. Hệ thống đã ghi nhận!", ephemeral=True)

    # --- NÚT 3: TỰ DUYỆT TỰ ĐỘNG CỘNG ĐIỂM ---
    @discord.ui.button(label="🏆 Tôi Đã Xong", style=discord.ButtonStyle.primary, custom_id="btn_self_complete")
    async def self_complete(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = interaction.client.db
        if db is None: return

        user_id = str(interaction.user.id)
        user_data = await db.users_points.find_one({"user_id": user_id})

        # Phòng vệ lỗi vặt: Nếu chưa nhận kèo hoặc kèo trống thì chặn click tặc
        if not user_data or user_data.get("status") != "DOING" or user_data.get("current_challenge") == "None":
            return await interaction.response.send_message("❌ Bạn chưa bấm nhận thử thách nào trên bảng điều khiển!", ephemeral=True)

        challenge_title = user_data.get("current_challenge", "Thử thách ẩn")
        reward = user_data.get("challenge_reward", 0)

        # Chống spam ghi dữ liệu trùng lặp lên Database
        await db.users_points.update_one(
            {"user_id": user_id},
            {
                "$set": {"status": "DONE", "current_challenge": "None", "challenge_reward": 0},
                "$inc": {"soul_points": reward}
            }
        )

        # 1. Phản hồi ẩn (Chỉ người bấm nút nhìn thấy) để xác nhận hệ thống đã xử lý xong
        await interaction.response.send_message(f"🎉 Hệ thống tự động cộng **`+{reward}`** Điểm Linh Hồn vào ví của bạn thành công!", ephemeral=True)
        
        # 2. Tin nhắn vinh danh công khai gửi vào kênh chat và tự động xóa sau 7 giây để tránh trôi bảng setup
        await interaction.channel.send(
            f"🔥 **{interaction.user.mention}** đã tự lực hoàn thành thử thách: **{challenge_title}** ➡️ Đút túi thành công `{reward}` điểm!",
            delete_after=7  # Số giây tồn tại trước khi tự hủy (bạn có thể chỉnh tùy ý)
        )

class ChallengeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup_challenge", description="Khởi tạo Bảng Điều Khiển Thử Thách JSON Vĩnh Cửu")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_challenge(self, interaction: discord.Interaction):
        view = ChallengeControlView()
        embed = view.get_current_embed()
        
        # Phản hồi ẩn sạch sẽ để che đi tên Admin gõ lệnh
        await interaction.response.send_message("⚙️Đang tải lên thử thách", ephemeral=True)
        
        if os.path.exists("./data/images/ReaperChallenge.png"):
            file = discord.File("./data/images/ReaperChallenge.png", filename="ReaperChallenge.png")
            await interaction.channel.send(file=file, embed=embed, view=view)
        else:
            await interaction.channel.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(ChallengeCog(bot))
    # Đăng ký view cố định với bot chính
    bot.add_view(ChallengeControlView())